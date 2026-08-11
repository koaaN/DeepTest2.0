import os
import tempfile
import unittest
from pathlib import Path

from deeptesting.vault import UnlockCodeVault


class UnlockCodeVaultTests(unittest.TestCase):
    def test_key_generation_and_persistence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault1 = UnlockCodeVault(temp_dir)
            key1 = vault1._get_key()
            self.assertEqual(len(key1), 32)
            self.assertTrue(vault1.key_path.is_file())

            # Reloading with the same directory should yield the same key
            vault2 = UnlockCodeVault(temp_dir)
            key2 = vault2._get_key()
            self.assertEqual(key1, key2)

    def test_save_and_load_by_serial_and_chip_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = UnlockCodeVault(temp_dir)
            
            # Initially empty
            self.assertIsNone(vault.load_by_serial("SERIAL123"))
            self.assertIsNone(vault.load_by_chip_id("CHIP456"))

            # Save a code
            vault.save("SERIAL123", "CHIP456", "UNLOCKCODE_XYZ_632CHARS")
            
            # Load by serial
            self.assertEqual(vault.load_by_serial("SERIAL123"), "UNLOCKCODE_XYZ_632CHARS")
            # Load by chip ID (case insensitive / normalized)
            self.assertEqual(vault.load_by_chip_id("chip456"), "UNLOCKCODE_XYZ_632CHARS")
            self.assertEqual(vault.load_by_chip_id("  CHIP456  "), "UNLOCKCODE_XYZ_632CHARS")
            
            # Non-existent
            self.assertIsNone(vault.load_by_serial("SERIAL_NOT_FOUND"))
            self.assertIsNone(vault.load_by_chip_id("CHIP_NOT_FOUND"))

    def test_vault_encryption(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = UnlockCodeVault(temp_dir)
            vault.save("SERIAL1", "CHIP1", "MY_SECRET_CODE")

            self.assertTrue(vault.vault_path.is_file())
            encrypted_bytes = vault.vault_path.read_bytes()
            
            # Ensure plaintext code is not visible in the raw file
            self.assertNotIn(b"MY_SECRET_CODE", encrypted_bytes)
            self.assertNotIn(b"SERIAL1", encrypted_bytes)

    def test_export_and_import_plaintext(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = UnlockCodeVault(temp_dir)
            vault.save("SERIAL1", "CHIP1", "CODE1")
            vault.save("SERIAL2", "CHIP2", "CODE2")

            export_file = Path(temp_dir) / "backup.json"
            vault.export_plaintext(export_file)

            self.assertTrue(export_file.is_file())
            # Plaintext backup should be readable json
            import json
            backup_data = json.loads(export_file.read_text(encoding="utf-8"))
            self.assertEqual(backup_data["SERIAL1"]["code"], "CODE1")
            self.assertEqual(backup_data["SERIAL2"]["code"], "CODE2")

            # Create a new empty vault and import the backup
            new_vault_dir = Path(temp_dir) / "new_vault"
            new_vault_dir.mkdir()
            new_vault = UnlockCodeVault(new_vault_dir)
            
            self.assertIsNone(new_vault.load_by_serial("SERIAL1"))
            new_vault.import_plaintext(export_file)
            
            self.assertEqual(new_vault.load_by_serial("SERIAL1"), "CODE1")
            self.assertEqual(new_vault.load_by_serial("SERIAL2"), "CODE2")
            self.assertEqual(new_vault.load_by_chip_id("chip1"), "CODE1")


if __name__ == "__main__":
    unittest.main()
