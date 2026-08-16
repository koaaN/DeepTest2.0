from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ProtocolError
from .heytap_models import HeyTapConfig, HeyTapDeviceProfile
from .heytap_transport import HeyTapV1Transport


SCENE_ID = "63GpVxAJXBp3TcCARNDa"


class HybridVerifier:
    """Direct client for the API hidden behind HeyTap's hybrid verification page."""

    def __init__(
        self,
        *,
        session_path: str | Path | None = None,
        device: HeyTapDeviceProfile | None = None,
        timeout: float = 30,
    ):
        path = Path(session_path) if session_path else Path.home() / ".config" / "deeptesting" / "login-session.json"
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"could not read login session: {path}") from exc
        if not isinstance(session, dict) or not session.get("process_token"):
            raise ProtocolError("login session has no process token")
        self.process_token = str(session["process_token"])
        host = str(session.get("host") or "https://uc-client-cn.heytapmobi.com")
        self.transport = HeyTapV1Transport(
            config=HeyTapConfig(host=host),
            device=device or HeyTapDeviceProfile(),
            timeout=timeout,
        )

    def methods(self) -> dict[str, Any]:
        checked = self.transport.post(
            "/api/verification/check",
            {
                "envInfo": json.dumps(
                    {
                        "sceneId": SCENE_ID,
                        "thirdPartyAppInfo": "",
                        "enableFinger": False,
                        "enablePin": False,
                    },
                    separators=(",", ":"),
                ),
                "processToken": self.process_token,
                "captchaCode": "",
                "deviceToken": {},
            },
        )
        self.process_token = self._process_token(checked)
        result = self.transport.post("/api/verification/list", {"processToken": self.process_token})
        data = self._data(result, "verification method list")
        if data.get("processToken"):
            self.process_token = str(data["processToken"])
        return data

    def verify_password(self, password: str) -> str:
        if not password:
            raise ValueError("password is required")
        result = self.transport.post(
            "/api/verification/validate-data",
            {
                "verMethod": "PASSWORD",
                "validateData": password,
                "processToken": self.process_token,
            },
        )
        data = self._data(result, "password verification")
        ticket = data.get("ticket")
        if isinstance(ticket, str) and ticket:
            return ticket
        raise ProtocolError("password verification did not return a completion ticket")

    @staticmethod
    def _data(result: dict[str, Any], operation: str) -> dict[str, Any]:
        if result.get("code") != 200:
            error = result.get("error")
            message = error.get("message") if isinstance(error, dict) else ""
            raise ProtocolError(f"{operation} failed: {result.get('code')} {message}".strip())
        data = result.get("data")
        if not isinstance(data, dict):
            raise ProtocolError(f"{operation} returned no data")
        return data

    def _process_token(self, result: dict[str, Any]) -> str:
        data = self._data(result, "environment verification")
        token = data.get("processToken")
        if not isinstance(token, str) or not token:
            raise ProtocolError("environment verification returned no process token")
        return token
