from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass, fields
from typing import Any

from .errors import AuthenticationError, ProtocolError


@dataclass(frozen=True)
class DeviceProfile:
    udid: str
    device_id: str
    model: str = "PLK110"
    ota_version: str = "PLK110_11.A.68_0680_202606250030"
    brand: str = "OnePlus"
    operator: str = ""
    chip_id: str = ""
    app_version: int = 17000003
    client_lock_status: int = 0
    os_version: str = "16"
    language: str = "en-US"

    def request_payload(self, endpoint: str, new_token: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "appVersion": self.app_version,
            "brand": self.brand,
            "deviceId": self.device_id,
            "clientLockStatus": self.client_lock_status,
            "udid": self.udid,
            "model": self.model,
            "newToken": new_token,
            "operator": self.operator,
            "otaVersion": self.ota_version,
            "chipId": self.chip_id,
        }
        if endpoint in {"get-apply-status", "unlock-condition-match"}:
            for key in ("model", "otaVersion", "brand"):
                payload.pop(key)
        elif endpoint == "get-history-unlock-code":
            for key in ("model", "otaVersion", "brand", "chipId", "operator"):
                payload.pop(key)
        return payload


@dataclass
class BusinessToken:
    access_token: str
    device_id: str
    refresh_token: str = ""
    id_token: str = ""
    host: str = "https://client-uc.heytapmobi.com"
    package_sign: str = ""
    access_token_exp: int = 0
    refresh_token_exp: int = 0
    access_token_refresh_ahead: int = 0
    refresh_token_refresh_ahead: int = 0
    ssoid: str = ""
    extra_data_json: str = ""

    def __post_init__(self) -> None:
        if not self.ssoid and self.id_token:
            self.ssoid = self._jwt_claim("ssoid") or self._jwt_claim("id") or ""

    def require_access(self) -> None:
        if not self.access_token or not self.device_id:
            raise AuthenticationError("business token requires access_token and device_id")

    def access_needs_refresh(self, now_ms: int | None = None) -> bool:
        if not self.access_token_exp:
            return False
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        return now_ms >= self.access_token_exp - self.access_token_refresh_ahead * 1000

    def refresh_is_expired(self, now_ms: int | None = None) -> bool:
        if not self.refresh_token_exp:
            return False
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        return now_ms >= self.refresh_token_exp - self.refresh_token_refresh_ahead * 1000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BusinessToken":
        aliases = {
            "accessToken": "access_token",
            "deviceId": "device_id",
            "refreshToken": "refresh_token",
            "idToken": "id_token",
            "pkgSign": "package_sign",
            "accessTokenExp": "access_token_exp",
            "refreshTokenExp": "refresh_token_exp",
            "accessTokenRfAdv": "access_token_refresh_ahead",
            "refreshTokenRfAdv": "refresh_token_refresh_ahead",
            "extraDataJson": "extra_data_json",
            "id": "ssoid",
        }
        normalized = {aliases.get(key, key): item for key, item in value.items()}
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: item for key, item in normalized.items() if key in allowed})

    def _jwt_claim(self, name: str) -> str | None:
        try:
            payload = self.id_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            value = claims.get(name)
            return str(value) if value is not None else None
        except (IndexError, ValueError, json.JSONDecodeError):
            return None


@dataclass(frozen=True)
class DeepTestingResponse:
    code: int
    message: str = ""
    data: Any = None

    @property
    def ok(self) -> bool:
        return self.code == 200

    @property
    def unlock_code(self) -> str | None:
        if isinstance(self.data, dict):
            value = self.data.get("unlockCode")
            return value if isinstance(value, str) else None
        return self.data if isinstance(self.data, str) else None

    def unlock_bytes(self) -> bytes | None:
        value = self.unlock_code
        if value is None:
            return None
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            raise ProtocolError("unlockCode is not an even-length hexadecimal string") from exc
