"""Data source gateway stubs for AIE."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

from admitpilot.agents.aie.schemas import CaseRecord, OfficialAdmissionRecord
from admitpilot.platform.common.time import utc_now


class OfficialSourceGateway(Protocol):
    """Gateway for official admissions sources."""

    def has_cycle_release(self, school: str, cycle: str, as_of_date: date) -> bool:
        """Return whether official release is available."""

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        """Fetch official records for a cycle."""


class CaseSourceGateway(Protocol):
    """Gateway for case-data sources."""

    def fetch_case_records(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> list[CaseRecord]:
        """Fetch historical cases for target scope."""


class StubOfficialSourceGateway:
    """Deterministic official source stub for local development."""

    _RELEASED_SCHOOLS = {"HKUST", "NTU", "CUHK"}

    def has_cycle_release(self, school: str, cycle: str, as_of_date: date) -> bool:
        del cycle, as_of_date
        return school in self._RELEASED_SCHOOLS

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        del query
        now = utc_now()
        return [
            OfficialAdmissionRecord(
                school=school,
                program=program,
                cycle=cycle,
                page_type="requirements",
                source_url=f"https://www.{school.lower()}.edu/admissions/{program.lower()}",
                content=f"{school} {program} {cycle} official requirements snapshot",
                published_date=as_of_date,
                effective_date=as_of_date,
                fetched_at=now,
                source_hash=f"{school}-{program}-{cycle}-official",
                quality_score=0.92,
                confidence=0.88,
                version_id=f"{school}-{cycle}-requirements-v1",
                is_policy_change=False,
                change_type="updated",
                delta_summary="baseline capture",
            ),
            OfficialAdmissionRecord(
                school=school,
                program=program,
                cycle=cycle,
                page_type="deadline",
                source_url=f"https://www.{school.lower()}.edu/admissions/{program.lower()}/deadline",
                content=f"{school} {program} deadline overview",
                published_date=as_of_date,
                effective_date=as_of_date,
                fetched_at=now + timedelta(seconds=1),
                source_hash=f"{school}-{program}-{cycle}-ddl",
                quality_score=0.9,
                confidence=0.86,
                version_id=f"{school}-{cycle}-deadline-v1",
                is_policy_change=True,
                change_type="updated",
                delta_summary="deadline table updated",
            ),
        ]


class StubCaseSourceGateway:
    """Deterministic case source stub for local development."""

    def fetch_case_records(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> list[CaseRecord]:
        now = utc_now()
        records: list[CaseRecord] = []
        for idx, school in enumerate(schools):
            records.append(
                CaseRecord(
                    candidate_fingerprint=f"anon-{school}-{idx}",
                    school=school,
                    program=program,
                    cycle=cycle,
                    source_type="community",
                    source_url=f"https://cases.example/{school.lower()}",
                    background_summary=f"{school} candidate profile summary",
                    outcome="offer",
                    captured_at=now - timedelta(days=idx * 7),
                    source_site_score=0.7,
                    evidence_completeness=0.72,
                    cross_source_consistency=0.68,
                    freshness_score=max(0.5, 0.9 - idx * 0.1),
                    confidence=max(0.55, 0.82 - idx * 0.06),
                    credibility_label="medium" if idx % 2 else "high",
                )
            )
        if not records:
            records.append(
                CaseRecord(
                    candidate_fingerprint="anon-default",
                    school="NUS",
                    program=program,
                    cycle=cycle,
                    source_type="community",
                    source_url="https://cases.example/default",
                    background_summary="default case summary",
                    outcome="offer",
                    captured_at=now,
                    source_site_score=0.7,
                    evidence_completeness=0.7,
                    cross_source_consistency=0.65,
                    freshness_score=0.75,
                    confidence=0.7,
                    credibility_label="medium",
                )
            )
        del as_of_date
        return records
