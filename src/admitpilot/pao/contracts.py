"""PAO 编排请求与响应契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admitpilot.core.schemas import AgentResult, ApplicationContext, UserProfile


@dataclass
class OrchestrationRequest:
    """编排层输入请求。"""

    user_query: str
    profile: UserProfile = field(default_factory=UserProfile)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResponse:
    """编排层输出响应。"""

    summary: str
    results: list[AgentResult] = field(default_factory=list)
    context: ApplicationContext | None = None


@dataclass
class OrchestrationEvent:
    """Incremental orchestration event emitted while PAO executes."""

    event: str
    data: dict[str, Any] = field(default_factory=dict)
