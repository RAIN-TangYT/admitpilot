"""AIE 业务服务实现。"""

from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import mean
from typing import Literal

from admitpilot.agents.aie.gateways import (
    CaseSourceGateway,
    NullCaseSourceGateway,
    OfficialLibrarySourceGateway,
    OfficialSourceGateway,
)
from admitpilot.agents.aie.live_sources import build_live_source_url_map
from admitpilot.agents.aie.prompts import SYSTEM_PROMPT
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
from admitpilot.agents.aie.snapshots import diff_official_record, record_identity
from admitpilot.config import AdmitPilotSettings
from admitpilot.core.english import english_items, english_or
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG, AdmissionsCatalog
from admitpilot.platform.common.time import utc_now, utc_today
from admitpilot.platform.llm.openai import OpenAIClient


class AdmissionsIntelligenceService:
    """Retrieve admissions intelligence, update signals, and confidence estimates."""

    OFFICIAL_SCHOOLS = DEFAULT_ADMISSIONS_CATALOG.all_school_codes()

    def __init__(
        self,
        official_gateway: OfficialSourceGateway | None = None,
        case_gateway: CaseSourceGateway | None = None,
        official_repository: OfficialSnapshotRepository | None = None,
        case_repository: CaseSnapshotRepository | None = None,
        llm_client: OpenAIClient | None = None,
        catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
    ) -> None:
        self.catalog = catalog
        self.official_repository = official_repository or InMemoryOfficialSnapshotRepository()
        self.official_gateway = official_gateway or OfficialLibrarySourceGateway(catalog=catalog)
        self.case_gateway = case_gateway or NullCaseSourceGateway()
        self.case_repository = case_repository or InMemoryCaseSnapshotRepository()
        self.llm_client = llm_client or OpenAIClient(settings=AdmitPilotSettings(run_mode="test"))
        self._live_source_urls = build_live_source_url_map()
        self._official_long_memory = self._build_official_long_memory()
        self._case_long_memory: list[CaseRecord] = []

    def retrieve(
        self,
        query: str,
        cycle: str,
        schools: list[str] | None = None,
        program: str = "MSCS",
        as_of_date: date | None = None,
        include_case_updates: bool = True,
    ) -> AdmissionsIntelligencePack:
        """Return a normalized admissions intelligence pack."""

        target_schools = self._normalize_target_schools(schools)
        target_date = as_of_date or utc_today()
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
                        insight=(
                            f"{school} has not released complete {cycle} official information; "
                            "use stable historical requirements as a forecast baseline."
                        ),
                        confidence=snapshot.confidence,
                        basis="official_long_memory",
                        reason="current_cycle_not_released",
                    )
                )
            official_snapshots.append(snapshot)
        case_snapshot: CaseSnapshot | None = None
        case_records: list[CaseRecord] = []
        case_patterns: list[str] = []
        if include_case_updates:
            case_snapshot, case_cache_hit = self._resolve_case_snapshot(
                schools=target_schools,
                program=normalized_program,
                cycle=cycle,
                as_of_date=target_date,
            )
            if case_cache_hit:
                cache_hit_count += 1
            case_records = self._case_gateway_records_by_scope(
                target_schools,
                normalized_program,
                cycle,
            )
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

    def refresh_official_library(
        self,
        query: str,
        cycle: str,
        targets: list[tuple[str, str]],
        as_of_date: date | None = None,
    ) -> list[OfficialCycleSnapshot]:
        """Refresh configured official sources without touching the case library."""

        snapshots: list[OfficialCycleSnapshot] = []
        target_date = as_of_date or utc_today()
        for school, program in targets:
            normalized_school = self.catalog.normalize_school_code(school)
            normalized_program = self._normalize_program(program)
            if normalized_school is None:
                continue
            snapshot, _ = self._resolve_official_snapshot(
                school=normalized_school,
                program=normalized_program,
                cycle=cycle,
                query=query,
                as_of_date=target_date,
            )
            snapshots.append(snapshot)
        return snapshots

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
        official_status_seed = [
            {
                "school": snapshot.school,
                "status": snapshot.status,
                "confidence": round(snapshot.confidence, 2),
                "update_released": snapshot.update_released,
            }
            for snapshot in official_snapshots
        ]
        forecast_seed = [
            {
                "school": signal.school,
                "insight": signal.insight,
                "confidence": round(signal.confidence, 2),
                "basis": signal.basis,
                "reason": signal.reason,
            }
            for signal in forecast_signals
        ]
        prompt = "\n".join(
            [
                (
                    "Generate JSON in English only from the admissions intelligence below."
                ),
                (
                    'Return format: {"case_patterns":["..."],'
                    '"forecast_signals":[{"school":"NUS","insight":"...","basis":"...","reason":"..."}]}'
                ),
                "Do not output markdown. All values must be English.",
                f"query={english_or(query, 'Official admissions query')}",
                f"cycle={cycle}",
                f"program={program}",
                f"official_status={official_status_seed}",
                f"case_patterns_seed={case_patterns}",
                f"forecast_seed={forecast_seed}",
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
        normalized_patterns = english_items(llm_patterns)
        if normalized_patterns:
            case_patterns[:] = normalized_patterns[:4]
        llm_signals = payload.get("forecast_signals", [])
        if not isinstance(llm_signals, list):
            return forecast_signals
        signal_by_school = {item.school: item for item in forecast_signals}
        for item in llm_signals:
            if not isinstance(item, dict):
                continue
            school = self.catalog.normalize_school_code(str(item.get("school", "")) or "")
            if school is None or school not in signal_by_school:
                continue
            signal = signal_by_school[school]
            insight = english_or(item.get("insight"))
            basis = english_or(item.get("basis"))
            reason = english_or(item.get("reason"))
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
        now = utc_now()
        cached = self.official_repository.get(cache_key, as_of=now)
        if cached is not None:
            return cached, True
        released = self.official_gateway.has_cycle_release(
            school=school, program=program, cycle=cycle, as_of_date=as_of_date
        )
        if released:
            records = self.official_gateway.fetch_cycle_records(
                school=school,
                program=program,
                cycle=cycle,
                query=query,
                as_of_date=as_of_date,
            )
            if records:
                versioned_records, update_released = self._version_official_records(records)
                confidence = (
                    mean(item.confidence for item in versioned_records)
                    if versioned_records
                    else 0.0
                )
                expected_page_types = set(self.catalog.default_page_types(school, program))
                fetched_page_types = {item.page_type for item in versioned_records}
                status: Literal["official_found", "mixed"] = (
                    "official_found"
                    if expected_page_types.issubset(fetched_page_types)
                    else "mixed"
                )
                snapshot = OfficialCycleSnapshot(
                    school=school,
                    program=program,
                    cycle=cycle,
                    as_of_date=as_of_date,
                    status=status,
                    confidence=confidence,
                    is_predicted=False,
                    entries=versioned_records,
                    source_urls=self._configured_source_urls(school, program),
                    update_released=update_released,
                    expires_at=now + timedelta(hours=24),
                )
                self._append_official_history(versioned_records)
            else:
                basis_records = self._historical_official_records(school=school, program=program)
                snapshot = self._build_predicted_snapshot(
                    school=school,
                    program=program,
                    cycle=cycle,
                    as_of_date=as_of_date,
                    basis_records=basis_records,
                )
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
        now = utc_now()
        cached = self.case_repository.get(cache_key, as_of=now)
        if cached is not None:
            return cached, True
        records = self.case_gateway.fetch_case_records(
            schools=schools,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
        )
        self._append_case_history(records)
        confidence_bands = {"high": 0, "medium": 0, "low": 0}
        for item in records:
            confidence_bands[item.credibility_label] += 1
        patterns = []
        if records:
            patterns = [
                f"{cycle} preparation favors course fit and complete evidence chains.",
                (
                    "High-confidence cases show that a closed research and internship "
                    "narrative lowers rejection risk."
                ),
            ]
        snapshot = CaseSnapshot(
            snapshot_date=as_of_date,
            sample_size=len(records),
            patterns=patterns,
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
            source_urls=self._configured_source_urls(school, program),
            prediction_basis=[
                f"{school}-{item.cycle}-{item.page_type}:{item.version_id}"
                for item in basis_records[-6:]
            ],
            update_released=False,
            expires_at=utc_now() + timedelta(days=7),
        )

    def _normalize_target_schools(self, schools: list[str] | None) -> list[str]:
        return self.catalog.normalize_school_scope(schools)

    def _normalize_program(self, program: str) -> str:
        normalized = self.catalog.normalize_program_code(program)
        return normalized or "MSCS"

    def _historical_official_records(
        self, school: str, program: str
    ) -> list[OfficialAdmissionRecord]:
        return [
            item
            for item in self._official_long_memory
            if item.school == school and item.program == program
        ]

    def _case_gateway_records_by_scope(
        self, schools: list[str], program: str, cycle: str
    ) -> list[CaseRecord]:
        return [
            item
            for item in self._case_long_memory
            if item.school in schools and item.program == program and item.cycle == cycle
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
        today = utc_today()
        for school in self.catalog.all_school_codes():
            domains = self.catalog.official_domains(school)
            source_url = f"https://{domains[0]}/admissions/archive/mscs/policy.html"
            for offset in range(1, 6):
                cycle_year = today.year - offset
                published_date = date(cycle_year, 9, 1)
                record = OfficialAdmissionRecord(
                    school=school,
                    program="MSCS",
                    cycle=str(cycle_year),
                    page_type="policy",
                    source_url=source_url,
                    content=f"{school} {cycle_year} historical admissions policy archive.",
                    published_date=published_date,
                    effective_date=published_date,
                    fetched_at=utc_now() - timedelta(days=offset * 180),
                    content_hash=f"{school}-{cycle_year}-history",
                    quality_score=0.9,
                    confidence=self._historical_confidence(offset),
                    extracted_fields={"policy_cycle": str(cycle_year)},
                    parse_confidence=0.8,
                    version_id=f"{school}-{cycle_year}-policy",
                    is_policy_change=offset % 2 == 0,
                    change_type="updated",
                    changed_fields=["policy_cycle"] if offset % 2 == 0 else [],
                    delta_summary=f"{school} {cycle_year} policy archive",
                )
                records.append(record)
        return records

    def _historical_confidence(self, offset: int) -> float:
        """Older historical data receives slight confidence decay."""

        return max(0.72, 0.9 * math.exp(-0.03 * offset))

    def _append_official_history(self, records: list[OfficialAdmissionRecord]) -> None:
        existing_keys = {self._official_record_key(item) for item in self._official_long_memory}
        for record in records:
            key = self._official_record_key(record)
            if key in existing_keys:
                continue
            self._official_long_memory.append(record)
            existing_keys.add(key)

    def _append_case_history(self, records: list[CaseRecord]) -> None:
        existing_keys = {
            (item.candidate_fingerprint, item.school, item.program, item.cycle)
            for item in self._case_long_memory
        }
        for record in records:
            key = (record.candidate_fingerprint, record.school, record.program, record.cycle)
            if key in existing_keys:
                continue
            self._case_long_memory.append(record)
            existing_keys.add(key)

    def _version_official_records(
        self, records: list[OfficialAdmissionRecord]
    ) -> tuple[list[OfficialAdmissionRecord], bool]:
        versioned_records: list[OfficialAdmissionRecord] = []
        has_updates = False
        for record in records:
            history_key = record_identity(record)
            previous = self.official_repository.get_latest_record(history_key)
            versioned_record, diff = diff_official_record(previous, record)
            if previous is None or previous.version_id != versioned_record.version_id:
                self.official_repository.save_record_version(history_key, versioned_record)
            versioned_records.append(versioned_record)
            if diff is not None:
                has_updates = True
        return versioned_records, has_updates

    def _official_record_key(
        self, record: OfficialAdmissionRecord
    ) -> tuple[str, str, str, str, str]:
        version = record.version_id or record.content_hash
        return (record.school, record.program, record.cycle, record.page_type, version)

    def _configured_source_urls(self, school: str, program: str) -> dict[str, str]:
        urls = self._live_source_urls.get((school, program))
        return dict(urls) if urls else {}
