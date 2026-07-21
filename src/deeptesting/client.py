from __future__ import annotations

import json
from typing import Any

import requests

from .crypto import LkSession
from .errors import ProtocolError
from .models import BusinessToken, DeepTestingResponse, DeviceProfile


ENDPOINTS = {
    "apply-unlock",
    "get-apply-status",
    "update-client-lock-status",
    "lock-client",
    "unlock-condition-match",
    "get-history-unlock-code",
}


class DeepTestingClient:
    def __init__(
        self,
        profile: DeviceProfile,
        token: BusinessToken,
        *,
        host: str = "lk-oneplus-cn.allawntech.com",
        timeout: float = 30,
        http: requests.Session | None = None,
    ):
        token.require_access()
        if profile.device_id != token.device_id:
            raise ValueError("profile.device_id must match the business token device_id")
        self.profile = profile
        self.token = token
        self.host = host.removeprefix("https://").rstrip("/")
        self.timeout = timeout
        self.http = http or requests.Session()
        self._lk: LkSession | None = None

    def establish_session(self, *, register_keys: bool = False) -> None:
        self._lk = LkSession.establish(self.http, self.host, self.timeout)
        if register_keys:
            LkSession.register_keys(self.http, self.host, self.profile.device_id, self.timeout)

    def request(self, endpoint: str) -> DeepTestingResponse:
        if endpoint not in ENDPOINTS:
            raise ValueError(f"unsupported endpoint: {endpoint}")
        if self._lk is None:
            self.establish_session()
        assert self._lk is not None

        payload = self.profile.request_payload(endpoint, self.token.new_token)
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        body = {"params": self._lk.encrypt(plaintext)}
        response = self.http.post(
            f"https://{self.host}/api/v3/{endpoint}",
            json=body,
            headers={
                "model": self.profile.model,
                "otaVersion": self.profile.ota_version,
                "language": self.profile.language,
                "osVersion": self.profile.os_version,
                "x-otci-cipherInfo": self._lk.cipher_header(),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            wrapper = response.json()
            encrypted_response = wrapper["resps"]
        except (requests.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProtocolError("DeepTesting response does not contain encrypted 'resps'") from exc
        if not isinstance(encrypted_response, str):
            raise ProtocolError("DeepTesting response 'resps' is not a string")
        try:
            result = json.loads(self._lk.decrypt(encrypted_response))
        except json.JSONDecodeError as exc:
            raise ProtocolError("decrypted DeepTesting response is not JSON") from exc
        return self._parse_response(endpoint, result)

    def apply_unlock(self) -> DeepTestingResponse:
        return self.request("apply-unlock")

    def get_apply_status(self) -> DeepTestingResponse:
        return self.request("get-apply-status")

    def update_client_lock_status(self) -> DeepTestingResponse:
        return self.request("update-client-lock-status")

    def lock_client(self) -> DeepTestingResponse:
        return self.request("lock-client")

    def unlock_condition_match(self) -> DeepTestingResponse:
        return self.request("unlock-condition-match")

    def get_history_unlock_code(self) -> DeepTestingResponse:
        return self.request("get-history-unlock-code")

    @staticmethod
    def _parse_response(endpoint: str, result: Any) -> DeepTestingResponse:
        if not isinstance(result, dict) or not isinstance(result.get("code"), int):
            raise ProtocolError("decrypted DeepTesting response has no integer code")
        message = result.get("message", result.get("msg", ""))
        if not isinstance(message, str):
            message = str(message)
        data = result.get("data")
        if endpoint == "get-history-unlock-code" and data is not None and not isinstance(data, str):
            raise ProtocolError("history unlock code response data is not a string")
        return DeepTestingResponse(result["code"], message, data)
