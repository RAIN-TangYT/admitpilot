"""Capability token model with default-deny validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class CapabilityToken:
    """Short-lived capability token for an agent."""

    token_id: str
    principal: str
    allowed_scopes: set[str]
    issued_at: datetime
    expires_at: datetime

    def is_valid(self, now: datetime | None = None) -> bool:
        """Return whether token is still valid."""
        return (now or datetime.utcnow()) < self.expires_at


@dataclass
class CapabilityManager:
    """Issue and validate capability tokens."""

    token_ttl_minutes: int = 10
    policy: dict[str, set[str]] = field(default_factory=dict)

    def issue(self, principal: str, scopes: set[str]) -> CapabilityToken:
        """Issue a token with scoped permissions."""
        now = datetime.utcnow()
        return CapabilityToken(
            token_id=f"{principal}-{int(now.timestamp())}",
            principal=principal,
            allowed_scopes=set(scopes),
            issued_at=now,
            expires_at=now + timedelta(minutes=self.token_ttl_minutes),
        )

    def validate(self, token: CapabilityToken, required_scope: str) -> bool:
        """Default deny if token invalid or scope missing."""
        if not token.is_valid():
            return False
        return required_scope in token.allowed_scopes

    def allowed_agent(self, agent_name: str) -> bool:
        """Check whether agent exists in policy."""
        return agent_name in self.policy
