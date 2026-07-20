import base64
import json
import unittest

from deeptesting.models import BusinessToken, DeviceProfile


class DeviceProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = DeviceProfile("guid", "device", chip_id="0x123", operator="46000")

    def test_full_request_uses_new_token(self):
        payload = self.profile.request_payload("apply-unlock", "TOKEN")
        self.assertEqual(payload["newToken"], "TOKEN")
        self.assertNotIn("token", payload)
        self.assertEqual(payload["appVersion"], 17000003)

    def test_status_omits_common_new_api_fields(self):
        payload = self.profile.request_payload("get-apply-status", "TOKEN")
        self.assertNotIn("model", payload)
        self.assertNotIn("otaVersion", payload)
        self.assertNotIn("brand", payload)
        self.assertEqual(payload["chipId"], "0x123")

    def test_history_omits_device_description(self):
        payload = self.profile.request_payload("get-history-unlock-code", "TOKEN")
        for key in ("model", "otaVersion", "brand", "chipId", "operator"):
            self.assertNotIn(key, payload)


class BusinessTokenTests(unittest.TestCase):
    def test_extracts_ssoid_from_jwt(self):
        body = base64.urlsafe_b64encode(json.dumps({"ssoid": "42"}).encode()).decode().rstrip("=")
        token = BusinessToken("access", "device", id_token=f"x.{body}.x")
        self.assertEqual(token.ssoid, "42")


if __name__ == "__main__":
    unittest.main()
