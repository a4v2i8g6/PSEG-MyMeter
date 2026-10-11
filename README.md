# PSE&G MyMeter → Home Assistant (experimental prototype)

**Status: development prototype; NOT a completed login integration. Do not install on production Tuvix yet.**

## Purpose

Home Assistant custom integration for PSE&G New Jersey MyMeter's **authenticated**
`GET https://mysmartenergy.nj.pseg.com/Dashboard/ChartData`, using the JSON
consumption data already observed in the user's own account.

It implements:
- Config flow for entering a **preexisting MyMeter browser session cookie** locally
  inside Home Assistant. This is a temporary developer-only way to test the backend.
- Polling every 6 hours, with a reauthentication flow on cookie expiry.
- Strict validation of **Consumption (kWh)** and **15-minute** chart selection.
- Filtering the meter series, excluding chart comparisons and temperature.
- Delayed **historically timestamped hourly Energy statistics** (`pseg_mymeter:electricity_consumption`) using the Recorder API. Incomplete hours are not imported. It refuses gaps rather than silently fabricating consumption.
- Diagnostic sensors for the last sync and last published reading.

## Not implemented yet

- **PSE&G My Account username/password SSO, Okta SAML, or email/SMS MFA**.
  Authentication can only be studied by testing PSE&G's live workflow using the
  user's own login; it cannot be inferred from the chart JSON.
- Silent long-term session renewal.
- Cost statistic synchronization (a separate daily-Dollar chart response was
  observed, but fetching both cost and consumption automatically requires chart
  selection independent of portal UI state).
- Robust DST fallback-hour handling and meter-account lifecycle.
- Robust service-side range selection (the current endpoint follows dashboard session state).

The HA integration is not yet suitable for publication to HACS or everyday operation.

## Major warnings

- **Do not send the Cookie header to ChatGPT or elsewhere.** It grants account
  session access. The prototype's config flow stores it in HA config-entry data
  (`.storage`), where Home Assistant administrators can access it. It is *not*
  protected with application-level encryption.
- Do not include cookies or auth tokens in any logs or issue reports.
- The backend may reject cookies replayed from a different computer (untested).
- Portal timestamps look like **local wall time encoded as UTC epoch**: this was
  observed when comparing sample `ChartData` and CSV readings. The parser maps
  them to America/New_York. DST transition behavior remains to be verified, and
  the ambiguous fall-back hour is skipped intentionally. That can prevent import
  for a DST day until this is resolved.
- The initial sum baseline is zero for the first retrieved hour. There is no
  extrapolation to the start of the account history.
- Source data is delayed (the observed data lagged about two days), not live.

## Source layout

`custom_components/pseg_mymeter/`: source files for a custom integration.
`tests/`: offline parser unit tests based on anonymized constructed samples.

## Local-only testing later, after review

1. Make a Home Assistant backup and test on a non-production HA instance.
2. Copy `custom_components/pseg_mymeter` under HA's `config/custom_components/`.
3. Restart the TEST instance and go to Settings → Devices & services → Add integration → PSE&G MyMeter.
4. Only if you explicitly choose to test the experimental cookie method, provide the Cookie **value** through your local HA UI. Do not upload or paste it into this chat.
5. Check logs, statistics and the imported Energy source. Never test first on your production Recorder database.

## Next engineering milestone (the user-requested experience)

Implement a **Home Assistant native 'Sign in via My Account'** flow with
username/password → choose SMS/email → verification code → SAML session →
automatic refresh or native reauth when MFA is required. This needs more
network-flow information about Okta form submission and token exchange, without
exposing authentication material. A browser-based helper might still prove
necessary; a clean `config_flow` cannot copy cookies out of a user's separate
browser due to the browser security model.

## References

Home Assistant developer config flow:
https://developers.home-assistant.io/docs/core/integration/config_flow/
Home Assistant external recorder statistics API:
https://developers.home-assistant.io/blog/2025/10/16/recorder-statistics-api-changes/
