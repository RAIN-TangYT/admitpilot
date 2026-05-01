import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from admitpilot.agents.aie.gateways import (
    FixtureCaseSourceGateway,
    JsonCaseLibrarySourceGateway,
    OfficialSourceGateway,
)
from admitpilot.agents.aie.realtime import HardThresholdRuleSyncer, RealtimeOfficialSourceGateway
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.aie.schemas import OfficialAdmissionRecord
from admitpilot.agents.aie.runtime import build_runtime_aie_service
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import AdmitPilotSettings

AS_OF_DATE = date(2026, 10, 1)


def _demo_official_records() -> list[OfficialAdmissionRecord]:
    return [
        _record(
            school="HKUST",
            program="MSCS",
            cycle="2026",
            page_type="requirements",
            content="HKUST official requirements. IELTS 6.5. TOEFL 80. Transcript required.",
            extracted_fields={
                "language_requirements": ["IELTS 6.5", "TOEFL 80"],
                "required_materials": ["Transcript"],
                "academic_requirement": "Applicants should hold a bachelor's degree in a related field.",
                "minimum_gpa": "3.0",
            },
        ),
        _record(
            school="HKUST",
            program="MSCS",
            cycle="2026",
            page_type="deadline",
            content="HKUST official deadline 2026-03-01.",
            extracted_fields={"application_deadline": "2026-03-01"},
        ),
    ]


def _fixture_service() -> AdmissionsIntelligenceService:
    return AdmissionsIntelligenceService(
        official_gateway=cast(OfficialSourceGateway, _StubOfficialGateway(_demo_official_records())),
        case_gateway=FixtureCaseSourceGateway(),
    )


def _record(
    *,
    school: str,
    program: str,
    cycle: str,
    page_type: str,
    content: str,
    extracted_fields: dict[str, Any],
) -> OfficialAdmissionRecord:
    return OfficialAdmissionRecord(
        school=school,
        program=program,
        cycle=cycle,
        page_type=page_type,
        source_url=f"https://example.edu/{school.lower()}/{program.lower()}/{page_type}",
        content=content,
        published_date=date(2026, 1, 1),
        effective_date=date(2026, 1, 1),
        fetched_at=datetime(2026, 1, 1, 0, 0, 0),
        content_hash=f"{school}:{program}:{page_type}:hash",
        quality_score=0.9,
        confidence=0.88,
        extracted_fields=extracted_fields,
        parse_confidence=0.84,
        source_hash=f"{school}:{program}:{page_type}:source",
    )


class _StubOfficialGateway:
    def __init__(self, records: list[OfficialAdmissionRecord]) -> None:
        self._records = records

    def has_cycle_release(
        self,
        school: str,
        program: str,
        cycle: str,
        as_of_date: date,
    ) -> bool:
        del as_of_date
        return any(
            item.school == school and item.program == program and item.cycle == cycle
            for item in self._records
        )

    def fetch_cycle_records(
        self,
        school: str,
        program: str,
        cycle: str,
        query: str,
        as_of_date: date,
    ) -> list[OfficialAdmissionRecord]:
        del query, as_of_date
        return [
            item
            for item in self._records
            if item.school == school and item.program == program and item.cycle == cycle
        ]


def _seed_official_library(output_path: Path) -> None:
    repository = JsonOfficialSnapshotRepository(path=output_path)
    service = AdmissionsIntelligenceService(
        official_gateway=cast(OfficialSourceGateway, _StubOfficialGateway(_demo_official_records())),
        official_repository=repository,
        case_gateway=FixtureCaseSourceGateway(),
    )
    service.refresh_official_library(
        query="seed official library",
        cycle="2026",
        targets=[("HKUST", "MSCS")],
        as_of_date=AS_OF_DATE,
    )


def test_aie_service_uses_same_day_cache() -> None:
    service = _fixture_service()

    first = service.retrieve(
        query="Check official requirements",
        cycle="2026",
        as_of_date=AS_OF_DATE,
    )
    second = service.retrieve(
        query="Check official requirements",
        cycle="2026",
        as_of_date=AS_OF_DATE,
    )

    assert first.cache_hit_count == 0
    assert second.cache_hit_count >= 1


def test_runtime_aie_service_reads_official_library_by_default() -> None:
    output_dir = Path(".pytest-local")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "runtime_official_library.json"
    case_output_path = output_dir / "runtime_empty_case_library.json"
    if output_path.exists():
        output_path.unlink()
    if case_output_path.exists():
        case_output_path.unlink()
    _seed_official_library(output_path)
    settings = AdmitPilotSettings(
        run_mode="test",
        official_library_path=str(output_path),
        case_library_path=str(case_output_path),
    )

    service = build_runtime_aie_service(settings=settings)
    pack = service.retrieve(
        query="Track current-cycle policy changes",
        cycle="2026",
        schools=["NUS", "HKUST"],
        as_of_date=AS_OF_DATE,
    )

    statuses = {item.school: item.status for item in pack.official_cycle_snapshots}
    assert statuses["NUS"] == "predicted"
    assert statuses["HKUST"] == "official_found"
    assert pack.case_long_memory == []
    assert pack.case_snapshot is not None
    assert pack.case_snapshot.sample_size == 0
    assert pack.case_snapshot.patterns == []


def test_runtime_aie_service_reads_case_library_by_default() -> None:
    output_dir = Path(".pytest-local")
    output_dir.mkdir(exist_ok=True)
    official_output_path = output_dir / "runtime_official_library_for_case.json"
    case_output_path = output_dir / "runtime_case_library.json"
    if official_output_path.exists():
        official_output_path.unlink()
    if case_output_path.exists():
        case_output_path.unlink()
    _seed_official_library(official_output_path)
    case_output_path.write_text(
        json.dumps(
            {
                "cycle": "2026",
                "generated_at": "2026-04-20T10:46:59Z",
                "records": [
                    {
                        "candidate_fingerprint": "anon-demo-nus",
                        "school": "NUS",
                        "program": "MCOMP_CS",
                        "cycle": "2026",
                        "source_type": "community",
                        "source_url": "https://example.com/nus-case",
                        "background_summary": "Research-heavy CS applicant.",
                        "outcome": "offer",
                        "captured_at": "2026-04-20T10:46:59Z",
                        "source_site_score": 0.62,
                        "evidence_completeness": 0.58,
                        "cross_source_consistency": 0.57,
                        "freshness_score": 0.52,
                        "confidence": 0.64,
                        "credibility_label": "medium",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    settings = AdmitPilotSettings(
        run_mode="test",
        official_library_path=str(official_output_path),
        case_library_path=str(case_output_path),
    )

    service = build_runtime_aie_service(settings=settings)
    pack = service.retrieve(
        query="Use cases to assess NUS competitiveness",
        cycle="2026",
        schools=["NUS"],
        program="MCOMP_CS",
        as_of_date=AS_OF_DATE,
    )

    assert isinstance(service.case_gateway, JsonCaseLibrarySourceGateway)
    assert len(pack.case_long_memory) == 1
    assert pack.case_long_memory[0].school == "NUS"
    assert pack.case_snapshot is not None
    assert pack.case_snapshot.sample_size == 1


def test_aie_service_enforces_supported_school_scope() -> None:
    service = _fixture_service()
    pack = service.retrieve(
        query="Scope constraint test",
        cycle="2026",
        schools=["mit", "stanford"],
        as_of_date=AS_OF_DATE,
    )
    scoped = sorted(item.school for item in pack.official_cycle_snapshots)
    assert scoped == sorted(list(service.OFFICIAL_SCHOOLS))


def test_aie_service_appends_fetched_official_records_only_once() -> None:
    service = _fixture_service()
    base_count = len(service._official_long_memory)
    pack = service.retrieve(
        query="Check official requirements",
        cycle="2026",
        schools=["HKUST"],
        as_of_date=AS_OF_DATE,
    )

    fetched_count = sum(len(item.entries) for item in pack.official_cycle_snapshots)

    assert fetched_count > 0
    assert len(service._official_long_memory) - base_count == fetched_count


def test_realtime_gateway_falls_back_by_field_and_syncs_hard_thresholds() -> None:
    workspace_dir = Path(".pytest-local") / "runtime-sync-test"
    if workspace_dir.exists():
        for path in sorted(workspace_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    rules_dir = workspace_dir / "rules"
    rules_dir.mkdir(parents=True)
    rule_path = rules_dir / "nus_mtech_eba.yaml"
    rule_path.write_text(
        "\n".join(
            [
                "school: NUS",
                "program: MTECH_EBA",
                "hard_thresholds:",
                "  gpa_min: 3.0",
                "  experience_years_min: 1",
                "soft_thresholds:",
                "  gpa_target: 3.4",
                "recommended_backgrounds:",
                "  - enterprise analytics",
                "risk_flags:",
                "  - work_experience_expected",
                "missing_input_penalties:",
                "  ielts: 0.06",
            ]
        ),
        encoding="utf-8",
    )
    library_records = [
        _record(
            school="NUS",
            program="MTECH_EBA",
            cycle="2026",
            page_type="requirements",
            content="Library requirements snapshot.",
            extracted_fields={
                "minimum_gpa": "3.0",
                "language_requirements": ["IELTS 6.0"],
                "required_materials": ["Transcript", "CV"],
                "academic_requirement": "Applicants must have at least 1 years of relevant work experience.",
            },
        ),
        _record(
            school="NUS",
            program="MTECH_EBA",
            cycle="2026",
            page_type="deadline",
            content="Library deadline snapshot.",
            extracted_fields={"application_deadline": "2026-03-31"},
        ),
    ]
    live_records = [
        replace(
            _record(
                school="NUS",
                program="MTECH_EBA",
                cycle="2026",
                page_type="requirements",
                content=(
                    "Applicants must have at least 2 years of relevant work experience. "
                    "Required English scores include IELTS 6.5 and TOEFL 100."
                ),
                extracted_fields={
                    "language_requirements": ["IELTS 99", "TOEFL 100", "IELTS 6.5"],
                    "required_materials": [],
                    "academic_requirement": (
                        "Applicants must have at least 2 years of relevant work experience."
                    ),
                },
            ),
            delta_summary="live-refresh",
        ),
        _record(
            school="NUS",
            program="MTECH_EBA",
            cycle="2026",
            page_type="deadline",
            content="Broken deadline page.",
            extracted_fields={"application_deadline": "2099-12-31"},
        ),
    ]
    gateway = RealtimeOfficialSourceGateway(
        live_gateway=cast(OfficialSourceGateway, _StubOfficialGateway(live_records)),
        library_gateway=cast(OfficialSourceGateway, _StubOfficialGateway(library_records)),
        rule_syncer=HardThresholdRuleSyncer(rules_dir=rules_dir),
    )

    records = gateway.fetch_cycle_records(
        school="NUS",
        program="MTECH_EBA",
        cycle="2026",
        query="refresh",
        as_of_date=AS_OF_DATE,
    )

    requirements = next(item for item in records if item.page_type == "requirements")
    deadline = next(item for item in records if item.page_type == "deadline")

    assert requirements.extracted_fields["language_requirements"] == ["TOEFL 100", "IELTS 6.5"]
    assert requirements.extracted_fields["required_materials"] == ["Transcript", "CV"]
    assert requirements.extracted_fields["minimum_gpa"] == "3"
    assert "field_fallback=required_materials" in requirements.delta_summary
    assert deadline.extracted_fields["application_deadline"] == "2026-03-31"

    updated_rule_text = rule_path.read_text(encoding="utf-8")
    assert "gpa_min: 3" in updated_rule_text
    assert "ielts_min: 6.5" in updated_rule_text
    assert "toefl_min: 100" in updated_rule_text
    assert "experience_years_min: 2" in updated_rule_text
