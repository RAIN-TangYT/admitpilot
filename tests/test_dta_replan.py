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


def _intel() -> AIEAgentOutput:
    return {
        "cycle": "2026",
        "as_of_date": "2026-01-01",
        "target_schools": ["NUS"],
        "target_program": "MCOMP_CS",
        "official_status_by_school": {"NUS": "official_found"},
        "official_records": [],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [],
        "evidence_levels": {},
        "official_confidence": 0.8,
        "case_confidence": 0.5,
        "cache_hit_count": 0,
        "prediction_used": False,
    }


def test_replan_shifts_due_weeks_when_delay() -> None:
    service = DynamicTimelineService()
    normal = service.build_plan(_strategy(), _intel(), {"timeline_weeks": 8})
    delayed = service.build_plan(
        _strategy(),
        _intel(),
        {"timeline_weeks": 8, "has_delay": True, "start_week": 3},
    )
    normal_due = {item.key: item.due_week for item in normal.milestones}
    delayed_due = {item.key: item.due_week for item in delayed.milestones}
    assert delayed_due["doc_pack_v1"] >= normal_due["doc_pack_v1"] + 1


def test_replan_marks_infeasible_when_critical_task_blocked() -> None:
    service = DynamicTimelineService()
    plan = service.build_plan(
        _strategy(),
        _intel(),
        {"timeline_weeks": 8, "has_delay": True, "start_week": 2, "blocked_tasks": ["submission_batch_1"]},
    )
    red_messages = [item.message for item in plan.risk_markers if item.level == "red"]
    assert any("关键任务阻塞" in msg for msg in red_messages)
    assert any("排期不可行" in msg for msg in red_messages)
