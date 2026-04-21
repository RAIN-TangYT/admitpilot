from datetime import date
from pathlib import Path

from admitpilot.agents.aie.gateways import CatalogOfficialSourceGateway, FixtureCaseSourceGateway
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.aie.runtime import build_runtime_aie_service
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import AdmitPilotSettings

AS_OF_DATE = date(2026, 10, 1)


def _fixture_service() -> AdmissionsIntelligenceService:
    return AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(),
        case_gateway=FixtureCaseSourceGateway(),
    )


def _seed_official_library(output_path: Path) -> None:
    repository = JsonOfficialSnapshotRepository(path=output_path)
    service = AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(),
        official_repository=repository,
        case_gateway=FixtureCaseSourceGateway(),
    )
    service.refresh_official_library(
        query="seed official library",
        cycle="2026",
        targets=[("HKUST", "MSCS")],
        as_of_date=AS_OF_DATE,
    )


def test_aie_service_uses_same_day_cache() -> None:
    service = _fixture_service()

    first = service.retrieve(query="查看官网要求", cycle="2026", as_of_date=AS_OF_DATE)
    second = service.retrieve(query="查看官网要求", cycle="2026", as_of_date=AS_OF_DATE)

    assert first.cache_hit_count == 0
    assert second.cache_hit_count >= 1


def test_runtime_aie_service_reads_official_library_by_default() -> None:
    output_dir = Path(".pytest-local")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "runtime_official_library.json"
    if output_path.exists():
        output_path.unlink()
    _seed_official_library(output_path)
    settings = AdmitPilotSettings(
        run_mode="test",
        official_library_path=str(output_path),
    )

    service = build_runtime_aie_service(settings=settings)
    pack = service.retrieve(
        query="关注本季政策变化",
        cycle="2026",
        schools=["NUS", "HKUST"],
        as_of_date=AS_OF_DATE,
    )

    statuses = {item.school: item.status for item in pack.official_cycle_snapshots}
    assert statuses["NUS"] == "predicted"
    assert statuses["HKUST"] == "official_found"
    assert pack.case_long_memory == []
    assert pack.case_snapshot is not None
    assert pack.case_snapshot.sample_size == 0
    assert pack.case_snapshot.patterns == []


def test_aie_service_enforces_supported_school_scope() -> None:
    service = _fixture_service()
    pack = service.retrieve(
        query="范围约束测试",
        cycle="2026",
        schools=["mit", "stanford"],
        as_of_date=AS_OF_DATE,
    )
    scoped = sorted(item.school for item in pack.official_cycle_snapshots)
    assert scoped == sorted(list(service.OFFICIAL_SCHOOLS))


def test_aie_service_appends_fetched_official_records_only_once() -> None:
    service = _fixture_service()
    base_count = len(service._official_long_memory)
    pack = service.retrieve(
        query="查看官网要求",
        cycle="2026",
        schools=["HKUST"],
        as_of_date=AS_OF_DATE,
    )

    fetched_count = sum(len(item.entries) for item in pack.official_cycle_snapshots)

    assert fetched_count > 0
    assert len(service._official_long_memory) - base_count == fetched_count
