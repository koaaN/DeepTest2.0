# DeepTest 2.0

DeepTest 2.0 is a desktop GUI for managing OnePlus/HeyTap DeepTesting authorization workflows. It is designed to replace terminal-heavy commands with a clearer, guided interface.

This project is an independent GUI built on the protocol implementation and research from [mikoker/deeptest](https://github.com/mikoker/deeptest). See the upstream project for protocol background and licensing information.

## What it does

- HeyTap account login and token management
- Device detection through ADB
- Automatic PRJ-ID mapping for OnePlus 15 (`24831`) and OnePlus Ace 6T (`24855`)
- Device profile and OTA-version configuration
- Eligibility, application, status, and unlock-code workflows
- Backup-first `oplusreserve1` authorization installation
- Technical log with command output and operation results
- Scrollable dark-themed interface with sensitive-value masking

## Linux release

Download the latest release archive, extract it, and run:

```bash
./DeepTest2/DeepTest2
```

The bundle includes its Python runtime and GUI assets. ADB must still be installed and available in `PATH` for phone communication. USB debugging must be enabled and the device authorized.

## Windows build

The repository builds Windows packages automatically with GitHub Actions. Open the **Actions** tab, run **Windows build**, and download the `DeepTest2-Windows` artifact. Android Platform Tools (`adb.exe`) is still required for phone communication.

## Source setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
./launch-deeptesting.sh
```

## Security notes

Token caches are stored locally under `~/.config/deeptesting/`. Treat them as secrets. Reserve-partition operations are explicit and create a local backup before writing. Review the target device and backup path before applying authorization.
