from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deeptesting.unlock_helper import (
    DeviceReadiness,
    UnlockHelperError,
    helper_jar_path,
    inspect_device,
    validate_unlock_code,
)


class UnlockCodeValidationTests(unittest.TestCase):
    def test_accepts_and_trims_hex(self) -> None:
        self.assertEqual(validate_unlock_code("  04aB  "), "04aB")

    def test_rejects_empty_odd_or_non_hex_values(self) -> None:
        for value in ("", "abc", "zz"):
            with self.subTest(value=value), self.assertRaises(UnlockHelperError):
                validate_unlock_code(value)

    def test_packaged_helper_exists(self) -> None:
        helper = helper_jar_path()
        self.assertIsInstance(helper, Path)
        self.assertGreater(helper.stat().st_size, 0)
        with zipfile.ZipFile(helper) as archive:
            self.assertIn("classes.dex", archive.namelist())


class DeviceReadinessTests(unittest.TestCase):
    @patch("deeptesting.unlock_helper._adb_path", return_value="/usr/bin/adb")
    @patch("deeptesting.unlock_helper._run")
    def test_detects_one_rooted_device(self, run, _adb) -> None:
        run.side_effect = [
            type("Result", (), {
                "stdout": "List of devices attached\nABC device product:x model:PLK110\n",
                "stderr": "",
                "returncode": 0,
            })(),
            type("Result", (), {"stdout": "uid=0(root)\n", "stderr": "", "returncode": 0})(),
        ]
        self.assertEqual(
            inspect_device(),
            DeviceReadiness(serial="ABC", model="PLK110", rooted=True),
        )

    @patch("deeptesting.unlock_helper._adb_path", return_value="/usr/bin/adb")
    @patch("deeptesting.unlock_helper._run")
    def test_rejects_multiple_devices(self, run, _adb) -> None:
        run.return_value = type("Result", (), {
            "stdout": "List of devices attached\nA device\nB device\n",
            "stderr": "",
            "returncode": 0,
        })()
        with self.assertRaisesRegex(UnlockHelperError, "More than one"):
            inspect_device()


if __name__ == "__main__":
    unittest.main()
