# DeepTest 2.0 for Android

Experimental arm64 Android client. It embeds the existing DeepTest protocol implementation and provides account login, server requests, root detection, unlock-code validation, an untouched `oplusreserve1` backup, and authorization installation.

The APK supports both an existing `/data/local/tmp/su`/normal `su` and a one-time UID-0 handoff from its bundled root helper. The helper contains modified code from [YuKongA/ghostlock-app](https://github.com/YuKongA/ghostlock-app), distributed under Apache-2.0. Its source is retained under `third_party/ghostlock-app`, the complete license is packaged at `assets/licenses/ghostlock-LICENSE.txt`, and attribution/modification details are recorded in the repository `THIRD_PARTY_NOTICES.md`. The app also exposes these notices through **Settings → Open-source licenses**.

The handoff deliberately does not create a reusable `su`. After the first successful Root-page run, GhostLock starts an app-private, fixed-operation DeepTest root service which remains available until reboot. It accepts only health checks, authorization installation, reboot-to-bootloader, and shutdown—never arbitrary shell commands. Apply authorization and reboot therefore reuse the existing temporary root instead of rerunning the exploit. DeepTest accepts installation success only after the written 316-byte authorization has been read back from `oplusreserve1` and compared byte-for-byte. An untouched backup is saved under `/sdcard/deeptest-backup/` first.

## Prebuilt GhostLock helper

The repository intentionally ships the ARM64 helper at
`app/src/main/jniLibs/arm64-v8a/libghostlock.so`. CI verifies it against
`PREBUILT_GHOSTLOCK.sha256` before Gradle runs, so release builds do not need an
Android NDK. The corresponding modified source, Apache-2.0 license, and
third-party notices remain in the repository.

Rebuild the bundled arm64 helper after changing its source:

```bash
make -C third_party/ghostlock-app clean
make -C third_party/ghostlock-app NDK_ROOT=/path/to/android-ndk
cp third_party/ghostlock-app/ghostlock app/src/main/jniLibs/arm64-v8a/libghostlock.so
```

Build with:

```bash
JAVA_HOME=/home/koaan/android/INFIX/prebuilts/jdk/jdk21/linux-x86 ./gradlew assembleDebug
```

Set `sdk.dir` in `local.properties` to an Android SDK containing platform 36.

Release signing is supplied through environment variables and is never stored
in the repository: `ANDROID_KEYSTORE_FILE`, `ANDROID_KEYSTORE_PASSWORD`,
`ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`. CI also sets
`DEEPTEST_ANDROID_VERSION_CODE` and `DEEPTEST_ANDROID_VERSION_NAME` from the
workflow run and release tag.
