from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errors import ProtocolError
from .heytap_models import HeyTapConfig, HeyTapDeviceProfile, new_trace_id
from .private_file import atomic_write_private


DEFAULT_RSA_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDpgSW5VkZ6/xvh+wMXezrOokNdiupuvuMj4RVJy44byWDupl4H37z907A26RVdFzMeyLUQB4rsDIaXdxCODlljWW+/K96uF5MsDtOFUBw7VlOclIjcYTv/YDQEul8JoXoOuy1Yf3b5sbTpTuVTcl97tAuLJ8PoGe2K7N3B1eUQqQIDAQAB"
)


def compact_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class HeyTapV1Transport:
    def __init__(
        self,
        config: HeyTapConfig | None = None,
        device: HeyTapDeviceProfile | None = None,
        *,
        timeout: float = 30,
        http: requests.Session | None = None,
        rsa_key_path: str | Path | None = None,
        random_bytes: Callable[[int], bytes] = os.urandom,
        now_ms: Callable[[], int] | None = None,
    ):
        self.config = config or HeyTapConfig()
        self.host = self.config.host.rstrip("/")
        self.device = device or HeyTapDeviceProfile()
        self.timeout = timeout
        self.http = http or requests.Session()
        self.rsa_key_path = Path(rsa_key_path) if rsa_key_path else Path.home() / ".config" / "deeptesting" / "heytap-rsa.der"
        self._random_bytes = random_bytes
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._key = random_bytes(32)
        self._iv = random_bytes(16)
        if len(self._key) != 32 or len(self._iv) != 16:
            raise ValueError("random byte source returned invalid AES material")
        self._rsa_der = self._load_rsa_key()

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        access_token: str = "",
        id_token: str = "",
        primary_token: str = "",
    ) -> dict[str, Any]:
        plaintext = compact_json({key: value for key, value in payload.items() if value is not None})
        retried_region = False
        rotated_rsa = False
        while True:
            response = self._send(
                path,
                plaintext,
                headers or {},
                access_token=access_token,
                id_token=id_token,
                primary_token=primary_token,
            )
            if response.status_code == 222 and not rotated_rsa:
                self._rotate_rsa(response.content)
                rotated_rsa = True
                continue
            if response.status_code == 222:
                raise ProtocolError("HeyTap returned HTTP 222 twice")
            if response.status_code == 233:
                raise ProtocolError("HeyTap returned HTTP 233")
            response.raise_for_status()
            text = response.text.strip()
            if not text:
                raise ProtocolError("HeyTap returned an empty encrypted response")
            try:
                decrypted = self.decrypt_response(text)
                result = json.loads(decrypted)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProtocolError("could not decrypt or decode HeyTap response") from exc
            if not isinstance(result, dict):
                raise ProtocolError("HeyTap response is not a JSON object")
            if result.get("code") == 301 and not retried_region:
                host = self._regional_host(result)
                if host and host != self.host:
                    self.host = host
                    retried_region = True
                    continue
            return result

    @staticmethod
    def _regional_host(result: dict[str, Any]) -> str:
        error = result.get("error")
        data = error.get("errorData") if isinstance(error, dict) else None
        if not isinstance(data, dict):
            return ""
        country = data.get("countryCode")
        mapping = data.get("countryDomainMapping")
        if not isinstance(country, str) or not isinstance(mapping, dict):
            return ""
        country = country.upper()
        for countries, host in mapping.items():
            if isinstance(countries, str) and isinstance(host, str):
                if country in {item.strip().upper() for item in countries.split(",")}:
                    return host.rstrip("/")
        return ""

    def signing_headers(self, plaintext: bytes) -> dict[str, str]:
        request_time = str(self._now_ms())
        body_hash = hashlib.md5(plaintext).hexdigest()
        canonical = (
            f"requestBody={body_hash}&requestTime={request_time}"
            f"&signAlgorithm=HMAC1_SK{self.config.account_app_key}"
        )
        signature = base64.b64encode(
            hmac.new(
                self.config.account_secret.encode("utf-8"),
                canonical.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("ascii")
        return {
            "X-Envelope-Version": "V1",
            "X-Sign-Key": self.config.account_app_key,
            "X-App-AcAppKey": self.config.account_app_key,
            "X-Sign-Algorithm": "HMAC1_SK",
            "X-RequestTime": request_time,
            "X-Sign": signature,
        }

    def encrypt_body(self, plaintext: bytes) -> bytes:
        public_key = serialization.load_der_public_key(self._rsa_der)
        oaep = padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
        )
        wrapped_key = public_key.encrypt(self._key, oaep)
        wrapped_iv = public_key.encrypt(self._iv, oaep)
        encrypted = self._crypt(plaintext)
        envelope = ".".join(
            base64.b64encode(value).decode("ascii")
            for value in (wrapped_key, wrapped_iv, encrypted)
        )
        return gzip.compress(envelope.encode("ascii"))

    def decrypt_response(self, value: str) -> str:
        raw = base64.b64decode("".join(value.split()) + "=" * (-len(value) % 4), validate=False)
        return self._crypt(raw).decode("utf-8")

    def common_headers(self) -> dict[str, str]:
        config = self.config
        device = self.device
        trace_id = new_trace_id()
        quote = lambda value: urllib.parse.quote(str(value), safe="")
        return {
            "User-Agent": "okhttp/4.12.0",
            "Content-Type": "application/json; charset=UTF-8",
            "Content-Encoding": "gzip",
            "X-App-OverseaClient": "false",
            "X-Context-Country": config.country,
            "X-Context-MaskRegion": config.country,
            "X-Device-Brand": quote(device.brand),
            "X-Device-Model": quote(device.model),
            "X-Device-HT": str(device.height),
            "X-Device-WD": str(device.width),
            "X-Device-HardwareType": quote(device.hardware_type),
            "X-Device-LSD": "false",
            "X-Context-TimeZone": device.timezone,
            "X-Context-Locale": device.locale,
            "X-Sys-RomVersion": quote(device.rom_version),
            "X-Sys-OsVersion": device.os_version,
            "X-Sys-AndroidVersion": str(device.android_api),
            "X-Sys-OsVersionCode": device.os_version,
            "X-Sys-OsBuildTime": str(device.build_time),
            "X-Sys-RpName": quote(device.product_name),
            "X-Sys-Rotaver": quote(device.ota_version),
            "X-App-HostPackage": config.account_package,
            "X-App-HostVersion": config.account_version_name,
            "X-App-AcPackage": config.account_package,
            "X-App-AcVersion": config.account_version,
            "X-App-AcAarVersion": config.account_aar_version,
            "X-App-DeviceId": device.device_id,
            "X-App-RegisterId": device.register_id,
            "X-App-FoldMode": "",
            "X-Safety-DeviceName": quote(device.device_name),
            "X-Safety-MarketName": quote(device.market_name),
            "X-LanguageTag": device.language_tag,
            "Accept-Language": device.language_tag,
            "X-Sys-DUID": device.duid,
            "X-Biz-Package": config.biz_package,
            "X-Biz-Version": config.biz_version,
            "X-Biz-AppKey": config.biz_app_key,
            "X-Biz-AppId": config.biz_app_id,
            "X-Biz-TraceId": trace_id,
            "X-App-TraceId": trace_id,
            "X-SDK-Version": config.sdk_version,
            "X-SDK-Type": config.sdk_type,
            "X-Biz-SellModeOpen": "false",
            "X-Sys-TalkBackState": "false",
        }

    def _send(
        self,
        path: str,
        plaintext: bytes,
        headers: dict[str, str],
        *,
        access_token: str,
        id_token: str,
        primary_token: str,
    ) -> requests.Response:
        request_headers = {**self.common_headers(), **self.signing_headers(plaintext), **headers}
        if self.device.ouid:
            request_headers.setdefault("X-Sys-OUID", self.device.ouid)
        if self.device.guid:
            request_headers.setdefault("X-Sys-GUID", self.device.guid)
        if access_token:
            request_headers["X-Token"] = access_token
        if id_token:
            request_headers["X-AcIdToken"] = id_token
        if primary_token:
            request_headers["X-AcPrimaryToken"] = primary_token
        return self.http.post(
            f"{self.host}/{path.lstrip('/')}",
            data=self.encrypt_body(plaintext),
            headers=request_headers,
            timeout=self.timeout,
        )

    def _crypt(self, value: bytes) -> bytes:
        cipher = Cipher(algorithms.AES(self._key), modes.CTR(self._iv))
        encryptor = cipher.encryptor()
        return encryptor.update(value) + encryptor.finalize()

    def _load_rsa_key(self) -> bytes:
        try:
            return self.rsa_key_path.read_bytes()
        except FileNotFoundError:
            return base64.b64decode(DEFAULT_RSA_PUBLIC_KEY)
        except OSError as exc:
            raise ProtocolError(f"could not read HeyTap RSA key: {self.rsa_key_path}") from exc

    def _rotate_rsa(self, encoded_key: bytes) -> None:
        try:
            der = base64.b64decode(b"".join(encoded_key.split()), validate=False)
            serialization.load_der_public_key(der)
        except (ValueError, TypeError) as exc:
            raise ProtocolError("HTTP 222 did not contain a valid RSA public key") from exc
        atomic_write_private(self.rsa_key_path, der, prefix=f".{self.rsa_key_path.name}-")
        self._rsa_der = der
