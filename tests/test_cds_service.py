from admitpilot.agents.cds.service import CoreDocumentService


def test_cds_abstains_when_upstream_context_is_missing() -> None:
    service = CoreDocumentService()

    pack = service.build_support_pack(
        strategy={
            "summary": "",
            "model_breakdown": {},
            "strengths": [],
            "weaknesses": [],
            "gap_actions": [],
            "recommendations": [],
            "ranking_order": [],
        },
        timeline={
            "board_title": "",
            "milestones": [],
            "weekly_plan": [],
            "risk_markers": [],
            "document_instructions": [],
        },
    )

    assert pack.drafts == []
    assert pack.consistency_issues[0].severity == "high"
    assert "缺少上游" in pack.consistency_issues[0].message
    assert "先补齐上游" in pack.review_checklist[0]
    assert "正式面试要点" in pack.interview_cues[0].cue
