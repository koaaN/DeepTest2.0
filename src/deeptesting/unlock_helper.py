from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


REMOTE_HELPER = "/data/local/tmp/fastboot-unlock-helper.jar"
REMOTE_RESERVE = "/data/local/tmp/oplusreserve1.img"
REMOTE_PRELOAD = "/data/local/tmp/preload.so"
SU_PATH = "/data/local/tmp/su"
RESERVE_OFFSET = 0x45A000
_HEX = re.compile(r"^[0-9a-fA-F]+$")


class UnlockHelperError(RuntimeError):
    """A safe, user-facing failure while preparing or applying authorization."""


@dataclass(frozen=True)
class DeviceReadiness:
    serial: str
    model: str
    rooted: bool
    chip_id: str = ""


def validate_unlock_code(value: str) -> str:
    code = value.strip()
    if not code or len(code) % 2 or not _HEX.fullmatch(code):
        raise UnlockHelperError("The issued unlock code is not valid even-length hexadecimal data.")
    return code


def unlock_code_chip_id(value: str) -> str:
    code = validate_unlock_code(value)
    if len(code) != 632:
        raise UnlockHelperError("The unlock code must contain exactly 632 hexadecimal characters.")
    try:
        chip_id = bytes.fromhex(code[512:528]).decode("ascii")
    except (UnicodeDecodeError, ValueError) as exc:
        raise UnlockHelperError("The unlock code does not contain a valid embedded Chip ID.") from exc
    if not re.fullmatch(r"[0-9a-fA-F]{8}", chip_id):
        raise UnlockHelperError("The unlock code does not contain a valid embedded Chip ID.")
    return chip_id.lower()


def _normalize_chip_id(value: str) -> str:
    chip_id = value.strip().lower()
    if chip_id.startswith("0x"):
        chip_id = chip_id[2:]
    if re.fullmatch(r"[0-9a-f]{1,8}", chip_id):
        return chip_id.zfill(8)
    return chip_id


def patch_reserve_image(image: Path, unlock_code: str) -> int:
    """Patch a local stock oplusreserve1 dump, returning bytes written."""
    code = bytes.fromhex(validate_unlock_code(unlock_code))
    if not image.is_file():
        raise UnlockHelperError(f"Reserve image does not exist: {image}")
    with image.open("r+b") as handle:
        handle.seek(RESERVE_OFFSET)
        written = handle.write(code)
        handle.flush()
    if written != len(code):
        raise UnlockHelperError("Could not write the complete unlock payload to the reserve image.")
    return written


def helper_jar_path() -> Path:
    resource = files("deeptesting").joinpath("assets", "fastboot-unlock-helper.jar")
    path = Path(str(resource))
    if not path.is_file():
        raise UnlockHelperError("The packaged Android authorization helper is missing.")
    return path


def _adb_path() -> str:
    candidates = []
    bundle_root = Path(getattr(__import__("sys"), "_MEIPASS", Path(__file__).resolve().parents[2]))
    candidates.extend((bundle_root / "platform-tools" / name for name in ("adb", "adb.exe")))
    candidates.extend((Path.cwd() / "platform-tools" / name for name in ("adb", "adb.exe")))
    candidates.extend((Path(item) for item in (shutil.which("adb"), shutil.which("adb.exe")) if item))
    adb = next((str(path) for path in candidates if path.is_file()), None)
    if not adb:
        raise UnlockHelperError("ADB is not installed or is not available in PATH.")
    return adb


def _run(command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise UnlockHelperError("The connected phone did not respond in time.") from exc
    except OSError as exc:
        raise UnlockHelperError(f"Could not run ADB: {exc}") from exc


def inspect_device() -> DeviceReadiness:
    adb = _adb_path()
    devices = _run([adb, "devices", "-l"])
    available: list[tuple[str, str]] = []
    for line in devices.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            model = next(
                (item.split(":", 1)[1] for item in parts[2:] if item.startswith("model:")),
                "Android device",
            )
            available.append((parts[0], model))
    if not available:
        raise UnlockHelperError(
            "No authorized ADB device was found. Enable USB debugging and accept the prompt."
        )
    if len(available) > 1:
        raise UnlockHelperError("More than one ADB device is connected. Leave only the target phone connected.")
    serial, model = available[0]
    root = _run([adb, "-s", serial, "shell", f"{SU_PATH} -c 'id'"])
    rooted = root.returncode == 0 and "uid=0" in root.stdout
    chip = _run([adb, "-s", serial, "shell", "getprop", "ro.boot.chipid"])
    chip_id = _normalize_chip_id(chip.stdout) if chip.returncode == 0 else ""
    return DeviceReadiness(serial=serial, model=model, rooted=rooted, chip_id=chip_id)


def _cleanup_temporary_root(adb: str, serial: str) -> bool:
    # Keep su available until every other temporary file has been removed.
    # Unlinking the running executable is supported on Android/Linux, so su can
    # remove itself as the final operation in the same privileged shell.
    temporary_files = (
        REMOTE_HELPER,
        REMOTE_RESERVE,
        REMOTE_PRELOAD,
        "/data/local/tmp/su_daemon.log",
        "/data/local/tmp/temp_su.sock",
    )
    other_files = " ".join(temporary_files)
    cleanup_command = (
        f"{SU_PATH} -c 'rm -f {other_files} && rm -f {SU_PATH}'"
    )
    cleanup = _run(
        [adb, "-s", serial, "shell", cleanup_command],
        timeout=20,
    )
    if cleanup.returncode != 0:
        return False

    all_files = (*temporary_files, SU_PATH)
    verify_command = " && ".join(f"test ! -e {path}" for path in all_files)
    verified = _run(
        [adb, "-s", serial, "shell", verify_command],
        timeout=20,
    )
    return verified.returncode == 0


def apply_authorization(unlock_code: str) -> str:
    code = validate_unlock_code(unlock_code)
    device = inspect_device()
    embedded_chip_id = unlock_code_chip_id(code)
    if not device.chip_id:
        raise UnlockHelperError("Could not read ro.boot.chipid from the connected phone.")
    if embedded_chip_id != device.chip_id:
        raise UnlockHelperError(
            "The unlock code was issued for a different Chip ID and will not be written."
        )
    if not device.rooted:
        raise UnlockHelperError(
            "Root access is required. Grant the ADB shell root permission in your root manager."
        )

    adb = _adb_path()
    # Work from a fresh device dump and preserve it locally before patching.
    backup_dir = Path.home() / ".local" / "share" / "deeptest" / "reserve-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    local_backup = backup_dir / f"oplusreserve1-preunlock-{device.serial}.img"
    dump_cmd = f"{SU_PATH} -c 'dd if=/dev/block/by-name/oplusreserve1 of={REMOTE_RESERVE} && chmod 0644 {REMOTE_RESERVE}'"
    dump = _run([adb, "-s", device.serial, "shell", dump_cmd], timeout=90)
    if dump.returncode != 0:
        detail = (dump.stderr or dump.stdout).strip()
        raise UnlockHelperError("Could not dump oplusreserve1 from the phone." + (f" {detail}" if detail else ""))
    pulled = _run([adb, "-s", device.serial, "pull", REMOTE_RESERVE, str(local_backup)], timeout=90)
    if pulled.returncode != 0:
        detail = (pulled.stderr or pulled.stdout).strip()
        raise UnlockHelperError("Could not save the stock oplusreserve1 backup." + (f" {detail}" if detail else ""))
    patched = local_backup.with_name(local_backup.stem + "-patched.img")
    shutil.copy2(local_backup, patched)
    patch_reserve_image(patched, code)
    pushed = _run([adb, "-s", device.serial, "push", str(patched), REMOTE_RESERVE], timeout=90)
    if pushed.returncode != 0:
        detail = (pushed.stderr or pushed.stdout).strip()
        raise UnlockHelperError(f"Could not copy the helper to the phone: {detail}")

    write_cmd = f"{SU_PATH} -c 'dd if={REMOTE_RESERVE} of=/dev/block/by-name/oplusreserve1 conv=fsync'"
    written = _run([adb, "-s", device.serial, "shell", write_cmd], timeout=90)
    if written.returncode != 0:
        raise UnlockHelperError("The patched reserve image could not be written to the phone.")

    cleanup_complete = _cleanup_temporary_root(adb, device.serial)
    cleanup_status = (
        "Temporary root cleanup: complete."
        if cleanup_complete
        else "Temporary root cleanup: incomplete; reboot the phone before continuing."
    )
    return (
        f"Patched and flashed oplusreserve1 "
        f"({len(bytes.fromhex(code))} bytes at 0x{RESERVE_OFFSET:X}). "
        f"Backup: {local_backup}\n{cleanup_status}"
    )
