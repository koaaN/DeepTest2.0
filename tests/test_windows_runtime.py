from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

from deeptesting.windows_runtime import (
    WEBVIEW2_INSTALLER,
    ensure_webview2_runtime,
)


class WindowsRuntimeTests(TestCase):
    @mock.patch("deeptesting.windows_runtime._webview2_installed", return_value=True)
    def test_existing_runtime_needs_no_installer(self, installed) -> None:
        with mock.patch("deeptesting.windows_runtime.sys.platform", "win32"):
            ready, message = ensure_webview2_runtime()

        self.assertTrue(ready)
        self.assertEqual(message, "")

    @mock.patch("deeptesting.windows_runtime.subprocess.run")
    @mock.patch(
        "deeptesting.windows_runtime._webview2_installed",
        side_effect=[False, True],
    )
    def test_bundled_installer_is_used_when_runtime_is_missing(self, installed, run) -> None:
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            installer = root / "webview2-runtime" / WEBVIEW2_INSTALLER
            installer.parent.mkdir()
            installer.write_bytes(b"installer")
            with mock.patch("deeptesting.windows_runtime.sys.platform", "win32"), mock.patch(
                "deeptesting.windows_runtime._bundle_root", return_value=root
            ):
                ready, message = ensure_webview2_runtime()

        self.assertTrue(ready)
        self.assertEqual(message, "")
        self.assertEqual(run.call_args.args[0][1:], ["/silent", "/install"])
        self.assertEqual(run.call_args.kwargs["timeout"], 600)

    @mock.patch("deeptesting.windows_runtime._webview2_installed", return_value=False)
    def test_missing_bundled_installer_is_reported(self, installed) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch(
                "deeptesting.windows_runtime.sys.platform", "win32"
            ), mock.patch(
                "deeptesting.windows_runtime._bundle_root", return_value=root
            ):
                ready, message = ensure_webview2_runtime()

        self.assertFalse(ready)
        self.assertIn("installer is missing", message)
