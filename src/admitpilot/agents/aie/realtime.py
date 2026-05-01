"""Runtime helpers for live-first official retrieval with safe fallback."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from admitpilot.agents.aie.gateways import OfficialSourceGateway
from admitpilot.agents.aie.schemas import OfficialAdmissionRecord
from admitpilot.agents.aie.snapshots import build_content_hash

_REQUIRED_FIELDS_BY_PAGE_TYPE = {
    "requirements": ("language_requirements", "required_materials", "academic_requirement"),
    "deadline": ("application_deadline",),
}
_IELTS_PATTERN = re.compile(
    r"IELTS\s*([0-9]+(?:\.[0-9])?)",
    flags=re.IGNORECASE,
)
_TOEFL_PATTERN = re.compile(
    r"TOEFL(?:\s|-)?IBT?\s*([0-9]{2,3})|TOEFL\s*([0-9]{2,3})",
    flags=re.IGNORECASE,
)
_DUOLINGO_PATTERN = re.compile(
    r"DUOLINGO(?:\s+ENGLISH\s+TEST)?\s*([0-9]{2,3})",
    flags=re.IGNORECASE,
)
_EXPERIENCE_PATTERN = re.compile(
    r"(?:at least|minimum(?:\s+of)?|not less than|must have)\s+(\d+(?:\.\d+)?)\s+years?",
    flags=re.IGNORECASE,
)
_ACADEMIC_NOISE_MARKERS = (
    "_wpemoji",
    "wp-emoji-release",
    "function(",
    "display: inline",
    ".js",
)


class HardThresholdRuleSyncer:
    """Update only the hard_thresholds section from trusted official facts."""

    def __init__(self, rules_dir: Path) -> None:
        self.rules_dir = rules_dir

    def sync(self, records: list[OfficialAdmissionRecord]) -> bool:
        if not records:
            return False
        school = records[0].school
        program = records[0].program
        rule_path = self._find_rule_path(school=school, program=program)
        if rule_path is None or not rule_path.exists():
            return False
        payload = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        current = payload.get("hard_thresholds")
        if not isinstance(current, dict):
            return False
        derived = self._derive_thresholds(records)
        if not derived:
            return False
        changed = False
        updated = dict(current)
        for key, value in derived.items():
            normalized = self._dump_number(value)
            if updated.get(key) != normalized:
                updated[key] = normalized
                changed = True
        if not changed:
            return False
        payload["hard_thresholds"] = updated
        rule_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        return True

    def _find_rule_path(self, school: str, program: str) -> Path | None:
        if not self.rules_dir.exists():
            return None
        for path in sorted(self.rules_dir.glob("*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            if str(payload.get("school", "")).strip().upper() != school:
                continue
            if str(payload.get("program", "")).strip() != program:
                continue
            return path
        return None

    def _derive_thresholds(self, records: list[OfficialAdmissionRecord]) -> dict[str, float]:
        merged_fields: dict[str, Any] = {}
        combined_text_parts: list[str] = []
        for record in sorted(records, key=lambda item: item.page_type):
            combined_text_parts.append(record.content)
            for key, value in record.extracted_fields.items():
                if value in ("", [], None):
                    continue
                merged_fields[key] = value
        thresholds: dict[str, float] = {}
        gpa = _coerce_gpa(merged_fields.get("minimum_gpa"))
        if gpa is not None:
            thresholds["gpa_min"] = gpa
        language_requirements = _sanitize_language_requirements(
            merged_fields.get("language_requirements", [])
        )
        for item in language_requirements:
            if match := _IELTS_PATTERN.fullmatch(item):
                thresholds["ielts_min"] = float(match.group(1))
            elif match := _TOEFL_PATTERN.fullmatch(item):
                score_text = match.group(1) or match.group(2)
                if score_text is not None:
                    thresholds["toefl_min"] = float(score_text)
            elif match := _DUOLINGO_PATTERN.fullmatch(item):
                thresholds["duolingo_min"] = float(match.group(1))
        combined_text = "\n".join(combined_text_parts)
        academic_requirement = str(merged_fields.get("academic_requirement", "")).strip()
        experience_years = _extract_experience_years(
            academic_requirement or combined_text
        )
        if experience_years is not None:
            thresholds["experience_years_min"] = experience_years
        return thresholds

    def _dump_number(self, value: float) -> int | float:
        return int(value) if float(value).is_integer() else float(value)


class RealtimeOfficialSourceGateway:
    """Use live records first, then fall back to persisted official-library fields."""

    def __init__(
        self,
        *,
        live_gateway: OfficialSourceGateway,
        library_gateway: OfficialSourceGateway,
        rule_syncer: HardThresholdRuleSyncer | None = None,
    ) -> None:
        self.live_gateway = live_gateway
        self.library_gateway = library_gateway
        self.rule_syncer = rule_syncer

    def has_cycle_release(
        self,
        school: str,
        program: str,
        cycle: str,
        as_of_date: date,
    ) -> bool:
        return self.live_gateway.has_cycle_release(
            school=school,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
        ) or self.library_gateway.has_cycle_release(
            school=school,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
        )

    def fetch_cycle_records(
        self,
        school: str,
        program: str,
        cycle: str,
        query: str,
        as_of_date: date,
    ) -> list[OfficialAdmissionRecord]:
        live_records = self.live_gateway.fetch_cycle_records(
            school=school,
            program=program,
            cycle=cycle,
            query=query,
            as_of_date=as_of_date,
        )
        library_records = self.library_gateway.fetch_cycle_records(
            school=school,
            program=program,
            cycle=cycle,
            query=query,
            as_of_date=as_of_date,
        )
        live_by_page_type = {item.page_type: item for item in live_records}
        library_by_page_type = {item.page_type: item for item in library_records}
        resolved: list[OfficialAdmissionRecord] = []
        page_types = set(live_by_page_type) | set(library_by_page_type)
        for page_type in sorted(page_types):
            merged = self._merge_record(
                live_record=live_by_page_type.get(page_type),
                library_record=library_by_page_type.get(page_type),
            )
            if merged is not None:
                resolved.append(merged)
        if self.rule_syncer is not None:
            self.rule_syncer.sync(resolved)
        return resolved

    def _merge_record(
        self,
        live_record: OfficialAdmissionRecord | None,
        library_record: OfficialAdmissionRecord | None,
    ) -> OfficialAdmissionRecord | None:
        if live_record is None:
            return library_record
        live_fields = _sanitize_extracted_fields(
            live_record.extracted_fields,
            page_type=live_record.page_type,
            cycle=live_record.cycle,
        )
        library_fields = (
            _sanitize_extracted_fields(
                library_record.extracted_fields,
                page_type=library_record.page_type,
                cycle=library_record.cycle,
            )
            if library_record is not None
            else {}
        )
        trusted_fields = dict(library_fields)
        trusted_fields.update(live_fields)
        required_fields = _REQUIRED_FIELDS_BY_PAGE_TYPE.get(live_record.page_type, ())
        if not trusted_fields and library_record is not None:
            return library_record
        if any(field not in trusted_fields for field in required_fields) and library_record is not None:
            if not live_fields:
                return library_record
        fallback_fields = [field for field in required_fields if field not in live_fields and field in library_fields]
        if not trusted_fields:
            return None
        confidence_penalty = min(0.12, 0.04 * len(fallback_fields))
        parse_confidence = max(0.4, live_record.parse_confidence - confidence_penalty)
        confidence = max(0.45, live_record.confidence - confidence_penalty)
        source_hash = live_record.source_hash or live_record.content_hash
        content_hash = build_content_hash(content=live_record.content, extracted_fields=trusted_fields)
        delta_summary = live_record.delta_summary
        if fallback_fields:
            delta_summary = (
                f"{delta_summary}; field_fallback={','.join(sorted(fallback_fields))}"
                if delta_summary
                else f"field_fallback={','.join(sorted(fallback_fields))}"
            )
        return replace(
            live_record,
            extracted_fields=trusted_fields,
            parse_confidence=parse_confidence,
            confidence=confidence,
            content_hash=content_hash,
            source_hash=source_hash,
            delta_summary=delta_summary,
        )


def _sanitize_extracted_fields(
    fields: dict[str, Any],
    *,
    page_type: str,
    cycle: str,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    deadline = _sanitize_deadline(fields.get("application_deadline"), cycle=cycle)
    if deadline is not None:
        sanitized["application_deadline"] = deadline
    if value := _sanitize_text(fields.get("deadline_round"), minimum_length=3, maximum_length=64):
        sanitized["deadline_round"] = value
    gpa = _coerce_gpa(fields.get("minimum_gpa"))
    if gpa is not None:
        sanitized["minimum_gpa"] = _format_decimal(gpa)
    language_requirements = _sanitize_language_requirements(
        fields.get("language_requirements", [])
    )
    if language_requirements:
        sanitized["language_requirements"] = language_requirements
    required_materials = _sanitize_required_materials(fields.get("required_materials", []))
    if required_materials:
        sanitized["required_materials"] = required_materials
    academic_requirement = _sanitize_academic_requirement(
        fields.get("academic_requirement")
    )
    if academic_requirement:
        sanitized["academic_requirement"] = academic_requirement
    if page_type == "deadline" and "application_deadline" not in sanitized:
        return {}
    return sanitized


def _sanitize_deadline(value: object, *, cycle: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        return None
    try:
        cycle_year = int(cycle)
    except ValueError:
        return parsed.isoformat()
    if not (cycle_year - 1 <= parsed.year <= cycle_year + 1):
        return None
    return parsed.isoformat()


def _sanitize_language_requirements(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    sanitized: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = " ".join(str(item).split())
        if not normalized:
            continue
        if match := _IELTS_PATTERN.fullmatch(normalized):
            score = float(match.group(1))
            if not (0.0 <= score <= 9.0):
                continue
            normalized = f"IELTS {_format_decimal(score)}"
        elif match := _TOEFL_PATTERN.fullmatch(normalized):
            score_text = match.group(1) or match.group(2)
            if score_text is None:
                continue
            score = int(score_text)
            if not (60 <= score <= 677):
                continue
            normalized = f"TOEFL {score}"
        elif match := _DUOLINGO_PATTERN.fullmatch(normalized):
            score = int(match.group(1))
            if not (10 <= score <= 160):
                continue
            normalized = f"Duolingo {score}"
        else:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        sanitized.append(normalized)
    return sanitized


def _sanitize_required_materials(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    sanitized: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = _sanitize_text(item, minimum_length=2, maximum_length=80)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        sanitized.append(normalized)
    return sanitized


def _sanitize_academic_requirement(value: object) -> str | None:
    normalized = _sanitize_text(value, minimum_length=20, maximum_length=500)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if any(marker in lowered for marker in _ACADEMIC_NOISE_MARKERS):
        return None
    return normalized


def _sanitize_text(
    value: object,
    *,
    minimum_length: int,
    maximum_length: int,
) -> str | None:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        return None
    if len(normalized) < minimum_length or len(normalized) > maximum_length:
        return None
    return normalized


def _coerce_gpa(value: object) -> float | None:
    try:
        numeric = float(str(value).strip())
    except ValueError:
        return None
    if not (0.0 < numeric <= 4.3):
        return None
    return round(numeric, 2)


def _extract_experience_years(text: str) -> float | None:
    match = _EXPERIENCE_PATTERN.search(text)
    if match is None:
        return None
    return float(match.group(1))


def _format_decimal(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
