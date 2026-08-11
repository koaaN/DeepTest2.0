from __future__ import annotations

import json
import os
import time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .private_file import atomic_write_private


class UnlockCodeVault:
    """Secure local storage for device-specific unlock codes.
    
    Uses AES-GCM (256-bit) to encrypt the vault file.
    The key is stored in a private vault.key file with 0600 permissions.
    """

    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory else Path.home() / ".config" / "deeptesting"
        self.key_path = self.directory / "vault.key"
        self.vault_path = self.directory / "unlock-vault.enc"
        self._key: bytes | None = None

    def _get_key(self) -> bytes:
        if self._key is not None:
            return self._key
        try:
            self._key = self.key_path.read_bytes()
            if len(self._key) != 32:
                raise ValueError("invalid key length")
        except (FileNotFoundError, OSError, ValueError):
            self._key = AESGCM.generate_key(bit_length=256)
            atomic_write_private(self.key_path, self._key, prefix=".vaultkey-")
        return self._key

    def _read_vault(self) -> dict[str, dict[str, str]]:
        if not self.vault_path.is_file():
            return {}
        try:
            raw = self.vault_path.read_bytes()
            if not raw:
                return {}
            if len(raw) < 28:  # 12 bytes IV + 16 bytes tag/minimum ciphertext
                return {}
            
            aesgcm = AESGCM(self._get_key())
            iv = raw[:12]
            ciphertext = raw[12:]
            plaintext = aesgcm.decrypt(iv, ciphertext, None)
            data = json.loads(plaintext.decode("utf-8"))
            if isinstance(data, dict):
                # Ensure structure integrity
                return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            # If corrupted, unreadable, or wrong key, fallback to empty
            pass
        return {}

    def _write_vault(self, data: dict[str, dict[str, str]]) -> None:
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        iv = os.urandom(12)
        aesgcm = AESGCM(self._get_key())
        ciphertext = aesgcm.encrypt(iv, plaintext, None)
        payload = iv + ciphertext
        atomic_write_private(self.vault_path, payload, prefix=".vault-")

    def save(self, serial: str, chip_id: str, code: str) -> None:
        """Save/update the unlock code for a specific device serial and chip ID."""
        if not serial:
            raise ValueError("Device serial cannot be empty")
        data = self._read_vault()
        data[serial] = {
            "chip_id": chip_id.lower().strip(),
            "code": code.strip(),
            "timestamp": str(int(time.time())),
        }
        self._write_vault(data)

    def load_by_serial(self, serial: str) -> str | None:
        """Retrieve the unlock code for a given device serial number."""
        if not serial:
            return None
        data = self._read_vault()
        record = data.get(serial)
        return record.get("code") if record else None

    def load_by_chip_id(self, chip_id: str) -> str | None:
        """Retrieve the unlock code for a given hardware chip ID."""
        if not chip_id:
            return None
        normalized = chip_id.lower().strip()
        data = self._read_vault()
        for record in data.values():
            if record.get("chip_id") == normalized:
                return record.get("code")
        return None

    def all_records(self) -> dict[str, dict[str, str]]:
        """Return a copy of all vault records."""
        return self._read_vault()

    def export_plaintext(self, dest_path: str | Path) -> None:
        """Export the decrypted vault as a plaintext JSON file."""
        data = self._read_vault()
        path = Path(dest_path)
        payload = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        atomic_write_private(path, payload, prefix=".export-")

    def import_plaintext(self, src_path: str | Path) -> None:
        """Import from a plaintext JSON file, merging with existing records."""
        path = Path(src_path)
        try:
            imported = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read import file: {exc}")
        
        if not isinstance(imported, dict):
            raise ValueError("Import file must be a JSON object")

        data = self._read_vault()
        for key, value in imported.items():
            if isinstance(value, dict) and "code" in value:
                data[str(key)] = {
                    "chip_id": str(value.get("chip_id", "")).lower().strip(),
                    "code": str(value["code"]).strip(),
                    "timestamp": str(value.get("timestamp", int(time.time()))),
                }
        self._write_vault(data)
