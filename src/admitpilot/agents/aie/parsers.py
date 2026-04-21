"""Fixture-friendly official page parsers for AIE."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any

from admitpilot.agents.aie.fetchers import FetchedOfficialPage
from admitpilot.agents.aie.schemas import OfficialAdmissionRecord
from admitpilot.agents.aie.snapshots import build_content_hash

_MONTH_NAME_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_DATE_PATTERNS = (
    re.compile(rf"\b(\d{{1,2}}\s+(?:{_MONTH_NAME_PATTERN})\s*,?\s+\d{{4}})\b", re.IGNORECASE),
    re.compile(rf"\b((?:{_MONTH_NAME_PATTERN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
)
_REQUIRED_MATERIAL_PATTERNS = (
    ("statement of purpose", "Statement of Purpose"),
    ("personal statement", "Personal Statement"),
    ("curriculum vitae", "CV"),
    ("c.v.", "CV"),
    ("official transcript", "Official Transcript"),
    ("transcript", "Transcript"),
    ("degree certificate", "Degree Certificate"),
    ("recommendation", "Recommendation Letter"),
    ("referee", "Recommendation Letter"),
    ("passport", "Identity Document"),
    ("identity document", "Identity Document"),
)


class OfficialPageParseError(ValueError):
    """Raised when an official page cannot be parsed into structured fields."""


class _StructuredFieldParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.fields: dict[str, list[str]] = {}
        self._field_stack: list[str] = []
        self._text_buffer: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "meta":
            name = attr_map.get("name", "").strip().lower()
            content = attr_map.get("content", "").strip()
            if name and content:
                self.meta[name] = content
            return
        field_name = attr_map.get("data-field", "").strip()
        if field_name:
            self._field_stack.append(field_name)
            self._text_buffer.append([])

    def handle_data(self, data: str) -> None:
        if not self._field_stack:
            return
        text = data.strip()
        if text:
            self._text_buffer[-1].append(text)

    def handle_endtag(self, tag: str) -> None:
        del tag
        if not self._field_stack:
            return
        field_name = self._field_stack.pop()
        parts = self._text_buffer.pop()
        if not parts:
            return
        self.fields.setdefault(field_name, []).append(" ".join(parts))


@dataclass(slots=True)
class OfficialPageParser:
    """Parse fetched official pages into structured admissions records."""

    def parse(self, page: FetchedOfficialPage) -> OfficialAdmissionRecord:
        parser = _StructuredFieldParser()
        parser.feed(page.content)
        content = self._normalize_text(page.content)
        extracted_fields = self._normalize_fields(
            raw_fields=parser.fields,
            content=content,
            page_type=page.spec.page_type,
        )
        published_date = self._resolve_published_date(parser.meta, page)
        effective_date = self._resolve_effective_date(
            page.spec.page_type,
            extracted_fields,
            published_date,
        )
        parse_confidence = self._parse_confidence(
            page.spec.page_type,
            extracted_fields,
            mode=page.mode,
        )
        quality_score = min(1.0, 0.6 + 0.1 * len(extracted_fields))
        confidence = min(1.0, round(parse_confidence * 0.6 + quality_score * 0.4, 4))
        return OfficialAdmissionRecord(
            school=page.spec.school,
            program=page.spec.program,
            cycle=page.spec.cycle,
            page_type=page.spec.page_type,
            source_url=page.spec.url,
            content=content,
            published_date=published_date,
            effective_date=effective_date,
            fetched_at=page.fetched_at,
            content_hash=build_content_hash(content=content, extracted_fields=extracted_fields),
            quality_score=quality_score,
            confidence=confidence,
            extracted_fields=extracted_fields,
            parse_confidence=parse_confidence,
            source_credibility="official_primary",
            change_type="new",
        )

    def _normalize_fields(
        self,
        raw_fields: dict[str, list[str]],
        content: str,
        page_type: str,
    ) -> dict[str, Any]:
        language_requirements = list(raw_fields.get("language_requirement", []))
        required_materials = list(raw_fields.get("required_material", []))
        normalized: dict[str, Any] = {}
        if value := self._single_value(raw_fields.get("minimum_gpa")):
            normalized["minimum_gpa"] = value
        if value := self._single_value(raw_fields.get("application_deadline")):
            normalized["application_deadline"] = value
        if value := self._single_value(raw_fields.get("deadline_round")):
            normalized["deadline_round"] = value
        heuristic_fields = self._extract_heuristic_fields(content, page_type)
        language_requirements.extend(heuristic_fields.pop("language_requirements", []))
        required_materials.extend(heuristic_fields.pop("required_materials", []))
        if language_requirements:
            normalized["language_requirements"] = self._dedupe_preserve_order(
                language_requirements
            )
        if required_materials:
            normalized["required_materials"] = self._dedupe_preserve_order(required_materials)
        normalized.update(
            {
                key: value
                for key, value in heuristic_fields.items()
                if key not in normalized and value
            }
        )
        return normalized

    def _resolve_published_date(
        self, meta: dict[str, str], page: FetchedOfficialPage
    ) -> date:
        published = meta.get("published_date") or meta.get("published-date")
        if published:
            return date.fromisoformat(published)
        if isinstance(page.fetched_at, datetime):
            return page.fetched_at.date()
        raise OfficialPageParseError("missing published date")

    def _resolve_effective_date(
        self, page_type: str, fields: dict[str, Any], published_date: date
    ) -> date:
        if page_type == "deadline":
            deadline = str(fields.get("application_deadline", "")).strip()
            if not deadline:
                raise OfficialPageParseError("missing_deadline")
            return date.fromisoformat(deadline)
        return published_date

    def _parse_confidence(
        self,
        page_type: str,
        fields: dict[str, Any],
        mode: str,
    ) -> float:
        required_by_page = {
            "requirements": {"minimum_gpa", "language_requirements", "required_materials"},
            "deadline": {"application_deadline"},
        }
        required = required_by_page.get(page_type, set())
        missing = required - set(fields.keys())
        if not missing:
            score = 0.75 + 0.08 * len(required)
            return min(0.98, round(score, 4))
        if mode != "live":
            raise OfficialPageParseError(
                f"missing_required_fields:{page_type}:{','.join(sorted(missing))}"
            )
        minimal_live_requirements = {
            "requirements": {"language_requirements", "required_materials", "academic_requirement"},
            "deadline": {"application_deadline"},
        }
        present = set(fields.keys()) & minimal_live_requirements.get(page_type, set())
        if not present:
            raise OfficialPageParseError(
                f"missing_required_fields:{page_type}:{','.join(sorted(missing))}"
            )
        score = 0.55 + 0.1 * len(present)
        return min(0.85, round(score, 4))

    def _normalize_text(self, html: str) -> str:
        text = unescape(html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\xa0", " ")
        text = text.replace("’", "'").replace("‘", "'")
        return " ".join(text.split())

    def _single_value(self, values: list[str] | None) -> str:
        if not values:
            return ""
        return values[0].strip()

    def _extract_heuristic_fields(self, content: str, page_type: str) -> dict[str, Any]:
        text = " ".join(content.split())
        lowered = text.lower()
        fields: dict[str, Any] = {}
        language_requirements = self._extract_language_requirements(text)
        required_materials = self._extract_required_materials(lowered)
        academic_requirement = self._extract_academic_requirement(text)
        if language_requirements:
            fields["language_requirements"] = language_requirements
        if required_materials:
            fields["required_materials"] = required_materials
        if academic_requirement:
            fields["academic_requirement"] = academic_requirement
        if page_type == "deadline":
            deadline = self._extract_latest_date(text)
            if deadline is not None:
                fields["application_deadline"] = deadline.isoformat()
                if "final round" in lowered:
                    fields["deadline_round"] = "final_round"
                elif "clearing" in lowered:
                    fields["deadline_round"] = "clearing_round"
                elif "main round" in lowered:
                    fields["deadline_round"] = "main_round"
                else:
                    fields["deadline_round"] = "latest_published_round"
        return fields

    def _extract_language_requirements(self, text: str) -> list[str]:
        requirements: list[str] = []
        for match in re.finditer(
            r"\bIELTS\b[^0-9]{0,40}(?<!\d)(\d(?:\.\d)?)(?!\d)",
            text,
            flags=re.IGNORECASE,
        ):
            requirements.append(f"IELTS {match.group(1)}")
        # Parse TOEFL scores from a local window and ignore institution codes
        # (e.g. 4-digit reporting codes like 9087).
        for marker in re.finditer(r"\bTOEFL(?:-iBT|-IBT)?\b", text, flags=re.IGNORECASE):
            window = text[marker.end() : marker.end() + 180]
            for score_match in re.finditer(r"(?<!\d)(\d{2,3})(?!\d)", window):
                score = int(score_match.group(1))
                if 60 <= score <= 677:
                    requirements.append(f"TOEFL {score}")
                    break
        return self._dedupe_preserve_order(requirements)

    def _extract_required_materials(self, lowered_text: str) -> list[str]:
        materials: list[str] = []
        for needle, label in _REQUIRED_MATERIAL_PATTERNS:
            if needle in lowered_text:
                materials.append(label)
        return self._dedupe_preserve_order(materials)

    def _extract_academic_requirement(self, text: str) -> str:
        patterns = (
            r"(Applicants? must possess a bachelor'?s degree[^.]*\.)",
            r"(Applicants? shall hold a Bachelor'?s degree[^.]*\.)",
            r"(Applicants? should possess[^.]*\.)",
            r"(Applicants? are expected to have[^.]*\.)",
            r"(graduated from a recognized university and obtained a bachelor'?s degree[^.]*\.)",
            r"(A good honours degree[^.]*\.)",
            r"(hold a Bachelor.?s degree[^.]*\.)",
            r"(second class honours[^.]*\.)",
            r"(bachelor'?s degree in [^.]*\.)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return " ".join(match.group(1).split())
        return ""

    def _extract_latest_date(self, text: str) -> date | None:
        candidates: list[date] = []
        for pattern in _DATE_PATTERNS:
            for match in pattern.finditer(text):
                parsed = self._parse_date_text(match.group(1))
                if parsed is not None:
                    candidates.append(parsed)
        if not candidates:
            return None
        return max(candidates)

    def _parse_date_text(self, raw: str) -> date | None:
        cleaned = " ".join(raw.replace(",", " ").split())
        for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        return None

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result
