"""CDS 文书支持输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NarrativeFactSlot:
    """文书事实槽位。"""

    slot_id: str
    value: str
    source_ref: str
    status: str = "missing"  # verified / inferred / missing
    verified: bool = False


@dataclass
class DocumentDraft:
    """文书草稿框架。"""

    document_type: str
    target_school: str
    version: str
    content_outline: list[str] = field(default_factory=list)
    fact_slots: list[NarrativeFactSlot] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    review_status: str = "draft"


@dataclass(slots=True)
class ConsistencyIssue:
    """跨文档一致性问题。"""

    severity: str
    message: str
    impacted_documents: list[str] = field(default_factory=list)


@dataclass
class InterviewCue:
    """面试高频问题与回答线索。"""

    question: str
    cue: str


@dataclass(slots=True)
class DocumentSupportPack:
    """CDS 结构化产物。"""

    drafts: list[DocumentDraft] = field(default_factory=list)
    interview_cues: list[InterviewCue] = field(default_factory=list)
    consistency_issues: list[ConsistencyIssue] = field(default_factory=list)
    review_checklist: list[str] = field(default_factory=list)
