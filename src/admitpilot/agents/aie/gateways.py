"""AIE data-source gateways backed by catalog, fixtures, and parsers."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Protocol

from admitpilot.agents.aie.case_ingestion import normalize_case_records
from admitpilot.agents.aie.fetchers import (
    FixtureHttpClient,
    LiveHttpClient,
    OfficialPageFetcher,
    OfficialPageFetchError,
    OfficialPageNotFoundError,
    OfficialPageSpec,
)
from admitpilot.agents.aie.live_sources import (
    DEFAULT_LIVE_OFFICIAL_SOURCES,
    OfficialLiveSourceConfig,
)
from admitpilot.agents.aie.parsers import OfficialPageParseError, OfficialPageParser
from admitpilot.agents.aie.repositories import (
    JsonOfficialSnapshotRepository,
    OfficialSnapshotRepository,
)
from admitpilot.agents.aie.schemas import CaseRecord, OfficialAdmissionRecord
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG, AdmissionsCatalog

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_OFFICIAL_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "official_pages"
_DEFAULT_CASE_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "cases"


class OfficialSourceGateway(Protocol):
    """Gateway for official admissions sources."""

    def has_cycle_release(
        self, school: str, program: str, cycle: str, as_of_date: date
    ) -> bool:
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


class CatalogOfficialSourceGateway:
    """Official source gateway that can run in fixture or live mode."""

    def __init__(
        self,
        *,
        catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
        parser: OfficialPageParser | None = None,
        mode: Literal["fixture", "live"] = "fixture",
        fixture_root: Path | None = None,
        fixture_overrides: dict[tuple[str, str, str, str], Path] | None = None,
        live_sources: tuple[OfficialLiveSourceConfig, ...] = DEFAULT_LIVE_OFFICIAL_SOURCES,
        fetcher: OfficialPageFetcher | None = None,
    ) -> None:
        self.catalog = catalog
        self.parser = parser or OfficialPageParser()
        self.mode = mode
        self.fixture_root = fixture_root or _DEFAULT_OFFICIAL_FIXTURE_ROOT
        self.fixture_overrides = fixture_overrides or {}
        self.live_sources = self._normalize_live_sources(live_sources)
        self._fixture_url_map = self._build_fixture_url_map()
        self.fetcher = fetcher or self._build_fetcher()

    def has_cycle_release(
        self, school: str, program: str, cycle: str, as_of_date: date
    ) -> bool:
        del as_of_date
        school_code = self.catalog.normalize_school_code(school)
        program_code = self.catalog.normalize_program_code(program)
        if school_code is None or program_code is None:
            return False
        if not self.catalog.is_supported_program(school_code, program_code):
            return False
        specs = self._build_page_specs(school_code, program_code, cycle)
        if not specs:
            return False
        if self.mode == "live":
            return True
        return all(spec.url in self._fixture_url_map for spec in specs)

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        del query, as_of_date
        school_code = self.catalog.normalize_school_code(school)
        program_code = self.catalog.normalize_program_code(program)
        if school_code is None or program_code is None:
            return []
        specs = self._build_page_specs(school_code, program_code, cycle)
        records: list[OfficialAdmissionRecord] = []
        for spec in specs:
            try:
                page = self.fetcher.fetch(spec)
            except (OfficialPageFetchError, OfficialPageNotFoundError):
                if self.mode == "live":
                    continue
                continue
            try:
                records.append(self.parser.parse(page))
            except OfficialPageParseError:
                if self.mode == "live":
                    continue
                raise
        return records

    def _build_fetcher(self) -> OfficialPageFetcher:
        if self.mode == "live":
            return OfficialPageFetcher(http_client=LiveHttpClient(), mode="live")
        return OfficialPageFetcher(
            http_client=FixtureHttpClient(self._fixture_url_map),
            mode="fixture",
        )

    def _build_page_specs(
        self, school_code: str, program_code: str, cycle: str
    ) -> list[OfficialPageSpec]:
        if self.mode == "live":
            sources = self.live_sources.get((school_code, program_code), {})
            if not sources:
                return []
            specs: list[OfficialPageSpec] = []
            for page_type in self.catalog.default_page_types(school_code, program_code):
                url = sources.get(page_type)
                if not url:
                    continue
                specs.append(
                    OfficialPageSpec(
                        school=school_code,
                        program=program_code,
                        cycle=cycle,
                        page_type=page_type,
                        url=url,
                        allowed_domains=self.catalog.official_domains(school_code),
                    )
                )
            return specs
        page_types = self.catalog.default_page_types(school_code, program_code)
        return [
            OfficialPageSpec(
                school=school_code,
                program=program_code,
                cycle=cycle,
                page_type=page_type,
                url=self.catalog.build_page_url(school_code, program_code, cycle, page_type),
                allowed_domains=self.catalog.official_domains(school_code),
            )
            for page_type in page_types
        ]

    def _build_fixture_url_map(self) -> dict[str, Path]:
        url_map: dict[str, Path] = {}
        if self.fixture_root.exists():
            for path in self.fixture_root.glob("*.html"):
                fixture_key = self._fixture_key_from_filename(path.stem)
                if fixture_key is None:
                    continue
                school_code, program_code, cycle, page_type = fixture_key
                url = self.catalog.build_page_url(
                    school_code=school_code,
                    program_code=program_code,
                    cycle=cycle,
                    page_type=page_type,
                )
                url_map[url] = path
        for key, path in self.fixture_overrides.items():
            school_code, program_code, cycle, page_type = key
            url = self.catalog.build_page_url(
                school_code=school_code,
                program_code=program_code,
                cycle=cycle,
                page_type=page_type,
            )
            url_map[url] = path
        return url_map

    def _fixture_key_from_filename(
        self, stem: str
    ) -> tuple[str, str, str, str] | None:
        parts = stem.split("_")
        if len(parts) != 4:
            return None
        school_code = self.catalog.normalize_school_code(parts[0])
        program_code = self.catalog.normalize_program_code(parts[1])
        cycle = parts[2]
        page_type = parts[3]
        if school_code is None or program_code is None:
            return None
        return school_code, program_code, cycle, page_type

    def _normalize_live_sources(
        self,
        live_sources: tuple[OfficialLiveSourceConfig, ...],
    ) -> dict[tuple[str, str], dict[str, str]]:
        normalized: dict[tuple[str, str], dict[str, str]] = {}
        for item in live_sources:
            school_code = self.catalog.normalize_school_code(item.school)
            program_code = self.catalog.normalize_program_code(item.program)
            if school_code is None or program_code is None:
                continue
            normalized[(school_code, program_code)] = {
                "requirements": item.requirements_url,
                "deadline": item.deadline_url,
            }
        return normalized


class OfficialLibrarySourceGateway:
    """Official source gateway backed by the persisted official library."""

    def __init__(
        self,
        *,
        catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
        repository: OfficialSnapshotRepository | None = None,
    ) -> None:
        self.catalog = catalog
        self.repository = repository or JsonOfficialSnapshotRepository()

    def has_cycle_release(
        self, school: str, program: str, cycle: str, as_of_date: date
    ) -> bool:
        return bool(self.fetch_cycle_records(school, program, cycle, "", as_of_date))

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        del query, as_of_date
        school_code = self.catalog.normalize_school_code(school)
        program_code = self.catalog.normalize_program_code(program)
        if school_code is None or program_code is None:
            return []
        if not self.catalog.is_supported_program(school_code, program_code):
            return []
        return self.repository.list_latest_cycle_records(
            school=school_code,
            program=program_code,
            cycle=cycle,
        )


class FixtureCaseSourceGateway:
    """Case source gateway that normalizes raw fixture payloads."""

    def __init__(
        self,
        *,
        catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
        fixture_root: Path | None = None,
    ) -> None:
        self.catalog = catalog
        self.fixture_root = fixture_root or _DEFAULT_CASE_FIXTURE_ROOT

    def fetch_case_records(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> list[CaseRecord]:
        raw_records: list[dict[str, object]] = []
        if self.fixture_root.exists():
            for path in sorted(self.fixture_root.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    raw_records.extend(item for item in payload if isinstance(item, dict))
        records = normalize_case_records(
            raw_records,
            schools=schools,
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
            catalog=self.catalog,
        )
        if records:
            return records
        now = date.fromisoformat((as_of_date - timedelta(days=7)).isoformat())
        fallback_payload = [
            {
                "school": schools[0] if schools else "NUS",
                "program": program,
                "cycle": cycle,
                "source_type": "community",
                "source_url": "https://cases.example/default",
                "captured_at": f"{now.isoformat()}T00:00:00+00:00",
                "gpa": "3.7",
                "ielts": "7.5",
                "experiences": ["course project", "internship"],
                "evidence": ["forum post"],
                "outcome": "offer",
                "corroborated_count": 1,
            }
        ]
        return normalize_case_records(
            fallback_payload,
            schools=schools or ["NUS"],
            program=program,
            cycle=cycle,
            as_of_date=as_of_date,
            catalog=self.catalog,
        )


class NullCaseSourceGateway:
    """Case source gateway for runtime mode before a real case library exists."""

    def fetch_case_records(
        self,
        schools: list[str],
        program: str,
        cycle: str,
        as_of_date: date,
    ) -> list[CaseRecord]:
        del schools, program, cycle, as_of_date
        return []
