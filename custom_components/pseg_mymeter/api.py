"""Read-only, experimental MyMeter cookie-backed client.

PSE&G My Account SSO and MFA are *not* supported. Never log or send cookies,
response bodies, or redirect query strings to issue trackers / chat.
"""
import asyncio
import json
import logging
import time

import aiohttp

from .const import CHART_URL, MYMETER_ROOT
from .parser import ChartDataError, extract_intervals

_LOGGER = logging.getLogger(__name__)


class AuthenticationRequired(Exception):
    """Explicit authentication rejection, not a generic parsing failure."""
    code = "invalid_auth"


class LoginRedirect(AuthenticationRequired):
    """Server sent a redirect, generally into login."""
    code = "login_redirect"


class AccessDenied(AuthenticationRequired):
    """Server returned HTTP 401 or 403."""
    code = "access_denied"


class SourceUnavailable(Exception):
    """Request/data problem; cannot assume the cookie is invalid."""
    code = "cannot_connect"


class NonJsonResponse(SourceUnavailable):
    """An HTTP 200 response that is not meter JSON."""
    code = "non_json"


class LoginHtmlResponse(NonJsonResponse):
    """MyMeter seems to be presenting a sign-in page with HTTP 200."""
    code = "html_login"


class SecurityHtmlResponse(NonJsonResponse):
    """MyMeter seems to be presenting a browser/security challenge."""
    code = "html_security"


class OtherHtmlResponse(NonJsonResponse):
    """MyMeter presented another HTML page, not the meter JSON."""
    code = "html_other"


class OtherTextResponse(NonJsonResponse):
    """MyMeter returned an unexpected non-JSON text response."""
    code = "text_other"


class ChartSettingsError(SourceUnavailable):
    """JSON arrived but did not contain expected 15-minute kWh data."""
    code = "chart_settings"


class ServerError(SourceUnavailable):
    """Unexpected HTTP status or oversized response."""
    code = "server_error"


def validate_cookie_string(cookie: str) -> str:
    """Require Cookie header VALUE only, without any other headers."""
    cookie = cookie.strip()
    if not cookie or "\n" in cookie or "\r" in cookie or cookie.casefold().startswith("cookie:"):
        raise ValueError("Enter only the Cookie header value, without 'Cookie:'")
    if "=" not in cookie:
        raise ValueError("Expected name=value session cookie")
    if len(cookie) > 16000:
        raise ValueError("Cookie value is unusually long")
    return cookie


def classify_non_json(raw: bytes, content_type: str) -> type[NonJsonResponse]:
    """Classify unexpected response safely, without surfacing any response data.

    NOTE: do not log the URL, body, tokens, redirect targets or cookies.
    Both the page source and response headers are untrusted input.
    """
    sample = raw[:100_000].decode("utf-8", errors="replace").casefold()
    content_type = content_type.partition(";")[0].strip().casefold()
    looks_html = (
        "<!doctype html" in sample or "<html" in sample
        or "<form" in sample or content_type in ("text/html", "application/xhtml+xml")
    )
    if not looks_html:
        return OtherTextResponse
    # Prefer challenge detection: challenge pages frequently say 'sign in'.
    if any(x in sample for x in (
        "cloudflare", "captcha", "checking your browser", "verify you are human",
        "security challenge", "access to this page has been denied", "please enable javascript",
    )):
        return SecurityHtmlResponse
    if any(x in sample for x in (
        'type="password"', "type='password'", "saml", "okta", "sign in",
        "signin", "log in", "login", "id.myaccount.pseg.com",
    )):
        return LoginHtmlResponse
    return OtherHtmlResponse


class MyMeterClient:
    """Fetch chart data using a session cookie from the user's browser."""

    def __init__(self, session: aiohttp.ClientSession, cookie: str) -> None:
        self.session = session
        self.cookie = validate_cookie_string(cookie)

    async def fetch_usage(self) -> tuple[dict, list]:
        # Use normal browser AJAX request headers. They don't substitute for
        # a valid SSO session and may need changes as PSE&G's portal changes.
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/155.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": MYMETER_ROOT.rstrip("/") + "/Dashboard",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Cookie": self.cookie,
        }
        try:
            async with asyncio.timeout(25):
                async with self.session.get(
                    CHART_URL,
                    params={"_": str(time.time_ns() // 1_000_000)},
                    headers=headers,
                    allow_redirects=False,
                ) as resp:
                    # Never follow a redirect: don't leak a session cookie to an
                    # external SSO domain. Do not record the Location URL.
                    if resp.status in (301, 302, 303, 307, 308):
                        raise LoginRedirect("The request was redirected (probably to sign-in).")
                    if resp.status in (401, 403):
                        raise AccessDenied("MyMeter rejected access (HTTP 401/403).")
                    if resp.status != 200:
                        raise ServerError(f"MyMeter returned HTTP {resp.status}.")
                    # Some servers mislabel JSON with text/html or text/plain.
                    # Do not mistake a successful JSON response for bad auth.
                    raw = await resp.content.read(10 * 1024 * 1024 + 1)
                    if len(raw) > 10 * 1024 * 1024:
                        raise ServerError("MyMeter response too large.")
                    try:
                        # A UTF-8 BOM must not cause otherwise valid JSON to fail.
                        payload = json.loads(raw.decode("utf-8-sig"))
                    except (ValueError, UnicodeError) as exc:
                        # Log only non-sensitive response metadata. Never log
                        # bodies, cookies, URL/redirects, tokens, or headers.
                        content_type = resp.content_type
                        # Use a fixed allowlist so a malicious header value
                        # cannot create log injection or expose custom data.
                        mime = content_type if content_type in (
                            "text/plain", "text/html", "application/json",
                            "application/javascript", "text/javascript",
                            "application/octet-stream", "application/xhtml+xml",
                        ) else "other"
                        _LOGGER.warning(
                            "MyMeter returned non-JSON: HTTP %s, MIME %s, bytes %s",
                            resp.status, mime, len(raw),
                        )
                        response_error = classify_non_json(raw, content_type)
                        raise response_error(
                            "MyMeter did not return meter JSON (safe response classification)."
                        ) from exc
                    try:
                        intervals = extract_intervals(payload)
                    except (ChartDataError, TypeError, AttributeError) as exc:
                        raise ChartSettingsError(
                            "JSON received, but not 15-minute Consumption (kWh) chart data."
                        ) from exc
                    return payload, intervals
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SourceUnavailable("Network or timeout error contacting PSE&G.") from exc
