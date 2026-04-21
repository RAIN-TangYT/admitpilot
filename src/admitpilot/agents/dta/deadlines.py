"""Deadline extraction and reverse-planning helpers."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from admitpilot.agents.dta.schemas import Milestone

_DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")


@dataclass(frozen=True)
class OfficialDeadline:
    school: str
    deadline_date: date
    source: str


def extract_official_deadlines(official_records: list[dict[str, Any]]) -> list[OfficialDeadline]:
    """Extract explicit YYYY-MM-DD deadlines from official records."""
    collected: list[OfficialDeadline] = []
    for record in official_records:
        school = str(record.get("school", "")).upper()
        source = str(record.get("source_url", ""))
        candidates = _candidate_deadline_strings(record)
        for value in candidates:
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                continue
            if school:
                collected.append(OfficialDeadline(school=school, deadline_date=parsed, source=source))
    earliest_by_school: dict[str, OfficialDeadline] = {}
    for item in collected:
        previous = earliest_by_school.get(item.school)
        if previous is None or item.deadline_date < previous.deadline_date:
            earliest_by_school[item.school] = item
    return list(earliest_by_school.values())


def apply_deadline_reverse_plan(
    milestones: list[Milestone],
    deadlines: list[OfficialDeadline],
    as_of_date: date,
    total_weeks: int,
) -> list[Milestone]:
    """Move milestone due_weeks based on earliest official deadline."""
    if not deadlines:
        return milestones
    earliest_deadline = min(item.deadline_date for item in deadlines)
    days_to_deadline = max((earliest_deadline - as_of_date).days, 1)
    deadline_week = min(total_weeks, max(1, math.ceil(days_to_deadline / 7)))

    due_by_key = {
        "scope_lock": max(1, deadline_week - 5),
        "doc_pack_v1": max(1, deadline_week - 3),
        "submission_batch_1": max(1, deadline_week - 1),
        "interview_prep": min(total_weeks, deadline_week + 1),
        "buffer_window": min(total_weeks, deadline_week),
    }
    for item in milestones:
        if item.key in due_by_key:
            item.due_week = due_by_key[item.key]
    return milestones


def _candidate_deadline_strings(record: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    extracted_fields = record.get("extracted_fields", {})
    if isinstance(extracted_fields, dict):
        for key in ("deadline", "deadline_date", "closing_date"):
            value = extracted_fields.get(key)
            if isinstance(value, str):
                candidates.append(value)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value)
    content = str(record.get("content", ""))
    candidates.extend(_DATE_PATTERN.findall(content))
    return candidates
