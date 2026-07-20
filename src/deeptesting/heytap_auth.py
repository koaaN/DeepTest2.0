from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

from .errors import HeyTapApiError, ProtocolError
from .heytap_models import (
    HeyTapConfig,
    LoginChallenge,
    LoginSession,
    PrimaryAccountToken,
    safety_check_fallback,
)
from .heytap_transport import HeyTapV1Transport, compact_json
from .models import BusinessToken
from .tokens import TokenCache


T = TypeVar("T")


class SecureJsonCache(Generic[T]):
    def __init__(self, path: str | Path, loader: Any):
        self.path = Path(path)
        self.loader = loader

    def load(self) -> T:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProtocolError(f"cache does not exist: {self.path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"could not read cache: {self.path}") from exc
        if not isinstance(value, dict):
            raise ProtocolError(f"cache must contain a JSON object: {self.path}")
        return self.loader(value)

    def save(self, value: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(value.to_dict(), ensure_ascii=False, indent=2) + "\n"
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}-", dir=self.path.parent)
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


class HeyTapAuthClient:
    def __init__(
        self,
        transport: HeyTapV1Transport,
        *,
        captcha_handler: Callable[[str], str] | None = None,
    ):
        self.transport = transport
        self.config = transport.config
        self.captcha_handler = captcha_handler

    def login_config(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "availableThirdApps": [],
            "imsis": [],
        }
        return self._data(
            self.transport.post(
                "/identity/v1/config/login",
                payload,
                headers={"X-Sys-DUID": self.transport.device.duid},
            ),
            "login config",
        )

    def begin_login(
        self,
        account_id: str,
        channel: str,
        *,
        country_calling_code: str = "",
        device_token: str = "",
        captcha_code: str = "",
    ) -> LoginSession | LoginChallenge:
        if channel not in {"phone", "email"}:
            raise ValueError("channel must be 'phone' or 'email'")
        if not account_id:
            raise ValueError("account_id is required")
        validation_headers = {
            "X-Validation-Method": channel,
            "X-Validation-Type": "verificationCode",
        }
        resolved_device_token = device_token or safety_check_fallback(self.config.account_package)
        check = self._check_account(
            account_id,
            country_calling_code,
            resolved_device_token,
            captcha_code,
            validation_headers,
        )
        if self._code(check) == 101001:
            error_data = self._error_data(check)
            captcha_payload = error_data.get("captchaHtml")
            captcha_html = self._captcha_html(captcha_payload)
            if self.captcha_handler is not None:
                if not captcha_html:
                    raise ProtocolError("CAPTCHA response does not contain HTML")
                raw_captcha_code = self.captcha_handler(captcha_html)
                if not isinstance(raw_captcha_code, str) or not raw_captcha_code:
                    raise ProtocolError("CAPTCHA handler returned no raw captchaCode")
                check = self._check_account(
                    account_id,
                    country_calling_code,
                    resolved_device_token,
                    raw_captcha_code,
                    validation_headers,
                )
                if self._code(check) == 101001:
                    raise HeyTapApiError(101001, self._message(check), self._error_data(check))
            else:
                return LoginChallenge(
                    "captcha",
                    payload=str(captcha_payload or ""),
                    message=self._message(check),
                )
        if self._code(check) == 101000:
            error_data = self._error_data(check)
            return LoginChallenge(
                "upgrade",
                url=str(error_data.get("upgradeUrl") or ""),
                payload=str(error_data.get("upgradeUrlType") or ""),
                message=self._message(check),
            )
        check_data = self._data(check, "account check")
        process_token = check_data.get("processToken")
        if not isinstance(process_token, str) or not process_token:
            raise ProtocolError("account check response has no processToken")
        sent = self.transport.post(
            "/identity/v1/authn/send-verification-code",
            {
                "processToken": process_token,
                "captchaType": "SMS" if channel == "phone" else "EMAIL",
            },
        )
        sent_data = self._optional_data(sent, "send verification code")
        code_length = sent_data.get("codeLength", 0)
        return LoginSession(
            account_id=account_id,
            channel=channel,
            process_token=process_token,
            country_calling_code=country_calling_code,
            code_length=code_length if isinstance(code_length, int) else 0,
        )

    def _check_account(
        self,
        account_id: str,
        country_calling_code: str,
        device_token: str,
        captcha_code: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        return self.transport.post(
            "/identity/v1/authn/check",
            {
                "accountId": account_id,
                "captchaCode": captcha_code or None,
                "countryCallingCode": country_calling_code or None,
                "deviceToken": device_token,
                "extendInfo": None,
                "fromRegisterPage": False,
                "sceneId": self.config.scene_id,
            },
            headers=headers,
        )

    @staticmethod
    def _captcha_html(value: Any) -> str:
        if isinstance(value, dict):
            html = value.get("html")
            return html if isinstance(html, str) else ""
        if not isinstance(value, str):
            return ""
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return ""
        if not isinstance(decoded, dict):
            return ""
        html = decoded.get("html")
        return html if isinstance(html, str) else ""

    def verify_code(
        self,
        session: LoginSession,
        verification_code: str,
    ) -> PrimaryAccountToken | LoginChallenge:
        if not verification_code:
            raise ValueError("verification_code is required")
        validated = self.transport.post(
            "/identity/v1/authn/validate",
            {
                "processToken": session.process_token,
                "validateParam": {"verificationCode": verification_code},
                "imsis": [],
            },
            headers={
                "X-Validation-Method": session.channel,
                "X-Validation-Type": "verificationCode",
            },
        )
        data = self._data(validated, "verification code validation")
        ticket = data.get("ticket")
        verification_url = data.get("verificationUrl")
        if isinstance(verification_url, str) and verification_url:
            session.ticket = str(ticket or "")
            return LoginChallenge("verification", url=verification_url)
        if not isinstance(ticket, str) or not ticket:
            raise ProtocolError("verification response has neither ticket nor verificationUrl")
        return self.complete(session, ticket)

    def complete(
        self,
        session: LoginSession,
        ticket: str,
    ) -> PrimaryAccountToken | LoginChallenge:
        completed = self.transport.post(
            "/completion/v1/redirect-judge",
            {
                "processToken": session.process_token,
                "ticket": ticket,
                "reRegister": False,
            },
        )
        data = self._data(completed, "login completion")
        completion_url = data.get("completionUrl")
        if isinstance(completion_url, str) and completion_url:
            session.ticket = ticket
            return LoginChallenge("completion", url=completion_url)
        return self.exchange_ticket(session, ticket)

    def exchange_ticket(self, session: LoginSession, ticket: str) -> PrimaryAccountToken:
        response = self.transport.post(
            "/identity/v1/authn/login",
            {
                "processToken": session.process_token,
                "ticket": ticket,
                "packages": self._account_packages(),
            },
        )
        return PrimaryAccountToken.from_login_response(self._data(response, "ticket exchange"))

    def biz_auth(
        self,
        primary: PrimaryAccountToken,
        *,
        env_param: str = "",
    ) -> BusinessToken:
        primary.require_access()
        env = {
            "appId": self.config.account_app_id,
            "appKey": self.config.account_app_key,
            "pkgName": self.config.account_package,
            "pkgNameSign": self.config.account_package_sign,
            "bizAppId": self.config.biz_app_id,
            "bizAppKey": self.config.biz_app_key,
            "bizPkgName": self.config.biz_package,
            "bizPkgNameSign": self.config.biz_package_sign,
            "envParam": env_param or safety_check_fallback(self.config.account_package),
        }
        response = self.transport.post(
            "/authorization/v1/token/authorize",
            {"envInfo": compact_json(env).decode("utf-8")},
            access_token=primary.access_token,
            id_token=primary.id_token,
        )
        token = TokenCache.extract_auth_response(response)
        token.require_access()
        return token

    def refresh_primary(
        self,
        primary: PrimaryAccountToken,
        *,
        env_param: str = "",
    ) -> PrimaryAccountToken:
        primary.require_access()
        env = {
            "appId": self.config.account_app_id,
            "appKey": self.config.account_app_key,
            "pkgName": self.config.account_package,
            "pkgNameSign": self.config.account_package_sign,
            "bizAppId": self.config.biz_app_id,
            "bizAppKey": self.config.biz_app_key,
            "bizPkgName": self.config.biz_package,
            "bizPkgNameSign": self.config.biz_package_sign,
            "envParam": env_param or safety_check_fallback(self.config.account_package),
        }
        response = self.transport.post(
            "/authorization/v1/token/refresh",
            {
                "ssoid": primary.ssoid,
                "envInfo": compact_json(env).decode("utf-8"),
                "packages": self._account_packages(),
            },
            headers={
                "X-AcRefreshToken": primary.refresh_token,
                "X-AcRefreshTicket": primary.refresh_ticket,
                "X-From-Source": self.config.biz_package,
            },
            access_token=primary.access_token,
            primary_token=primary.primary_token,
        )
        data = self._data(response, "primary token refresh")
        refreshed = data.get("v3TokenResp")
        if refreshed is None:
            return primary
        if not isinstance(refreshed, dict):
            raise ProtocolError("primary refresh v3TokenResp is not an object")
        secondary = data.get("secondaryTokenMap")
        if secondary is None:
            secondary = primary.secondary_token_map
        if not isinstance(secondary, dict):
            raise ProtocolError("primary refresh secondaryTokenMap is not an object")
        token = PrimaryAccountToken(
            access_token=str(refreshed.get("accessToken") or ""),
            id_token=str(refreshed.get("idToken") or ""),
            refresh_token=str(refreshed.get("refreshToken") or ""),
            primary_token=primary.primary_token,
            refresh_ticket=primary.refresh_ticket,
            ssoid=primary.ssoid,
            device_id=str(data.get("deviceId") or primary.device_id),
            account_name=primary.account_name,
            user_name=primary.user_name,
            country_code=primary.country_code,
            secondary_token_map={
                str(key): str(value)
                for key, value in secondary.items()
            },
        )
        token.require_access()
        return token

    def _account_packages(self) -> list[str]:
        return [
            self.config.account_package,
            "com.nearme.instant.platform",
            "com.android.launcher",
            "com.android.contacts",
            "com.oneplus.soundrecorder",
            "net.oneplus.forums",
            self.config.biz_package,
        ]

    @staticmethod
    def _code(response: dict[str, Any]) -> int:
        code = response.get("code")
        if not isinstance(code, int):
            raise ProtocolError("HeyTap response has no integer code")
        return code

    @classmethod
    def _data(cls, response: dict[str, Any], operation: str) -> dict[str, Any]:
        code = cls._code(response)
        if code != 200:
            raise HeyTapApiError(code, cls._message(response), cls._error_data(response))
        data = response.get("data")
        if data is None:
            raise ProtocolError(f"{operation} returned no data")
        if not isinstance(data, dict):
            raise ProtocolError(f"{operation} response data is not an object")
        return data

    @classmethod
    def _optional_data(cls, response: dict[str, Any], operation: str) -> dict[str, Any]:
        code = cls._code(response)
        if code != 200:
            raise HeyTapApiError(code, cls._message(response), cls._error_data(response))
        data = response.get("data")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ProtocolError(f"{operation} response data is not an object")
        return data

    @staticmethod
    def _message(response: dict[str, Any]) -> str:
        error = response.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        message = response.get("netMessage", response.get("message", ""))
        return message if isinstance(message, str) else str(message)

    @staticmethod
    def _error_data(response: dict[str, Any]) -> dict[str, Any]:
        error = response.get("error")
        data = error.get("errorData") if isinstance(error, dict) else None
        return data if isinstance(data, dict) else {}


def default_primary_cache(path: str | Path | None = None) -> SecureJsonCache[PrimaryAccountToken]:
    target = Path(path) if path else Path.home() / ".config" / "deeptesting" / "primary-auth.json"
    return SecureJsonCache(target, PrimaryAccountToken.from_dict)


def default_login_cache(path: str | Path | None = None) -> SecureJsonCache[LoginSession]:
    target = Path(path) if path else Path.home() / ".config" / "deeptesting" / "login-session.json"
    return SecureJsonCache(target, LoginSession.from_dict)
