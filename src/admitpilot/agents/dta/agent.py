"""DTA 代理入口。"""

from __future__ import annotations

from typing import cast

from admitpilot.agents.base import BaseAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.core.schemas import (
    AgentResult,
    AgentTask,
    AIEAgentOutput,
    ApplicationContext,
    DTAAgentOutput,
    SAEAgentOutput,
)


class DTAAgent(BaseAgent):
    """Dynamic Timeline Architect 代理实现。"""

    name = "dta"

    def __init__(self, service: DynamicTimelineService) -> None:
        """注入 DTA 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行时间规划并输出关键统计。"""
        sae_data = cast(
            SAEAgentOutput,
            context.shared_memory.get(
                "sae",
                {
                    "summary": "",
                    "model_breakdown": {},
                    "strengths": [],
                    "weaknesses": [],
                    "gap_actions": [],
                    "recommendations": [],
                    "ranking_order": [],
                },
            ),
        )
        aie_data = cast(
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
        plan = self.service.build_plan(
            strategy=sae_data, intelligence=aie_data, constraints=context.constraints
        )
        output: DTAAgentOutput = {
            "board_title": plan.title,
            "milestones": [
                {
                    "key": item.key,
                    "title": item.title,
                    "due_week": item.due_week,
                    "status": item.status,
                    "depends_on": item.depends_on,
                }
                for item in plan.milestones
            ],
            "weekly_plan": [
                {
                    "week": item.week,
                    "focus": item.focus,
                    "items": item.items,
                    "risks": item.risks,
                    "school_scope": item.school_scope,
                }
                for item in plan.weeks
            ],
            "risk_markers": [
                {
                    "week": item.week,
                    "level": item.level,
                    "message": item.message,
                    "mitigation": item.mitigation,
                }
                for item in plan.risk_markers
            ],
            "document_instructions": plan.document_instructions,
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.8,
        )
