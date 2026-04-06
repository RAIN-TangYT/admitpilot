"""SAE 评估输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProgramRecommendation:
    """单个项目推荐结果。"""

    school: str
    program: str
    tier: str
    rule_score: float
    semantic_score: float
    risk_score: float
    overall_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StrategicReport:
    """SAE 结构化评估报告。"""

    summary: str
    model_breakdown: dict[str, float] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    gap_actions: list[str] = field(default_factory=list)
    recommendations: list[ProgramRecommendation] = field(default_factory=list)
    ranking_order: list[str] = field(default_factory=list)
