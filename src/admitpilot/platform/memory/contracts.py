"""Memory 层接口定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class MemoryNamespace(StrEnum):
    """Memory 命名空间。"""

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
    """通用版本化记录。"""

    tenant_id: str
    user_id: str
    application_id: str
    cycle: str
    namespace: MemoryNamespace
    version_id: str
    as_of_date: str
    payload: dict[str, Any]
    lineage: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class SessionMemoryStore(Protocol):
    """会话内存接口（建议 Redis）。"""

    def get(self, key: str) -> dict[str, Any] | None:
        """读取会话状态。"""

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        """写入会话状态。"""


class VersionedMemoryStore(Protocol):
    """版本化结构化存储接口（建议 PostgreSQL）。"""

    def upsert(self, record: VersionedRecord) -> str:
        """写入并返回版本号。"""

    def get_latest(
        self,
        namespace: MemoryNamespace,
        tenant_id: str,
        user_id: str,
        application_id: str,
        cycle: str,
    ) -> VersionedRecord | None:
        """读取最新版本。"""

    def get_by_version(self, namespace: MemoryNamespace, version_id: str) -> VersionedRecord | None:
        """按版本读取。"""


class ArtifactObjectStore(Protocol):
    """大文本/原文对象存储接口（建议 S3/MinIO）。"""

    def put_text(self, key: str, content: str) -> str:
        """写入文本并返回对象引用。"""

    def get_text(self, key: str) -> str:
        """读取文本。"""


@dataclass(slots=True)
class MemoryTopology:
    """Memory 部署拓扑。"""

    session_backend: str
    relational_backend: str
    vector_backend: str
    object_backend: str
    audit_backend: str
    todo: tuple[str, ...] = field(default_factory=tuple)


def default_memory_topology() -> MemoryTopology:
    """默认拓扑建议。"""
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
