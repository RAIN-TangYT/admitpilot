"""AIE 记忆仓储接口与默认内存实现。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from admitpilot.agents.aie.schemas import CaseSnapshot, OfficialCycleSnapshot


@dataclass(slots=True)
class _SnapshotCacheEntry:
    """带过期时间的缓存条目。"""

    value: OfficialCycleSnapshot | CaseSnapshot
    expires_at: datetime


class OfficialSnapshotRepository(Protocol):
    """官方快照仓储接口。"""

    def get(self, key: str, as_of: datetime) -> OfficialCycleSnapshot | None:
        """读取官方快照。"""

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        """写入官方快照。"""


class CaseSnapshotRepository(Protocol):
    """案例快照仓储接口。"""

    def get(self, key: str, as_of: datetime) -> CaseSnapshot | None:
        """读取案例快照。"""

    def save(self, key: str, value: CaseSnapshot, expires_at: datetime) -> None:
        """写入案例快照。"""


class InMemoryOfficialSnapshotRepository:
    """官方快照内存仓储。"""

    def __init__(self) -> None:
        self._store: dict[str, _SnapshotCacheEntry] = {}

    def get(self, key: str, as_of: datetime) -> OfficialCycleSnapshot | None:
        entry = self._store.get(key)
        if entry is None or entry.expires_at <= as_of:
            return None
        value = entry.value
        if isinstance(value, OfficialCycleSnapshot):
            return value
        return None

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        self._store[key] = _SnapshotCacheEntry(value=value, expires_at=expires_at)


class InMemoryCaseSnapshotRepository:
    """案例快照内存仓储。"""

    def __init__(self) -> None:
        self._store: dict[str, _SnapshotCacheEntry] = {}

    def get(self, key: str, as_of: datetime) -> CaseSnapshot | None:
        entry = self._store.get(key)
        if entry is None or entry.expires_at <= as_of:
            return None
        value = entry.value
        if isinstance(value, CaseSnapshot):
            return value
        return None

    def save(self, key: str, value: CaseSnapshot, expires_at: datetime) -> None:
        self._store[key] = _SnapshotCacheEntry(value=value, expires_at=expires_at)
