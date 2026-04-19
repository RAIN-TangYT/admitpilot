"""Case-data normalization pipeline for AIE."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from admitpilot.agents.aie.schemas import CaseRecord
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG, AdmissionsCatalog
from admitpilot.platform.common.time import ensure_utc

_SOURCE_SITE_SCORES = {
    "gradcafe": 0.72,
    "official_forum": 0.8,
    "student_blog": 0.58,
    "community": 0.64,
}


def normalize_case_records(
    raw_records: Iterable[dict[str, Any]],
    *,
    schools: list[str],
    program: str,
    cycle: str,
    as_of_date: date,
    catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
) -> list[CaseRecord]:
    """Normalize raw case payloads into deterministic CaseRecord entries."""

    allowed_schools = set(catalog.normalize_school_scope(schools))
    normalized_program = catalog.normalize_program_code(program) or "MSCS"
    records: list[CaseRecord] = []
    seen: set[str] = set()
    for item in raw_records:
        school = catalog.normalize_school_code(str(item.get("school", "")))
        if school is None or school not in allowed_schools:
            continue
        record_program = catalog.normalize_program_code(
            str(item.get("program", normalized_program))
        )
        if record_program != normalized_program:
            continue
        captured_at = _parse_captured_at(item.get("captured_at"))
        if captured_at is None:
            continue
        background_summary = _background_summary(item)
        outcome = str(item.get("outcome", "")).strip().lower()
        if not background_summary or not outcome:
            continue
        source_type = str(item.get("source_type", "community")).strip().lower() or "community"
        source_url = str(item.get("source_url", "")).strip()
        evidence_completeness = _evidence_completeness(item)
        cross_source_consistency = _cross_source_consistency(item)
        freshness_score = _freshness_score(captured_at, as_of_date)
        source_site_score = _SOURCE_SITE_SCORES.get(source_type, 0.55)
        confidence = round(
            0.3 * source_site_score
            + 0.25 * evidence_completeness
            + 0.2 * cross_source_consistency
            + 0.25 * freshness_score,
            4,
        )
        fingerprint = _candidate_fingerprint(
            school=school,
            program=normalized_program,
            cycle=str(item.get("cycle", cycle) or cycle),
            source_url=source_url,
            background_summary=background_summary,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        records.append(
            CaseRecord(
                candidate_fingerprint=fingerprint,
                school=school,
                program=normalized_program,
                cycle=str(item.get("cycle", cycle) or cycle),
                source_type=source_type,
                source_url=source_url,
                background_summary=background_summary,
                outcome=outcome,
                captured_at=captured_at,
                source_site_score=source_site_score,
                evidence_completeness=evidence_completeness,
                cross_source_consistency=cross_source_consistency,
                freshness_score=freshness_score,
                confidence=confidence,
                credibility_label=_credibility_label(confidence),
            )
        )
    return records


def _parse_captured_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    return ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


def _background_summary(item: dict[str, Any]) -> str:
    pieces: list[str] = []
    if gpa := str(item.get("gpa", "")).strip():
        pieces.append(f"GPA {gpa}")
    if language := str(item.get("ielts", "") or item.get("toefl", "")).strip():
        pieces.append(f"Language {language}")
    experiences = item.get("experiences", [])
    if isinstance(experiences, list) and experiences:
        pieces.append("; ".join(str(entry).strip() for entry in experiences if str(entry).strip()))
    if statement := str(item.get("background_summary", "")).strip():
        pieces.append(statement)
    return " | ".join(piece for piece in pieces if piece)


def _evidence_completeness(item: dict[str, Any]) -> float:
    checks = [
        bool(str(item.get("gpa", "")).strip()),
        bool(str(item.get("ielts", "") or item.get("toefl", "")).strip()),
        bool(item.get("experiences")),
        bool(item.get("evidence")),
        bool(str(item.get("outcome", "")).strip()),
    ]
    return round(sum(checks) / len(checks), 4)


def _cross_source_consistency(item: dict[str, Any]) -> float:
    corroborated_count = int(item.get("corroborated_count", 0) or 0)
    return min(1.0, round(0.55 + corroborated_count * 0.12, 4))


def _freshness_score(captured_at: datetime, as_of_date: date) -> float:
    age_days = max((as_of_date - captured_at.date()).days, 0)
    if age_days <= 30:
        return 0.95
    if age_days <= 90:
        return 0.82
    if age_days <= 180:
        return 0.68
    return 0.52


def _credibility_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _candidate_fingerprint(
    *,
    school: str,
    program: str,
    cycle: str,
    source_url: str,
    background_summary: str,
) -> str:
    digest = hashlib.sha256(
        f"{school}|{program}|{cycle}|{source_url}|{background_summary}".encode()
    ).hexdigest()
    return f"case-{digest[:12]}"
