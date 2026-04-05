"""Memory 适配器初始化定义。

提供内存版本的适配器，便于本地开发与联调。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from admitpilot.platform.memory.contracts import (
    ArtifactObjectStore,
    MemoryNamespace,
    SessionMemoryStore,
    VersionedMemoryStore,
    VersionedRecord,
)


@dataclass(slots=True)
class _SessionValue:
    value: dict[str, object]
    expires_at: datetime


@dataclass(slots=True)
class InMemorySessionMemoryStore(SessionMemoryStore):
    """会话内存适配器（开发用途）。"""

    data: dict[str, _SessionValue] = field(default_factory=dict)

    def get(self, key: str) -> dict[str, object] | None:
        stored = self.data.get(key)
        if stored is None:
            return None
        if datetime.now(UTC) >= stored.expires_at:
            self.data.pop(key, None)
            return None
        return dict(stored.value)

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self.data[key] = _SessionValue(value=dict(value), expires_at=expires_at)


@dataclass(slots=True)
class InMemoryVersionedMemoryStore(VersionedMemoryStore):
    """版本化内存适配器（开发用途）。"""

    records: dict[str, VersionedRecord] = field(default_factory=dict)
    latest_index: dict[tuple[MemoryNamespace, str, str, str, str], str] = field(
        default_factory=dict
    )

    def upsert(self, record: VersionedRecord) -> str:
        self.records[record.version_id] = record
        latest_key = (
            record.namespace,
            record.tenant_id,
            record.user_id,
            record.application_id,
            record.cycle,
        )
        self.latest_index[latest_key] = record.version_id
        return record.version_id

    def get_latest(
        self,
        namespace: MemoryNamespace,
        tenant_id: str,
        user_id: str,
        application_id: str,
        cycle: str,
    ) -> VersionedRecord | None:
        latest_key = (namespace, tenant_id, user_id, application_id, cycle)
        version = self.latest_index.get(latest_key)
        if version is None:
            return None
        return self.records.get(version)

    def get_by_version(self, namespace: MemoryNamespace, version_id: str) -> VersionedRecord | None:
        record = self.records.get(version_id)
        if record is None:
            return None
        if record.namespace != namespace:
            return None
        return record


@dataclass(slots=True)
class InMemoryArtifactObjectStore(ArtifactObjectStore):
    """文本对象存储适配器（开发用途）。"""

    storage: dict[str, str] = field(default_factory=dict)

    def put_text(self, key: str, content: str) -> str:
        self.storage[key] = content
        return key

    def get_text(self, key: str) -> str:
        return self.storage[key]


@dataclass(slots=True)
class MemoryAdapterBundle:
    """公共 memory 初始化产物。"""

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
    """构建默认 memory 适配器集合。"""

    return MemoryAdapterBundle(
        session_store=InMemorySessionMemoryStore(),
        versioned_store=InMemoryVersionedMemoryStore(),
        artifact_store=InMemoryArtifactObjectStore(),
    )
