"""Runtime contracts shared across orchestration and agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    NEW = "NEW"
    INTENT_PARSED = "INTENT_PARSED"
    PLAN_BUILT = "PLAN_BUILT"
    EXECUTING = "EXECUTING"
    AGGREGATING = "AGGREGATING"
    DELIVERED = "DELIVERED"
    PARTIAL_DELIVERED = "PARTIAL_DELIVERED"
    FAILED = "FAILED"


@dataclass
class AgentTask:
    """Single agent task unit."""

    name: str
    description: str
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required_memory: list[str] = field(default_factory=list)
    can_degrade: bool = False


@dataclass
class AgentResult:
    """Single agent result payload."""

    agent: str
    task: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: TaskStatus | None = None
    evidence_level: str = "unknown"
    lineage: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status is None:
            self.status = TaskStatus.SUCCESS if self.success else TaskStatus.FAILED
