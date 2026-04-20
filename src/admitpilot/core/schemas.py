"""项目级核心数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NotRequired, TypedDict, cast

from admitpilot.platform.runtime import contracts as runtime_contracts

AgentTask = runtime_contracts.AgentTask
AgentResult = runtime_contracts.AgentResult


@dataclass(slots=True)
class UserProfile:
    """用户画像与申请背景。"""

    name: str = ""
    degree_level: str = ""
    major_interest: str = ""
    target_regions: list[str] = field(default_factory=list)
    academic_metrics: dict[str, Any] = field(default_factory=dict)
    language_scores: dict[str, Any] = field(default_factory=dict)
    experiences: list[str] = field(default_factory=list)
    target_schools: list[str] = field(default_factory=list)
    target_programs: list[str] = field(default_factory=list)
    risk_preference: str = "balanced"


class AIEAgentOutput(TypedDict):
    """AIE 代理输出契约。"""

    cycle: str
    as_of_date: str
    target_schools: list[str]
    target_program: str
    target_program_by_school: NotRequired[dict[str, str]]
    unsupported_program_by_school: NotRequired[dict[str, str]]
    official_source_urls_by_school: NotRequired[dict[str, dict[str, str]]]
    official_status_by_school: dict[str, str]
    official_records: list[dict[str, Any]]
    case_records: list[dict[str, Any]]
    case_patterns: list[str]
    forecast_signals: list[dict[str, Any]]
    evidence_levels: dict[str, str]
    official_confidence: float
    case_confidence: float
    cache_hit_count: int
    prediction_used: bool


class SAEAgentOutput(TypedDict):
    """SAE 代理输出契约。"""

    summary: str
    model_breakdown: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    gap_actions: list[str]
    recommendations: list[dict[str, Any]]
    ranking_order: list[str]


class DTAAgentOutput(TypedDict):
    """DTA 代理输出契约。"""

    board_title: str
    milestones: list[dict[str, Any]]
    weekly_plan: list[dict[str, Any]]
    risk_markers: list[dict[str, Any]]
    document_instructions: list[str]


class CDSAgentOutput(TypedDict):
    """CDS 代理输出契约。"""

    document_drafts: list[dict[str, Any]]
    interview_talking_points: list[str]
    consistency_issues: list[dict[str, Any]]
    review_checklist: list[str]


class SharedMemory(TypedDict, total=False):
    """跨代理共享内存契约。"""

    aie: AIEAgentOutput
    sae: SAEAgentOutput
    dta: DTAAgentOutput
    cds: CDSAgentOutput


@dataclass(slots=True)
class ApplicationContext:
    """PAO 统一管理的共享上下文。"""

    user_query: str
    profile: UserProfile = field(default_factory=UserProfile)
    constraints: dict[str, Any] = field(default_factory=dict)
    shared_memory: SharedMemory = field(default_factory=lambda: cast(SharedMemory, {}))
    decisions: dict[str, Any] = field(default_factory=dict)
