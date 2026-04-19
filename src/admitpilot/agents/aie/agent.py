"""AIE 代理入口。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from admitpilot.agents.aie.schemas import CaseRecord, ForecastSignal
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
        target_program_by_school = self._resolve_target_programs_by_school(
            task=task,
            context=context,
            target_schools=target_schools,
        )
        packs = [
            self.service.retrieve(
                query=context.user_query,
                cycle=cycle,
                schools=[school],
                program=target_program_by_school[school],
                as_of_date=utc_today(),
            )
            for school in target_schools
        ]
        official_snapshots = [
            snapshot
            for pack in packs
            for snapshot in pack.official_cycle_snapshots
        ]
        official_status_by_school = {
            snapshot.school: snapshot.status for snapshot in official_snapshots
        }
        forecast_signals: list[ForecastSignal] = []
        seen_forecast_keys: set[tuple[str, str]] = set()
        for pack in packs:
            for signal in pack.forecast_signals:
                forecast_key = (signal.school, signal.reason)
                if forecast_key in seen_forecast_keys:
                    continue
                seen_forecast_keys.add(forecast_key)
                forecast_signals.append(signal)
        case_records: list[CaseRecord] = []
        seen_case_keys: set[tuple[str, str, str, str]] = set()
        for pack in packs:
            for item in pack.case_long_memory:
                case_key = (
                    item.candidate_fingerprint,
                    item.school,
                    item.program,
                    item.cycle,
                )
                if case_key in seen_case_keys:
                    continue
                seen_case_keys.add(case_key)
                case_records.append(item)
        case_patterns: list[str] = []
        for pack in packs:
            for pattern in pack.case_snapshot.patterns if pack.case_snapshot else []:
                if pattern not in case_patterns:
                    case_patterns.append(pattern)
        avg_official_confidence = (
            sum(item.confidence for item in official_snapshots)
            / len(official_snapshots)
            if official_snapshots
            else 0.0
        )
        case_confidence = 0.0
        if case_records:
            case_confidence = sum(item.confidence for item in case_records) / len(case_records)
        prediction_used = any(item.is_predicted for item in official_snapshots)
        unique_programs = list(
            dict.fromkeys(target_program_by_school[school] for school in target_schools)
        )
        target_program = (
            unique_programs[0] if len(unique_programs) == 1 else "MULTI_PROGRAM_PORTFOLIO"
        )
        output: AIEAgentOutput = {
            "cycle": cycle,
            "as_of_date": utc_today().isoformat(),
            "target_schools": target_schools,
            "target_program": target_program,
            "target_program_by_school": dict(target_program_by_school),
            "official_status_by_school": {
                school: str(status) for school, status in official_status_by_school.items()
            },
            "official_records": [
                self._official_record_to_dict(item)
                for snapshot in official_snapshots
                for item in snapshot.entries
            ],
            "case_records": [self._case_record_to_dict(item) for item in case_records],
            "case_patterns": case_patterns,
            "forecast_signals": [
                {
                    "school": signal.school,
                    "insight": signal.insight,
                    "confidence": signal.confidence,
                    "basis": signal.basis,
                    "reason": signal.reason,
                }
                for signal in forecast_signals
            ],
            "evidence_levels": self._build_evidence_levels(official_status_by_school),
            "official_confidence": avg_official_confidence,
            "case_confidence": case_confidence,
            "cache_hit_count": sum(pack.cache_hit_count for pack in packs),
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
            return self.service.catalog.normalize_school_scope(str(item) for item in schools)
        if context.profile.target_schools:
            return self.service.catalog.normalize_school_scope(context.profile.target_schools)
        return list(self.service.catalog.all_school_codes())

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

    def _resolve_target_programs_by_school(
        self,
        task: AgentTask,
        context: ApplicationContext,
        target_schools: list[str],
    ) -> dict[str, str]:
        portfolio = self.service.catalog.default_program_portfolio(target_schools)
        profile_programs = [
            normalized
            for item in context.profile.target_programs
            if (normalized := self.service.catalog.normalize_program_code(item)) is not None
        ]
        for school in target_schools:
            for program in profile_programs:
                if self.service.catalog.is_supported_program(school, program):
                    portfolio[school] = program
                    break
        explicit_program = self._resolve_target_program(task=task, context=context)
        normalized_explicit = self.service.catalog.normalize_program_code(explicit_program)
        if normalized_explicit is not None:
            for school in target_schools:
                if self.service.catalog.is_supported_program(school, normalized_explicit):
                    portfolio[school] = normalized_explicit
        for raw_mapping in (
            context.constraints.get("target_program_by_school"),
            task.payload.get("target_program_by_school"),
        ):
            if not isinstance(raw_mapping, dict):
                continue
            for raw_school, raw_program in raw_mapping.items():
                school_code = self.service.catalog.normalize_school_code(str(raw_school))
                program_code = self.service.catalog.normalize_program_code(str(raw_program))
                if school_code is None or program_code is None:
                    continue
                if school_code not in target_schools:
                    continue
                if self.service.catalog.is_supported_program(school_code, program_code):
                    portfolio[school_code] = program_code
        return {
            school: portfolio.get(school) or self.service.catalog.supported_programs(school)[0]
            for school in target_schools
        }

    def _build_evidence_levels(self, status_by_school: Mapping[str, str]) -> dict[str, str]:
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
            "parse_confidence": float(record.get("parse_confidence", 0.0)),
            "is_policy_change": bool(record.get("is_policy_change", False)),
            "change_type": str(record.get("change_type", "")),
            "changed_fields": ",".join(
                str(item) for item in record.get("changed_fields", []) if str(item)
            ),
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
