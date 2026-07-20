# DeepTesting client

Python implementation of the protocols used by `com.coloros.deeptesting`
17.0.3 and the current CN HeyTap UserCenter. It supports SMS/email verification
login, primary-token exchange, DeepTesting business authorization, and all six
current DeepTesting endpoints.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## Token cache

### HeyTap CN login

Send an SMS or email code:

```bash
.venv/bin/deeptesting-token login --phone '13800000000' --country-calling-code +86
.venv/bin/deeptesting-token login --email 'person@example.com'
```

When `authn/check` requires a slider CAPTCHA, `login` starts a local server,
opens the challenge in the default browser, waits up to five minutes, and
automatically retries the check. Use `--no-open-browser` to print the local URL
instead, or adjust the wait with `--captcha-timeout`. The complete raw callback
JSON returned by the CAPTCHA is sent unchanged as `captchaCode`.

Complete login and create the DeepTesting business token cache:

```bash
.venv/bin/deeptesting-token verify 123456
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
.venv/bin/deeptesting-token resume --stage verification --ticket '<ticket>'
.venv/bin/deeptesting-token resume --stage completion --ticket '<ticket>'
```

Refresh primary tokens and issue a fresh DeepTesting business authorization:

```bash
.venv/bin/deeptesting-token primary-refresh
```

The client generates the same unsigned SafetyCheck compatibility fallback used
by UserCenter when the vendor SRP provider is unavailable. A real value can be
provided through `DEEPTEST_DEVICE_TOKEN` for login and `DEEPTEST_ENV_PARAM` for
authorization. Server acceptance of the compatibility fallback can vary.

### Import an existing token

Import a complete `AuthResponse`, a `bizAuth` response, or its `data` object:

```bash
.venv/bin/deeptesting-token import auth-response.json
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
export DEEPTEST_CHIP_ID='<raw /proc/oplusVersion/serialID value>' # or "0x" + getprop ro.boot.chipid

.venv/bin/deeptesting get-apply-status
.venv/bin/deeptesting unlock-condition-match
.venv/bin/deeptesting apply-unlock
.venv/bin/deeptesting get-history-unlock-code
```

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

Use `--register-keys` to call `/crypto/cert/register` before creating the `lk`
session. Normal requests perform `/crypto/cert/upgrade`, derive an AES-256-GCM
key with P-256 ECDH and HKDF-SHA256, and encrypt both request and response.

For a one-off token without a cache:

```bash
.venv/bin/deeptesting get-apply-status \
  --token '<business accessToken>' \
  --device-id '<business deviceId>' \
  --udid '<device GUID>'
```

## Legacy experimental refresh

The cache must contain `accessToken`, `refreshToken`, `ssoid`, `deviceId`,
`host`, and preferably `pkgSign`. SafetyCheck output can be supplied explicitly:

```bash
.venv/bin/deeptesting-token refresh --env-param '<vendor SafetyCheck value>'
```

This is the older direct business `/api/token/refresh` implementation. New
sessions should use `primary-refresh`, which reproduces current UserCenter V1
refresh and then calls `authorization/v1/token/authorize` again.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
