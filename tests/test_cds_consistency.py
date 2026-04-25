from admitpilot.agents.cds.consistency import check_consistency
from admitpilot.agents.cds.schemas import DocumentDraft, NarrativeFactSlot


def _slot(slot_id: str, value: str, status: str = "verified") -> NarrativeFactSlot:
    return NarrativeFactSlot(
        slot_id=slot_id,
        value=value,
        source_ref="test:source",
        status=status,
        verified=(status == "verified"),
    )


def test_consistency_detects_timeline_conflict() -> None:
    drafts = [
        DocumentDraft(
            document_type="sop",
            target_school="NUS",
            version="v0",
            content_outline=["NUS fit: emphasize curriculum depth and systems practice"],
            fact_slots=[_slot("execution_proof", "milestone count=3")],
        ),
        DocumentDraft(
            document_type="cv",
            target_school="shared",
            version="v0",
            content_outline=["Education background"],
            fact_slots=[_slot("execution_proof", "milestone count=6")],
        ),
    ]
    issues = check_consistency(drafts)
    assert any("execution_proof conflicts" in item.message for item in issues)


def test_consistency_detects_motivation_conflict() -> None:
    drafts = [
        DocumentDraft(
            document_type="sop",
            target_school="HKU",
            version="v0",
            content_outline=["HKU fit: emphasize algorithmic depth and applied impact"],
            fact_slots=[_slot("motivation_core", "Motivation supported by project evidence: A")],
        ),
        DocumentDraft(
            document_type="cv",
            target_school="shared",
            version="v0",
            content_outline=["Project experience"],
            fact_slots=[_slot("motivation_core", "Motivation supported by project evidence: B")],
        ),
    ]
    issues = check_consistency(drafts)
    assert any("motivation_core conflicts" in item.message for item in issues)


def test_consistency_detects_school_name_alignment_issue() -> None:
    drafts = [
        DocumentDraft(
            document_type="sop",
            target_school="NUS",
            version="v0",
            content_outline=["Program fit: emphasize curriculum depth and systems practice"],
            fact_slots=[_slot("motivation_core", "core", status="inferred")],
        )
    ]
    issues = check_consistency(drafts)
    assert any("does not mention the target school name" in item.message for item in issues)
