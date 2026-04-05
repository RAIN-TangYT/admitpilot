"""Runtime 状态机骨架。"""

from __future__ import annotations

from dataclasses import dataclass

from admitpilot.platform.runtime.contracts import WorkflowStatus


@dataclass(slots=True)
class RuntimeStateMachine:
    """工作流状态迁移校验器。"""

    def can_transition(self, current: WorkflowStatus, target: WorkflowStatus) -> bool:
        allowed = _ALLOWED_TRANSITIONS.get(current, ())
        return target in allowed

    def transition(self, current: WorkflowStatus, target: WorkflowStatus) -> WorkflowStatus:
        if not self.can_transition(current=current, target=target):
            raise ValueError(f"invalid_transition:{current.value}->{target.value}")
        return target


_ALLOWED_TRANSITIONS: dict[WorkflowStatus, tuple[WorkflowStatus, ...]] = {
    WorkflowStatus.NEW: (WorkflowStatus.INTENT_PARSED, WorkflowStatus.FAILED),
    WorkflowStatus.INTENT_PARSED: (WorkflowStatus.PLAN_BUILT, WorkflowStatus.FAILED),
    WorkflowStatus.PLAN_BUILT: (WorkflowStatus.EXECUTING, WorkflowStatus.FAILED),
    WorkflowStatus.EXECUTING: (
        WorkflowStatus.AGGREGATING,
        WorkflowStatus.PARTIAL_DELIVERED,
        WorkflowStatus.FAILED,
    ),
    WorkflowStatus.AGGREGATING: (
        WorkflowStatus.DELIVERED,
        WorkflowStatus.PARTIAL_DELIVERED,
        WorkflowStatus.FAILED,
    ),
    WorkflowStatus.PARTIAL_DELIVERED: (WorkflowStatus.EXECUTING, WorkflowStatus.FAILED),
    WorkflowStatus.DELIVERED: (),
    WorkflowStatus.FAILED: (),
}
