"""DTA 代理入口。"""

from __future__ import annotations

from typing import cast

from admitpilot.agents.base import BaseAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.core.schemas import AgentResult, AgentTask, ApplicationContext, DTAAgentOutput, SAEAgentOutput


class DTAAgent(BaseAgent):
    """Dynamic Timeline Architect 代理实现。"""

    name = "dta"

    def __init__(self, service: DynamicTimelineService) -> None:
        """注入 DTA 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行时间规划并输出关键统计。"""
        sae_data: SAEAgentOutput = context.shared_memory.get(
            "sae",
            {
                "summary": "",
                "strengths": [],
                "weaknesses": [],
                "gap_count": 0,
                "tiers": [],
            },
        )
        priorities = sae_data.get("tiers", [])
        plan = self.service.build_plan(priorities=priorities, constraints=context.constraints)
        output: DTAAgentOutput = {
            "title": plan.title,
            "milestone_count": len(plan.milestones),
            "week_count": len(plan.weeks),
            "risk_weeks": [item.week for item in plan.weeks if item.risks],
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.8,
        )
