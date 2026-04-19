"""In-memory adapters used by the platform bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from admitpilot.platform.memory.contracts import MemoryNamespace, MemoryRecord, VersionedRecord


@dataclass(slots=True)
class _SessionValue:
    value: dict[str, Any]
    expires_at: datetime


@dataclass(slots=True)
class SessionMemoryStore:
    """Namespace-isolated short-term memory with legacy compatibility helpers."""

    ttl_hours: int = 12
    _data: dict[str, dict[str, MemoryRecord]] = field(default_factory=dict, repr=False)
    _compat_data: dict[str, _SessionValue] = field(default_factory=dict, repr=False)
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

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._compat_data[key] = _SessionValue(
            value=dict(value),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        )

    def get(self, namespace: str, key: str | None = None) -> MemoryRecord | dict[str, Any] | None:
        if key is None:
            stored = self._compat_data.get(namespace)
            if stored is None:
                return None
            if datetime.utcnow() >= stored.expires_at:
                self._compat_data.pop(namespace, None)
                return None
            return dict(stored.value)
        record = self._data.get(namespace, {}).get(key)
        if record is None:
            return None
        if record.is_expired():
            self._data[namespace].pop(key, None)
            return None
        return record

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)


@dataclass(slots=True)
class VersionedMemoryStore:
    """Versioned long-term memory store with compatibility APIs."""

    _versions: dict[str, dict[str, list[MemoryRecord]]] = field(default_factory=dict, repr=False)
    _compat_records: dict[str, VersionedRecord] = field(default_factory=dict, repr=False)
    _latest_index: dict[tuple[MemoryNamespace, str, str, str, str], str] = field(
        default_factory=dict,
        repr=False,
    )
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
        history = self._versions.get(namespace, {}).get(key, [])
        return history[-1] if history else None

    def versions(self, namespace: str, key: str) -> list[MemoryRecord]:
        return list(self._versions.get(namespace, {}).get(key, []))

    def upsert(self, record: VersionedRecord) -> str:
        self._compat_records[record.version_id] = record
        latest_key = (
            record.namespace,
            record.tenant_id,
            record.user_id,
            record.application_id,
            record.cycle,
        )
        self._latest_index[latest_key] = record.version_id
        return record.version_id

    def get_latest(
        self,
        namespace: MemoryNamespace,
        tenant_id: str,
        user_id: str,
        application_id: str,
        cycle: str,
    ) -> VersionedRecord | None:
        version_id = self._latest_index.get((namespace, tenant_id, user_id, application_id, cycle))
        if version_id is None:
            return None
        return self._compat_records.get(version_id)

    def get_by_version(
        self,
        namespace: MemoryNamespace,
        version_id: str,
    ) -> VersionedRecord | None:
        record = self._compat_records.get(version_id)
        if record is None or record.namespace != namespace:
            return None
        return record

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)


@dataclass(slots=True)
class ArtifactObjectStore:
    """Artifact store for generated outputs."""

    _objects: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict, repr=False)
    _text_objects: dict[str, str] = field(default_factory=dict, repr=False)
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def put(self, namespace: str, object_id: str, payload: dict[str, Any]) -> None:
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
        return self._objects.get(namespace, {}).get(object_id)

    def put_text(self, key: str, content: str) -> str:
        self._text_objects[key] = content
        return key

    def get_text(self, key: str) -> str:
        return self._text_objects[key]

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)


@dataclass(slots=True)
class MemoryAdapterBundle:
    """Shared bundle returned by the compatibility bootstrap."""

    session_store: SessionMemoryStore
    versioned_store: VersionedMemoryStore
    artifact_store: ArtifactObjectStore
    todo: tuple[str, ...] = field(
        default_factory=lambda: (
            "替换为 Redis/PostgreSQL/S3 生产适配器",
            "接入 namespace ACL 与租户隔离",
            "接入审计与指标埋点",
        )
    )


def build_default_memory_adapters() -> MemoryAdapterBundle:
    return MemoryAdapterBundle(
        session_store=SessionMemoryStore(),
        versioned_store=VersionedMemoryStore(),
        artifact_store=ArtifactObjectStore(),
    )
