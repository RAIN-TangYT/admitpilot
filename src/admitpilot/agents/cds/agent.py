"""CDS 代理入口。"""

from __future__ import annotations

from typing import cast

from admitpilot.agents.base import BaseAgent
from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.core.schemas import (
    AgentResult,
    AgentTask,
    ApplicationContext,
    CDSAgentOutput,
    DTAAgentOutput,
    SAEAgentOutput,
)


class CDSAgent(BaseAgent):
    """Core Document Specialist 代理实现。"""

    name = "cds"

    def __init__(self, service: CoreDocumentService) -> None:
        """注入 CDS 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行文书支持任务并输出结果摘要。"""
        strategy = cast(
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
        timeline = cast(
            DTAAgentOutput,
            context.shared_memory.get(
            "dta",
            {
                "board_title": "",
                "milestones": [],
                "weekly_plan": [],
                "risk_markers": [],
                "document_instructions": [],
            },
            ),
        )
        pack = self.service.build_support_pack(strategy=strategy, timeline=timeline)
        output: CDSAgentOutput = {
            "document_drafts": [
                {
                    "document_type": item.document_type,
                    "target_school": item.target_school,
                    "version": item.version,
                    "content_outline": item.content_outline,
                    "fact_slots": [
                        {
                            "slot_id": slot.slot_id,
                            "value": slot.value,
                            "source": slot.source,
                            "verified": slot.verified,
                        }
                        for slot in item.fact_slots
                    ],
                    "risks": item.risks,
                    "review_status": item.review_status,
                }
                for item in pack.drafts
            ],
            "interview_talking_points": [
                f"{item.question} -> {item.cue}" for item in pack.interview_cues
            ],
            "consistency_issues": [
                {
                    "severity": item.severity,
                    "message": item.message,
                    "impacted_documents": item.impacted_documents,
                }
                for item in pack.consistency_issues
            ],
            "review_checklist": pack.review_checklist,
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.82,
        )
