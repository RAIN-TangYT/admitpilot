from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.core.schemas import AIEAgentOutput, SAEAgentOutput


def _strategy() -> SAEAgentOutput:
    return {
        "summary": "ok",
        "model_breakdown": {},
        "strengths": [],
        "weaknesses": [],
        "gap_actions": [],
        "recommendations": [{"school": "NUS", "program": "MCOMP_CS"}],
        "ranking_order": ["NUS:MCOMP_CS"],
    }


def _intel_with_deadline() -> AIEAgentOutput:
    return {
        "cycle": "2026",
        "as_of_date": "2026-01-01",
        "target_schools": ["NUS"],
        "target_program": "MCOMP_CS",
        "official_status_by_school": {"NUS": "official_found"},
        "official_records": [
            {
                "school": "NUS",
                "page_type": "deadline",
                "source_url": "https://example/nus",
                "content": "Application closes on 2026-01-31",
            }
        ],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [],
        "evidence_levels": {"NUS": "official_primary"},
        "official_confidence": 0.8,
        "case_confidence": 0.5,
        "cache_hit_count": 0,
        "prediction_used": False,
    }


def _intel_without_deadline() -> AIEAgentOutput:
    payload = _intel_with_deadline()
    payload["official_records"] = []
    return payload


def test_build_plan_uses_deadline_reverse_planning() -> None:
    service = DynamicTimelineService()
    plan = service.build_plan(_strategy(), _intel_with_deadline(), {"timeline_weeks": 8})
    due_by_key = {item.key: item.due_week for item in plan.milestones}
    # deadline in about 4-5 weeks -> submission should be near week 4
    assert due_by_key["submission_batch_1"] <= 5
    assert due_by_key["doc_pack_v1"] < due_by_key["submission_batch_1"]


def test_build_plan_falls_back_when_no_deadline() -> None:
    service = DynamicTimelineService()
    plan = service.build_plan(_strategy(), _intel_without_deadline(), {"timeline_weeks": 8})
    due_by_key = {item.key: item.due_week for item in plan.milestones}
    assert due_by_key["submission_batch_1"] == 6
