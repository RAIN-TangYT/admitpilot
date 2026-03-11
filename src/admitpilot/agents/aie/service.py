"""AIE 业务服务实现。"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean

from admitpilot.agents.aie.schemas import (
    AdmissionsIntelligencePack,
    CaseRecord,
    CaseSnapshot,
    ForecastSignal,
    OfficialAdmissionRecord,
    OfficialCycleSnapshot,
)


@dataclass(slots=True)
class _OfficialCacheEntry:
    snapshot: OfficialCycleSnapshot
    expires_at: datetime


@dataclass(slots=True)
class _CaseCacheEntry:
    snapshot: CaseSnapshot
    expires_at: datetime


class AdmissionsIntelligenceService:
    """负责招生知识检索、更新识别与置信度推断。"""

    OFFICIAL_SCHOOLS = ("NUS", "NTU", "HKU", "CUHK", "HKUST")
    _CASE_SOURCE_SCORE = {"agency": 0.72, "forum": 0.55, "xiaohongshu": 0.48}

    def __init__(self) -> None:
        self._official_long_memory = self._build_official_long_memory()
        self._case_long_memory = self._build_case_long_memory()
        self._official_short_memory: dict[str, _OfficialCacheEntry] = {}
        self._case_short_memory: dict[str, _CaseCacheEntry] = {}

    def retrieve(
        self,
        query: str,
        cycle: str,
        schools: list[str] | None = None,
        program: str = "MSCS",
        as_of_date: date | None = None,
    ) -> AdmissionsIntelligencePack:
        """返回标准化招生情报包。"""
        target_schools = schools or list(self.OFFICIAL_SCHOOLS)
        target_date = as_of_date or date.today()
        official_snapshots: list[OfficialCycleSnapshot] = []
        forecast_signals: list[ForecastSignal] = []
        cache_hit_count = 0
        for school in target_schools:
            snapshot, cache_hit = self._resolve_official_snapshot(
                school=school,
                program=program,
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
                    )
                )
            official_snapshots.append(snapshot)
        case_snapshot, case_cache_hit = self._resolve_case_snapshot(
            schools=target_schools,
            program=program,
            cycle=cycle,
            as_of_date=target_date,
        )
        if case_cache_hit:
            cache_hit_count += 1
        return AdmissionsIntelligencePack(
            official_long_memory=[
                record
                for record in self._official_long_memory
                if record.school in target_schools and record.program == program
            ],
            case_long_memory=[
                record
                for record in self._case_long_memory
                if record.school in target_schools and record.program == program
            ],
            official_cycle_snapshots=official_snapshots,
            case_snapshot=case_snapshot,
            forecast_signals=forecast_signals,
            cache_hit_count=cache_hit_count,
        )

    def _resolve_official_snapshot(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> tuple[OfficialCycleSnapshot, bool]:
        cache_key = self._official_cache_key(school=school, program=program, cycle=cycle, as_of_date=as_of_date)
        now = datetime.now()
        cached = self._official_short_memory.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.snapshot, True
        published = self._is_cycle_published(school=school, cycle=cycle)
        if published:
            records = self._fetch_official_cycle_records(
                school=school,
                program=program,
                cycle=cycle,
                query=query,
                as_of_date=as_of_date,
            )
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
                expires_at=now + timedelta(hours=24),
            )
        else:
            basis_records = self._historical_official_records(school=school, program=program)
            snapshot = self._build_predicted_snapshot(
                school=school, program=program, cycle=cycle, as_of_date=as_of_date, basis_records=basis_records
            )
        self._official_short_memory[cache_key] = _OfficialCacheEntry(
            snapshot=snapshot,
            expires_at=snapshot.expires_at or now + timedelta(hours=24),
        )
        return snapshot, False

    def _resolve_case_snapshot(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> tuple[CaseSnapshot, bool]:
        cache_key = self._case_cache_key(schools=schools, program=program, cycle=cycle, as_of_date=as_of_date)
        now = datetime.now()
        cached = self._case_short_memory.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.snapshot, True
        records = [item for item in self._case_long_memory if item.school in schools and item.program == program]
        confidence_bands = {"high": 0, "medium": 0, "low": 0}
        for item in records:
            if item.confidence >= 0.75:
                confidence_bands["high"] += 1
            elif item.confidence >= 0.6:
                confidence_bands["medium"] += 1
            else:
                confidence_bands["low"] += 1
        patterns = [
            f"{cycle} 前置准备更看重课程契合与证据链完整性",
            "高置信案例显示科研与实习叙事闭环可显著降低拒录风险",
        ]
        snapshot = CaseSnapshot(
            snapshot_date=as_of_date,
            sample_size=len(records),
            patterns=patterns,
            confidence_distribution=confidence_bands,
            expires_at=now + timedelta(days=3),
        )
        self._case_short_memory[cache_key] = _CaseCacheEntry(snapshot=snapshot, expires_at=snapshot.expires_at)
        return snapshot, False

    def _fetch_official_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        fetched_at = datetime.now()
        pages = (
            ("admission", "admission", True, "updated"),
            ("requirement", "requirement", False, "updated"),
            ("faq", "faq", True, "new"),
        )
        results: list[OfficialAdmissionRecord] = []
        for page_type, section, changed, change_type in pages:
            content = f"{school} {cycle} {program} {section} 与查询“{query}”相关。"
            parse_score = 0.96 if section != "faq" else 0.91
            fresh_score = math.exp(-1 / 30)
            confidence = self._official_confidence(source_score=1.0, parse_score=parse_score, fresh_score=fresh_score)
            source_hash = hashlib.sha256(f"{school}|{program}|{cycle}|{page_type}|{content}".encode("utf-8")).hexdigest()
            record = OfficialAdmissionRecord(
                school=school,
                program=program,
                cycle=cycle,
                page_type=page_type,
                source_url=f"https://www.{school.lower()}.edu/admissions/{program.lower()}",
                content=content,
                published_date=as_of_date,
                effective_date=as_of_date,
                fetched_at=fetched_at,
                source_hash=source_hash,
                quality_score=parse_score,
                confidence=confidence,
                is_policy_change=changed,
                change_type=change_type,
                delta_summary=f"{school} {page_type} 条目于 {as_of_date.isoformat()} 更新",
            )
            results.append(record)
            self._official_long_memory.append(record)
        return results

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
            prediction_basis=[f"{school}-{item.cycle}-{item.page_type}" for item in basis_records[-6:]],
            expires_at=datetime.now() + timedelta(days=7),
        )

    def _historical_official_records(self, school: str, program: str) -> list[OfficialAdmissionRecord]:
        return [item for item in self._official_long_memory if item.school == school and item.program == program]

    def _is_cycle_published(self, school: str, cycle: str) -> bool:
        return cycle[-1].isdigit() and (int(cycle[-1]) + len(school)) % 3 != 0

    def _official_cache_key(self, school: str, program: str, cycle: str, as_of_date: date) -> str:
        return f"aie:official:{school}:{program}:{cycle}:{as_of_date.isoformat()}"

    def _case_cache_key(self, schools: list[str], program: str, cycle: str, as_of_date: date) -> str:
        school_part = ",".join(sorted(schools))
        return f"aie:case_snapshot:{school_part}:{program}:{cycle}:{as_of_date.isoformat()}"

    def _official_confidence(self, source_score: float, parse_score: float, fresh_score: float) -> float:
        return 0.7 * source_score + 0.2 * parse_score + 0.1 * fresh_score

    def _case_confidence(
        self, source_score: float, completeness: float, consistency: float, freshness: float
    ) -> float:
        return 0.35 * source_score + 0.25 * completeness + 0.25 * consistency + 0.15 * freshness

    def _build_official_long_memory(self) -> list[OfficialAdmissionRecord]:
        records: list[OfficialAdmissionRecord] = []
        today = date.today()
        for school in self.OFFICIAL_SCHOOLS:
            for offset in range(1, 6):
                cycle_year = today.year - offset
                published_date = date(cycle_year, 9, 1)
                content = f"{school} {cycle_year} 历史招生政策归档。"
                source_hash = hashlib.sha256(f"{school}|MSCS|{cycle_year}|history".encode("utf-8")).hexdigest()
                records.append(
                    OfficialAdmissionRecord(
                        school=school,
                        program="MSCS",
                        cycle=str(cycle_year),
                        page_type="policy",
                        source_url=f"https://www.{school.lower()}.edu/admissions/mscs",
                        content=content,
                        published_date=published_date,
                        effective_date=published_date,
                        fetched_at=datetime.now() - timedelta(days=offset * 180),
                        source_hash=source_hash,
                        quality_score=0.9,
                        confidence=0.9,
                        is_policy_change=offset % 2 == 0,
                        change_type="updated",
                        delta_summary=f"{school} {cycle_year} 年政策归档",
                    )
                )
        return records

    def _build_case_long_memory(self) -> list[CaseRecord]:
        records: list[CaseRecord] = []
        today = datetime.now()
        for school in self.OFFICIAL_SCHOOLS:
            for idx, source_type in enumerate(("agency", "forum", "xiaohongshu"), start=1):
                source_score = self._CASE_SOURCE_SCORE[source_type]
                completeness = 0.65 + idx * 0.08
                consistency = 0.55 + idx * 0.1
                freshness = math.exp(-(idx * 45) / 180)
                confidence = self._case_confidence(
                    source_score=source_score,
                    completeness=min(completeness, 0.95),
                    consistency=min(consistency, 0.95),
                    freshness=freshness,
                )
                records.append(
                    CaseRecord(
                        candidate_fingerprint=f"{school}-{idx}",
                        school=school,
                        program="MSCS",
                        cycle=str(today.year - idx),
                        source_type=source_type,
                        source_url=f"https://example.com/{source_type}/{school.lower()}",
                        background_summary="GPA3.7+，语言105+，有科研与实习组合背景",
                        outcome="admit" if idx == 1 else "unknown",
                        captured_at=today - timedelta(days=idx * 45),
                        source_site_score=source_score,
                        evidence_completeness=min(completeness, 0.95),
                        cross_source_consistency=min(consistency, 0.95),
                        freshness_score=freshness,
                        confidence=confidence,
                    )
                )
        return records
