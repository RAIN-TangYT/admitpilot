"""AIE 代理入口。"""

from __future__ import annotations

from datetime import date
from typing import cast

from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.agents.base import BaseAgent
from admitpilot.core.schemas import AIEAgentOutput, AgentResult, AgentTask, ApplicationContext


class AIEAgent(BaseAgent):
    """Admissions Intelligence Engine 代理实现。"""

    name = "aie"

    def __init__(self, service: AdmissionsIntelligenceService) -> None:
        """注入 AIE 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行招生情报任务并输出标准结果。"""
        cycle = str(context.constraints.get("cycle", "2026"))
        target_schools = self._resolve_target_schools(task=task, context=context)
        target_program = self._resolve_target_program(task=task, context=context)
        pack = self.service.retrieve(
            query=context.user_query,
            cycle=cycle,
            schools=target_schools,
            program=target_program,
            as_of_date=date.today(),
        )
        official_status = "official_found"
        if any(item.is_predicted for item in pack.official_cycle_snapshots):
            official_status = "mixed"
        if all(item.is_predicted for item in pack.official_cycle_snapshots):
            official_status = "predicted"
        avg_official_confidence = (
            sum(item.confidence for item in pack.official_cycle_snapshots) / len(pack.official_cycle_snapshots)
            if pack.official_cycle_snapshots
            else 0.0
        )
        case_confidence = 0.0
        if pack.case_long_memory:
            case_confidence = sum(item.confidence for item in pack.case_long_memory) / len(pack.case_long_memory)
        output: AIEAgentOutput = {
            "official_update_count": sum(len(item.entries) for item in pack.official_cycle_snapshots),
            "official_memory_count": len(pack.official_long_memory),
            "case_memory_count": len(pack.case_long_memory),
            "forecast_count": len(pack.forecast_signals),
            "official_status": official_status,
            "as_of_date": date.today().isoformat(),
            "cache_hit_count": pack.cache_hit_count,
            "prediction_used": official_status != "official_found",
            "official_confidence": avg_official_confidence,
            "case_confidence": case_confidence,
            "target_schools": target_schools,
            "target_program": target_program,
        }
        return AgentResult(
            agent=self.name,
            task=task.name,
            success=True,
            output=cast(dict, output),
            confidence=max(avg_official_confidence, case_confidence),
        )

    def _resolve_target_schools(self, task: AgentTask, context: ApplicationContext) -> list[str]:
        payload_schools = task.payload.get("target_schools", [])
        constraint_schools = context.constraints.get("target_schools", [])
        schools = payload_schools if isinstance(payload_schools, list) and payload_schools else constraint_schools
        if isinstance(schools, list) and schools:
            return [str(item).upper() for item in schools]
        return list(self.service.OFFICIAL_SCHOOLS)

    def _resolve_target_program(self, task: AgentTask, context: ApplicationContext) -> str:
        payload_program = task.payload.get("target_program")
        if isinstance(payload_program, str) and payload_program:
            return payload_program
        constraint_program = context.constraints.get("target_program")
        if isinstance(constraint_program, str) and constraint_program:
            return constraint_program
        if context.profile.major_interest:
            return context.profile.major_interest
        return "MSCS"
