"""项目级核心数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


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


@dataclass(slots=True)
class AgentTask:
    """单个代理任务定义。"""

    name: str
    description: str
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    """单个代理执行结果。"""

    agent: str
    task: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    trace: list[str] = field(default_factory=list)


class AIEAgentOutput(TypedDict):
    """AIE 代理输出契约。"""

    official_update_count: int
    official_memory_count: int
    case_memory_count: int
    forecast_count: int
    official_status: str
    as_of_date: str
    cache_hit_count: int
    prediction_used: bool
    official_confidence: float
    case_confidence: float
    target_schools: list[str]
    target_program: str


class SAEAgentOutput(TypedDict):
    """SAE 代理输出契约。"""

    summary: str
    strengths: list[str]
    weaknesses: list[str]
    gap_count: int
    tiers: list[str]


class DTAAgentOutput(TypedDict):
    """DTA 代理输出契约。"""

    title: str
    milestone_count: int
    week_count: int
    risk_weeks: list[int]


class CDSAgentOutput(TypedDict):
    """CDS 代理输出契约。"""

    blueprint_count: int
    interview_cue_count: int
    document_types: list[str]


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
    shared_memory: SharedMemory = field(default_factory=dict)
