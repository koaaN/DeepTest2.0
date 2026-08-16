import json
from pathlib import Path

from deeptesting.client import DeepTestingClient
from deeptesting.heytap_auth import HeyTapAuthClient, SecureJsonCache
from deeptesting.heytap_models import HeyTapConfig, HeyTapDeviceProfile, LoginChallenge, LoginSession, PrimaryAccountToken
from deeptesting.heytap_transport import HeyTapV1Transport
from deeptesting.models import DeviceProfile
from deeptesting.tokens import TokenCache


def _result(**values):
    return json.dumps(values, ensure_ascii=False)


def _paths(base):
    root = Path(base) / "auth"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _client(model="PLK110"):
    transport = HeyTapV1Transport(HeyTapConfig(), HeyTapDeviceProfile(model=model), timeout=30)
    return HeyTapAuthClient(transport)


def dispatch(action, raw, base):
    try:
        data = json.loads(raw or "{}")
        root = _paths(base)
        client = _client(data.get("model", "PLK110"))
        login_cache = SecureJsonCache(root / "login-session.json", LoginSession.from_dict)
        primary_cache = SecureJsonCache(root / "primary-auth.json", PrimaryAccountToken.from_dict)
        token_cache = TokenCache(root / "auth.json")

        def save_authorization(primary):
            primary.host = client.transport.host
            primary_cache.save(primary)
            business = client.biz_auth(primary)
            token_cache.save(business)
            return _result(ok=True, message="Account authorization saved.")

        if action == "login":
            result = client.begin_login(
                data["accountId"].strip(),
                data["channel"],
                country_calling_code=data.get("country", "") if data["channel"] == "phone" else "",
                captcha_code=data.get("captchaCode", ""),
            )
            if isinstance(result, LoginChallenge):
                return _result(
                    ok=False,
                    interaction=True,
                    kind=result.kind,
                    url=result.url,
                    payload=result.payload,
                    message=result.message,
                )
            result.host = client.transport.host
            login_cache.save(result)
            return _result(ok=True, message="Verification code sent.")
        if action == "verify":
            session = login_cache.load()
            if session.host:
                client.transport.host = session.host.rstrip("/")
            result = client.verify_code(session, data["code"].strip())
            if isinstance(result, LoginChallenge):
                session.host = client.transport.host
                login_cache.save(session)
                return _result(ok=False, interaction=True, kind=result.kind, url=result.url, payload=result.payload, message="Additional identity verification required.")
            return save_authorization(result)
        if action == "resume":
            session = login_cache.load()
            if session.host:
                client.transport.host = session.host.rstrip("/")
            ticket = str(data.get("ticket") or session.ticket or "").strip()
            if not ticket:
                raise ValueError("The saved identity-verification ticket is missing. Start login again.")
            stage = str(data.get("stage") or "verification")
            if stage == "completion":
                result = client.exchange_ticket(session, ticket)
            else:
                result = client.complete(session, ticket)
            if isinstance(result, LoginChallenge):
                session.host = client.transport.host
                login_cache.save(session)
                return _result(ok=False, interaction=True, kind=result.kind, url=result.url, payload=result.payload, message="One more identity-verification step is required.")
            return save_authorization(result)
        if action == "request":
            token = token_cache.load()
            saved_profile = {}
            profile_file = root / "gui-settings.json"
            if profile_file.is_file():
                try:
                    saved_profile = json.loads(profile_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    saved_profile = {}
            profile = DeviceProfile(udid=saved_profile.get("udid") or data.get("udid") or "", device_id=token.device_id, model=saved_profile.get("model") or data.get("model", "PLK110"), ota_version=saved_profile.get("ota_version") or data.get("otaVersion", "PLK110_11.A.68_0680_202606250030"), chip_id=saved_profile.get("chip_id") or data.get("chipId", ""))
            if not profile.udid:
                raise ValueError("Enter the phone UDID in the request profile before running a request.")
            response = DeepTestingClient(profile, token).request(data["endpoint"])
            message = json.dumps({
                "code": response.code,
                "message": response.message,
                "data": response.data,
            }, ensure_ascii=False, indent=2)
            return _result(ok=response.ok, code=response.code, message=message, data=response.data, unlockCode=response.unlock_code)
        return _result(ok=False, error="Unknown action")
    except Exception as exc:
        return _result(ok=False, error=str(exc))
