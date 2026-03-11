"""CDS 文书支持输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DocumentBlueprint:
    """单个文书蓝图。"""

    document_type: str
    narrative_focus: str
    evidence_points: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InterviewCue:
    """面试高频问题与回答线索。"""

    question: str
    cue: str


@dataclass(slots=True)
class DocumentSupportPack:
    """CDS 结构化产物。"""

    blueprints: list[DocumentBlueprint] = field(default_factory=list)
    interview_cues: list[InterviewCue] = field(default_factory=list)
