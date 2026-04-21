from admitpilot.agents.cds.service import CoreDocumentService


def _strategy() -> dict:
    return {
        "summary": "ok",
        "model_breakdown": {},
        "strengths": [],
        "weaknesses": [],
        "gap_actions": [],
        "recommendations": [{"school": "NUS", "program": "MCOMP_CS"}],
        "ranking_order": ["NUS:MCOMP_CS"],
    }


def _timeline() -> dict:
    return {
        "board_title": "board",
        "milestones": [{"key": "doc_pack_v1"}],
        "weekly_plan": [{"week": 1}],
        "risk_markers": [],
        "document_instructions": [],
    }


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


def test_cds_service_abstains_when_core_evidence_missing() -> None:
    service = CoreDocumentService()
    pack = service.build_support_pack(strategy=_strategy(), timeline=_timeline(), user_artifacts_payload=[])
    assert pack.drafts == []
    assert any("CDS abstain" in item.message for item in pack.consistency_issues)


def test_cds_service_generates_drafts_when_core_evidence_present() -> None:
    service = CoreDocumentService()
    pack = service.build_support_pack(
        strategy=_strategy(),
        timeline=_timeline(),
        user_artifacts_payload=[
            {
                "artifact_id": "proj-1",
                "title": "Distributed Systems Project",
                "source_ref": "cv:project-1",
                "evidence_type": "project",
                "verified": True,
            }
        ],
    )
    assert pack.drafts
    first_slot = pack.drafts[0].fact_slots[0]
    assert first_slot.source_ref
    assert first_slot.status in {"verified", "inferred", "missing"}
