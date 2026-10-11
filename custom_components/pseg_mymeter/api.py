"""Read-only MyMeter session client.

An experimental cookie-backed adapter, NOT an implementation of PSE&G SSO.
Cookie values must only be supplied inside the user's own Home Assistant UI.
"""
import asyncio
import json
from collections.abc import Mapping

import aiohttp

from .const import CHART_URL, MYMETER_ROOT
from .parser import ChartDataError, extract_intervals


class AuthenticationRequired(Exception):
    """MyMeter cookie no longer authenticates data requests."""


class SourceUnavailable(Exception):
    """MyMeter endpoint failed for a non-authentication reason."""


def validate_cookie_string(cookie: str) -> str:
    """Require browser Cookie *value* only, not a HAR/cURL or headers dump."""
    cookie = cookie.strip()
    if not cookie or "\n" in cookie or "\r" in cookie or "Cookie:" in cookie:
        raise ValueError("Enter only the Cookie header value, without 'Cookie:'")
    if ";" not in cookie and "=" not in cookie:
        raise ValueError("Expected name=value session cookie")
    if len(cookie) > 16000:
        raise ValueError("Cookie value is unusually long")
    return cookie


class MyMeterClient:
    """Fetch and validate chart data using a preexisting user browser session."""

    def __init__(self, session: aiohttp.ClientSession, cookie: str) -> None:
        self.session = session
        self.cookie = validate_cookie_string(cookie)

    async def fetch_usage(self) -> tuple[dict, list]:
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": MYMETER_ROOT,
            "Cookie": self.cookie,
        }
        try:
            # Let redirects happen only to classify login vs data (never send
            # cookie on cross-domain redirect: aiohttp drops Authorization,
            # but not necessarily a custom Cookie header). For safety turn
            # redirects off and treat 3xx as authentication failures.
            async with asyncio.timeout(25):
                async with self.session.get(
                    CHART_URL, headers=headers, allow_redirects=False,
                ) as resp:
                    if resp.status in (301, 302, 303, 307, 308, 401, 403):
                        raise AuthenticationRequired("PSE&G requires login again")
                    if resp.status != 200:
                        raise SourceUnavailable(f"MyMeter HTTP {resp.status}")
                    # Avoid accepting an HTML login page returned with 200.
                    if "json" not in resp.headers.get("Content-Type", "").lower():
                        raise AuthenticationRequired("MyMeter returned non-JSON login content")
                    try:
                        payload = await resp.json(content_type=None)
                        intervals = extract_intervals(payload)
                    except (ValueError, json.JSONDecodeError, ChartDataError) as exc:
                        raise SourceUnavailable("Unexpected chart response or chart settings") from exc
                    return payload, intervals
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SourceUnavailable("Unable to reach PSE&G MyMeter") from exc
