import json
import os
import tempfile
import unittest
from pathlib import Path

from deeptesting.models import BusinessToken
from deeptesting.refresh import BusinessTokenRefresher
from deeptesting.tokens import TokenCache


class TokenCacheTests(unittest.TestCase):
    def test_extracts_biz_auth_response(self):
        token = TokenCache.extract_auth_response(
            {
                "data": {
                    "v3BizTokenResp": {"accessToken": "access", "refreshToken": "refresh"},
                    "deviceId": "device",
                    "host": "https://example.test",
                }
            }
        )
        self.assertEqual(token.access_token, "access")
        self.assertEqual(token.device_id, "device")

    def test_extracts_deeptesting_secondary_token(self):
        token = TokenCache.extract_auth_response(
            {
                "data": {
                    "v3BizTokenResp": {"accessToken": "access", "refreshToken": "refresh"},
                    "deviceId": "device",
                    "secondaryTokenMap": {"com.coloros.deeptesting": "TOKEN_scoped"},
                }
            }
        )
        self.assertEqual(token.new_token, "TOKEN_scoped")

    def test_refresh_response_inherits_device_metadata(self):
        previous = BusinessToken("old", "device", refresh_token="old-refresh", ssoid="42")
        token = TokenCache.extract_auth_response(
            {"data": {"v3TokenResp": {"accessToken": "new", "refreshToken": "new-refresh"}}},
            fallback=previous,
        )
        self.assertEqual(token.access_token, "new")
        self.assertEqual(token.device_id, "device")
        self.assertEqual(token.ssoid, "42")
        self.assertEqual(token.new_token, "new")

    def test_cache_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            cache = TokenCache(path)
            cache.save(BusinessToken("access", "device"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(cache.load().access_token, "access")


class RefreshPayloadTests(unittest.TestCase):
    def test_payload_signature_is_deterministic(self):
        token = BusinessToken(
            "access",
            "device",
            refresh_token="refresh",
            package_sign="sign",
            ssoid="42",
        )
        refresher = BusinessTokenRefresher()
        first = refresher.build_payload(token, now_ms=123)
        second = refresher.build_payload(token, now_ms=123)
        self.assertEqual(first, second)
        self.assertEqual(len(first["sign"]), 32)
        self.assertEqual(json.loads(first["envInfo"])["bizAppId"], "37020981")


if __name__ == "__main__":
    unittest.main()
