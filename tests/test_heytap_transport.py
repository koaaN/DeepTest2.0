import base64
import gzip
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from deeptesting.heytap_models import HeyTapConfig
from deeptesting.heytap_transport import DEFAULT_RSA_PUBLIC_KEY, HeyTapV1Transport, compact_json


class HeyTapTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        values = iter((b"k" * 32, b"i" * 16))
        self.transport = HeyTapV1Transport(
            rsa_key_path=Path(self.temporary.name) / "rsa.der",
            random_bytes=lambda size: next(values),
            now_ms=lambda: 1_720_000_000_123,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_compact_json_preserves_unicode(self):
        self.assertEqual(compact_json({"name": "测试", "empty": None}), b'{"name":"\xe6\xb5\x8b\xe8\xaf\x95","empty":null}')

    def test_signing_headers_match_canonical_hmac(self):
        plaintext = b'{"accountId":"13800000000"}'
        headers = self.transport.signing_headers(plaintext)
        canonical = (
            f"requestBody={hashlib.md5(plaintext).hexdigest()}"
            "&requestTime=1720000000123&signAlgorithm=HMAC1_SK"
            f"{HeyTapConfig().account_app_key}"
        )
        expected = base64.b64encode(
            hmac.new(
                HeyTapConfig().account_secret.encode(),
                canonical.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
        self.assertEqual(headers["X-Sign"], expected)
        self.assertEqual(headers["X-Sign-Key"], HeyTapConfig().account_app_key)

    def test_encrypted_body_is_gzipped_three_part_envelope(self):
        body = self.transport.encrypt_body(b'{"value":1}')
        parts = gzip.decompress(body).decode().split(".")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(base64.b64decode(parts[0])), 128)
        self.assertEqual(len(base64.b64decode(parts[1])), 128)
        encrypted = base64.b64decode(parts[2])
        decryptor = Cipher(algorithms.AES(b"k" * 32), modes.CTR(b"i" * 16)).decryptor()
        self.assertEqual(decryptor.update(encrypted) + decryptor.finalize(), b'{"value":1}')

    def test_response_uses_same_process_key_and_iv(self):
        plaintext = json.dumps({"code": 200}, separators=(",", ":")).encode()
        encryptor = Cipher(algorithms.AES(b"k" * 32), modes.CTR(b"i" * 16)).encryptor()
        encrypted = encryptor.update(plaintext) + encryptor.finalize()
        self.assertEqual(self.transport.decrypt_response(base64.b64encode(encrypted).decode()), plaintext.decode())

    def test_http_222_rotates_key_and_retries_once(self):
        new_key = base64.b64decode(DEFAULT_RSA_PUBLIC_KEY)
        success = requests.Response()
        success.status_code = 200
        plaintext = b'{"code":200,"data":{}}'
        encryptor = Cipher(algorithms.AES(b"k" * 32), modes.CTR(b"i" * 16)).encryptor()
        success._content = base64.b64encode(encryptor.update(plaintext) + encryptor.finalize())
        rotate = requests.Response()
        rotate.status_code = 222
        rotate._content = base64.b64encode(new_key)

        class FakeHttp:
            def __init__(self):
                self.responses = iter((rotate, success))
                self.calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                return next(self.responses)

        http = FakeHttp()
        self.transport.http = http
        result = self.transport.post("/test", {"value": 1})
        self.assertEqual(result, {"code": 200, "data": {}})
        self.assertEqual(http.calls, 2)
        self.assertEqual(self.transport.rsa_key_path.read_bytes(), new_key)


if __name__ == "__main__":
    unittest.main()
