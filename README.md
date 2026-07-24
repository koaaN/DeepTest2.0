# DeepTest 2.0

DeepTest 2.0 is a desktop GUI for OnePlus/HeyTap DeepTesting workflows. It replaces terminal-heavy commands with a guided interface for login, device detection, authorization, diagnostics, and unlock-code management.

This is an independent GUI built on the protocol implementation and research from [mikoker/deeptest](https://github.com/mikoker/deeptest). Please review the upstream project’s license and documentation.

## Download a ready-to-run release

Open the repository’s [Releases](https://github.com/koaaN/DeepTest2.0/releases) page and download the archive for your operating system.

### Linux

1. Download `DeepTest2-linux-x86_64.tar.gz`.
2. Extract it:

   ```bash
   tar -xzf DeepTest2-linux-x86_64.tar.gz
   ```

3. Start the application:

   ```bash
   ./DeepTest2/DeepTest2
   ```

### Windows

1. Download `DeepTest2-windows.zip`.
2. Extract the ZIP file.
3. Open the extracted `DeepTest2` folder.
4. Double-click `DeepTest2.exe`.

The Windows release includes Platform Tools and `adb.exe`. The Linux release uses system ADB when available; install Android Platform Tools if ADB is not already on your `PATH`.

## Before connecting a phone

- Enable USB debugging.
- Accept the RSA authorization prompt on the phone.
- Keep only the intended device connected.

The Connected Device card shows the live ADB connection. Saved target-device fields may remain visible between launches and do not prove that a phone is connected.

## Main workflow

1. Open **Account Login** and sign in with HeyTap.
2. Continue to **Device & unlock**.
3. Confirm the detected model, PRJ-ID, OTA version, and chip ID.
4. Run the workflow actions in order: eligibility, application, status, and unlock code.
5. In **Gain temp root**, select the installed device version and press **Run root helper**.
6. Press **Check requirements** to confirm that root access and the unlock code are ready.
7. Use **Install unlock authorization** only after checking the target device and confirming the backup location.

The application creates a local `oplusreserve1` backup before applying an authorization. Review the Technical Log after each operation.

## Token storage

Login and authorization data is stored locally under:

```text
~/.config/deeptesting/
```

Treat these JSON files as secrets and never upload them. Device settings are also local and are not sent to the repository.

## Building from source

The repository includes separate GitHub Actions workflows for Linux and Windows, plus a combined release workflow. Maintainers can run them from the **Actions** tab or trigger the release workflow with a `v*` tag.
