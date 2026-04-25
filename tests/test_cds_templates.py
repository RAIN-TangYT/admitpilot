from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput


def _timeline() -> DTAAgentOutput:
    return {
        "board_title": "board",
        "milestones": [{"key": "submission_batch_1", "due_week": 4}],
        "weekly_plan": [{"week": 1}, {"week": 2}],
        "risk_markers": [],
        "document_instructions": [],
    }


def _strategy(schools: list[str]) -> SAEAgentOutput:
    recs = []
    for school in schools:
        recs.append(
            {
                "school": school,
                "program": "MSCS",
                "gaps": [f"{school}-gap"],
                "risk_flags": [f"{school}-risk"],
                "missing_inputs": [],
            }
        )
    return {
        "summary": "ok",
        "model_breakdown": {},
        "strengths": [],
        "weaknesses": [],
        "gap_actions": [],
        "recommendations": recs,
        "ranking_order": [f"{schools[0]}:MSCS"],
    }


def _artifacts() -> list[dict[str, str | bool]]:
    return [
        {
            "artifact_id": "proj-1",
            "title": "Distributed Systems Project",
            "source_ref": "cv:project-1",
            "evidence_type": "project",
            "verified": True,
        }
    ]


def test_templates_generate_different_outlines_for_schools() -> None:
    service = CoreDocumentService()
    pack = service.build_support_pack(
        strategy=_strategy(["NUS", "HKU"]),
        timeline=_timeline(),
        user_artifacts_payload=_artifacts(),
    )
    sop_by_school = {
        item.target_school: item.content_outline
        for item in pack.drafts
        if item.document_type == "sop"
    }
    assert sop_by_school["NUS"] != sop_by_school["HKU"]


def test_templates_include_upstream_gap_and_risk_flags() -> None:
    service = CoreDocumentService()
    pack = service.build_support_pack(
        strategy=_strategy(["NUS"]),
        timeline=_timeline(),
        user_artifacts_payload=_artifacts(),
    )
    sop = next(
        item
        for item in pack.drafts
        if item.document_type == "sop" and item.target_school == "NUS"
    )
    assert any("NUS-gap" in risk for risk in sop.risks)
    assert any("NUS-risk" in risk for risk in sop.risks)
