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
        strategy: SAEAgentOutput = context.shared_memory.get(
            "sae",
            {
                "summary": "",
                "strengths": [],
                "weaknesses": [],
                "gap_count": 0,
                "tiers": [],
            },
        )
        timeline: DTAAgentOutput = context.shared_memory.get(
            "dta",
            {"title": "", "milestone_count": 0, "week_count": 0, "risk_weeks": []},
        )
        pack = self.service.build_support_pack(strategy=strategy, timeline=timeline)
        output: CDSAgentOutput = {
            "blueprint_count": len(pack.blueprints),
            "interview_cue_count": len(pack.interview_cues),
            "document_types": [item.document_type for item in pack.blueprints],
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=0.82,
        )
