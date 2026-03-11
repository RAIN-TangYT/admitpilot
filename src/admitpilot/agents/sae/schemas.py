"""SAE 评估输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProgramRecommendation:
    """单个项目推荐结果。"""

    school: str
    program: str
    tier: str
    risk_score: float
    reason: str


@dataclass(slots=True)
class StrategicReport:
    """SAE 结构化评估报告。"""

    summary: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendations: list[ProgramRecommendation] = field(default_factory=list)
