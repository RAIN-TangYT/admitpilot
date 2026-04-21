"""In-memory adapters used by the platform bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from admitpilot.platform.memory.contracts import MemoryRecord


@dataclass
class SessionMemoryStore:
    """Namespace-isolated short-term memory with TTL."""

    ttl_hours: int = 12
    _data: dict[str, dict[str, MemoryRecord]] = field(default_factory=dict, repr=False)
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def put(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        source: str = "unknown",
        confidence: float = 0.0,
        evidence_level: str = "unknown",
        lineage: list[str] | None = None,
    ) -> MemoryRecord:
        """Upsert a namespaced short-term record."""
        expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)
        current = self._data.setdefault(namespace, {})
        version = current[key].version + 1 if key in current else 1
        record = MemoryRecord(
            namespace=namespace,
            key=key,
            value=value,
            version=version,
            source=source,
            confidence=confidence,
            evidence_level=evidence_level,
            lineage=lineage or [],
            expires_at=expires_at,
        )
        current[key] = record
        self._audit.append(
            {
                "event": "session_memory_put",
                "namespace": namespace,
                "key": key,
                "version": version,
                "at": datetime.utcnow().isoformat(),
            }
        )
        return record

    def get(self, namespace: str, key: str) -> MemoryRecord | None:
        """Read a record if not expired."""
        record = self._data.get(namespace, {}).get(key)
        if record is None:
            return None
        if record.is_expired():
            self._data[namespace].pop(key, None)
            return None
        return record

    def audit_log(self) -> list[dict[str, Any]]:
        """Return memory write audit entries."""
        return list(self._audit)


@dataclass
class VersionedMemoryStore:
    """Versioned long-term memory store."""

    _versions: dict[str, dict[str, list[MemoryRecord]]] = field(default_factory=dict, repr=False)
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def append(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        source: str = "unknown",
        confidence: float = 0.0,
        evidence_level: str = "unknown",
        lineage: list[str] | None = None,
    ) -> MemoryRecord:
        """Append a new version for a namespaced key."""
        keys = self._versions.setdefault(namespace, {})
        history = keys.setdefault(key, [])
        next_version = history[-1].version + 1 if history else 1
        record = MemoryRecord(
            namespace=namespace,
            key=key,
            value=value,
            version=next_version,
            source=source,
            confidence=confidence,
            evidence_level=evidence_level,
            lineage=lineage or [],
        )
        history.append(record)
        self._audit.append(
            {
                "event": "versioned_memory_append",
                "namespace": namespace,
                "key": key,
                "version": next_version,
                "at": datetime.utcnow().isoformat(),
            }
        )
        return record

    def latest(self, namespace: str, key: str) -> MemoryRecord | None:
        """Return latest version by key."""
        history = self._versions.get(namespace, {}).get(key, [])
        return history[-1] if history else None

    def versions(self, namespace: str, key: str) -> list[MemoryRecord]:
        """Return full version history."""
        return list(self._versions.get(namespace, {}).get(key, []))

    def audit_log(self) -> list[dict[str, Any]]:
        """Return versioned memory write audit entries."""
        return list(self._audit)


@dataclass
class ArtifactObjectStore:
    """Artifact store for larger generated outputs."""

    _objects: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict, repr=False)
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def put(self, namespace: str, object_id: str, payload: dict[str, Any]) -> None:
        """Save object payload under a namespace."""
        self._objects.setdefault(namespace, {})[object_id] = payload
        self._audit.append(
            {
                "event": "artifact_put",
                "namespace": namespace,
                "object_id": object_id,
                "at": datetime.utcnow().isoformat(),
            }
        )

    def get(self, namespace: str, object_id: str) -> dict[str, Any] | None:
        """Read object payload."""
        return self._objects.get(namespace, {}).get(object_id)

    def audit_log(self) -> list[dict[str, Any]]:
        """Return artifact write audit entries."""
        return list(self._audit)
