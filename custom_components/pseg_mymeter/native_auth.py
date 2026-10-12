"""Provider-independent native-auth state machine for PSE&G MyMeter.

Developer scaffold only. An actual PSE&G Okta/SAML provider has NOT been
implemented. No password or OTP is persisted or logged by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Mapping, Protocol


class NativeAuthenticationError(Exception):
    """Error shown to Home Assistant via its *static* localized error code."""
    code = "native_auth_failed"


class InvalidLogin(NativeAuthenticationError):
    code = "invalid_auth"


class InvalidVerificationCode(NativeAuthenticationError):
    code = "invalid_code"


class SessionExpired(NativeAuthenticationError):
    code = "session_expired"


class BackendNotImplemented(NativeAuthenticationError):
    code = "native_auth_unavailable"


class InvalidFlowState(NativeAuthenticationError):
    code = "native_auth_state"


@dataclass(frozen=True)
class VerificationMethod:
    id: str
    channel: str  # "sms" or "email"; never store actual phone/email here
    label: str  # redacted display label supplied by provider (e.g. "Text message")

    def __post_init__(self):
        if self.channel not in ("sms", "email"):
            raise ValueError("Unsupported verification channel")
        if not self.id or not self.label:
            raise ValueError("Verification method needs an ID and label")


@dataclass(frozen=True)
class VerificationChallenge:
    transaction_id: str  # opaque challenge state, stored in memory only
    methods: tuple[VerificationMethod, ...]

    def __post_init__(self):
        if not self.transaction_id or not self.methods:
            raise ValueError("Incomplete verification challenge")
        if len({m.id for m in self.methods}) != len(self.methods):
            raise ValueError("Duplicate method identifiers")

    def __repr__(self):
        # Transaction identifiers may themselves be session credentials.
        return f"VerificationChallenge(methods={len(self.methods)})"


@dataclass(frozen=True)
class AuthenticatedSession:
    """Serializable provider session; schema to be defined by real provider.

    A cookie HEADER copied from Chrome has already proven unreliable. The
    provider must manage a browser-equivalent cookie jar and/or own tokens,
    with renewal and secure storage, before this can be used live.
    """
    account_id: str
    state: Mapping[str, str] = field(repr=False)

    def __repr__(self):
        return "AuthenticatedSession(account_id=[redacted], state=[redacted])"


StartResult = VerificationChallenge | AuthenticatedSession


class NativeAuthProvider(Protocol):
    async def start(self, username: str, password: str) -> StartResult:
        """Begin login; return challenge when a code is required."""

    async def send_code(self, transaction_id: str, method_id: str) -> None:
        """Ask provider to deliver the selected SMS/email code."""

    async def verify_code(self, transaction_id: str, code: str) -> AuthenticatedSession:
        """Finish authentication without logging or persisting the OTP."""

    async def renew(self, session: AuthenticatedSession) -> AuthenticatedSession:
        """Renew a session or raise SessionExpired."""


class PendingStep(Enum):
    START = auto()
    CHOOSE_FACTOR = auto()
    ENTER_CODE = auto()
    AUTHENTICATED = auto()


class NativeLoginController:
    """Minimal MFA state machine; credentials never retained in this class."""

    def __init__(self, provider: NativeAuthProvider):
        self.provider = provider
        self.step = PendingStep.START
        self.challenge: VerificationChallenge | None = None
        self.session: AuthenticatedSession | None = None

    async def start(self, username: str, password: str) -> StartResult:
        if not username.strip() or not password:
            raise InvalidLogin("Missing credentials")
        # Only the backend receives the password; controller never stores it.
        self.reset()
        response = await self.provider.start(username.strip(), password)
        if isinstance(response, VerificationChallenge):
            self.challenge = response
            self.step = PendingStep.CHOOSE_FACTOR
        elif isinstance(response, AuthenticatedSession):
            self.session = response
            self.step = PendingStep.AUTHENTICATED
        else:
            raise InvalidFlowState("Unrecognized authentication result")
        return response

    async def choose_factor(self, method_id: str) -> None:
        if self.step != PendingStep.CHOOSE_FACTOR or self.challenge is None:
            raise InvalidFlowState("Verification method not expected")
        if method_id not in {method.id for method in self.challenge.methods}:
            raise InvalidFlowState("Unrecognized verification method")
        await self.provider.send_code(self.challenge.transaction_id, method_id)
        self.step = PendingStep.ENTER_CODE

    async def verify(self, code: str) -> AuthenticatedSession:
        if self.step != PendingStep.ENTER_CODE or self.challenge is None:
            raise InvalidFlowState("Verification code not expected")
        code = code.strip()
        # Do not restrict to digits: providers may accept alphanumeric OTPs.
        if not 4 <= len(code) <= 16:
            raise InvalidVerificationCode("Invalid verification code")
        result = await self.provider.verify_code(self.challenge.transaction_id, code)
        if not isinstance(result, AuthenticatedSession):
            raise InvalidFlowState("Invalid authentication result")
        self.session = result
        self.challenge = None
        self.step = PendingStep.AUTHENTICATED
        return result

    async def renew(self) -> AuthenticatedSession:
        if self.session is None:
            raise SessionExpired("No authenticated session")
        result = await self.provider.renew(self.session)
        if not isinstance(result, AuthenticatedSession):
            raise InvalidFlowState("Invalid renewed session")
        self.session = result
        return result

    def reset(self) -> None:
        self.step = PendingStep.START
        self.challenge = None
        self.session = None


class PsegOktaBackendPlaceholder:
    """Intentionally nonfunctional: no undocumented auth endpoints guessed."""

    async def start(self, username: str, password: str) -> StartResult:
        raise BackendNotImplemented("PSE&G Okta implementation is unverified")

    async def send_code(self, transaction_id: str, method_id: str) -> None:
        raise BackendNotImplemented("PSE&G MFA implementation is unverified")

    async def verify_code(self, transaction_id: str, code: str) -> AuthenticatedSession:
        raise BackendNotImplemented("PSE&G MFA implementation is unverified")

    async def renew(self, session: AuthenticatedSession) -> AuthenticatedSession:
        raise BackendNotImplemented("PSE&G session renewal is unverified")
