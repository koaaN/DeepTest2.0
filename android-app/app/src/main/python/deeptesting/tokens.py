from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ProtocolError
from .models import BusinessToken
from .private_file import atomic_write_private


class TokenCache:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".config" / "deeptesting" / "auth.json"

    def load(self) -> BusinessToken:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProtocolError(f"token cache does not exist: {self.path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"could not read token cache: {self.path}") from exc
        if not isinstance(value, dict):
            raise ProtocolError("token cache must contain a JSON object")
        return BusinessToken.from_dict(value)

    def save(self, token: BusinessToken) -> None:
        payload = (json.dumps(token.to_dict(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        atomic_write_private(self.path, payload, prefix=".auth-")

    @staticmethod
    def extract_auth_response(
        value: dict[str, Any],
        fallback: BusinessToken | None = None,
    ) -> BusinessToken:
        data: Any = value.get("data", value)
        token_key = None
        if isinstance(data, dict):
            token_key = next(
                (key for key in ("v3BizTokenResp", "v3TokenResp") if isinstance(data.get(key), dict)),
                None,
            )
        if isinstance(data, dict) and token_key:
            token_data = dict(data[token_key])
            for key in ("deviceId", "extraDataJson", "host", "pkgSign"):
                if key in data:
                    token_data[key] = data[key]
            if fallback:
                defaults = {
                    "deviceId": fallback.device_id,
                    "host": fallback.host,
                    "pkgSign": fallback.package_sign,
                    "idToken": fallback.id_token,
                    "refreshToken": fallback.refresh_token,
                    "ssoid": fallback.ssoid,
                }
                for key, item in defaults.items():
                    if item:
                        token_data.setdefault(key, item)
            secondary = data.get("secondaryTokenMap")
            if isinstance(secondary, dict):
                token_data["deeptestingToken"] = str(
                    secondary.get("com.coloros.deeptesting") or ""
                )
            return BusinessToken.from_dict(token_data)
        if isinstance(data, dict):
            token = BusinessToken.from_dict(data)
            secondary = data.get("secondaryTokenMap")
            if isinstance(secondary, dict):
                token.deeptesting_token = str(
                    secondary.get("com.coloros.deeptesting") or ""
                )
            return token
        raise ProtocolError("authorization response does not contain a token object")
