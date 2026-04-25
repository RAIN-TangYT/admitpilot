from admitpilot.agents.cds.facts import build_fact_slots
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput
from admitpilot.core.user_artifacts import parse_user_artifacts


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


def _timeline() -> DTAAgentOutput:
    return {
        "board_title": "board",
        "milestones": [{"key": "doc_pack_v1"}],
        "weekly_plan": [],
        "risk_markers": [],
        "document_instructions": [],
    }


def test_fact_slots_have_status_and_source_ref() -> None:
    artifacts = parse_user_artifacts(
        [
            {
                "artifact_id": "proj-1",
                "title": "ML Project",
                "source_ref": "cv:ml-project",
                "evidence_type": "project",
                "verified": True,
            }
        ]
    )
    slots = build_fact_slots(artifacts=artifacts, strategy=_strategy(), timeline=_timeline())
    assert slots
    assert all(item.source_ref for item in slots)
    assert all(item.status in {"verified", "inferred", "missing"} for item in slots)
    motivation = next(item for item in slots if item.slot_id == "motivation_core")
    assert motivation.status == "verified"


def test_fact_slots_mark_missing_when_core_evidence_absent() -> None:
    empty_timeline: DTAAgentOutput = {
        "board_title": "x",
        "milestones": [],
        "weekly_plan": [],
        "risk_markers": [],
        "document_instructions": [],
    }
    slots = build_fact_slots(
        artifacts=parse_user_artifacts([]),
        strategy=_strategy(),
        timeline=empty_timeline,
    )
    motivation = next(item for item in slots if item.slot_id == "motivation_core")
    assert motivation.status == "missing"
