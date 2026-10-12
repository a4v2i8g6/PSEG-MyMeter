# PSE&G MyMeter — diagnostic patch 0.1.2 (experimental)

**Read-only diagnostic update. Does not implement PSE&G username/password login, Okta SSO, or email/SMS verification. No guarantee cookie-only authentication will work.**

## Why this update

Version 0.1.1 returned `non_json` for any HTTP 200 response that was not valid meter JSON. This does not prove an invalid cookie. This update distinguishes these cases using **local response classification only**:

- `html_login`: MyMeter returned what looks like an HTML sign-in or SSO page.
- `html_security`: MyMeter returned what looks like a security/bot challenge.
- `html_other`: MyMeter returned another HTML page.
- `text_other`: MyMeter returned other non-JSON text.

The classifier does **not** log or disclose raw responses, session cookies, headers, or redirect URLs. It also rejects a mistakenly pasted `Cookie:` prefix, regardless of capitalization, as `invalid_cookie`.

## Install / retest

1. Back up Home Assistant before modifying custom components. Test outside your production Energy database whenever possible.
2. Extract this ZIP. Copy **only the contents** of `custom_components/pseg_mymeter/` over `/config/custom_components/pseg_mymeter/` (not the entire ZIP directory).
3. Restart Home Assistant. Confirm the integration's installed manifest version is `0.1.2`.
4. If the setup form is open, close and reopen it. Submit the **Cookie header value only**, in your own Home Assistant instance. Use an authenticated `ChartData` request, not `Chart`.
5. Report the *error code or wording only*. **Never share cookies, network request headers, HAR files, cURL commands, raw responses, or account/meter identifiers.**

If the error says `html_login` or `html_security`, repeatedly pasting a new cookie is unlikely to work. Implementing a real My Account SSO/verification flow (or a supported utility API) would be the next task. The native credential login is **not implemented** here.

## Limitations

- Even a working cookie expires and cannot be refreshed automatically by this version.
- Browser fingerprint/TLS behavior may cause a remote service to respond differently to `aiohttp` than to Chrome.
- Historical statistics and DST edge cases are experimental and not certified for production Energy data.
