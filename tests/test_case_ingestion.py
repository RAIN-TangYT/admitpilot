import json
from datetime import date
from pathlib import Path

from admitpilot.agents.aie.case_ingestion import normalize_case_records
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cases" / "community_cases.json"


def test_case_ingestion_normalizes_and_filters_invalid_records() -> None:
    raw_records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    records = normalize_case_records(
        raw_records,
        schools=["HKUST", "NTU"],
        program="Computer Science",
        cycle="2026",
        as_of_date=date(2026, 4, 1),
        catalog=DEFAULT_ADMISSIONS_CATALOG,
    )

    assert len(records) == 2
    assert {item.school for item in records} == {"HKUST", "NTU"}
    assert all(item.program == "MSCS" for item in records)
    assert all(item.candidate_fingerprint.startswith("case-") for item in records)
    assert {item.credibility_label for item in records} <= {"high", "medium"}


def test_case_ingestion_assigns_confidence_metadata() -> None:
    raw_records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    records = normalize_case_records(
        raw_records,
        schools=["HKUST", "NTU"],
        program="MSCS",
        cycle="2026",
        as_of_date=date(2026, 4, 1),
        catalog=DEFAULT_ADMISSIONS_CATALOG,
    )
    record_by_school = {item.school: item for item in records}

    assert record_by_school["HKUST"].confidence > record_by_school["NTU"].confidence
    assert record_by_school["HKUST"].source_site_score >= 0.7
    assert record_by_school["NTU"].freshness_score > 0.6
