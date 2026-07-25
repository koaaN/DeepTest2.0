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
