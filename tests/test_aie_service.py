from datetime import date

from admitpilot.agents.aie.service import AdmissionsIntelligenceService


def test_aie_service_uses_same_day_cache() -> None:
    service = AdmissionsIntelligenceService()
    today = date.today()
    first = service.retrieve(query="查看官网要求", cycle="2026", as_of_date=today)
    second = service.retrieve(query="查看官网要求", cycle="2026", as_of_date=today)
    assert first.cache_hit_count == 0
    assert second.cache_hit_count >= 1


def test_aie_service_mixes_official_and_prediction() -> None:
    service = AdmissionsIntelligenceService()
    pack = service.retrieve(
        query="关注本季政策变化",
        cycle="2026",
        schools=["NUS", "HKUST"],
        as_of_date=date.today(),
    )
    statuses = {item.school: item.status for item in pack.official_cycle_snapshots}
    assert statuses["NUS"] == "predicted"
    assert statuses["HKUST"] == "official_found"
    assert pack.case_snapshot is not None
    assert pack.case_snapshot.sample_size > 0


def test_aie_service_enforces_supported_school_scope() -> None:
    service = AdmissionsIntelligenceService()
    pack = service.retrieve(
        query="范围约束测试",
        cycle="2026",
        schools=["mit", "stanford"],
        as_of_date=date.today(),
    )
    scoped = sorted(item.school for item in pack.official_cycle_snapshots)
    assert scoped == sorted(list(service.OFFICIAL_SCHOOLS))
