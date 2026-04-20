"""DTA 时间规划输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Milestone:
    """里程碑节点定义。"""

    key: str
    title: str
    due_week: int
    status: str = "planned"
    depends_on: list[str] = field(default_factory=list)


@dataclass
class RiskMarker:
    """风险标记定义。"""

    week: int
    level: str
    message: str
    mitigation: str


class WeekTask:
    """周级执行任务。"""

    week: int
    focus: str
    items: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    school_scope: list[str] = field(default_factory=list)


class TimelinePlan:
    """动态申请执行板。"""

    title: str
    milestones: list[Milestone] = field(default_factory=list)
    weeks: list[WeekTask] = field(default_factory=list)
    risk_markers: list[RiskMarker] = field(default_factory=list)
    document_instructions: list[str] = field(default_factory=list)
