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
                message="Start week is later than the available planning window.",
                mitigation="Reduce the application scope or move to a later cycle.",
            )
        )

    blocked_critical = {"submission_batch_1", "doc_pack_v1"} & blocked_tasks
    if blocked_critical:
        feasible = False
        risks.append(
            RiskMarker(
                week=min(total_weeks, start_week),
                level="red",
                message=f"Critical tasks are blocked: {','.join(sorted(blocked_critical))}",
                mitigation="Unblock critical tasks before regenerating the timeline.",
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
                message="Too many milestones are concentrated in the same week.",
                mitigation="Move non-critical tasks to adjacent weeks and add buffer.",
            )
        )

    submission = next((item for item in shifted if item.key == "submission_batch_1"), None)
    if submission is not None and submission.due_week >= total_weeks:
        risks.append(
            RiskMarker(
                week=submission.due_week,
                level="red",
                message="Submission milestone is too close to the end of the window.",
                mitigation="Move document and portal preparation earlier.",
            )
        )
    return ReplanResult(milestones=shifted, risks=risks, feasible=feasible)
