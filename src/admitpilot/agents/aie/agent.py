"""AIE 代理入口。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, cast

from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.agents.base import BaseAgent
from admitpilot.core.schemas import AgentResult, AgentTask, AIEAgentOutput, ApplicationContext
from admitpilot.platform.common.time import utc_today


class AIEAgent(BaseAgent):
    """Admissions Intelligence Engine 代理实现。"""

    name = "aie"

    def __init__(self, service: AdmissionsIntelligenceService) -> None:
        """注入 AIE 服务。"""
        self.service = service

    def run(self, task: AgentTask, context: ApplicationContext) -> AgentResult:
        """执行招生情报任务并输出标准结果。"""
        if task.name == "llm_smoke_test":
            from admitpilot.platform.llm.openai import openai_chat

            prompt = str(task.payload.get("prompt") or context.user_query or "ping")
            resp = openai_chat(prompt=prompt)
            return AgentResult(
                agent=self.name,
                task=task.name,
                success=True,
                output={"provider": "openai", "prompt": prompt, "content": resp.content},
                confidence=1.0,
            )
        cycle = str(context.constraints.get("cycle", "2026"))
        target_schools = self._resolve_target_schools(task=task, context=context)
        target_program = self._resolve_target_program(task=task, context=context)
        pack = self.service.retrieve(
            query=context.user_query,
            cycle=cycle,
            schools=target_schools,
            program=target_program,
            as_of_date=utc_today(),
        )
        avg_official_confidence = (
            sum(item.confidence for item in pack.official_cycle_snapshots)
            / len(pack.official_cycle_snapshots)
            if pack.official_cycle_snapshots
            else 0.0
        )
        case_confidence = 0.0
        if pack.case_long_memory:
            case_confidence = sum(item.confidence for item in pack.case_long_memory) / len(
                pack.case_long_memory
            )
        prediction_used = any(item.is_predicted for item in pack.official_cycle_snapshots)
        output: AIEAgentOutput = {
            "cycle": cycle,
            "as_of_date": utc_today().isoformat(),
            "target_schools": target_schools,
            "target_program": target_program,
            "official_status_by_school": dict(pack.official_status_by_school),
            "official_records": [
                self._official_record_to_dict(item)
                for snapshot in pack.official_cycle_snapshots
                for item in snapshot.entries
            ],
            "case_records": [self._case_record_to_dict(item) for item in pack.case_long_memory],
            "case_patterns": list(pack.case_snapshot.patterns if pack.case_snapshot else []),
            "forecast_signals": [
                {
                    "school": signal.school,
                    "insight": signal.insight,
                    "confidence": signal.confidence,
                    "basis": signal.basis,
                    "reason": signal.reason,
                }
                for signal in pack.forecast_signals
            ],
            "evidence_levels": self._build_evidence_levels(pack.official_status_by_school),
            "official_confidence": avg_official_confidence,
            "case_confidence": case_confidence,
            "cache_hit_count": pack.cache_hit_count,
            "prediction_used": prediction_used,
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
        schools = (
            payload_schools
            if isinstance(payload_schools, list) and payload_schools
            else constraint_schools
        )
        if isinstance(schools, list) and schools:
            return [str(item).upper() for item in schools]
        if context.profile.target_schools:
            return [item.upper() for item in context.profile.target_schools]
        return list(self.service.OFFICIAL_SCHOOLS)

    def _resolve_target_program(self, task: AgentTask, context: ApplicationContext) -> str:
        payload_program = task.payload.get("target_program")
        if isinstance(payload_program, str) and payload_program:
            return payload_program
        constraint_program = context.constraints.get("target_program")
        if isinstance(constraint_program, str) and constraint_program:
            return constraint_program
        if context.profile.target_programs:
            return context.profile.target_programs[0]
        if context.profile.major_interest:
            return context.profile.major_interest
        return "MSCS"

    def _build_evidence_levels(self, status_by_school: dict[str, str]) -> dict[str, str]:
        levels: dict[str, str] = {}
        for school, status in status_by_school.items():
            levels[school] = (
                "official_primary" if status == "official_found" else "forecast_with_history"
            )
        return levels

    def _official_record_to_dict(self, item: object) -> dict[str, str | float | bool]:
        record = self._to_dict(item)
        return {
            "school": str(record.get("school", "")),
            "program": str(record.get("program", "")),
            "cycle": str(record.get("cycle", "")),
            "page_type": str(record.get("page_type", "")),
            "source_url": str(record.get("source_url", "")),
            "version_id": str(record.get("version_id", "")),
            "confidence": float(record.get("confidence", 0.0)),
            "is_policy_change": bool(record.get("is_policy_change", False)),
        }

    def _case_record_to_dict(self, item: object) -> dict[str, str | float]:
        record = self._to_dict(item)
        return {
            "school": str(record.get("school", "")),
            "program": str(record.get("program", "")),
            "cycle": str(record.get("cycle", "")),
            "source_type": str(record.get("source_type", "")),
            "credibility_label": str(record.get("credibility_label", "")),
            "confidence": float(record.get("confidence", 0.0)),
        }

    def _to_dict(self, item: object) -> dict[str, Any]:
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        return {}
