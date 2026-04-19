from datetime import date
from pathlib import Path

from admitpilot.agents.aie.gateways import CatalogOfficialSourceGateway, FixtureCaseSourceGateway
from admitpilot.agents.aie.repositories import InMemoryOfficialSnapshotRepository
from admitpilot.agents.aie.service import AdmissionsIntelligenceService

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "official_pages"


def test_aie_service_integrates_fixture_based_official_and_case_data() -> None:
    service = AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(),
        case_gateway=FixtureCaseSourceGateway(),
    )

    pack = service.retrieve(
        query="检查 2026 招生要求",
        cycle="2026",
        schools=["HKUST", "NUS"],
        program="Computer Science",
        as_of_date=date(2026, 10, 1),
    )

    statuses = {item.school: item.status for item in pack.official_cycle_snapshots}
    hkust_snapshot = next(item for item in pack.official_cycle_snapshots if item.school == "HKUST")

    assert statuses["HKUST"] == "official_found"
    assert statuses["NUS"] == "predicted"
    assert {entry.page_type for entry in hkust_snapshot.entries} == {"requirements", "deadline"}
    assert pack.case_snapshot is not None
    assert pack.case_snapshot.sample_size >= 1
    assert pack.case_long_memory


def test_aie_service_detects_official_page_updates_across_snapshot_versions() -> None:
    repository = InMemoryOfficialSnapshotRepository()
    baseline_gateway = CatalogOfficialSourceGateway()
    baseline_service = AdmissionsIntelligenceService(
        official_gateway=baseline_gateway,
        official_repository=repository,
        case_gateway=FixtureCaseSourceGateway(),
    )
    updated_gateway = CatalogOfficialSourceGateway(
        fixture_overrides={
            ("HKUST", "MSCS", "2026", "deadline"): (
                FIXTURE_ROOT / "hkust_mscs_2026_deadline_v2.html"
            )
        }
    )
    updated_service = AdmissionsIntelligenceService(
        official_gateway=updated_gateway,
        official_repository=repository,
        case_gateway=FixtureCaseSourceGateway(),
    )

    baseline_pack = baseline_service.retrieve(
        query="检查官网 deadline",
        cycle="2026",
        schools=["HKUST"],
        as_of_date=date(2026, 10, 1),
    )
    updated_pack = updated_service.retrieve(
        query="检查官网 deadline 更新",
        cycle="2026",
        schools=["HKUST"],
        as_of_date=date(2026, 10, 2),
    )

    baseline_deadline = next(
        entry
        for entry in baseline_pack.official_cycle_snapshots[0].entries
        if entry.page_type == "deadline"
    )
    updated_deadline = next(
        entry
        for entry in updated_pack.official_cycle_snapshots[0].entries
        if entry.page_type == "deadline"
    )

    assert baseline_deadline.version_id != updated_deadline.version_id
    assert updated_deadline.change_type == "updated"
    assert "application_deadline" in updated_deadline.changed_fields
    assert updated_pack.official_cycle_snapshots[0].diffs[0]["page_type"] == "deadline"
