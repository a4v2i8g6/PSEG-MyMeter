"""Configuration flow for a *user-owned* browser session.

Important: Okta SAML/email-SMS MFA remains unimplemented. We intentionally
DO NOT collect a PSE&G account password or pretend direct login works.
"""
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationRequired, MyMeterClient, SourceUnavailable, validate_cookie_string
from .const import CONF_SESSION_COOKIE, DOMAIN, NAME


class PsegMyMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input:
            try:
                cookie = validate_cookie_string(user_input[CONF_SESSION_COOKIE])
                client = MyMeterClient(async_get_clientsession(self.hass), cookie)
                await client.fetch_usage()
            except ValueError:
                errors["base"] = "invalid_cookie"
            except AuthenticationRequired as exc:
                errors["base"] = exc.code
            except SourceUnavailable as exc:
                errors["base"] = exc.code
            else:
                await self.async_set_unique_id("pseg_single_meter")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data={CONF_SESSION_COOKIE: cookie})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SESSION_COOKIE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input:
            try:
                cookie = validate_cookie_string(user_input[CONF_SESSION_COOKIE])
                await MyMeterClient(async_get_clientsession(self.hass), cookie).fetch_usage()
            except ValueError:
                errors["base"] = "invalid_cookie"
            except AuthenticationRequired as exc:
                errors["base"] = exc.code
            except SourceUnavailable as exc:
                errors["base"] = exc.code
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_SESSION_COOKIE: cookie},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_SESSION_COOKIE): str}),
            errors=errors,
        )
