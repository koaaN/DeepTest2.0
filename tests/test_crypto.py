import json
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone

from deeptesting.crypto import LkSession, _load_certificate


class LkSessionTests(unittest.TestCase):
    def test_loads_pem_certificate_returned_by_upgrade_endpoint(self):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
        loaded = _load_certificate(pem)
        self.assertEqual(loaded.serial_number, 1)

    def test_envelope_round_trip(self):
        session = LkSession(b"a" * 32, b"public", 123)
        encrypted = session.encrypt('{"hello":"world"}')
        self.assertEqual(session.decrypt(encrypted), '{"hello":"world"}')
        inner = json.loads(encrypted)
        self.assertEqual(len(inner["iv"]), 16)

    def test_header_version_contains_expiry_and_random_suffix(self):
        session = LkSession(b"a" * 32, b"public", 123)
        header = json.loads(session.cipher_header(now_ms=1000))["lk"]
        expected_expiry = 1000 + 86400 * 1000
        self.assertEqual(header["version"] // 10000, expected_expiry)
        self.assertEqual(header["certVersion"], 123)


if __name__ == "__main__":
    unittest.main()
