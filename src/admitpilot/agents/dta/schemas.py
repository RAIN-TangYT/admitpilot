"""DTA 时间规划输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WeekTask:
    """周级执行任务。"""

    week: int
    focus: str
    items: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TimelinePlan:
    """动态申请执行板。"""

    title: str
    milestones: list[str] = field(default_factory=list)
    weeks: list[WeekTask] = field(default_factory=list)
