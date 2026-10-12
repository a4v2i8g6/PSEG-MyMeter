# PSE&G MyMeter — diagnostic patch 0.1.1 (experimental)

This is **NOT** an authenticated PSE&G SSO integration. It still depends on a
short-lived browser session cookie and is not production-ready. **Do not install
on production Tuvix without a backup.**

## What changed since 0.1.0

- Distinguishes HTTP redirect, 401/403, unexpected HTTP status, invalid JSON,
  unexpected chart settings, and network failures instead of showing one
  misleading `session expired` message.
- Attempts a more browser-like AJAX GET request (including normal browser
  user-agent and request metadata). This may improve compatibility but is not
  guaranteed to overcome server-side anti-automation/session binding.
- Parses JSON regardless of its declared Content-Type, so mislabelled JSON is
  not incorrectly reported as an authentication failure.
- Does not log session credentials, response bodies, or redirect target URLs.

## Updating an existing manually-installed test integration

1. Back up Home Assistant (including its `/config` directory).
2. Extract this archive. Replace the existing files under
   `/config/custom_components/pseg_mymeter/` with the files from the same
   directory in this archive. Preserve your existing Home Assistant settings.
3. Restart Home Assistant. If you installed via a *custom GitHub repository* in
   HACS, place the updated files in that repository instead of assuming HACS
   can install a ZIP; HACS updates can overwrite manual modifications.
4. Retry adding the integration with a fresh cookie. **Only enter the cookie
   into your own Home Assistant config-flow field.**
5. Report the **error message text only** (for example, “redirected” or
   “non-JSON”). Do not share cookies, redirects, request headers, HAR exports,
   copied cURL commands, or full response bodies.

## Known limitations

- Okta SSO and email/SMS verification still require a separate implementation.
- Even a successful cookie-based test will eventually expire.
- Data import, DST handling and cost synchronization have not been certified
  for production use; historical statistics must be tested against a backup.
