"""AIE 代理入口。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from admitpilot.agents.aie.live_sources import build_live_source_url_map
from admitpilot.agents.aie.schemas import CaseRecord, ForecastSignal
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.agents.base import BaseAgent
from admitpilot.core.english import english_or
from admitpilot.core.schemas import AgentResult, AgentTask, AIEAgentOutput, ApplicationContext
from admitpilot.platform.common.time import utc_today


class AIEAgent(BaseAgent):
    """Admissions Intelligence Engine 代理实现。"""

    name = "aie"

    def __init__(self, service: AdmissionsIntelligenceService) -> None:
        """注入 AIE 服务。"""
        self.service = service
        self._live_source_urls = build_live_source_url_map()

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
        target_program_by_school, unsupported_program_by_school = (
            self._resolve_target_programs_by_school(
                task=task,
                context=context,
                target_schools=target_schools,
            )
        )
        active_schools = [
            school for school in target_schools if school in target_program_by_school
        ]
        packs = [
            self.service.retrieve(
                query=context.user_query,
                cycle=cycle,
                schools=[school],
                program=target_program_by_school[school],
                as_of_date=utc_today(),
            )
            for school in active_schools
        ]
        official_snapshots = [
            snapshot
            for pack in packs
            for snapshot in pack.official_cycle_snapshots
        ]
        official_status_by_school: dict[str, str] = {
            snapshot.school: snapshot.status for snapshot in official_snapshots
        }
        for school in unsupported_program_by_school:
            official_status_by_school[school] = "unsupported_program"
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
            dict.fromkeys(target_program_by_school[school] for school in active_schools)
        )
        official_source_urls_by_school = self._build_official_source_urls_by_school(
            target_program_by_school=target_program_by_school,
            official_snapshots=official_snapshots,
        )
        target_program = "UNSUPPORTED_PROGRAM"
        if unique_programs:
            target_program = (
                unique_programs[0]
                if len(unique_programs) == 1
                else "MULTI_PROGRAM_PORTFOLIO"
            )
        output: AIEAgentOutput = {
            "cycle": cycle,
            "as_of_date": utc_today().isoformat(),
            "target_schools": target_schools,
            "target_program": target_program,
            "target_program_by_school": dict(target_program_by_school),
            "unsupported_program_by_school": dict(unsupported_program_by_school),
            "official_source_urls_by_school": official_source_urls_by_school,
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
        query_schools = self.service.catalog.extract_school_codes_from_text(context.user_query)
        if query_schools:
            return query_schools
        if context.profile.target_schools:
            return self.service.catalog.normalize_school_scope(context.profile.target_schools)
        return list(self.service.catalog.all_school_codes())

    def _resolve_explicit_target_program(
        self,
        task: AgentTask,
        context: ApplicationContext,
    ) -> str | None:
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
        return None

    def _resolve_target_programs_by_school(
        self,
        task: AgentTask,
        context: ApplicationContext,
        target_schools: list[str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        portfolio = self.service.catalog.default_program_portfolio(target_schools)
        unsupported_program_by_school: dict[str, str] = {}
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
        explicit_program = self._resolve_explicit_target_program(task=task, context=context)
        normalized_explicit = (
            self.service.catalog.normalize_program_code(explicit_program)
            if explicit_program is not None
            else None
        )
        if normalized_explicit is not None:
            for school in target_schools:
                if self.service.catalog.is_supported_program(school, normalized_explicit):
                    portfolio[school] = normalized_explicit
        query_mentions_program = self.service.catalog.has_program_intent(context.user_query)
        query_schools = set(self.service.catalog.extract_school_codes_from_text(context.user_query))
        query_program_hint = self.service.catalog.extract_program_hint(context.user_query)
        for school in target_schools:
            query_programs = self.service.catalog.extract_program_codes_from_text(
                context.user_query,
                school_code=school,
            )
            if query_programs:
                portfolio[school] = query_programs[0]
                unsupported_program_by_school.pop(school, None)
                continue
            if not query_mentions_program:
                continue
            if query_schools and school not in query_schools:
                continue
            unsupported_program_by_school[school] = query_program_hint or "unsupported_program"
            portfolio.pop(school, None)
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
                    unsupported_program_by_school.pop(school_code, None)
        payload_unsupported = task.payload.get("unsupported_program_by_school")
        if isinstance(payload_unsupported, dict):
            for raw_school, raw_program in payload_unsupported.items():
                school_code = self.service.catalog.normalize_school_code(str(raw_school))
                if school_code is None or school_code not in target_schools:
                    continue
                unsupported_program_by_school[school_code] = english_or(
                    raw_program,
                    "unsupported_program",
                )
                portfolio.pop(school_code, None)
        supported_programs_by_school = {
            school: portfolio.get(school) or self.service.catalog.supported_programs(school)[0]
            for school in target_schools
            if school not in unsupported_program_by_school
        }
        return supported_programs_by_school, unsupported_program_by_school

    def _build_official_source_urls_by_school(
        self,
        target_program_by_school: Mapping[str, str],
        official_snapshots: list[Any],
    ) -> dict[str, dict[str, str]]:
        urls_by_school: dict[str, dict[str, str]] = {}
        for snapshot in official_snapshots:
            record = self._to_dict(snapshot)
            school = str(record.get("school", "")).strip()
            if not school:
                continue
            raw_source_urls = record.get("source_urls", {})
            if not isinstance(raw_source_urls, dict):
                continue
            snapshot_urls = {
                str(key): str(value).strip()
                for key, value in raw_source_urls.items()
                if str(key).strip() and str(value).strip()
            }
            if snapshot_urls:
                urls_by_school[school] = snapshot_urls
        for school, program in target_program_by_school.items():
            if school in urls_by_school:
                continue
            source_urls = self._live_source_urls.get((school, program))
            if not source_urls:
                continue
            urls_by_school[school] = dict(source_urls)
        return urls_by_school

    def _build_evidence_levels(self, status_by_school: Mapping[str, str]) -> dict[str, str]:
        levels: dict[str, str] = {}
        for school, status in status_by_school.items():
            if status == "official_found":
                levels[school] = "official_primary"
            elif status == "unsupported_program":
                levels[school] = "unsupported_program"
            else:
                levels[school] = "forecast_with_history"
        return levels

    def _official_record_to_dict(self, item: object) -> dict[str, Any]:
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
            "delta_summary": str(record.get("delta_summary", "")),
            "effective_date": str(record.get("effective_date", "")),
            "published_date": str(record.get("published_date", "")),
            "extracted_fields": dict(record.get("extracted_fields", {})),
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
