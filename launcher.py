import sys


def _is_blocked_python_runtime_error(exc: BaseException) -> bool:
    message = str(exc)
    return (
        "Python.Runtime.Loader.Initialize" in message
        or "Python.Runtime.dll" in message
    )


def _show_windows_unblock_message() -> None:
    message = (
        "DeepTest 2.0 could not load its Windows interface because files from "
        "the downloaded ZIP are blocked by Windows.\n\n"
        "Download the latest one-file Windows build, or open PowerShell in the "
        "extracted DeepTest2 folder and run:\n\n"
        "Get-ChildItem -Recurse -File -Force | Unblock-File\n\n"
        "Then start DeepTest2.exe again."
    )
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "DeepTest 2.0 could not start",
            0x10,
        )
    except Exception:
        pass


def _show_windows_runtime_message(detail: str) -> None:
    message = (
        "DeepTest 2.0 requires Microsoft Edge WebView2 to display its interface.\n\n"
        f"{detail}\n\n"
        "Try starting DeepTest as administrator, or install Microsoft Edge "
        "WebView2 Runtime manually and start DeepTest again."
    )
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "DeepTest 2.0 requires WebView2",
            0x10,
        )
    except Exception:
        pass


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] in {"deeptesting.cli", "deeptesting.token_cli"}:
    if sys.argv[2] == "deeptesting.token_cli":
        from deeptesting.token_cli import main
    else:
        from deeptesting.cli import main
    sys.argv = [sys.argv[2], *sys.argv[3:]]
else:
    if sys.platform == "win32":
        from deeptesting.windows_runtime import ensure_webview2_runtime

        _runtime_ready, _runtime_error = ensure_webview2_runtime()
        if not _runtime_ready:
            _show_windows_runtime_message(_runtime_error)
            raise SystemExit(1)
    try:
        from deeptesting.web_gui import main
    except RuntimeError as exc:
        if sys.platform == "win32" and _is_blocked_python_runtime_error(exc):
            _show_windows_unblock_message()
            raise SystemExit(1)
        raise

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        if sys.platform == "win32" and _is_blocked_python_runtime_error(exc):
            _show_windows_unblock_message()
            raise SystemExit(1)
        raise
