from __future__ import annotations

import subprocess
import sys
from pathlib import Path


WEBVIEW2_CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def _webview2_installed() -> bool:
    if sys.platform != "win32":
        return True

    import winreg

    registry_paths = (
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}",
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}",
    )
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for path in registry_paths:
            try:
                with winreg.OpenKey(hive, path) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
                major_version = int(str(version).split(".", 1)[0])
                if major_version >= 86:
                    return True
            except (OSError, TypeError, ValueError):
                continue
    return False


def ensure_webview2_runtime() -> tuple[bool, str]:
    """Install the bundled WebView2 runtime when Windows does not have it."""
    if sys.platform != "win32" or _webview2_installed():
        return True, ""

    installer = _bundle_root() / "webview2-runtime" / WEBVIEW2_INSTALLER
    if not installer.is_file():
        return False, "The bundled Microsoft Edge WebView2 installer is missing."

    try:
        result = subprocess.run(
            [str(installer), "/silent", "/install"],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"The bundled WebView2 installer could not run: {exc}"

    if result.returncode not in (0, 3010):
        detail = (result.stderr or result.stdout).strip()
        message = f"WebView2 installation failed with code {result.returncode}."
        return False, message + (f"\n\n{detail}" if detail else "")
    if not _webview2_installed():
        return False, "WebView2 installation finished, but Windows did not register the runtime."
    return True, ""
