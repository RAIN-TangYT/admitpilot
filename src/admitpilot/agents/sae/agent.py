"""SAE 代理入口。"""

from __future__ import annotations

from typing import cast

from admitpilot.agents.base import BaseAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import (
    AgentResult,
    AgentTask,
    AIEAgentOutput,
    ApplicationContext,
    SAEAgentOutput,
)


class SAEAgent(BaseAgent):
    """Strategic Admissions Evaluator 代理实现。"""

    name = "sae"

    def __init__(self, service: StrategicAdmissionsService) -> None:
        """注入 SAE 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行匹配评估并输出结构化摘要。"""
        intelligence = cast(
            AIEAgentOutput,
            context.shared_memory.get(
                "aie",
                {
                    "cycle": "",
                    "as_of_date": "",
                    "target_schools": [],
                    "target_program": "",
                    "official_status_by_school": {},
                    "official_records": [],
                    "case_records": [],
                    "case_patterns": [],
                    "forecast_signals": [],
                    "evidence_levels": {},
                    "official_confidence": 0.0,
                    "case_confidence": 0.0,
                    "cache_hit_count": 0,
                    "prediction_used": False,
                },
            ),
        )
        report = self.service.evaluate(user_profile=context.profile, intelligence=intelligence)
        output: SAEAgentOutput = {
            "summary": report.summary,
            "model_breakdown": report.model_breakdown,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
            "gap_actions": report.gap_actions,
            "recommendations": [
                {
                    "school": item.school,
                    "program": item.program,
                    "tier": item.tier,
                    "rule_score": item.rule_score,
                    "semantic_score": item.semantic_score,
                    "risk_score": item.risk_score,
                    "overall_score": item.overall_score,
                    "reasons": item.reasons,
                    "rule_breakdown": item.rule_breakdown,
                    "rule_notes": item.rule_notes,
                    "evidence": item.evidence,
                    "gaps": item.gaps,
                    "risk_flags": item.risk_flags,
                    "missing_inputs": item.missing_inputs,
                    "semantic_breakdown": item.semantic_breakdown,
                }
                for item in report.recommendations
            ],
            "ranking_order": report.ranking_order,
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.78,
        )
