from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deeptesting.unlock_helper import (
    DeviceReadiness,
    UnlockHelperError,
    _cleanup_temporary_root,
    helper_jar_path,
    inspect_device,
    unlock_code_chip_id,
    validate_unlock_code,
)


class UnlockCodeValidationTests(unittest.TestCase):
    def test_accepts_and_trims_hex(self) -> None:
        self.assertEqual(validate_unlock_code("  04aB  "), "04aB")

    def test_extracts_embedded_chip_id(self) -> None:
        code = ("00" * 256) + "a1b2c3d4".encode("ascii").hex() + ("00" * 52)
        self.assertEqual(len(code), 632)
        self.assertEqual(unlock_code_chip_id(code), "a1b2c3d4")

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
    def test_zero_pads_short_chip_id_to_unlock_code_width(self, run, _adb) -> None:
        run.side_effect = [
            type("Result", (), {
                "stdout": "List of devices attached\nABC device product:x model:PLK110\n",
                "stderr": "",
                "returncode": 0,
            })(),
            type("Result", (), {"stdout": "uid=0(root)\n", "stderr": "", "returncode": 0})(),
            type("Result", (), {"stdout": "0xabc1234\n", "stderr": "", "returncode": 0})(),
        ]

        self.assertEqual(inspect_device().chip_id, "0abc1234")

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
            type("Result", (), {"stdout": "0xa1b2c3d4\n", "stderr": "", "returncode": 0})(),
        ]
        self.assertEqual(
            inspect_device(),
            DeviceReadiness(serial="ABC", model="PLK110", rooted=True, chip_id="a1b2c3d4"),
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


class TemporaryRootCleanupTests(unittest.TestCase):
    @patch("deeptesting.unlock_helper._run")
    def test_cleanup_uses_root_and_removes_su_last(self, run) -> None:
        run.side_effect = [
            type("Result", (), {"returncode": 0})(),
            type("Result", (), {"returncode": 0})(),
        ]

        self.assertTrue(_cleanup_temporary_root("adb", "TEST-DEVICE"))

        cleanup_command = run.call_args_list[0].args[0][-1]
        self.assertTrue(cleanup_command.startswith("/data/local/tmp/su -c '"))
        self.assertIn("/data/local/tmp/preload.so", cleanup_command)
        self.assertIn("/data/local/tmp/oplusreserve1.img", cleanup_command)
        self.assertTrue(cleanup_command.endswith("&& rm -f /data/local/tmp/su'"))
        final_su_removal = cleanup_command.index("&& rm -f /data/local/tmp/su")
        self.assertLess(cleanup_command.index("/data/local/tmp/preload.so"), final_su_removal)
        self.assertLess(cleanup_command.index("/data/local/tmp/oplusreserve1.img"), final_su_removal)

        verify_command = run.call_args_list[1].args[0][-1]
        self.assertIn("test ! -e /data/local/tmp/su", verify_command)

    @patch("deeptesting.unlock_helper._run")
    def test_failed_root_cleanup_is_not_reported_as_complete(self, run) -> None:
        run.return_value = type("Result", (), {"returncode": 1})()

        self.assertFalse(_cleanup_temporary_root("adb", "TEST-DEVICE"))
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
