"""Memory contracts for short-term and versioned stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from admitpilot.platform.common.time import ensure_utc, utc_now


class MemoryNamespace(StrEnum):
    """Well-known memory namespaces."""

    SESSION = "session"
    APPLICATION = "application"
    OFFICIAL = "official"
    CASE = "case"
    STRATEGY = "strategy"
    TIMELINE = "timeline"
    ARTIFACT = "artifact"
    AUDIT = "audit"


@dataclass(slots=True)
class VersionedRecord:
    """Structured versioned record used by compatibility tests."""

    tenant_id: str
    user_id: str
    application_id: str
    cycle: str
    namespace: MemoryNamespace
    version_id: str
    as_of_date: str
    payload: dict[str, Any]
    lineage: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class MemoryRecord:
    """Runtime memory item with metadata and versioning."""

    namespace: str
    key: str
    value: dict[str, Any]
    version: int = 1
    source: str = "unknown"
    confidence: float = 0.0
    evidence_level: str = "unknown"
    lineage: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return ensure_utc(now or utc_now()) >= ensure_utc(self.expires_at)


@dataclass(slots=True)
class MemoryTopology:
    """Suggested backend topology."""

    session_backend: str
    relational_backend: str
    vector_backend: str
    object_backend: str
    audit_backend: str
    todo: tuple[str, ...] = field(default_factory=tuple)


def default_memory_topology() -> MemoryTopology:
    return MemoryTopology(
        session_backend="redis",
        relational_backend="postgresql",
        vector_backend="pgvector_or_milvus",
        object_backend="s3_or_minio",
        audit_backend="clickhouse_or_elk",
        todo=(
            "落地 namespace 级别读写 ACL",
            "落地数据生命周期与归档策略",
            "落地跨版本回放工具",
        ),
    )


def default_expiry(hours: int = 24) -> datetime:
    """Build a default expiration timestamp."""

    return utc_now() + timedelta(hours=hours)
