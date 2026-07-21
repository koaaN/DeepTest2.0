from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from .captcha_handler import solve_captcha
from .errors import DeepTestingError, HeyTapApiError, ProtocolError
from .heytap_auth import HeyTapAuthClient, default_login_cache, default_primary_cache
from .heytap_models import HeyTapConfig, HeyTapDeviceProfile, LoginChallenge
from .heytap_transport import HeyTapV1Transport
from .refresh import BusinessTokenRefresher, RefreshConfig
from .tokens import TokenCache


def _read_json(path: str) -> dict:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"could not read authorization response: {path}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("authorization response must be a JSON object")
    return value


def _host_for_country(mapping: object, country: object) -> str:
    if not isinstance(mapping, dict) or not isinstance(country, str):
        return ""
    country = country.strip().upper()
    for countries, host in mapping.items():
        if not isinstance(countries, str) or not isinstance(host, str):
            continue
        if country in {item.strip().upper() for item in countries.split(",")}:
            return host.rstrip("/")
    default = mapping.get("default")
    return default.rstrip("/") if isinstance(default, str) else ""


def _auth_client(args: argparse.Namespace) -> HeyTapAuthClient:
    device = HeyTapDeviceProfile(
        model=args.model,
        duid=args.duid,
        ouid=args.ouid,
        guid=args.guid,
        device_id=args.device_id,
    )
    transport = HeyTapV1Transport(
        config=HeyTapConfig(
            host=args.host or os.getenv("DEEPTEST_HEYTAP_HOST") or "https://client-uc.heytapmobi.com"
        ),
        device=device,
        timeout=args.timeout,
    )
    captcha_timeout = getattr(args, "captcha_timeout", 300.0)
    no_open_browser = getattr(args, "no_open_browser", False)
    return HeyTapAuthClient(
        transport,
        captcha_handler=lambda html: solve_captcha(
            html,
            timeout=captcha_timeout,
            auto_open_browser=not no_open_browser,
        ),
    )


def _challenge(challenge: LoginChallenge) -> int:
    print(json.dumps({
        "status": "interaction_required",
        "kind": challenge.kind,
        "url": challenge.url,
        "payload": challenge.payload,
        "message": challenge.message,
    }, indent=2, ensure_ascii=False))
    return 3


def _add_auth_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--login-cache", default=os.getenv("DEEPTEST_LOGIN_CACHE"))
    parser.add_argument("--primary-cache", default=os.getenv("DEEPTEST_PRIMARY_CACHE"))
    parser.add_argument("--duid", default=os.getenv("DEEPTEST_DUID", ""))
    parser.add_argument("--ouid", default=os.getenv("DEEPTEST_OUID", ""))
    parser.add_argument("--guid", default=os.getenv("DEEPTEST_UDID", ""))
    parser.add_argument("--device-id", default=os.getenv("DEEPTEST_DEVICE_ID", ""))
    parser.add_argument("--model", default=os.getenv("DEEPTEST_MODEL", "PLK110"))
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--host",
        default=None,
        help="HeyTap UserCenter host; use the host reported by a 301 domain error",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage DeepTesting account and business tokens")
    parser.add_argument("--token-cache", default=os.getenv("DEEPTEST_TOKEN_CACHE"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="import an AuthResponse or bizAuth JSON response")
    import_parser.add_argument("path", help="JSON file, or - for stdin")

    refresh_parser = subparsers.add_parser("refresh", help="experimentally refresh the cached business token")
    refresh_parser.add_argument("--env-param", default=os.getenv("DEEPTEST_ENV_PARAM", ""))
    refresh_parser.add_argument("--duid", default=os.getenv("DEEPTEST_DUID", ""))
    refresh_parser.add_argument("--timeout", type=float, default=30)

    login_parser = subparsers.add_parser("login", help="send a HeyTap CN SMS or email verification code")
    account = login_parser.add_mutually_exclusive_group(required=True)
    account.add_argument("--phone")
    account.add_argument("--email")
    login_parser.add_argument("--country-calling-code", default="+86")
    login_parser.add_argument("--device-token", default=os.getenv("DEEPTEST_DEVICE_TOKEN", ""))
    login_parser.add_argument("--captcha-code", default="")
    login_parser.add_argument("--captcha-timeout", type=float, default=300)
    login_parser.add_argument("--no-open-browser", action="store_true")
    _add_auth_options(login_parser)

    verify_parser = subparsers.add_parser("verify", help="validate a code and obtain DeepTesting business tokens")
    verify_parser.add_argument("code")
    verify_parser.add_argument("--env-param", default=os.getenv("DEEPTEST_ENV_PARAM", ""))
    _add_auth_options(verify_parser)

    resume_parser = subparsers.add_parser("resume", help="resume an H5 validation or completion challenge")
    resume_parser.add_argument("--ticket", required=True)
    resume_parser.add_argument("--stage", choices=("verification", "completion"), required=True)
    resume_parser.add_argument("--env-param", default=os.getenv("DEEPTEST_ENV_PARAM", ""))
    _add_auth_options(resume_parser)

    biz_parser = subparsers.add_parser("biz-auth", help="authorize DeepTesting from cached primary tokens")
    biz_parser.add_argument("--env-param", default=os.getenv("DEEPTEST_ENV_PARAM", ""))
    _add_auth_options(biz_parser)

    primary_refresh_parser = subparsers.add_parser("primary-refresh", help="refresh primary tokens and reauthorize DeepTesting")
    primary_refresh_parser.add_argument("--env-param", default=os.getenv("DEEPTEST_ENV_PARAM", ""))
    _add_auth_options(primary_refresh_parser)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    token_cache = TokenCache(args.token_cache)
    try:
        if args.command == "import":
            token = token_cache.extract_auth_response(_read_json(args.path))
            token.require_access()
            token_cache.save(token)
            print(f"saved business token cache: {token_cache.path}")
            return 0
        if args.command == "refresh":
            token = token_cache.load()
            config = RefreshConfig(env_param=args.env_param, duid=args.duid)
            refreshed = BusinessTokenRefresher(config, timeout=args.timeout).refresh(token)
            token_cache.save(refreshed)
            print(f"refreshed business token cache: {token_cache.path}")
            return 0

        client = _auth_client(args)
        login_cache = default_login_cache(args.login_cache)
        primary_cache = default_primary_cache(args.primary_cache)
        if args.command == "login":
            channel = "phone" if args.phone else "email"
            account_id = args.phone or args.email
            country_code = args.country_calling_code if channel == "phone" else ""
            result = client.begin_login(
                account_id,
                channel,
                country_calling_code=country_code,
                device_token=args.device_token,
                captcha_code=args.captcha_code,
            )
            if isinstance(result, LoginChallenge):
                return _challenge(result)
            result.host = client.transport.host
            login_cache.save(result)
            print(f"verification code sent; saved login session: {login_cache.path}")
            return 0

        if args.command in {"biz-auth", "primary-refresh"}:
            primary = primary_cache.load()
            if primary.host and not args.host and not os.getenv("DEEPTEST_HEYTAP_HOST"):
                client.transport.host = primary.host.rstrip("/")
            if args.command == "primary-refresh":
                primary = client.refresh_primary(primary, env_param=args.env_param)
                primary_cache.save(primary)
        else:
            session = login_cache.load()
            if session.host and not args.host and not os.getenv("DEEPTEST_HEYTAP_HOST"):
                client.transport.host = session.host.rstrip("/")
            if args.command == "verify":
                result = client.verify_code(session, args.code)
            elif args.stage == "verification":
                result = client.complete(session, args.ticket)
            else:
                result = client.exchange_ticket(session, args.ticket)
            if isinstance(result, LoginChallenge):
                session.host = client.transport.host
                login_cache.save(session)
                return _challenge(result)
            primary = result
            primary.host = client.transport.host
            primary_cache.save(primary)

        business = client.biz_auth(primary, env_param=args.env_param)
        primary.host = client.transport.host
        primary_cache.save(primary)
        token_cache.save(business)
        print(f"saved primary token cache: {primary_cache.path}")
        print(f"saved business token cache: {token_cache.path}")
        return 0
    except HeyTapApiError as exc:
        if exc.code == 301:
            print(f"error: HeyTap request failed: {exc.code} {exc.message}", file=sys.stderr)
            if exc.response is not None:
                print(json.dumps(exc.response, indent=2, ensure_ascii=False), file=sys.stderr)
            mapping = exc.error_data.get("countryDomainMapping") if isinstance(exc.error_data, dict) else None
            country = exc.error_data.get("countryCode") if isinstance(exc.error_data, dict) else None
            host = _host_for_country(mapping, country)
            if host:
                print(f"hint: retry with --host {host} for region {country}", file=sys.stderr)
            else:
                print("hint: retry with --host <regional-host> from countryDomainMapping", file=sys.stderr)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except (DeepTestingError, requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
