from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

from .errors import AuthenticationError, ProtocolError


@dataclass(frozen=True)
class HeyTapDeviceProfile:
    model: str = "PLK110"
    market_name: str = "OnePlus 15"
    brand: str = "OnePlus"
    product_name: str = "PLK110"
    ota_version: str = "PLK110_11.A.68_0680_202606250030"
    rom_version: str = "V16.0"
    os_version: str = "16"
    android_api: int = 36
    build_time: int = 0
    width: int = 1272
    height: int = 2800
    timezone: str = "Asia/Shanghai"
    locale: str = "zh_CN"
    language_tag: str = "zh-CN"
    hardware_type: str = "phone"
    device_name: str = "PLK110"
    duid: str = ""
    ouid: str = ""
    guid: str = ""
    device_id: str = ""
    register_id: str = ""


@dataclass(frozen=True)
class HeyTapConfig:
    host: str = "https://client-uc.heytapmobi.com"
    account_package: str = "com.oplus.account"
    account_package_sign: str = "2ce12ce68a183f56af0e8f715f202b9e"
    account_version: str = "916106"
    account_version_name: str = "CN_9.16.106_c93b62a"
    account_aar_version: str = "916106"
    account_app_id: str = "30749365"
    account_app_key: str = "c372fbbff12f48678a1e0e8b66b431b9"
    account_secret: str = "5e95ae46905d4adca9a7cff6ead3b3f3"
    biz_package: str = "com.coloros.deeptesting"
    biz_package_sign: str = "bd876af0b4647d665ff78389bd690641"
    biz_version: str = "17.0.3"
    biz_app_id: str = "37020981"
    biz_app_key: str = "7bb73a85f2d6462f95259fc574c66784"
    sdk_version: str = "917001"
    sdk_type: str = "account_sdk"
    scene_id: str = "63GpVxAJXBp3TcCARNDa"
    country: str = "CN"


@dataclass
class PrimaryAccountToken:
    access_token: str
    id_token: str
    refresh_token: str
    primary_token: str
    refresh_ticket: str
    ssoid: str
    device_id: str
    account_name: str = ""
    user_name: str = ""
    country_code: str = ""
    secondary_token_map: dict[str, str] = field(default_factory=dict)

    def require_access(self) -> None:
        required = (
            self.access_token,
            self.id_token,
            self.refresh_token,
            self.primary_token,
            self.ssoid,
            self.device_id,
        )
        if not all(required):
            raise AuthenticationError("primary account response is missing required token fields")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PrimaryAccountToken":
        aliases = {
            "accessToken": "access_token",
            "idToken": "id_token",
            "refreshToken": "refresh_token",
            "primaryToken": "primary_token",
            "refreshTicket": "refresh_ticket",
            "deviceId": "device_id",
            "accountName": "account_name",
            "userName": "user_name",
            "countryCode": "country_code",
            "secondaryTokenMap": "secondary_token_map",
        }
        normalized = {aliases.get(key, key): item for key, item in value.items()}
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: item for key, item in normalized.items() if key in allowed})

    @classmethod
    def from_login_response(cls, value: dict[str, Any]) -> "PrimaryAccountToken":
        account = value.get("accountToken")
        if not isinstance(account, dict):
            raise ProtocolError("login response does not contain accountToken")
        secondary = value.get("secondaryTokenMap")
        if not isinstance(secondary, dict):
            raise ProtocolError("login response does not contain secondaryTokenMap")
        token = cls(
            access_token=str(account.get("accessToken") or ""),
            id_token=str(account.get("idToken") or ""),
            refresh_token=str(account.get("refreshToken") or ""),
            primary_token=str(value.get("primaryToken") or ""),
            refresh_ticket=str(value.get("refreshTicket") or ""),
            ssoid=str(value.get("ssoid") or ""),
            device_id=str(value.get("deviceId") or ""),
            account_name=str(value.get("accountName") or ""),
            user_name=str(value.get("userName") or ""),
            country_code=str(value.get("countryCode") or ""),
            secondary_token_map={str(key): str(item) for key, item in secondary.items()},
        )
        token.require_access()
        return token


@dataclass
class LoginSession:
    account_id: str
    channel: Literal["phone", "email"]
    process_token: str
    country_calling_code: str = ""
    ticket: str = ""
    code_length: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LoginSession":
        return cls(**{item.name: value[item.name] for item in fields(cls) if item.name in value})


@dataclass(frozen=True)
class LoginChallenge:
    kind: Literal["captcha", "verification", "completion", "upgrade"]
    url: str = ""
    payload: str = ""
    message: str = ""


def safety_check_fallback(package_name: str, *, nonce: bytes | None = None) -> str:
    raw_nonce = nonce if nonce is not None else os.urandom(16)
    if len(raw_nonce) != 16:
        raise ValueError("SafetyCheck nonce must be 16 bytes")
    value = {
        "bizToken": "",
        "effectiveTime": 0,
        "nonce": base64.b64encode(raw_nonce).decode("ascii"),
        "pkgName": package_name,
        "reserved": "",
        "sysIntegrity": False,
        "timestamp": int(time.time() * 1000),
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def new_trace_id() -> str:
    return uuid.uuid4().hex
