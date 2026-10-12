# PSE&G MyMeter diagnostic patch 0.1.3 (experimental)

**This does not implement SSO or MFA and does not fix cookie-only authentication.**

Changes:
- Sends the cache-busting `_` query parameter seen on working Chrome `ChartData` requests.
- Handles JSON responses containing a UTF-8 BOM.
- On an HTTP 200 non-JSON response, logs only HTTP status, a fixed/whitelisted MIME type, and response size in bytes. **No cookie, body content, URL, or authentication tokens are logged.**

## Installation (testing only)

1. Back up your Home Assistant `/config` folder and recorder database.
2. Copy `custom_components/pseg_mymeter/` into your HA `/config/custom_components/` directory, replacing existing integration files.
3. Restart Home Assistant and verify manifest version `0.1.3`.
4. Retry setup privately with a valid session cookie (do not paste it into chats, issues, or screenshots).
5. If you see `text_other`, open Home Assistant **Settings → System → Logs**, find the warning from `custom_components.pseg_mymeter.api` and share **only** HTTP status, MIME category, and bytes count.

The integration remains experimental and has not been live-tested against MyMeter. It does not offer a self-sustaining login. It must not be used as a reliable energy billing or accounting source.
