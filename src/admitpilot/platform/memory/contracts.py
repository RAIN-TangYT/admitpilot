"""Memory contracts for short-term and versioned stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class MemoryRecord:
    """Memory item with metadata and versioning."""

    namespace: str
    key: str
    value: dict[str, Any]
    version: int = 1
    source: str = "unknown"
    confidence: float = 0.0
    evidence_level: str = "unknown"
    lineage: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return whether the record is expired."""
        if self.expires_at is None:
            return False
        return (now or datetime.utcnow()) >= self.expires_at


def default_expiry(hours: int = 24) -> datetime:
    """Build a default expiration timestamp."""
    return datetime.utcnow() + timedelta(hours=hours)
