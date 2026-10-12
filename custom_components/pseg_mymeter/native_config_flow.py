"""Reusable HA login/MFA flow steps (NOT wired into config_flow.py).

These steps can be integrated only after a real PSEG Okta provider is tested.
A backend that has never authenticated a user must not invite collection
of live PSE&G passwords. It is deliberately NOT a second ConfigFlow class.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .native_auth import (
    AuthenticatedSession, NativeAuthenticationError,
    NativeLoginController, VerificationChallenge,
)

_LOGIN_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
})
_VERIFY_SCHEMA = vol.Schema({vol.Required("verification_code"): str})


class NativeConfigStepsMixin:
    """Methods expected to be mixed into the existing HA ConfigFlow.

    Host must implement _native_login_controller() and
    _native_authenticated(session), which *validates session against actual
    meter data* then creates/updates the config entry. No credentials are
    persisted by this mixin. Form submission runs only when wired in.
    """

    def _native_login_controller(self) -> NativeLoginController:
        raise NotImplementedError

    async def _native_authenticated(self, session: AuthenticatedSession):
        raise NotImplementedError

    async def async_step_native_login(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                result = await self._native_login_controller().start(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD],
                )
                if isinstance(result, VerificationChallenge):
                    return await self.async_step_native_factor()
                return await self._native_authenticated(result)
            except NativeAuthenticationError as exc:
                errors["base"] = exc.code
        return self.async_show_form(
            step_id="native_login", data_schema=_LOGIN_SCHEMA, errors=errors,
        )

    async def async_step_native_factor(self, user_input: dict[str, Any] | None = None):
        controller = self._native_login_controller()
        challenge = controller.challenge
        if challenge is None:
            return self.async_abort(reason="native_auth_state")
        options = {method.id: method.label for method in challenge.methods}
        errors = {}
        if user_input is not None:
            try:
                await controller.choose_factor(user_input["verification_method"])
                return await self.async_step_native_code()
            except NativeAuthenticationError as exc:
                errors["base"] = exc.code
        return self.async_show_form(
            step_id="native_factor", errors=errors,
            data_schema=vol.Schema({vol.Required("verification_method"): vol.In(options)}),
        )

    async def async_step_native_code(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                session = await self._native_login_controller().verify(
                    user_input["verification_code"]
                )
                return await self._native_authenticated(session)
            except NativeAuthenticationError as exc:
                errors["base"] = exc.code
        return self.async_show_form(
            step_id="native_code", data_schema=_VERIFY_SCHEMA, errors=errors,
        )
