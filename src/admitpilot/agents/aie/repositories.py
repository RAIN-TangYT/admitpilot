"""Snapshot repository abstractions and in-memory implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, TypeVar

from admitpilot.agents.aie.schemas import CaseSnapshot, OfficialCycleSnapshot

T = TypeVar("T")


@dataclass
class _CacheEntry:
    value: object
    expires_at: datetime


class OfficialSnapshotRepository(Protocol):
    """Repository for official snapshots."""

    def get(self, key: str, as_of: datetime) -> OfficialCycleSnapshot | None:
        """Read a non-expired snapshot by key."""

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        """Persist snapshot with expiration."""


class CaseSnapshotRepository(Protocol):
    """Repository for case snapshots."""

    def get(self, key: str, as_of: datetime) -> CaseSnapshot | None:
        """Read a non-expired case snapshot by key."""

    def save(self, key: str, value: CaseSnapshot, expires_at: datetime) -> None:
        """Persist case snapshot with expiration."""


@dataclass
class _InMemoryTTLRepository:
    _entries: dict[str, _CacheEntry] = field(default_factory=dict)

    def _get(self, key: str, as_of: datetime, expected_type: type[T]) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if as_of >= entry.expires_at:
            self._entries.pop(key, None)
            return None
        if not isinstance(entry.value, expected_type):
            return None
        return entry.value

    def _save(self, key: str, value: object, expires_at: datetime) -> None:
        self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)


@dataclass
class InMemoryOfficialSnapshotRepository(_InMemoryTTLRepository):
    """TTL repository for official snapshots."""

    def get(self, key: str, as_of: datetime) -> OfficialCycleSnapshot | None:
        return self._get(key=key, as_of=as_of, expected_type=OfficialCycleSnapshot)

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        self._save(key=key, value=value, expires_at=expires_at)


@dataclass
class InMemoryCaseSnapshotRepository(_InMemoryTTLRepository):
    """TTL repository for case snapshots."""

    def get(self, key: str, as_of: datetime) -> CaseSnapshot | None:
        return self._get(key=key, as_of=as_of, expected_type=CaseSnapshot)

    def save(self, key: str, value: CaseSnapshot, expires_at: datetime) -> None:
        self._save(key=key, value=value, expires_at=expires_at)
