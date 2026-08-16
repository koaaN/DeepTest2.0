from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errors import AuthenticationError, ProtocolError
from .models import BusinessToken
from .tokens import TokenCache


DEFAULT_RSA_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDpgSW5VkZ6/xvh+wMXezrOokNdiupuvuMj4RVJy44byWDupl4H37z907A26RVdFzMeyLUQB4rsDIaXdxCODlljWW+/K96uF5MsDtOFUBw7VlOclIjcYTv/YDQEul8JoXoOuy1Yf3b5sbTpTuVTcl97tAuLJ8PoGe2K7N3B1eUQqQIDAQAB"
)
SIGN_SECRET = "6CyfIPKEDKF0RIR3fdtFsQ=="


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


@dataclass(frozen=True)
class RefreshConfig:
    app_id: str = "37020981"
    app_key: str = "7bb73a85f2d6462f95259fc574c66784"
    package_name: str = "com.coloros.deeptesting"
    package_version: str = "17.0.3"
    sdk_version: str = "1.4.8"
    sdk_type: str = "account_sdk"
    id_sdk_version: str = "10408"
    duid: str = ""
    env_param: str = ""
    rsa_public_key: str = DEFAULT_RSA_PUBLIC_KEY


class _EncryptedJsonEnvelope:
    def __init__(self, rsa_public_key: str):
        random_secret = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii")
        self.key = random_secret.encode("utf-8")
        self.iv = os.urandom(16)
        public_key = serialization.load_der_public_key(base64.b64decode(rsa_public_key))
        self.encrypted_key = public_key.encrypt(self.key, padding.PKCS1v15())

    def crypt(self, value: bytes) -> bytes:
        cipher = Cipher(algorithms.AES(self.key), modes.CTR(self.iv))
        return cipher.encryptor().update(value)

    def encrypt_text(self, value: str) -> str:
        return _b64(self.crypt(value.encode("utf-8")))

    def decrypt_text(self, value: str) -> str:
        try:
            raw = base64.b64decode("".join(value.split()) + "=" * (-len(value) % 4))
            return self.crypt(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProtocolError("could not decrypt business refresh response") from exc

    def headers(self, security_json: str) -> dict[str, str]:
        encrypted_security = self.encrypt_text(security_json)
        protocol = _compact_json(
            {
                "key": _b64(self.encrypted_key),
                "iv": base64.urlsafe_b64encode(self.iv).decode("ascii"),
                "sessionTicket": "",
            }
        )
        return {
            "Accept": "application/encrypted-json",
            "Content-Type": "application/encrypted-json; charset=UTF-8",
            "X-Protocol-Version": "3.0",
            "X-Protocol-Ver": "3.0",
            "X-Key": _b64(self.encrypted_key),
            "X-I-V": base64.urlsafe_b64encode(self.iv).decode("ascii"),
            "X-Security": encrypted_security,
            "X-Safety": urllib.parse.quote(encrypted_security, safe=""),
            "X-Protocol": urllib.parse.quote(protocol, safe=""),
        }


class BusinessTokenRefresher:
    """Experimental implementation of DeepTesting's direct business refresh."""

    def __init__(
        self,
        config: RefreshConfig | None = None,
        *,
        timeout: float = 30,
        http: requests.Session | None = None,
    ):
        self.config = config or RefreshConfig()
        self.timeout = timeout
        self.http = http or requests.Session()

    def build_payload(self, token: BusinessToken, now_ms: int | None = None) -> dict[str, Any]:
        token.require_access()
        if not token.refresh_token or not token.ssoid:
            raise AuthenticationError("refresh requires refresh_token and ssoid")
        timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        env_info = _compact_json(
            {
                "bizAppId": self.config.app_id,
                "bizAppKey": self.config.app_key,
                "bizPkgName": self.config.package_name,
                "bizPkgNameSign": token.package_sign,
                "deviceId": token.device_id,
                "envParam": self.config.env_param,
            }
        )
        payload: dict[str, Any] = {
            "bizk": self.config.app_key,
            "ssoid": token.ssoid,
            "envInfo": env_info,
            "accessToken": token.access_token,
            "refreshToken": token.refresh_token,
            "duid": self.config.duid or None,
            "timestamp": timestamp,
        }
        sign_fields = {key: value for key, value in payload.items() if value not in (None, "")}
        canonical = "".join(
            f"{key}={sign_fields[key]}&"
            for key in sorted(sign_fields, key=str.casefold)
        )
        payload["sign"] = hashlib.md5(f"{canonical}key={SIGN_SECRET}".encode("utf-8")).hexdigest()
        return {key: value for key, value in payload.items() if value is not None}

    def refresh(self, token: BusinessToken) -> BusinessToken:
        envelope = _EncryptedJsonEnvelope(self.config.rsa_public_key)
        plaintext = _compact_json(self.build_payload(token))
        security_json = _compact_json(
            {
                "imei": "",
                "imei1": "",
                "mac": "",
                "serialNum": "",
                "serial": "",
                "wifissid": "",
                "hasPermission": False,
                "deviceName": "",
                "marketName": "",
            }
        )
        headers = {
            **envelope.headers(security_json),
            "X-BIZ-PACKAGE": self.config.package_name,
            "X-BIZ-VERSION": self.config.package_version,
            "X-BIZ-APPKEY": self.config.app_key,
            "X-SDK-VERSION": self.config.sdk_version,
            "X-SDK-TYPE": self.config.sdk_type,
            "X-ID-SDK-VERSION": self.config.id_sdk_version,
        }
        host = token.host.rstrip("/")
        response = self.http.post(
            f"{host}/api/token/refresh",
            data=envelope.encrypt_text(plaintext),
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            raise ProtocolError("business refresh returned an empty response")
        try:
            result = json.loads(text if text.startswith("{") else envelope.decrypt_text(text))
        except json.JSONDecodeError as exc:
            raise ProtocolError("business refresh response is not JSON") from exc
        if not isinstance(result, dict):
            raise ProtocolError("business refresh response is not an object")
        code = result.get("code")
        if code not in (0, 200, -200) or not isinstance(result.get("data"), dict):
            raise AuthenticationError(f"business refresh failed: {code} {result.get('msg', result.get('message', ''))}")
        refreshed = TokenCache.extract_auth_response(result, fallback=token)
        refreshed.require_access()
        return refreshed
