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
            content_outline=["NUS项目定位：强调课程深度与系统工程实践"],
            fact_slots=[_slot("execution_proof", "关键里程碑数量=3")],
        ),
        DocumentDraft(
            document_type="cv",
            target_school="shared",
            version="v0",
            content_outline=["教育背景"],
            fact_slots=[_slot("execution_proof", "关键里程碑数量=6")],
        ),
    ]
    issues = check_consistency(drafts)
    assert any("时间线不一致" in item.message for item in issues)


def test_consistency_detects_motivation_conflict() -> None:
    drafts = [
        DocumentDraft(
            document_type="sop",
            target_school="HKU",
            version="v0",
            content_outline=["HKU项目定位：强调算法能力与跨领域应用"],
            fact_slots=[_slot("motivation_core", "核心动机由项目经历支撑: A")],
        ),
        DocumentDraft(
            document_type="cv",
            target_school="shared",
            version="v0",
            content_outline=["项目经历"],
            fact_slots=[_slot("motivation_core", "核心动机由项目经历支撑: B")],
        ),
    ]
    issues = check_consistency(drafts)
    assert any("经历叙事不一致" in item.message for item in issues)


def test_consistency_detects_school_name_alignment_issue() -> None:
    drafts = [
        DocumentDraft(
            document_type="sop",
            target_school="NUS",
            version="v0",
            content_outline=["项目定位：强调课程深度与系统工程实践"],  # missing school name
            fact_slots=[_slot("motivation_core", "core", status="inferred")],
        )
    ]
    issues = check_consistency(drafts)
    assert any("未出现目标学校名" in item.message for item in issues)
