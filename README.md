# DeepTest 2.0

> DeepTest 2.0 is an independent graphical client built on the protocol implementation and research from [mikoker/deeptest](https://github.com/mikoker/deeptest). Please review the upstream license and project history before redistributing.

Python implementation of the protocols used by `com.coloros.deeptesting`
17.0.3 and the current CN HeyTap UserCenter. It supports SMS/email verification
login, primary-token exchange, DeepTesting business authorization, and all six
current DeepTesting endpoints.

## Python GUI

This repository includes the DeepTest 2.0 graphical Python app for sign-in, token import and
refresh, device configuration, and all six DeepTesting actions.

After installing the Python environment, double-click `launch-deeptesting.sh`
or start it from a Python environment with `deeptesting-gui`. The GUI is
portable and does not install an application-menu entry.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
pip install -e .
```

## Token cache

### HeyTap CN login

Send an SMS or email code:

```bash
deeptesting-token login --phone '13800000000' --country-calling-code +86
deeptesting-token login --email 'person@example.com'
```

HeyTap routes accounts to regional UserCenter hosts. The default host is
`https://client-uc.heytapmobi.com`. If the server returns `301 domain error`,
the client automatically selects the host matching `countryCode`, retries the
request once, and stores that host in the login/primary cache for the next
flow step. If the mapping is missing or the regional retry also fails, the CLI
prints the complete response and a suggested retry command:

```bash
deeptesting-token login --email 'person@example.com' \
  --host 'https://uc-client-sg.heytapmobile.com'
```

The same host must be supplied to the later command that continues the flow
(`verify`, `resume`, `biz-auth`, or `primary-refresh`). It can also be set once
with `DEEPTEST_HEYTAP_HOST`.

When `authn/check` requires a slider CAPTCHA, `login` starts a local server,
opens the challenge in the default browser, waits up to five minutes, and
automatically retries the check. Use `--no-open-browser` to print the local URL
instead, or adjust the wait with `--captcha-timeout`. The complete raw callback
JSON returned by the CAPTCHA is sent unchanged as `captchaCode`.

Complete login and create the DeepTesting business token cache:

```bash
deeptesting-token verify 123456
```

The login flow writes these mode-`0600` files under
`~/.config/deeptesting/`:

```text
login-session.json  pending processToken and OTP flow state
primary-auth.json   UserCenter primary account credentials
auth.json           DeepTesting business credentials used as newToken
heytap-rsa.der      RSA key learned from an HTTP 222 key rotation
```

If no CAPTCHA handler is configured through the Python API, CAPTCHA remains an
`interaction_required` result. H5 verification always returns the challenge
URL and can be resumed after obtaining its ticket:

```bash
deeptesting-token resume --stage verification --ticket '<ticket>'
deeptesting-token resume --stage completion --ticket '<ticket>'
```

Refresh primary tokens and issue a fresh DeepTesting business authorization:

```bash
deeptesting-token primary-refresh
```

The client generates the same unsigned SafetyCheck compatibility fallback used
by UserCenter when the vendor SRP provider is unavailable. A real value can be
provided through `DEEPTEST_DEVICE_TOKEN` for login and `DEEPTEST_ENV_PARAM` for
authorization. Server acceptance of the compatibility fallback can vary.

### Import an existing token

Import a complete `AuthResponse`, a `bizAuth` response, or its `data` object:

```bash
deeptesting-token import auth-response.json
```

The default cache is `~/.config/deeptesting/auth.json`. It is written with mode
`0600`. Override it with `--token-cache` or `DEEPTEST_TOKEN_CACHE`.

Accepted business authorization shape:

```json
{
  "data": {
    "v3BizTokenResp": {
      "accessToken": "...",
      "refreshToken": "...",
      "idToken": "...",
      "accessTokenExp": 0,
      "refreshTokenExp": 0,
      "accessTokenRfAdv": 0,
      "refreshTokenRfAdv": 0
    },
    "deviceId": "...",
    "host": "https://client-uc.heytapmobi.com",
    "pkgSign": "..."
  }
}
```

Do not commit this file. It contains account credentials.

## API calls

At minimum provide the device GUID (`udid`). Model-specific values can be
passed as flags or environment variables:

```bash
export DEEPTEST_UDID='<GUID returned by the Oplus ID provider>'
export DEEPTEST_CHIP_ID='<raw /proc/oplusVersion/serialID value>'

# Windows PowerShell:  $env:DEEPTEST_UDID='<value>'
# Windows CMD:         set DEEPTEST_UDID=<value>
```

The Chip ID can be read with `adb shell cat /proc/oplusVersion/serialID` on a
rooted device. On a non-rooted device, use `adb shell getprop ro.boot.chipid`
and add the `0x` prefix when it is not already present.

```bash
deeptesting get-apply-status
deeptesting unlock-condition-match
deeptesting apply-unlock
deeptesting get-history-unlock-code
```

The DeepTesting request uses the secondary token scoped to
`com.coloros.deeptesting` when it is present in the business cache. Older
caches without that field fall back to their existing business access token.

Default device profile:

```text
model=PLK110
otaVersion=PLK110_11.A.68_0680_202606250030
appVersion=17000003
brand=OnePlus
osVersion=16
```

The available endpoint commands are:

```text
apply-unlock
get-apply-status
update-client-lock-status
lock-client
unlock-condition-match
get-history-unlock-code
```

## Apply the issued authorization to the phone

The Device page can pass an approved unlock code to the connected phone with
**Apply authorization to phone**. This step requires one authorized ADB device,
root access granted to the ADB shell, and an unlock code returned by **Check
status** or **Get unlock code**.

DeepTest pushes its packaged Android helper to `/data/local/tmp` and invokes
`android.engineer.OplusEngineerManager.fastbootUnlock` through `app_process`.
It does not reboot the phone, erase data, enable the OEM-unlock setting, or run
`fastboot flashing unlock`. The later bootloader-unlock operation remains a
separate, destructive step.

This integration is based on the documented mechanism in
[mikoker/unlock-helper](https://github.com/mikoker/unlock-helper). DeepTest
contains its own minimal helper implementation. The GUI keeps the issued code
in memory only and redacts it from the displayed helper command.

Use `--register-keys` to call `/crypto/cert/register` before creating the `lk`
session. Normal requests perform `/crypto/cert/upgrade`, derive an AES-256-GCM
key with P-256 ECDH and HKDF-SHA256, and encrypt both request and response.

For a one-off token without a cache:

```bash
deeptesting get-apply-status \
  --token '<business accessToken>' \
  --device-id '<business deviceId>' \
  --udid '<device GUID>'
```

## Legacy experimental refresh

The cache must contain `accessToken`, `refreshToken`, `ssoid`, `deviceId`,
`host`, and preferably `pkgSign`. SafetyCheck output can be supplied explicitly:

```bash
deeptesting-token refresh --env-param '<vendor SafetyCheck value>'
```

This is the older direct business `/api/token/refresh` implementation. New
sessions should use `primary-refresh`, which reproduces current UserCenter V1
refresh and then calls `authorization/v1/token/authorize` again.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
