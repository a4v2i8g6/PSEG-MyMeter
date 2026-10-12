"""Offline tests for the native-login architecture. No PSE&G requests."""
import asyncio
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "pseg_mymeter" / "native_auth.py"
spec = importlib.util.spec_from_file_location("pseg_native_auth_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)
(
    NativeLoginController, VerificationMethod, VerificationChallenge,
    AuthenticatedSession, PendingStep, InvalidFlowState,
    InvalidVerificationCode, SessionExpired, PsegOktaBackendPlaceholder,
    BackendNotImplemented,
) = (
    module.NativeLoginController, module.VerificationMethod, module.VerificationChallenge,
    module.AuthenticatedSession, module.PendingStep, module.InvalidFlowState,
    module.InvalidVerificationCode, module.SessionExpired, module.PsegOktaBackendPlaceholder,
    module.BackendNotImplemented,
)


class FakeAuthProvider:
    def __init__(self):
        self.sent = []
        self.verification_values = []
        self.credentials = []
        self.renewed = 0
        self.is_challenge = True

    async def start(self, username, password):
        self.credentials.append((username, password))
        if not self.is_challenge:
            return AuthenticatedSession("account-1", {"opaque": "secret-session"})
        return VerificationChallenge("opaque_txn_code", (
            VerificationMethod("sms-01", "sms", "Text message"),
            VerificationMethod("email-01", "email", "Email"),
        ))

    async def send_code(self, txn, method):
        self.sent.append((txn, method))

    async def verify_code(self, txn, code):
        self.verification_values.append((txn, code))
        if code != "123456":
            raise InvalidVerificationCode("Bad code")
        return AuthenticatedSession("account-1", {"opaque": "secret-session"})

    async def renew(self, session):
        self.renewed += 1
        return AuthenticatedSession(session.account_id, {"opaque": "renewed-secret"})


class NativeLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = FakeAuthProvider()
        self.controller = NativeLoginController(self.backend)

    async def test_sms_login(self):
        challenge = await self.controller.start(" a@example.com ", "a-password")
        self.assertIsInstance(challenge, VerificationChallenge)
        self.assertEqual(self.controller.step, PendingStep.CHOOSE_FACTOR)
        await self.controller.choose_factor("sms-01")
        self.assertEqual(self.controller.step, PendingStep.ENTER_CODE)
        session = await self.controller.verify(" 123456 ")
        self.assertEqual(session.account_id, "account-1")
        self.assertEqual(self.backend.credentials, [("a@example.com", "a-password")])
        self.assertEqual(self.backend.sent[0][1], "sms-01")
        self.assertEqual(self.controller.step, PendingStep.AUTHENTICATED)
        self.assertIsNone(self.controller.challenge)
        self.assertNotIn("a-password", repr(self.controller))

    async def test_email_login(self):
        await self.controller.start("a@example.com", "pass")
        await self.controller.choose_factor("email-01")
        await self.controller.verify("123456")
        self.assertEqual(self.backend.sent[0][1], "email-01")

    async def test_login_without_mfa(self):
        self.backend.is_challenge = False
        result = await self.controller.start("a@example.com", "pass")
        self.assertIsInstance(result, AuthenticatedSession)
        self.assertEqual(self.controller.step, PendingStep.AUTHENTICATED)

    async def test_invalid_method_rejected(self):
        await self.controller.start("a@example.com", "pass")
        with self.assertRaises(InvalidFlowState):
            await self.controller.choose_factor("random-method")
        self.assertEqual(self.backend.sent, [])

    async def test_no_code_before_factor(self):
        await self.controller.start("a@example.com", "pass")
        with self.assertRaises(InvalidFlowState):
            await self.controller.verify("123456")

    async def test_wrong_code_allows_retry(self):
        await self.controller.start("a@example.com", "pass")
        await self.controller.choose_factor("sms-01")
        with self.assertRaises(InvalidVerificationCode):
            await self.controller.verify("wrongcode")
        self.assertEqual(self.controller.step, PendingStep.ENTER_CODE)
        await self.controller.verify("123456")
        self.assertEqual(self.controller.step, PendingStep.AUTHENTICATED)

    async def test_code_length_rejected_locally(self):
        await self.controller.start("a@example.com", "pass")
        await self.controller.choose_factor("sms-01")
        with self.assertRaises(InvalidVerificationCode):
            await self.controller.verify("12")
        self.assertEqual(self.backend.verification_values, [])

    async def test_renew(self):
        self.backend.is_challenge = False
        await self.controller.start("a@example.com", "pass")
        renewed = await self.controller.renew()
        self.assertEqual(renewed.state["opaque"], "renewed-secret")
        self.assertEqual(self.backend.renewed, 1)

    async def test_renew_no_session(self):
        with self.assertRaises(SessionExpired):
            await self.controller.renew()

    async def test_cancel_clears_secrets(self):
        await self.controller.start("a@example.com", "pass")
        self.controller.reset()
        self.assertIsNone(self.controller.challenge)
        self.assertIsNone(self.controller.session)
        self.assertEqual(self.controller.step, PendingStep.START)

    async def test_repr_does_not_leak_tokens(self):
        challenge = VerificationChallenge("very-secret-token", (VerificationMethod("sms", "sms", "SMS"),))
        self.assertNotIn("very-secret-token", repr(challenge))
        session = AuthenticatedSession("123456secret", {"opaque": "really-secret"})
        self.assertNotIn("123456secret", repr(session))
        self.assertNotIn("really-secret", repr(session))

    async def test_placeholder_refuses_live_login(self):
        with self.assertRaises(BackendNotImplemented):
            await PsegOktaBackendPlaceholder().start("a@example.com", "pass")
