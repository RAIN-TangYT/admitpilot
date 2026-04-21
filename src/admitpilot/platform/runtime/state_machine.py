"""Workflow state-machine definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.runtime.contracts import WorkflowStatus


@dataclass
class RuntimeStateMachine:
    """Validate workflow transitions."""

    transitions: dict[WorkflowStatus, set[WorkflowStatus]] = field(
        default_factory=lambda: {
            WorkflowStatus.NEW: {WorkflowStatus.INTENT_PARSED, WorkflowStatus.FAILED},
            WorkflowStatus.INTENT_PARSED: {WorkflowStatus.PLAN_BUILT, WorkflowStatus.FAILED},
            WorkflowStatus.PLAN_BUILT: {WorkflowStatus.EXECUTING, WorkflowStatus.FAILED},
            WorkflowStatus.EXECUTING: {
                WorkflowStatus.AGGREGATING,
                WorkflowStatus.PARTIAL_DELIVERED,
                WorkflowStatus.FAILED,
            },
            WorkflowStatus.AGGREGATING: {
                WorkflowStatus.DELIVERED,
                WorkflowStatus.PARTIAL_DELIVERED,
                WorkflowStatus.FAILED,
            },
            WorkflowStatus.DELIVERED: set(),
            WorkflowStatus.PARTIAL_DELIVERED: set(),
            WorkflowStatus.FAILED: set(),
        }
    )

    def can_transition(self, current: WorkflowStatus, target: WorkflowStatus) -> bool:
        """Return whether transition is allowed."""
        if current == target:
            return True
        return target in self.transitions.get(current, set())

    def transition(self, current: WorkflowStatus, target: WorkflowStatus) -> WorkflowStatus:
        """Validate and return the target status."""
        if not self.can_transition(current=current, target=target):
            raise ValueError(f"Invalid workflow transition: {current.value} -> {target.value}")
        return target
