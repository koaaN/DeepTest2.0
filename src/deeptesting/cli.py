from __future__ import annotations

import argparse
import json
import os
import sys

import requests

from .client import ENDPOINTS, DeepTestingClient
from .errors import DeepTestingError
from .models import BusinessToken, DeviceProfile
from .tokens import TokenCache


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepTesting 17.0.3 API client")
    parser.add_argument("endpoint", choices=sorted(ENDPOINTS))
    parser.add_argument("--token", default=os.getenv("DEEPTEST_NEW_TOKEN", ""))
    parser.add_argument("--device-id", default=os.getenv("DEEPTEST_DEVICE_ID", ""))
    parser.add_argument("--token-cache", default=os.getenv("DEEPTEST_TOKEN_CACHE"))
    parser.add_argument("--udid", default=os.getenv("DEEPTEST_UDID", ""))
    parser.add_argument("--model", default=os.getenv("DEEPTEST_MODEL", "PLK110"))
    parser.add_argument("--ota-version", default=os.getenv("DEEPTEST_OTA_VERSION", "PLK110_11.A.68_0680_202606250030"))
    parser.add_argument("--brand", default=os.getenv("DEEPTEST_BRAND", "OnePlus"))
    parser.add_argument("--operator", default=os.getenv("DEEPTEST_OPERATOR", ""))
    parser.add_argument("--chip-id", default=os.getenv("DEEPTEST_CHIP_ID", ""))
    parser.add_argument("--os-version", default=os.getenv("DEEPTEST_OS_VERSION", "16"))
    parser.add_argument("--app-version", type=int, default=int(os.getenv("DEEPTEST_APP_VERSION", "17000003")))
    parser.add_argument("--client-lock-status", type=int, default=int(os.getenv("DEEPTEST_LOCK_STATUS", "0")))
    parser.add_argument("--host", default=os.getenv("DEEPTEST_HOST", "lk-oneplus-cn.allawntech.com"))
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--register-keys", action="store_true")
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.token:
            if not args.device_id:
                parser.error("--device-id is required with --token")
            token = BusinessToken(args.token, args.device_id)
        else:
            token = TokenCache(args.token_cache).load()
            if args.device_id and args.device_id != token.device_id:
                parser.error("--device-id does not match the cached token")
        if not args.udid:
            parser.error("--udid or DEEPTEST_UDID is required; it must be the device GUID")
        profile = DeviceProfile(
            udid=args.udid,
            device_id=token.device_id,
            model=args.model,
            ota_version=args.ota_version,
            brand=args.brand,
            operator=args.operator,
            chip_id=args.chip_id,
            app_version=args.app_version,
            client_lock_status=args.client_lock_status,
            os_version=args.os_version,
        )
        client = DeepTestingClient(profile, token, host=args.host, timeout=args.timeout)
        if args.register_keys:
            client.establish_session(register_keys=True)
        result = client.request(args.endpoint)
        output = {"code": result.code, "message": result.message, "data": result.data}
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0 if result.ok else 2
    except (DeepTestingError, requests.RequestException, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
