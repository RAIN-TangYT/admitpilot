"""Governance hooks for policy validation and audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class GovernanceEngine:
    """Simple policy gate and audit trail."""

    blocked_terms: tuple[str, ...] = ("fabricate", "fake", "作弊", "伪造")
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def policy_validate(self, text: str) -> tuple[bool, str]:
        """Validate output content against policy."""
        lowered = text.lower()
        for term in self.blocked_terms:
            if term.lower() in lowered:
                return False, f"policy_blocked:{term}"
        return True, "ok"

    def redact_pii(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply lightweight PII redaction."""
        redacted = dict(payload)
        if "name" in redacted:
            redacted["name"] = "***"
        return redacted

    def audit(self, event: str, details: dict[str, Any]) -> None:
        """Append an audit event."""
        self._audit.append(
            {"event": event, "details": details, "at": datetime.utcnow().isoformat()}
        )

    def audit_log(self) -> list[dict[str, Any]]:
        """Return governance audit events."""
        return list(self._audit)
