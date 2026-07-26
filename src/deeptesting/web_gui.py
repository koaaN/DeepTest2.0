from __future__ import annotations

import json
import io
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import webview

from .unlock_helper import (
    UnlockHelperError,
    apply_authorization,
    inspect_device,
    unlock_code_chip_id,
    validate_unlock_code,
)


APP_DIR = Path.home() / ".config" / "deeptesting"
SETTINGS_PATH = APP_DIR / "gui-settings.json"
TOKEN_PATH = APP_DIR / "auth.json"
DEFAULTS = {
    "account_type": "Email", "account": "", "calling_code": "+46",
    "verification_code": "", "model": "PLK110", "udid": "",
    "ota_version": "PLK110_11.A.68_0680_202606250030", "brand": "OnePlus",
    "operator": "", "chip_id": "", "os_version": "16",
    "app_version": "17000003", "lock_status": "0",
    "api_host": "lk-oneplus-cn.allawntech.com", "register_keys": False,
    "token_cache": str(TOKEN_PATH),
}

DEVICE_PROFILES = {
    "24831": {
        "name": "OnePlus 15",
        "model": "PLK110",
        "ota_version": "PLK110_11.A.68_0680_202606250030",
        "root_family": "OP15",
    },
    "24855": {
        "name": "OnePlus Ace 6T",
        "model": "PLR110",
        "ota_version": "PLR110_11.A.62_0620_202606152334",
        "root_family": "ACE6T",
    },
    "25821": {
        "name": "OnePlus 15T",
        "model": "PLZ110",
        "ota_version": "PLZ110_11.A.31_0310_202605280615",
        "root_family": "15T",
    },
}


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def _adb_path() -> str:
    name = "adb.exe" if os.name == "nt" else "adb"
    candidates = [
        _bundle_root() / "platform-tools" / name,
        Path.cwd() / "platform-tools" / name,
    ]
    located = shutil.which("adb") or shutil.which("adb.exe")
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("ADB is not installed or available in the bundled Platform Tools.")


class Api:
    def __init__(self) -> None:
        self.settings = dict(DEFAULTS)
        self.unlock_code = ""
        self.log = "DeepTest 2.0 ready.\n"
        self.device = {
            "connected": False, "name": "No device connected", "model": "",
            "serial": "", "prjid": "", "rooted": False,
        }
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                self.settings.update({
                    key: saved[key] for key in self.settings.keys() & saved.keys()
                })
        except (OSError, json.JSONDecodeError):
            pass
        if not str(self.settings["udid"]).strip():
            self.settings["udid"] = uuid.uuid4().hex
        self._save()

    def _save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    def _versions(self) -> list[str]:
        profile = DEVICE_PROFILES.get(str(self.device["prjid"]))
        family = profile["root_family"] if profile else None
        root = _bundle_root() / "android-helper" / "assets" / str(family)
        if not family or not root.is_dir():
            return []
        return sorted(item.name for item in root.iterdir() if item.is_dir())

    def get_state(self) -> dict:
        return {
            "settings": self.settings, "device": self.device,
            "authorized": Path(str(self.settings["token_cache"])).expanduser().is_file(),
            "versions": self._versions(), "has_code": bool(self.unlock_code),
            "log": self.log,
        }

    def save_settings(self, values: dict) -> dict:
        if isinstance(values, dict):
            for key in self.settings:
                if key in values:
                    self.settings[key] = values[key]
            self._save()
        return self.get_state()

    def _result(self, message: str, *, output: str = "") -> dict:
        if output:
            self.log += self._redact(output).rstrip() + "\n"
        return {"ok": True, "message": message, "output": output, "state": self.get_state()}

    def _error(self, exc: Exception) -> dict:
        message = self._redact(str(exc))
        self.log += f"error: {message}\n"
        return {"ok": False, "message": message, "state": self.get_state()}

    def _command(self, module: str, args: list[str]) -> str:
        display_args = list(args)
        sensitive_options = {
            "--udid", "--chip-id", "--phone", "--email", "--guid",
            "--device-id", "--ticket",
        }
        for index, item in enumerate(display_args[:-1]):
            if item in sensitive_options:
                display_args[index + 1] = "••••"
        if "verify" in display_args:
            verify_index = display_args.index("verify")
            if verify_index + 1 < len(display_args):
                display_args[verify_index + 1] = "••••"
        display = "$ -m " + module + " " + " ".join(display_args)
        self.log += display + "\n"
        if getattr(sys, "frozen", False):
            returncode, stdout, stderr = self._run_embedded(module, args)
        else:
            command = [sys.executable, "-m", module, *args]
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(command, capture_output=True, text=True, env=env)
            returncode = result.returncode
            stdout = result.stdout or ""
            stderr = result.stderr or ""
        output = (stdout + stderr).strip()
        if returncode not in (0, 3):
            raise RuntimeError(output or "The operation failed.")
        return output

    @staticmethod
    def _run_embedded(module: str, args: list[str]) -> tuple[int, str, str]:
        """Run a CLI inside a frozen windowed app where stdio is unavailable."""
        if module == "deeptesting.cli":
            from .cli import main as command_main
        elif module == "deeptesting.token_cli":
            from .token_cli import main as command_main
        else:
            raise RuntimeError(f"Unsupported embedded command module: {module}")

        stdout = io.StringIO()
        stderr = io.StringIO()
        previous_argv = sys.argv
        sys.argv = [module, *args]
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    returncode = command_main()
                except SystemExit as exc:
                    returncode = exc.code if isinstance(exc.code, int) else 1
        finally:
            sys.argv = previous_argv
        return int(returncode or 0), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _redact(value: str) -> str:
        return value

    def refresh_device(self) -> dict:
        try:
            adb = _adb_path()
            result = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=15)
            rows = []
            for line in result.stdout.splitlines()[1:]:
                columns = line.split()
                if len(columns) >= 2 and columns[1] == "device":
                    rows.append(columns)
            if len(rows) != 1:
                self.device = {
                    "connected": False, "name": "No device connected", "model": "",
                    "serial": "", "prjid": "", "rooted": False,
                }
                return self._result("No single authorized ADB device found.")
            row = rows[0]
            serial = row[0]
            model = next((item.split(":", 1)[1] for item in row if item.startswith("model:")), "Android device")

            def prop(name: str) -> str:
                reply = subprocess.run(
                    [adb, "-s", serial, "shell", "getprop", name],
                    capture_output=True, text=True, timeout=10,
                )
                return reply.stdout.strip()

            raw_prjid = prop("ro.boot.prjname") or prop("ro.boot.prjid") or prop("ro.product.prjname")
            match = re.search(r"\d{5}", raw_prjid)
            prjid = match.group(0) if match else ""
            chip = prop("ro.boot.chipid")
            root = subprocess.run(
                [adb, "-s", serial, "shell", "/data/local/tmp/su -c 'id'"],
                capture_output=True, text=True, timeout=10,
            )
            profile = DEVICE_PROFILES.get(prjid)
            name = profile["name"] if profile else model
            if profile:
                self.settings["model"] = profile["model"]
                self.settings["ota_version"] = profile["ota_version"]
            if chip:
                self.settings["chip_id"] = chip if chip.lower().startswith("0x") else f"0x{chip}"
            self.device = {
                "connected": True, "name": name, "model": model, "serial": serial,
                "prjid": prjid or "unknown",
                "rooted": root.returncode == 0 and "uid=0" in root.stdout,
            }
            self._save()
            return self._result(f"Connected to {name}.")
        except Exception as exc:
            return self._error(exc)

    def _token_args(self) -> list[str]:
        return ["--token-cache", str(Path(str(self.settings["token_cache"])).expanduser())]

    def _profile_args(self) -> list[str]:
        s = self.settings
        args = [
            "--token-cache", str(Path(str(s["token_cache"])).expanduser()),
            "--udid", str(s["udid"]), "--model", str(s["model"]),
            "--ota-version", str(s["ota_version"]), "--brand", str(s["brand"]),
            "--operator", str(s["operator"]), "--chip-id", str(s["chip_id"]),
            "--os-version", str(s["os_version"]), "--app-version", str(s["app_version"]),
            "--client-lock-status", str(s["lock_status"]), "--host", str(s["api_host"]),
        ]
        if s.get("register_keys"):
            args.append("--register-keys")
        return args

    def send_code(self) -> dict:
        try:
            s = self.settings
            account = str(s["account"]).strip()
            if not account:
                raise RuntimeError("Enter an email address or phone number.")
            option = "--phone" if s["account_type"] == "Phone" else "--email"
            args = self._token_args() + ["login", option, account]
            if option == "--phone":
                args += ["--country-calling-code", str(s["calling_code"])]
            args += ["--model", str(s["model"]), "--guid", str(s["udid"])]
            return self._result("Verification code sent.", output=self._command("deeptesting.token_cli", args))
        except Exception as exc:
            return self._error(exc)

    def verify_code(self) -> dict:
        try:
            code = str(self.settings["verification_code"]).strip()
            if not code:
                raise RuntimeError("Enter the verification code.")
            args = self._token_args() + [
                "verify", code, "--model", str(self.settings["model"]),
                "--guid", str(self.settings["udid"]),
            ]
            return self._result("Account authorized.", output=self._command("deeptesting.token_cli", args))
        except Exception as exc:
            return self._error(exc)

    def device_action(self, endpoint: str) -> dict:
        try:
            output = self._command("deeptesting.cli", [endpoint, *self._profile_args()])
            code_received = False
            start = output.find("{")
            if start >= 0:
                payload = json.loads(output[start:])
                data = payload.get("data")
                if isinstance(data, str):
                    code = data
                elif isinstance(data, dict):
                    code = data.get("unlockCode")
                else:
                    code = None
                if isinstance(code, str) and code:
                    # Server-side application actions must remain usable without
                    # ADB. Validate the payload structure here and defer matching
                    # its embedded Chip ID to the live phone until readiness.
                    code = validate_unlock_code(code.strip())
                    unlock_code_chip_id(code)
                    self.unlock_code = code
                    code_received = True
            result = self._result(
                "Unlock code received. Connect the phone and run Check requirements to validate it."
                if code_received else "Request complete.",
                output=output,
            )
            result["code_received"] = code_received
            return result
        except Exception as exc:
            return self._error(exc)

    def _validate_code(self, value: str) -> None:
        code = validate_unlock_code(value.strip())
        if len(code) != 632:
            raise UnlockHelperError("The unlock code must contain exactly 632 hexadecimal characters.")
        embedded = unlock_code_chip_id(code)
        device = inspect_device()
        if not device.chip_id:
            raise UnlockHelperError("Could not read the connected phone Chip ID.")
        if embedded != device.chip_id:
            raise UnlockHelperError("The unlock code belongs to a different connected phone.")
        self.unlock_code = code

    def load_unlock_code(self, value: str) -> dict:
        try:
            self._validate_code(value)
            return self._result("Unlock code ready & validated.")
        except Exception as exc:
            return self._error(exc)

    def run_root_helper(self, version: str) -> dict:
        try:
            profile = DEVICE_PROFILES.get(str(self.device["prjid"]))
            family = profile["root_family"] if profile else None
            if not family or not version:
                raise RuntimeError("No compatible root helper is available.")
            directory = _bundle_root() / "android-helper" / "assets" / family / version
            script = directory / ("root.bat" if os.name == "nt" else "root.sh")
            if not script.is_file():
                raise RuntimeError(f"Root helper is missing for {version}.")
            env = os.environ.copy()
            if os.name != "nt" and getattr(sys, "frozen", False):
                original = env.pop("LD_LIBRARY_PATH_ORIG", "")
                if original:
                    env["LD_LIBRARY_PATH"] = original
                else:
                    env.pop("LD_LIBRARY_PATH", None)
            command = ["cmd", "/c", str(script)] if os.name == "nt" else ["/bin/sh", str(script)]
            process = subprocess.Popen(
                command, cwd=directory, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=env,
            )
            lines: list[str] = []
            self.log += "$ root helper started…\n"
            if process.stdout is not None:
                for line in process.stdout:
                    lines.append(line)
                    self.log += line
                    try:
                        webview.windows[0].evaluate_js(
                            f"appendRootLog({json.dumps(line)})"
                        )
                    except Exception:
                        pass
            return_code = process.wait()
            output = "".join(lines).strip()
            if return_code or ("root complete" not in output.lower() and "uid=0(root)" not in output.lower()):
                raise RuntimeError(output or "Root helper did not complete.")
            return self._result("Temporary root helper complete.")
        except Exception as exc:
            return self._error(exc)

    def check_requirements(self) -> dict:
        checks = {"device": False, "root": False, "code": False}
        details: list[str] = []
        try:
            device = inspect_device()
            checks["device"] = True
            checks["root"] = device.rooted
            details.append(f"{device.model} ({device.serial})")
            if self.unlock_code:
                code = validate_unlock_code(self.unlock_code)
                embedded = unlock_code_chip_id(code)
                checks["code"] = bool(device.chip_id and embedded == device.chip_id)
            details.extend((
                "Temporary root ready" if checks["root"] else "Temporary root not available",
                "Unlock code ready & validated" if checks["code"] else "Unlock code not available or not validated",
            ))
            ready = all(checks.values())
            output = "\n".join(details)
            self.log += output + "\n"
            return {
                "ok": ready,
                "message": "All requirements are ready." if ready else "Some requirements are not ready.",
                "checks": checks,
                "state": self.get_state(),
            }
        except Exception as exc:
            self.log += f"Requirements check failed: {exc}\n"
            return {
                "ok": False, "message": str(exc), "checks": checks,
                "state": self.get_state(),
            }

    def apply_authorization(self) -> dict:
        try:
            if not self.unlock_code:
                raise RuntimeError("Load and validate an unlock code first.")
            output = apply_authorization(self.unlock_code)
            return self._result("Authorization installed successfully.", output=output)
        except Exception as exc:
            return self._error(exc)

    def reboot_bootloader(self) -> dict:
        try:
            device = inspect_device()
            result = subprocess.run(
                [_adb_path(), "-s", device.serial, "reboot", "bootloader"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout).strip() or "ADB reboot failed.")
            return self._result("Rebooting to bootloader.")
        except Exception as exc:
            return self._error(exc)


def main() -> int:
    api = Api()
    html = Path(__file__).with_name("web") / "index.html"
    if getattr(sys, "frozen", False):
        html = _bundle_root() / "deeptesting" / "web" / "index.html"
    window = webview.create_window(
        "DeepTest 2.0", url=str(html.resolve()), js_api=api,
        width=1440, height=900, min_size=(1080, 700),
        background_color="#090b10",
    )
    if sys.platform == "darwin":
        gui = "cocoa"
    elif os.name == "nt":
        gui = None
    else:
        gui = "qt"
    webview.start(gui=gui, debug=False)
    return 0
