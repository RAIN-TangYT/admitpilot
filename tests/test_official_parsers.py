from pathlib import Path

import pytest

from admitpilot.agents.aie.fetchers import FetchedOfficialPage, OfficialPageSpec
from admitpilot.agents.aie.parsers import OfficialPageParseError, OfficialPageParser
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG
from admitpilot.platform.common.time import utc_now

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "official_pages"


def _build_page(filename: str, page_type: str) -> FetchedOfficialPage:
    catalog = DEFAULT_ADMISSIONS_CATALOG
    spec = OfficialPageSpec(
        school="HKUST",
        program="MSCS",
        cycle="2026",
        page_type=page_type,
        url=catalog.build_page_url("HKUST", "MSCS", "2026", page_type),
        allowed_domains=catalog.official_domains("HKUST"),
    )
    return FetchedOfficialPage(
        spec=spec,
        content=(FIXTURE_ROOT / filename).read_text(encoding="utf-8"),
        fetched_at=utc_now(),
        status_code=200,
        content_type="text/html",
        mode="fixture",
    )


def test_official_parser_extracts_requirements_fields() -> None:
    parser = OfficialPageParser()

    record = parser.parse(_build_page("hkust_mscs_2026_requirements.html", "requirements"))

    assert record.page_type == "requirements"
    assert record.extracted_fields["minimum_gpa"] == "3.2/4.0"
    assert record.extracted_fields["language_requirements"] == ["IELTS 6.5", "TOEFL 80"]
    assert "Statement of Purpose" in record.extracted_fields["required_materials"]
    assert record.parse_confidence > 0.9


def test_official_parser_extracts_deadline_fields() -> None:
    parser = OfficialPageParser()

    record = parser.parse(_build_page("hkust_mscs_2026_deadline.html", "deadline"))

    assert record.page_type == "deadline"
    assert record.extracted_fields["application_deadline"] == "2026-12-01"
    assert record.effective_date.isoformat() == "2026-12-01"


def test_official_parser_raises_on_missing_required_fields() -> None:
    parser = OfficialPageParser()

    with pytest.raises(OfficialPageParseError):
        parser.parse(_build_page("invalid_mscs_2026_deadline.html", "deadline"))


def test_official_parser_decodes_entities_and_curly_quotes() -> None:
    parser = OfficialPageParser()
    spec = OfficialPageSpec(
        school="NUS",
        program="MCOMP_CS",
        cycle="2026",
        page_type="requirements",
        url="https://www.comp.nus.edu.sg/programmes/pg/mcs/admissions/",
        allowed_domains=("comp.nus.edu.sg",),
    )
    page = FetchedOfficialPage(
        spec=spec,
        content=(
            "<html><body>"
            "<p>Applicants must possess a bachelor’s degree in computing.</p>"
            "<p>Required documents include statement of purpose and official transcript.</p>"
            "<p>English requirement: IELTS&nbsp;6.0 or TOEFL&nbsp;85.</p>"
            "</body></html>"
        ),
        fetched_at=utc_now(),
        status_code=200,
        content_type="text/html",
        mode="live",
    )

    record = parser.parse(page)

    assert record.extracted_fields["academic_requirement"] == (
        "Applicants must possess a bachelor's degree in computing."
    )
    assert "IELTS 6.0" in record.extracted_fields["language_requirements"]
    assert "TOEFL 85" in record.extracted_fields["language_requirements"]


def test_official_parser_ignores_toefl_reporting_code_when_extracting_score() -> None:
    parser = OfficialPageParser()
    spec = OfficialPageSpec(
        school="NUS",
        program="MCOMP_CS",
        cycle="2026",
        page_type="requirements",
        url="https://www.comp.nus.edu.sg/programmes/pg/mcs/admissions/",
        allowed_domains=("comp.nus.edu.sg",),
    )
    page = FetchedOfficialPage(
        spec=spec,
        content=(
            "<html><body>"
            "<p>English requirement: IELTS 6.0 (with no band below IELTS 5.0) "
            "or TOEFL iBT 90.</p>"
            "<p>Institution code for TOEFL reporting is 9087.</p>"
            "</body></html>"
        ),
        fetched_at=utc_now(),
        status_code=200,
        content_type="text/html",
        mode="live",
    )

    record = parser.parse(page)

    assert "IELTS 6.0" in record.extracted_fields["language_requirements"]
    assert "IELTS 5.0" in record.extracted_fields["language_requirements"]
    assert "TOEFL 90" in record.extracted_fields["language_requirements"]
    assert "TOEFL 908" not in record.extracted_fields["language_requirements"]
