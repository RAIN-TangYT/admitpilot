"""Capability token model with default-deny validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from admitpilot.platform.common.time import ensure_utc, utc_now


@dataclass(slots=True)
class CapabilityToken:
    """Short-lived capability token for an agent."""

    token_id: str
    subject: str
    expires_at: datetime
    issued_at: datetime
    allowed_methods: tuple[str, ...] = ()
    allowed_scopes: tuple[str, ...] = ()
    constraints: dict[str, str] = field(default_factory=dict)

    @property
    def principal(self) -> str:
        return self.subject

    def is_expired(self, now: datetime | None = None) -> bool:
        return ensure_utc(now or utc_now()) >= ensure_utc(self.expires_at)

    def is_valid(self, now: datetime | None = None) -> bool:
        return not self.is_expired(now)


class CapabilityIssuer(Protocol):
    """Capability issuer contract."""

    def issue(
        self,
        subject: str,
        allowed_methods: tuple[str, ...],
        allowed_scopes: tuple[str, ...],
        ttl_seconds: int,
    ) -> CapabilityToken:
        """Issue a capability token."""


class CapabilityValidator(Protocol):
    """Capability validator contract."""

    def validate_method(self, token: CapabilityToken, method: str, now: datetime) -> bool:
        """Validate method-level access."""

    def validate_scope(self, token: CapabilityToken, scope: str, now: datetime) -> bool:
        """Validate scope-level access."""


@dataclass(slots=True)
class InMemoryCapabilityValidator:
    """In-memory validator used by tests."""

    def validate_method(self, token: CapabilityToken, method: str, now: datetime) -> bool:
        if token.is_expired(now):
            return False
        return method in token.allowed_methods

    def validate_scope(self, token: CapabilityToken, scope: str, now: datetime) -> bool:
        if token.is_expired(now):
            return False
        if "*" in token.allowed_scopes:
            return True
        return scope in token.allowed_scopes


@dataclass(slots=True)
class CapabilityManager:
    """Issue and validate capability tokens for the orchestrator."""

    token_ttl_minutes: int = 10
    policy: dict[str, set[str]] = field(default_factory=dict)

    def issue(self, principal: str, scopes: set[str]) -> CapabilityToken:
        now = utc_now()
        return CapabilityToken(
            token_id=f"{principal}-{int(now.timestamp())}",
            subject=principal,
            expires_at=now + timedelta(minutes=self.token_ttl_minutes),
            issued_at=now,
            allowed_scopes=tuple(sorted(scopes)),
        )

    def validate(self, token: CapabilityToken, required_scope: str) -> bool:
        if not token.is_valid():
            return False
        return required_scope in token.allowed_scopes

    def allowed_agent(self, agent_name: str) -> bool:
        return agent_name in self.policy
