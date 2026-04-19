"""Runtime contracts shared across orchestration and agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """Task execution status."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"


class WorkflowStatus(StrEnum):
    """Workflow execution status."""

    NEW = "NEW"
    INTENT_PARSED = "INTENT_PARSED"
    PLAN_BUILT = "PLAN_BUILT"
    EXECUTING = "EXECUTING"
    AGGREGATING = "AGGREGATING"
    DELIVERED = "DELIVERED"
    PARTIAL_DELIVERED = "PARTIAL_DELIVERED"
    FAILED = "FAILED"


@dataclass(slots=True)
class AgentTask:
    """Single agent task unit."""

    name: str
    description: str
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required_memory: list[str] = field(default_factory=list)
    can_degrade: bool = False


@dataclass(slots=True)
class AgentResult:
    """Single agent result payload."""

    agent: str
    task: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: TaskStatus = TaskStatus.SUCCESS
    evidence_level: str = "unknown"
    lineage: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.success and self.status == TaskStatus.SUCCESS:
            return
        if not self.success and self.status == TaskStatus.SUCCESS:
            self.status = TaskStatus.FAILED
