"""PAO 编排请求与响应契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admitpilot.core.schemas import AgentResult, ApplicationContext, UserProfile


@dataclass(slots=True)
class OrchestrationRequest:
    """编排层输入请求。"""

    user_query: str
    profile: UserProfile = field(default_factory=UserProfile)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestrationResponse:
    """编排层输出响应。"""

    summary: str
    results: list[AgentResult] = field(default_factory=list)
    context: ApplicationContext | None = None
