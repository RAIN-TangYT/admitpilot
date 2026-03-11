"""SAE 代理入口。"""

from __future__ import annotations

from typing import cast

from admitpilot.agents.base import BaseAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import AIEAgentOutput, AgentResult, AgentTask, ApplicationContext, SAEAgentOutput


class SAEAgent(BaseAgent):
    """Strategic Admissions Evaluator 代理实现。"""

    name = "sae"

    def __init__(self, service: StrategicAdmissionsService) -> None:
        """注入 SAE 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行匹配评估并输出结构化摘要。"""
        intelligence: AIEAgentOutput = context.shared_memory.get(
            "aie",
            {
                "official_update_count": 0,
                "official_memory_count": 0,
                "case_memory_count": 0,
                "forecast_count": 0,
                "official_status": "unknown",
                "as_of_date": "",
                "cache_hit_count": 0,
                "prediction_used": False,
                "official_confidence": 0.0,
                "case_confidence": 0.0,
                "target_schools": [],
                "target_program": "",
            },
        )
        report = self.service.evaluate(user_profile=context.profile, intelligence=intelligence)
        output: SAEAgentOutput = {
            "summary": report.summary,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
            "gap_count": len(report.gaps),
            "tiers": [item.tier for item in report.recommendations],
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.78,
        )
