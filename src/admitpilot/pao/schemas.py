"""PAO 图状态与路由计划结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TypedDict

from admitpilot.core.schemas import AgentResult, AgentTask, ApplicationContext
from admitpilot.platform.runtime import WorkflowStatus


@dataclass
class RoutePlan:
    """任务拆解后的顺序执行计划。"""

    intent: str
    tasks: list[AgentTask] = field(default_factory=list)
    rationale: str = ""


class PaoGraphState(TypedDict):
    """LangGraph 在 PAO 层使用的状态容器。"""

    query: str
    context: ApplicationContext
    workflow_status: WorkflowStatus
    route_plan: RoutePlan
    pending_tasks: list[AgentTask]
    current_task: Optional[AgentTask]
    results: list[AgentResult]
    final_summary: str
