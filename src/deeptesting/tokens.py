from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import ProtocolError
from .models import BusinessToken


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
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(token.to_dict(), indent=2, ensure_ascii=False) + "\n"
        fd, temporary_name = tempfile.mkstemp(prefix=".auth-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

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
            return BusinessToken.from_dict(token_data)
        if isinstance(data, dict):
            return BusinessToken.from_dict(data)
        raise ProtocolError("authorization response does not contain a token object")
