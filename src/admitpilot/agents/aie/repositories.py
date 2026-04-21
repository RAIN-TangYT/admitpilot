"""Snapshot repository abstractions and in-memory implementations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar, cast

from admitpilot.agents.aie.schemas import (
    CaseSnapshot,
    OfficialAdmissionRecord,
    OfficialCycleSnapshot,
)
from admitpilot.platform.common.time import ensure_utc

T = TypeVar("T")
OfficialSnapshotStatus = Literal["official_found", "predicted", "mixed"]


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

    def get_latest_record(self, key: str) -> OfficialAdmissionRecord | None:
        """Read the latest stored official record version."""

    def save_record_version(self, key: str, record: OfficialAdmissionRecord) -> None:
        """Append a new official record version."""

    def list_record_versions(self, key: str) -> list[OfficialAdmissionRecord]:
        """List all stored official record versions."""

    def list_latest_cycle_records(
        self,
        school: str,
        program: str,
        cycle: str,
    ) -> list[OfficialAdmissionRecord]:
        """List the latest official record per page type for one cycle."""


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

    _history: dict[str, list[OfficialAdmissionRecord]] = field(default_factory=dict)

    def get(self, key: str, as_of: datetime) -> OfficialCycleSnapshot | None:
        return self._get(key=key, as_of=as_of, expected_type=OfficialCycleSnapshot)

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        self._save(key=key, value=value, expires_at=expires_at)

    def get_latest_record(self, key: str) -> OfficialAdmissionRecord | None:
        history = self._history.get(key, [])
        return history[-1] if history else None

    def save_record_version(self, key: str, record: OfficialAdmissionRecord) -> None:
        self._history.setdefault(key, []).append(record)

    def list_record_versions(self, key: str) -> list[OfficialAdmissionRecord]:
        return list(self._history.get(key, []))

    def list_latest_cycle_records(
        self,
        school: str,
        program: str,
        cycle: str,
    ) -> list[OfficialAdmissionRecord]:
        latest_records: list[OfficialAdmissionRecord] = []
        for records in self._history.values():
            if not records:
                continue
            latest = records[-1]
            if latest.school != school or latest.program != program or latest.cycle != cycle:
                continue
            latest_records.append(latest)
        return sorted(latest_records, key=lambda item: item.page_type)


@dataclass
class InMemoryCaseSnapshotRepository(_InMemoryTTLRepository):
    """TTL repository for case snapshots."""

    def get(self, key: str, as_of: datetime) -> CaseSnapshot | None:
        return self._get(key=key, as_of=as_of, expected_type=CaseSnapshot)

    def save(self, key: str, value: CaseSnapshot, expires_at: datetime) -> None:
        self._save(key=key, value=value, expires_at=expires_at)


@dataclass(slots=True)
class JsonOfficialSnapshotRepository(InMemoryOfficialSnapshotRepository):
    """Persist official snapshot cache and history to a JSON file."""

    path: Path = field(default_factory=lambda: Path("data/official_library/official_library.json"))

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._load()

    def save(self, key: str, value: OfficialCycleSnapshot, expires_at: datetime) -> None:
        InMemoryOfficialSnapshotRepository.save(
            self,
            key=key,
            value=value,
            expires_at=expires_at,
        )
        self._persist()

    def save_record_version(self, key: str, record: OfficialAdmissionRecord) -> None:
        InMemoryOfficialSnapshotRepository.save_record_version(
            self,
            key=key,
            record=record,
        )
        self._persist()

    def _persist(self) -> None:
        compact_entries = self._compact_official_entries()
        payload = {
            "entries": {
                key: {
                    "value": self._serialize_snapshot(entry.value),
                    "expires_at": ensure_utc(entry.expires_at).isoformat(),
                }
                for key, entry in compact_entries.items()
                if isinstance(entry.value, OfficialCycleSnapshot)
            },
            "history": {
                key: [self._serialize_record(record) for record in records]
                for key, records in self._history.items()
            },
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _compact_official_entries(self) -> dict[str, _CacheEntry]:
        """Keep only the latest snapshot per school/program/cycle in persisted cache."""

        latest_by_scope: dict[tuple[str, str, str], tuple[str, _CacheEntry]] = {}
        compacted: dict[str, _CacheEntry] = {}
        for key, entry in self._entries.items():
            if not isinstance(entry.value, OfficialCycleSnapshot):
                compacted[key] = entry
                continue
            snapshot = entry.value
            scope_key = (snapshot.school, snapshot.program, snapshot.cycle)
            existing = latest_by_scope.get(scope_key)
            if existing is None:
                latest_by_scope[scope_key] = (key, entry)
                continue
            existing_snapshot = cast(OfficialCycleSnapshot, existing[1].value)
            if snapshot.as_of_date > existing_snapshot.as_of_date:
                latest_by_scope[scope_key] = (key, entry)
                continue
            if (
                snapshot.as_of_date == existing_snapshot.as_of_date
                and ensure_utc(entry.expires_at) > ensure_utc(existing[1].expires_at)
            ):
                latest_by_scope[scope_key] = (key, entry)
        for key, entry in latest_by_scope.values():
            compacted[key] = entry
        self._entries = compacted
        return compacted

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return
        raw_entries = payload.get("entries", {})
        raw_history = payload.get("history", {})
        if not isinstance(raw_entries, dict) or not isinstance(raw_history, dict):
            return
        for key, raw_entry in raw_entries.items():
            if not isinstance(raw_entry, dict):
                continue
            raw_value = raw_entry.get("value")
            raw_expires_at = raw_entry.get("expires_at")
            if not isinstance(raw_value, dict) or not isinstance(raw_expires_at, str):
                continue
            value = self._deserialize_snapshot(raw_value)
            expires_at = ensure_utc(datetime.fromisoformat(raw_expires_at))
            self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
        for key, records in raw_history.items():
            if not isinstance(records, list):
                continue
            self._history[key] = [
                self._deserialize_record(item) for item in records if isinstance(item, dict)
            ]

    def _serialize_snapshot(self, snapshot: OfficialCycleSnapshot) -> dict[str, object]:
        data = asdict(snapshot)
        data["as_of_date"] = snapshot.as_of_date.isoformat()
        data["expires_at"] = (
            ensure_utc(snapshot.expires_at).isoformat()
            if snapshot.expires_at is not None
            else None
        )
        data["entries"] = [self._serialize_record(record) for record in snapshot.entries]
        return data

    def _serialize_record(self, record: OfficialAdmissionRecord) -> dict[str, object]:
        data = asdict(record)
        data["published_date"] = record.published_date.isoformat()
        data["effective_date"] = record.effective_date.isoformat()
        data["fetched_at"] = ensure_utc(record.fetched_at).isoformat()
        return data

    def _deserialize_snapshot(self, payload: dict[str, object]) -> OfficialCycleSnapshot:
        raw_entries = payload.get("entries", [])
        entry_payloads = raw_entries if isinstance(raw_entries, list) else []
        entries = [
            self._deserialize_record(item)
            for item in entry_payloads
            if isinstance(item, dict)
        ]
        expires_at_value = payload.get("expires_at")
        expires_at = (
            ensure_utc(datetime.fromisoformat(str(expires_at_value)))
            if expires_at_value
            else None
        )
        raw_prediction_basis = payload.get("prediction_basis", [])
        prediction_basis = (
            [str(item) for item in raw_prediction_basis]
            if isinstance(raw_prediction_basis, list)
            else []
        )
        raw_source_urls = payload.get("source_urls", {})
        source_urls = (
            {
                str(key): str(value).strip()
                for key, value in raw_source_urls.items()
                if str(key).strip() and str(value).strip()
            }
            if isinstance(raw_source_urls, dict)
            else {}
        )
        return OfficialCycleSnapshot(
            school=str(payload["school"]),
            program=str(payload["program"]),
            cycle=str(payload["cycle"]),
            as_of_date=datetime.fromisoformat(f"{payload['as_of_date']}T00:00:00+00:00").date(),
            status=cast(OfficialSnapshotStatus, str(payload["status"])),
            confidence=float(cast(Any, payload["confidence"])),
            is_predicted=bool(payload["is_predicted"]),
            entries=entries,
            source_urls=source_urls,
            prediction_basis=prediction_basis,
            update_released=bool(payload.get("update_released", False)),
            expires_at=expires_at,
        )

    def _deserialize_record(self, payload: dict[str, object]) -> OfficialAdmissionRecord:
        raw_extracted_fields = payload.get("extracted_fields", {})
        extracted_fields = (
            dict(cast(dict[str, object], raw_extracted_fields))
            if isinstance(raw_extracted_fields, dict)
            else {}
        )
        raw_changed_fields = payload.get("changed_fields", [])
        changed_fields = (
            [str(item) for item in raw_changed_fields]
            if isinstance(raw_changed_fields, list)
            else []
        )
        return OfficialAdmissionRecord(
            school=str(payload["school"]),
            program=str(payload["program"]),
            cycle=str(payload["cycle"]),
            page_type=str(payload["page_type"]),
            source_url=str(payload["source_url"]),
            content=str(payload["content"]),
            published_date=datetime.fromisoformat(
                f"{payload['published_date']}T00:00:00+00:00"
            ).date(),
            effective_date=datetime.fromisoformat(
                f"{payload['effective_date']}T00:00:00+00:00"
            ).date(),
            fetched_at=ensure_utc(datetime.fromisoformat(str(payload["fetched_at"]))),
            content_hash=str(payload["content_hash"]),
            quality_score=float(cast(Any, payload["quality_score"])),
            confidence=float(cast(Any, payload["confidence"])),
            extracted_fields=extracted_fields,
            parse_confidence=float(cast(Any, payload.get("parse_confidence", 0.0))),
            source_type=str(payload.get("source_type", "official")),
            source_credibility=str(payload.get("source_credibility", "official_primary")),
            version_id=str(payload.get("version_id", "")),
            source_hash=str(payload.get("source_hash", "")),
            is_policy_change=bool(payload.get("is_policy_change", False)),
            change_type=str(payload.get("change_type", "updated")),
            changed_fields=changed_fields,
            delta_summary=str(payload.get("delta_summary", "")),
        )
