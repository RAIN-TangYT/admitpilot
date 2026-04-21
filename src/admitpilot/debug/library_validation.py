"""Validation helpers for official/case libraries."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

OFFICIAL_REQUIRED_FIELDS = {
    "school",
    "program",
    "cycle",
    "page_type",
    "source_url",
    "content",
    "published_date",
    "effective_date",
    "fetched_at",
    "source_hash",
    "quality_score",
    "confidence",
    "source_type",
    "source_credibility",
    "version_id",
    "is_policy_change",
    "change_type",
    "delta_summary",
}

CASE_REQUIRED_FIELDS = {
    "candidate_fingerprint",
    "school",
    "program",
    "cycle",
    "source_type",
    "source_url",
    "background_summary",
    "outcome",
    "captured_at",
    "source_site_score",
    "evidence_completeness",
    "cross_source_consistency",
    "freshness_score",
    "confidence",
    "credibility_label",
}


def validate_official_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(OFFICIAL_REQUIRED_FIELDS - set(record))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    _validate_common_metadata(record, errors)
    _validate_iso_date(record, "published_date", errors)
    _validate_iso_date(record, "effective_date", errors)
    _validate_iso_datetime(record, "fetched_at", errors)
    _validate_score(record, "quality_score", errors)
    _validate_score(record, "confidence", errors)
    if not isinstance(record.get("is_policy_change"), bool):
        errors.append("is_policy_change must be bool")
    return errors


def validate_case_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(CASE_REQUIRED_FIELDS - set(record))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    _validate_common_metadata(record, errors)
    _validate_iso_datetime(record, "captured_at", errors)
    _validate_score(record, "source_site_score", errors)
    _validate_score(record, "evidence_completeness", errors)
    _validate_score(record, "cross_source_consistency", errors)
    _validate_score(record, "freshness_score", errors)
    _validate_score(record, "confidence", errors)
    return errors


def is_predicted_official_record(record: dict[str, Any]) -> bool:
    source_type = str(record.get("source_type", "")).lower()
    change_type = str(record.get("change_type", "")).lower()
    content = str(record.get("content", "")).lower()
    return (
        "predicted" in source_type
        or "forecast" in source_type
        or "predicted" in change_type
        or "预测" in content
        or "predicted" in content
    )


def _validate_common_metadata(record: dict[str, Any], errors: list[str]) -> None:
    for field_name in ("school", "program", "cycle", "source_url"):
        if not str(record.get(field_name, "")).strip():
            errors.append(f"{field_name} must be non-empty string")


def _validate_iso_date(record: dict[str, Any], field_name: str, errors: list[str]) -> None:
    value = record.get(field_name)
    if not isinstance(value, str):
        errors.append(f"{field_name} must be ISO date string")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field_name} has invalid ISO date: {value}")


def _validate_iso_datetime(record: dict[str, Any], field_name: str, errors: list[str]) -> None:
    value = record.get(field_name)
    if not isinstance(value, str):
        errors.append(f"{field_name} must be ISO datetime string")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field_name} has invalid ISO datetime: {value}")


def _validate_score(record: dict[str, Any], field_name: str, errors: list[str]) -> None:
    value = record.get(field_name)
    if not isinstance(value, (int, float)):
        errors.append(f"{field_name} must be number")
        return
    numeric = float(value)
    if not (0.0 <= numeric <= 1.0):
        errors.append(f"{field_name} out of range [0,1]: {numeric}")
