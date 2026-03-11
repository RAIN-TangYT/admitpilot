"""代理抽象基类定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from admitpilot.core.schemas import AgentResult, AgentTask, ApplicationContext


class BaseAgent(ABC):
    """所有业务代理的统一接口。"""

    name: str

    @abstractmethod
    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行代理任务并返回标准结果。"""
