from pathlib import Path

from admitpilot.agents.aie.fetchers import FetchedOfficialPage, OfficialPageSpec
from admitpilot.agents.aie.parsers import OfficialPageParser
from admitpilot.agents.aie.snapshots import diff_official_record
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG
from admitpilot.platform.common.time import utc_now

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "official_pages"


def _page(filename: str, page_type: str) -> FetchedOfficialPage:
    spec = OfficialPageSpec(
        school="HKUST",
        program="MSCS",
        cycle="2026",
        page_type=page_type,
        url=DEFAULT_ADMISSIONS_CATALOG.build_page_url("HKUST", "MSCS", "2026", page_type),
        allowed_domains=DEFAULT_ADMISSIONS_CATALOG.official_domains("HKUST"),
    )
    return FetchedOfficialPage(
        spec=spec,
        content=(FIXTURE_ROOT / filename).read_text(encoding="utf-8"),
        fetched_at=utc_now(),
        status_code=200,
        content_type="text/html",
        mode="fixture",
    )


def test_snapshot_diff_reuses_version_for_identical_content() -> None:
    parser = OfficialPageParser()
    baseline, _ = diff_official_record(
        None,
        parser.parse(_page("hkust_mscs_2026_deadline.html", "deadline")),
    )
    repeated, diff = diff_official_record(
        baseline,
        parser.parse(_page("hkust_mscs_2026_deadline.html", "deadline")),
    )

    assert diff is None
    assert repeated.version_id == baseline.version_id
    assert repeated.change_type == "unchanged"


def test_snapshot_diff_detects_deadline_and_requirement_updates() -> None:
    parser = OfficialPageParser()
    deadline_v1, _ = diff_official_record(
        None,
        parser.parse(_page("hkust_mscs_2026_deadline.html", "deadline")),
    )
    deadline_v2, deadline_diff = diff_official_record(
        deadline_v1,
        parser.parse(_page("hkust_mscs_2026_deadline_v2.html", "deadline")),
    )
    requirements_v1, _ = diff_official_record(
        None,
        parser.parse(_page("hkust_mscs_2026_requirements.html", "requirements")),
    )
    requirements_v2, requirements_diff = diff_official_record(
        requirements_v1,
        parser.parse(_page("hkust_mscs_2026_requirements_v2.html", "requirements")),
    )

    assert deadline_diff is not None
    assert "application_deadline" in deadline_diff.changed_fields
    assert deadline_v2.version_id != deadline_v1.version_id
    assert requirements_diff is not None
    assert "minimum_gpa" in requirements_diff.changed_fields
    assert requirements_v2.change_type == "updated"
