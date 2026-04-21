"""Official snapshot versioning and diff helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from admitpilot.agents.aie.schemas import OfficialAdmissionRecord


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    """Structured diff between two official record versions."""

    school: str
    program: str
    cycle: str
    page_type: str
    previous_version_id: str
    current_version_id: str
    change_type: str
    changed_fields: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "school": self.school,
            "program": self.program,
            "cycle": self.cycle,
            "page_type": self.page_type,
            "previous_version_id": self.previous_version_id,
            "current_version_id": self.current_version_id,
            "change_type": self.change_type,
            "changed_fields": list(self.changed_fields),
        }


def build_content_hash(content: str, extracted_fields: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "content": content,
            "extracted_fields": extracted_fields,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_identity(record: OfficialAdmissionRecord) -> str:
    return f"{record.school}:{record.program}:{record.cycle}:{record.page_type}"


def version_id_for(record: OfficialAdmissionRecord) -> str:
    return f"{record_identity(record)}:{record.content_hash[:12]}"


def diff_official_record(
    previous: OfficialAdmissionRecord | None, current: OfficialAdmissionRecord
) -> tuple[OfficialAdmissionRecord, SnapshotDiff | None]:
    if previous is None:
        current.version_id = version_id_for(current)
        current.change_type = "new"
        current.changed_fields = sorted(current.extracted_fields.keys())
        current.is_policy_change = bool(current.changed_fields)
        current.delta_summary = "initial official snapshot captured"
        return current, None
    if previous.content_hash == current.content_hash:
        current.version_id = previous.version_id
        current.change_type = "unchanged"
        current.changed_fields = []
        current.is_policy_change = False
        current.delta_summary = "official content unchanged"
        return current, None
    changed_fields = _changed_fields(previous.extracted_fields, current.extracted_fields)
    current.version_id = version_id_for(current)
    current.change_type = "updated"
    current.changed_fields = changed_fields
    current.is_policy_change = bool(changed_fields)
    current.delta_summary = ", ".join(changed_fields) if changed_fields else "content updated"
    diff = SnapshotDiff(
        school=current.school,
        program=current.program,
        cycle=current.cycle,
        page_type=current.page_type,
        previous_version_id=previous.version_id,
        current_version_id=current.version_id,
        change_type=current.change_type,
        changed_fields=changed_fields,
    )
    return current, diff


def _changed_fields(
    previous_fields: dict[str, Any], current_fields: dict[str, Any]
) -> list[str]:
    keys = set(previous_fields) | set(current_fields)
    changed = [
        key
        for key in sorted(keys)
        if json.dumps(previous_fields.get(key), default=str, ensure_ascii=False, sort_keys=True)
        != json.dumps(current_fields.get(key), default=str, ensure_ascii=False, sort_keys=True)
    ]
    return changed
