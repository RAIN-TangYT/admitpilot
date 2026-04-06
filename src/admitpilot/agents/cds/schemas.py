"""CDS 文书支持输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NarrativeFactSlot:
    """文书事实槽位定义。"""

    slot_id: str
    value: str
    source: str
    verified: bool = False


@dataclass(slots=True)
class DocumentDraft:
    """单个文书草稿元信息。"""

    document_type: str
    target_school: str
    version: str
    content_outline: list[str] = field(default_factory=list)
    fact_slots: list[NarrativeFactSlot] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    review_status: str = "needs_human_review"


@dataclass(slots=True)
class InterviewCue:
    """面试高频问题与回答线索。"""

    question: str
    cue: str


@dataclass(slots=True)
class ConsistencyIssue:
    """跨文档一致性问题定义。"""

    severity: str
    message: str
    impacted_documents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentSupportPack:
    """CDS 结构化产物。"""

    drafts: list[DocumentDraft] = field(default_factory=list)
    interview_cues: list[InterviewCue] = field(default_factory=list)
    consistency_issues: list[ConsistencyIssue] = field(default_factory=list)
    review_checklist: list[str] = field(default_factory=list)
