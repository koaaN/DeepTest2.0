from types import SimpleNamespace
from unittest import TestCase, mock

from deeptesting.web_gui import Api, DEVICE_PROFILES


class DeviceProfileTests(TestCase):
    def test_disconnected_device_has_empty_chip_id(self) -> None:
        with mock.patch.object(Api, "_save"):
            api = Api()

        self.assertEqual(api.get_state()["device"]["chip_id"], "")

    def test_oneplus_15t_profile(self) -> None:
        self.assertEqual(
            DEVICE_PROFILES["25821"],
            {
                "name": "OnePlus 15T",
                "model": "PLZ110",
                "ota_version": "PLZ110_11.A.31_0310_202605280615",
                "root_family": "15T",
            },
        )


class CommandOutputTests(TestCase):
    @mock.patch("deeptesting.web_gui.subprocess.run")
    def test_sensitive_command_values_follow_visibility_setting(self, run) -> None:
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(Api, "_save"):
            api = Api()
        api.settings["udid"] = "device-guid"
        api.settings["chip_id"] = "0x12345678"

        api._command(
            "deeptesting.cli",
            ["get-apply-status", "--udid", "device-guid", "--chip-id", "0x12345678"],
        )

        self.assertIn("--udid device-guid", api.get_state()["log"])
        self.assertIn("--chip-id 0x12345678", api.get_state()["log"])
        hidden = api.set_sensitive_values(False)["log"]
        self.assertNotIn("device-guid", hidden)
        self.assertNotIn("0x12345678", hidden)
        self.assertIn("--udid ••••", hidden)
        self.assertIn("--chip-id ••••", hidden)
        shown = api.set_sensitive_values(True)["log"]
        self.assertIn("--udid device-guid", shown)
        self.assertIn("--chip-id 0x12345678", shown)

    @mock.patch("deeptesting.web_gui.subprocess.run")
    def test_missing_windows_output_stream_is_treated_as_empty(self, run) -> None:
        run.return_value = SimpleNamespace(returncode=0, stdout=None, stderr="")
        with mock.patch.object(Api, "_save"):
            api = Api()

        self.assertEqual(api._command("deeptesting.cli", ["get-apply-status"]), "")

    @mock.patch("deeptesting.cli.main")
    def test_frozen_app_runs_cli_in_process_and_captures_output(self, main) -> None:
        main.side_effect = lambda: print("captured response") or 0
        with mock.patch.object(Api, "_save"), mock.patch(
            "deeptesting.web_gui.sys.frozen", True, create=True
        ):
            api = Api()
            output = api._command("deeptesting.cli", ["get-apply-status"])

        self.assertEqual(output, "captured response")
