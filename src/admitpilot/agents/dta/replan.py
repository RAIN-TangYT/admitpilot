"""Delay-aware timeline replanning and conflict detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admitpilot.agents.dta.schemas import Milestone, RiskMarker


@dataclass(frozen=True)
class ReplanResult:
    milestones: list[Milestone]
    risks: list[RiskMarker] = field(default_factory=list)
    feasible: bool = True


def apply_replan(
    milestones: list[Milestone],
    constraints: dict[str, Any],
    total_weeks: int,
) -> ReplanResult:
    """Shift milestones for delay and emit structured conflict risks."""
    delayed = bool(constraints.get("has_delay", False))
    start_week = int(constraints.get("start_week", 1))
    blocked_tasks = set(str(item) for item in constraints.get("blocked_tasks", []))

    shifted: list[Milestone] = []
    week_shift = max(0, start_week - 1) if delayed else 0
    for item in milestones:
        item.due_week = min(total_weeks, max(1, item.due_week + week_shift))
        shifted.append(item)

    risks: list[RiskMarker] = []
    feasible = True
    if start_week > total_weeks:
        feasible = False
        risks.append(
            RiskMarker(
                week=total_weeks,
                level="red",
                message="启动周晚于排期窗口，当前计划不可执行",
                mitigation="缩减申请范围或延后申请季",
            )
        )

    blocked_critical = {"submission_batch_1", "doc_pack_v1"} & blocked_tasks
    if blocked_critical:
        feasible = False
        risks.append(
            RiskMarker(
                week=min(total_weeks, start_week),
                level="red",
                message=f"关键任务阻塞: {','.join(sorted(blocked_critical))}",
                mitigation="解除关键阻塞后再生成排期",
            )
        )

    week_counts: dict[int, int] = {}
    for item in shifted:
        week_counts[item.due_week] = week_counts.get(item.due_week, 0) + 1
    if any(count >= 3 for count in week_counts.values()):
        risks.append(
            RiskMarker(
                week=min(week for week, count in week_counts.items() if count >= 3),
                level="yellow",
                message="同周里程碑过于集中，存在任务挤压",
                mitigation="拆分非关键任务到前后周并增加缓冲",
            )
        )

    submission = next((item for item in shifted if item.key == "submission_batch_1"), None)
    if submission is not None and submission.due_week >= total_weeks:
        risks.append(
            RiskMarker(
                week=submission.due_week,
                level="red",
                message="提交节点逼近窗口末端，缓冲不足",
                mitigation="前移文书与网申准备，避免截止前集中提交",
            )
        )
    return ReplanResult(milestones=shifted, risks=risks, feasible=feasible)
