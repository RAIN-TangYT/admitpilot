"""AIE 业务服务实现。"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from statistics import mean

from admitpilot.agents.aie.prompts import SYSTEM_PROMPT
from admitpilot.agents.aie.gateways import (
    CaseSourceGateway,
    OfficialSourceGateway,
    StubCaseSourceGateway,
    StubOfficialSourceGateway,
)
from admitpilot.agents.aie.repositories import (
    CaseSnapshotRepository,
    InMemoryCaseSnapshotRepository,
    InMemoryOfficialSnapshotRepository,
    OfficialSnapshotRepository,
)
from admitpilot.agents.aie.schemas import (
    AdmissionsIntelligencePack,
    CaseRecord,
    CaseSnapshot,
    ForecastSignal,
    OfficialAdmissionRecord,
    OfficialCycleSnapshot,
)
from admitpilot.platform.llm.qwen import QwenClient


class AdmissionsIntelligenceService:
    """负责招生知识检索、更新识别与置信度推断。"""

    OFFICIAL_SCHOOLS = ("NUS", "NTU", "HKU", "CUHK", "HKUST")

    def __init__(
        self,
        official_gateway: OfficialSourceGateway | None = None,
        case_gateway: CaseSourceGateway | None = None,
        official_repository: OfficialSnapshotRepository | None = None,
        case_repository: CaseSnapshotRepository | None = None,
        llm_client: QwenClient | None = None,
    ) -> None:
        self.official_gateway = official_gateway or StubOfficialSourceGateway()
        self.case_gateway = case_gateway or StubCaseSourceGateway()
        self.official_repository = official_repository or InMemoryOfficialSnapshotRepository()
        self.case_repository = case_repository or InMemoryCaseSnapshotRepository()
        self.llm_client = llm_client or QwenClient()
        self._official_long_memory = self._build_official_long_memory()
        self._case_long_memory: list[CaseRecord] = []

    def retrieve(
        self,
        query: str,
        cycle: str,
        schools: list[str] | None = None,
        program: str = "MSCS",
        as_of_date: date | None = None,
    ) -> AdmissionsIntelligencePack:
        """返回标准化招生情报包。"""
        target_schools = self._normalize_target_schools(schools)
        target_date = as_of_date or date.today()
        normalized_program = self._normalize_program(program)
        official_snapshots: list[OfficialCycleSnapshot] = []
        forecast_signals: list[ForecastSignal] = []
        cache_hit_count = 0
        for school in target_schools:
            snapshot, cache_hit = self._resolve_official_snapshot(
                school=school,
                program=normalized_program,
                cycle=cycle,
                query=query,
                as_of_date=target_date,
            )
            if cache_hit:
                cache_hit_count += 1
            if snapshot.is_predicted:
                forecast_signals.append(
                    ForecastSignal(
                        school=school,
                        insight=f"{school} {cycle} 尚未发布完整官方信息，先按历史稳定项预测。",
                        confidence=snapshot.confidence,
                        basis="official_long_memory",
                        reason="current_cycle_not_released",
                    )
                )
            official_snapshots.append(snapshot)
        case_snapshot, case_cache_hit = self._resolve_case_snapshot(
            schools=target_schools,
            program=normalized_program,
            cycle=cycle,
            as_of_date=target_date,
        )
        if case_cache_hit:
            cache_hit_count += 1
        case_records = self._case_gateway_records_by_scope(target_schools, normalized_program)
        case_patterns = list(case_snapshot.patterns if case_snapshot else [])
        forecast_signals = self._llm_refine_intelligence(
            query=query,
            cycle=cycle,
            program=normalized_program,
            case_patterns=case_patterns,
            forecast_signals=forecast_signals,
            official_snapshots=official_snapshots,
        )
        if case_snapshot is not None:
            case_snapshot.patterns = case_patterns
        status_by_school = {item.school: str(item.status) for item in official_snapshots}
        return AdmissionsIntelligencePack(
            official_long_memory=[
                record
                for record in self._official_long_memory
                if record.school in target_schools and record.program == normalized_program
            ],
            case_long_memory=case_records,
            official_cycle_snapshots=official_snapshots,
            case_snapshot=case_snapshot,
            forecast_signals=forecast_signals,
            official_status_by_school=status_by_school,
            cache_hit_count=cache_hit_count,
        )

    def _llm_refine_intelligence(
        self,
        query: str,
        cycle: str,
        program: str,
        case_patterns: list[str],
        forecast_signals: list[ForecastSignal],
        official_snapshots: list[OfficialCycleSnapshot],
    ) -> list[ForecastSignal]:
        if not self.llm_client.enabled:
            return forecast_signals
        prompt = "\n".join(
            [
                "请基于以下招生情报生成 JSON。",
                '返回格式：{"case_patterns":["..."],"forecast_signals":[{"school":"NUS","insight":"...","basis":"...","reason":"..."}]}',
                "不要输出 markdown。",
                f"query={query}",
                f"cycle={cycle}",
                f"program={program}",
                f"official_status={[{'school': item.school, 'status': item.status, 'confidence': round(item.confidence, 2)} for item in official_snapshots]}",
                f"case_patterns_seed={case_patterns}",
                f"forecast_seed={[{'school': item.school, 'insight': item.insight, 'confidence': round(item.confidence, 2), 'basis': item.basis, 'reason': item.reason} for item in forecast_signals]}",
            ]
        )
        try:
            payload = self.llm_client.chat_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0,
            )
        except RuntimeError:
            return forecast_signals
        llm_patterns = payload.get("case_patterns", [])
        if isinstance(llm_patterns, list):
            normalized_patterns = [str(item).strip() for item in llm_patterns if str(item).strip()]
            if normalized_patterns:
                case_patterns[:] = normalized_patterns[:4]
        llm_signals = payload.get("forecast_signals", [])
        if not isinstance(llm_signals, list):
            return forecast_signals
        signal_by_school = {item.school: item for item in forecast_signals}
        for item in llm_signals:
            if not isinstance(item, dict):
                continue
            school = str(item.get("school", "")).upper()
            if school not in signal_by_school:
                continue
            signal = signal_by_school[school]
            insight = str(item.get("insight", "")).strip()
            basis = str(item.get("basis", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if insight:
                signal.insight = insight
            if basis:
                signal.basis = basis
            if reason:
                signal.reason = reason
        return forecast_signals

    def _resolve_official_snapshot(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> tuple[OfficialCycleSnapshot, bool]:
        cache_key = self._official_cache_key(
            school=school, program=program, cycle=cycle, as_of_date=as_of_date
        )
        now = datetime.utcnow()
        cached = self.official_repository.get(cache_key, as_of=now)
        if cached is not None:
            return cached, True
        released = self.official_gateway.has_cycle_release(
            school=school, cycle=cycle, as_of_date=as_of_date
        )
        if released:
            records = self.official_gateway.fetch_cycle_records(
                school=school,
                program=program,
                cycle=cycle,
                query=query,
                as_of_date=as_of_date,
            )
            self._official_long_memory.extend(records)
            confidence = mean(item.confidence for item in records) if records else 0.0
            snapshot = OfficialCycleSnapshot(
                school=school,
                program=program,
                cycle=cycle,
                as_of_date=as_of_date,
                status="official_found",
                confidence=confidence,
                is_predicted=False,
                entries=records,
                update_released=True,
                expires_at=now + timedelta(hours=24),
            )
            self._official_long_memory.extend(records)
        else:
            basis_records = self._historical_official_records(school=school, program=program)
            snapshot = self._build_predicted_snapshot(
                school=school,
                program=program,
                cycle=cycle,
                as_of_date=as_of_date,
                basis_records=basis_records,
            )
        self.official_repository.save(
            key=cache_key,
            value=snapshot,
            expires_at=snapshot.expires_at or (now + timedelta(hours=24)),
        )
        return snapshot, False

    def _resolve_case_snapshot(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> tuple[CaseSnapshot, bool]:
        cache_key = self._case_cache_key(
            schools=schools, program=program, cycle=cycle, as_of_date=as_of_date
        )
        now = datetime.utcnow()
        cached = self.case_repository.get(cache_key, as_of=now)
        if cached is not None:
            return cached, True
        records = self.case_gateway.fetch_case_records(
            schools=schools,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
        )
        self._case_long_memory.extend(records)
        confidence_bands = {"high": 0, "medium": 0, "low": 0}
        for item in records:
            if item.confidence >= 0.75:
                confidence_bands["high"] += 1
            elif item.confidence >= 0.6:
                confidence_bands["medium"] += 1
            else:
                confidence_bands["low"] += 1
        snapshot = CaseSnapshot(
            snapshot_date=as_of_date,
            sample_size=len(records),
            patterns=[
                f"{cycle} 前置准备更看重课程契合与证据链完整性",
                "高置信案例显示科研与实习叙事闭环可显著降低拒录风险",
            ],
            confidence_distribution=confidence_bands,
            expires_at=now + timedelta(days=3),
        )
        self.case_repository.save(
            key=cache_key,
            value=snapshot,
            expires_at=snapshot.expires_at or (now + timedelta(days=3)),
        )
        return snapshot, False

    def _build_predicted_snapshot(
        self,
        school: str,
        program: str,
        cycle: str,
        as_of_date: date,
        basis_records: list[OfficialAdmissionRecord],
    ) -> OfficialCycleSnapshot:
        if not basis_records:
            history_conf = 0.65
            stability = 0.6
        else:
            history_conf = mean(item.confidence for item in basis_records)
            stability = 0.75 if sum(item.is_policy_change for item in basis_records) <= 4 else 0.55
        signal_strength = 0.62
        confidence = 0.5 * history_conf + 0.3 * stability + 0.2 * signal_strength
        return OfficialCycleSnapshot(
            school=school,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
            status="predicted",
            confidence=confidence,
            is_predicted=True,
            entries=[],
            prediction_basis=[
                f"{school}-{item.cycle}-{item.page_type}" for item in basis_records[-6:]
            ],
            update_released=False,
            expires_at=datetime.now() + timedelta(days=7),
        )

    def _normalize_target_schools(self, schools: list[str] | None) -> list[str]:
        if not schools:
            return list(self.OFFICIAL_SCHOOLS)
        normalized = [str(item).upper() for item in schools]
        filtered = [item for item in normalized if item in self.OFFICIAL_SCHOOLS]
        return filtered or list(self.OFFICIAL_SCHOOLS)

    def _normalize_program(self, program: str) -> str:
        normalized = program.strip()
        return normalized if normalized else "MSCS"

    def _historical_official_records(
        self, school: str, program: str
    ) -> list[OfficialAdmissionRecord]:
        return [
            item
            for item in self._official_long_memory
            if item.school == school and item.program == program
        ]

    def _case_gateway_records_by_scope(self, schools: list[str], program: str) -> list[CaseRecord]:
        return [
            item
            for item in self._case_long_memory
            if item.school in schools and item.program == program
        ]

    def _official_cache_key(self, school: str, program: str, cycle: str, as_of_date: date) -> str:
        return f"aie:official:{school}:{program}:{cycle}:{as_of_date.isoformat()}"

    def _case_cache_key(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> str:
        school_part = ",".join(sorted(schools))
        return f"aie:case_snapshot:{school_part}:{program}:{cycle}:{as_of_date.isoformat()}"

    def _build_official_long_memory(self) -> list[OfficialAdmissionRecord]:
        records: list[OfficialAdmissionRecord] = []
        today = date.today()
        for school in self.OFFICIAL_SCHOOLS:
            for offset in range(1, 6):
                cycle_year = today.year - offset
                published_date = date(cycle_year, 9, 1)
                records.append(
                    OfficialAdmissionRecord(
                        school=school,
                        program="MSCS",
                        cycle=str(cycle_year),
                        page_type="policy",
                        source_url=f"https://www.{school.lower()}.edu/admissions/mscs",
                        content=f"{school} {cycle_year} 历史招生政策归档。",
                        published_date=published_date,
                        effective_date=published_date,
                        fetched_at=datetime.utcnow() - timedelta(days=offset * 180),
                        source_hash=f"{school}-{cycle_year}-history",
                        quality_score=0.9,
                        confidence=self._historical_confidence(offset),
                        version_id=f"{school}-{cycle_year}-policy",
                        is_policy_change=offset % 2 == 0,
                        change_type="updated",
                        delta_summary=f"{school} {cycle_year} 年政策归档",
                    )
                )
        return records

    def _historical_confidence(self, offset: int) -> float:
        """历史数据越久远，置信轻微衰减。"""
        return max(0.72, 0.9 * math.exp(-0.03 * offset))
