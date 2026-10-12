# PSE&G MyMeter — Native Authentication Architecture (v0.2.0 scaffold)

**Developer package. Not a working PSE&G login. Do not deploy it as an authentication update.**
The existing v0.1.3 cookie-based integration files are included unchanged.

## What's implemented

- `custom_components/pseg_mymeter/native_auth.py` — provider-independent
  session and SMS/email MFA state machine, with optional renewal hook.
- `custom_components/pseg_mymeter/native_config_flow.py` — reusable Home
  Assistant login, factor-choice, and OTP form steps, not yet connected to
  `config_flow.py`.
- Tests simulate successful SMS/email MFA, invalid codes, expired sessions,
  renewal, and redaction of opaque secrets.
- Existing energy/recorder statistics logic is untouched.

## Not yet implemented (blocking)

- A verified Okta/SAML authentication client specific to PSE&G's My Account,
  including anti-bot/device checks and successful SAML ACS exchange.
- PSE&G session persistence/cookie jar that survives restart, and renewal
  behavior under real session expiry.
- Enabling or exposing the new form steps in the installed integration.
- Production account-level unique IDs, security review, and live validation
  with PSE&G (without sharing account credentials or MFA secrets).

The backend placeholder deliberately refuses live authentication. It never
accepts/stores your PSE&G credentials. The successful authentication in unit
tests is **simulated** using a fake provider; it is not evidence that the
actual PSE&G portal supports an API-driven login.

## Why it follows Cync

Cync's integration separates HA UI (`config_flow`) from an authentication
library (`pycync.Auth`). This package follows the same separation, allowing
a provider adapter for PSE&G's Okta/SAML process to be added and verified
without rewriting forms and state transitions.

## Run offline tests (Python 3.11+)

From this extracted folder:

```bash
python -m unittest discover -s tests -v
python -m compileall -q custom_components/pseg_mymeter
```

No changes were applied to Home Assistant Tuvix or your GitHub repository.
