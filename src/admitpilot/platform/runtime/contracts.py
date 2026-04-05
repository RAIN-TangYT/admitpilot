"""Agent Runtime 核心契约。

单一契约源：
1) PAO/Agent 执行任务协议
2) 任务与工作流状态
3) 运行预算与重试策略
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class TaskStatus(StrEnum):
    """任务状态。"""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"


class WorkflowStatus(StrEnum):
    """工作流状态。"""

    NEW = "new"
    INTENT_PARSED = "intent_parsed"
    PLAN_BUILT = "plan_built"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    DELIVERED = "delivered"
    PARTIAL_DELIVERED = "partial_delivered"
    FAILED = "failed"


@dataclass(slots=True)
class RetryPolicy:
    """重试策略。"""

    max_attempts: int = 2
    backoff_seconds: int = 3
    retryable_errors: tuple[str, ...] = ("SYS_001", "SYS_002")


@dataclass(slots=True)
class RuntimeBudget:
    """运行预算限制。"""

    timeout_seconds: int = 30
    max_tool_calls: int = 6
    max_prompt_tokens: int = 6000


@dataclass(slots=True)
class AgentTask:
    """统一任务定义（PAO/Agent 共用）。"""

    name: str
    description: str
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required_memory: list[str] = field(default_factory=list)
    can_degrade: bool = False
    task_id: str = ""
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    budget: RuntimeBudget = field(default_factory=RuntimeBudget)
    status: TaskStatus = TaskStatus.PENDING


@dataclass(slots=True)
class RuntimeExecutionContext:
    """任务执行上下文。"""

    trace_id: str
    tenant_id: str
    user_id: str
    application_id: str
    cycle: str
    memory_refs: dict[str, str] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    """统一任务结果定义（PAO/Agent 共用）。"""

    agent: str
    task: str
    success: bool
    status: TaskStatus = TaskStatus.SUCCESS
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    trace: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""
    lineage: list[dict[str, Any]] = field(default_factory=list)


class AgentRuntimeProtocol(Protocol):
    """统一 Runtime 接口。"""

    def run_task(self, task: AgentTask, context: RuntimeExecutionContext) -> AgentResult:
        """执行任务并返回结构化结果。"""


# Backward compatibility aliases
RuntimeTask = AgentTask
RuntimeResult = AgentResult
