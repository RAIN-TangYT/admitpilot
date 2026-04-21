import json
from datetime import date
from pathlib import Path

from admitpilot.agents.aie.fetchers import FetchedOfficialPage, OfficialPageSpec
from admitpilot.agents.aie.gateways import CatalogOfficialSourceGateway
from admitpilot.agents.aie.parsers import OfficialPageParser
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.aie.schemas import CaseRecord
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.platform.common.time import utc_now


def test_live_parser_extracts_deadline_and_materials_from_plain_html() -> None:
    parser = OfficialPageParser()
    html = """
    <html>
      <body>
        <h1>Admissions</h1>
        <p>
          Applicants must possess a bachelor's degree in Computer Science
          or related disciplines.
        </p>
        <p>Applicants should have an IELTS score of 6.5 or TOEFL iBT score of 80.</p>
        <p>
          Required documents include a statement of purpose, official transcript
          and two recommendation letters.
        </p>
        <p>The application deadline is 31 January 2026. This is the final round.</p>
      </body>
    </html>
    """
    spec = OfficialPageSpec(
        school="CUHK",
        program="MSCS",
        cycle="2026",
        page_type="deadline",
        url="https://example.edu/admission",
        allowed_domains=("example.edu",),
    )
    page = FetchedOfficialPage(
        spec=spec,
        content=html,
        fetched_at=utc_now(),
        status_code=200,
        content_type="text/html",
        mode="live",
    )

    record = parser.parse(page)

    assert record.extracted_fields["application_deadline"] == "2026-01-31"
    assert record.extracted_fields["deadline_round"] == "final_round"
    assert "IELTS 6.5" in record.extracted_fields["language_requirements"]
    assert "Statement of Purpose" in record.extracted_fields["required_materials"]


class _ExplodingCaseGateway:
    def fetch_case_records(
        self,
        schools: list[str],
        program: str,
        cycle: str,
        as_of_date: date,
    ) -> list[CaseRecord]:
        del schools, program, cycle, as_of_date
        raise AssertionError("case gateway should not be called")


def test_refresh_official_library_skips_case_gateway() -> None:
    service = AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(),
        case_gateway=_ExplodingCaseGateway(),
    )

    snapshots = service.refresh_official_library(
        query="refresh",
        cycle="2026",
        targets=[("HKUST", "MSCS")],
        as_of_date=date(2026, 10, 1),
    )

    assert len(snapshots) == 1
    assert not service._case_long_memory


def test_json_official_repository_persists_versions() -> None:
    output_dir = Path(".pytest-local")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "official_library_test.json"
    if output_path.exists():
        output_path.unlink()
    repository = JsonOfficialSnapshotRepository(path=output_path)
    service = AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(),
        official_repository=repository,
    )

    service.refresh_official_library(
        query="refresh",
        cycle="2026",
        targets=[("HKUST", "MSCS")],
        as_of_date=date(2026, 10, 1),
    )
    service.refresh_official_library(
        query="refresh next day",
        cycle="2026",
        targets=[("HKUST", "MSCS")],
        as_of_date=date(2026, 10, 2),
    )

    reloaded = JsonOfficialSnapshotRepository(path=output_path)
    history_key = "HKUST:MSCS:2026:requirements"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries", {})

    assert reloaded.get_latest_record(history_key) is not None
    assert reloaded.list_record_versions(history_key)
    assert len(raw_entries) == 1
    snapshot_payload = next(iter(raw_entries.values()))["value"]
    assert "diffs" not in snapshot_payload
