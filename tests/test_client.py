import json
import unittest

from deeptesting.client import DeepTestingClient
from deeptesting.crypto import LkSession
from deeptesting.models import BusinessToken, DeviceProfile


class FakeResponse:
    def __init__(self, value):
        self.value = value
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class FakeHttp:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.response)


class DeepTestingClientTests(unittest.TestCase):
    def test_encrypted_request_and_response(self):
        lk = LkSession(b"k" * 32, b"temporary-public-key", 7)
        encrypted_response = lk.encrypt(
            json.dumps({"code": 200, "message": "ok", "data": {"state": 1}})
        )
        http = FakeHttp({"resps": encrypted_response})
        profile = DeviceProfile("guid", "device", chip_id="0x123")
        token = BusinessToken("access", "device")
        client = DeepTestingClient(profile, token, http=http)
        client._lk = lk

        result = client.apply_unlock()

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"state": 1})
        url, request = http.calls[0]
        self.assertTrue(url.endswith("/api/v3/apply-unlock"))
        self.assertIn("x-otci-cipherInfo", request["headers"])
        encrypted_request = request["json"]["params"]
        plaintext = json.loads(lk.decrypt(encrypted_request))
        self.assertEqual(plaintext["newToken"], "access")
        self.assertEqual(plaintext["udid"], "guid")

    def test_device_id_must_match_token(self):
        with self.assertRaises(ValueError):
            DeepTestingClient(
                DeviceProfile("guid", "other-device"),
                BusinessToken("access", "device"),
            )


if __name__ == "__main__":
    unittest.main()
