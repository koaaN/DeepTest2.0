from types import SimpleNamespace
from unittest import TestCase, mock

from deeptesting.web_gui import Api


class CommandOutputTests(TestCase):
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
