from __future__ import annotations

import base64
import json
import os
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import ProtocolError


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    compact = "".join(value.split())
    return base64.b64decode(compact + "=" * (-len(compact) % 4), validate=False)


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _public_key_der(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _load_certificate(value: str) -> x509.Certificate:
    encoded = value.encode("ascii")
    if "-----BEGIN CERTIFICATE-----" in value:
        return x509.load_pem_x509_certificate(encoded)
    return x509.load_der_x509_certificate(_b64decode(value))


@dataclass
class LkSession:
    aes_key: bytes
    temporary_public_key_der: bytes
    cert_version: int
    ttl_seconds: int = 86400

    @classmethod
    def establish(
        cls,
        http: requests.Session,
        host: str,
        timeout: float = 30,
        biz: str = "lk",
    ) -> "LkSession":
        response = http.post(
            f"https://{host}/crypto/cert/upgrade",
            json={"biz": biz},
            timeout=timeout,
        )
        response.raise_for_status()
        result = _json_object(response)
        if result.get("code") != 200 or not isinstance(result.get("data"), dict):
            raise ProtocolError(f"cert upgrade failed: {result.get('code')} {result.get('message', '')}")
        data = result["data"]
        try:
            certificate = _load_certificate(data["cert4Encrypt"])
            server_public_key = certificate.public_key()
            cert_version = int(data["version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolError("cert upgrade response has invalid certificate data") from exc
        if not isinstance(server_public_key, ec.EllipticCurvePublicKey):
            raise ProtocolError("lk encryption certificate does not contain an EC public key")
        if not isinstance(server_public_key.curve, ec.SECP256R1):
            raise ProtocolError("lk encryption certificate does not use P-256")

        private_key = ec.generate_private_key(ec.SECP256R1())
        shared_secret = private_key.exchange(ec.ECDH(), server_public_key)
        aes_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"\x00" * 32,
            info=b"",
        ).derive(shared_secret)
        return cls(aes_key, _public_key_der(private_key.public_key()), cert_version)

    def encrypt(self, plaintext: str) -> str:
        iv = os.urandom(12)
        ciphertext = AESGCM(self.aes_key).encrypt(iv, plaintext.encode("utf-8"), None)
        return _compact_json({"cipher": _b64encode(ciphertext), "iv": _b64encode(iv)})

    def decrypt(self, envelope: str) -> str:
        try:
            value = json.loads(envelope)
            ciphertext = _b64decode(value["cipher"])
            iv = _b64decode(value["iv"])
            plaintext = AESGCM(self.aes_key).decrypt(iv, ciphertext, None)
            return plaintext.decode("utf-8")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProtocolError("invalid lk encrypted envelope") from exc

    def cipher_header(self, now_ms: int | None = None) -> str:
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        expiry_ms = now_ms + self.ttl_seconds * 1000
        version = expiry_ms * 10000 + random.SystemRandom().randrange(10000)
        return _compact_json(
            {
                "lk": {
                    "tmpPublicKey": _b64encode(self.temporary_public_key_der),
                    "version": version,
                    "certVersion": self.cert_version,
                }
            }
        )

    @staticmethod
    def register_keys(
        http: requests.Session,
        host: str,
        device_id: str,
        timeout: float = 30,
        biz: str = "lk",
    ) -> dict[str, Any]:
        encryption_key = ec.generate_private_key(ec.SECP256R1())
        signing_key = ec.generate_private_key(ec.SECP256R1())
        response = http.post(
            f"https://{host}/crypto/cert/register",
            json={
                "deviceId": device_id,
                "biz": biz,
                "authType": 2,
                "authMsg": str(uuid.uuid4()),
                "expireTime": 0,
                "publicKey4Encrypt": _b64encode(_public_key_der(encryption_key.public_key())),
                "publicKey4Sign": _b64encode(_public_key_der(signing_key.public_key())),
            },
            timeout=timeout,
        )
        response.raise_for_status()
        result = _json_object(response)
        if result.get("code") != 200:
            raise ProtocolError(f"cert registration failed: {result.get('code')} {result.get('message', '')}")
        return result


def _json_object(response: requests.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except requests.JSONDecodeError as exc:
        raise ProtocolError(f"server returned non-JSON response (HTTP {response.status_code})") from exc
    if not isinstance(value, dict):
        raise ProtocolError("server JSON response is not an object")
    return value
