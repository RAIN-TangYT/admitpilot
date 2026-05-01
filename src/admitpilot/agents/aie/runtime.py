"""Runtime assembly helpers for the AIE service."""

from __future__ import annotations

from pathlib import Path

from admitpilot.agents.aie.gateways import CatalogOfficialSourceGateway
from admitpilot.agents.aie.gateways import (
    JsonCaseLibrarySourceGateway,
    OfficialLibrarySourceGateway,
)
from admitpilot.agents.aie.realtime import HardThresholdRuleSyncer, RealtimeOfficialSourceGateway
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import AdmitPilotSettings, load_settings
from admitpilot.platform.llm.openai import OpenAIClient


def build_runtime_aie_service(
    settings: AdmitPilotSettings | None = None,
    llm_client: OpenAIClient | None = None,
) -> AdmissionsIntelligenceService:
    """Build the runtime AIE service that reads the persisted official library."""

    effective_settings = settings or load_settings()
    official_library_path = Path(effective_settings.official_library_path)
    rules_path = Path(effective_settings.program_rules_path)
    library_repository = JsonOfficialSnapshotRepository(
        path=official_library_path
    )
    library_gateway = OfficialLibrarySourceGateway(repository=library_repository)
    official_gateway = library_gateway
    if not effective_settings.is_test_mode:
        official_gateway = RealtimeOfficialSourceGateway(
            live_gateway=CatalogOfficialSourceGateway(mode="live"),
            library_gateway=library_gateway,
            rule_syncer=HardThresholdRuleSyncer(
                rules_dir=rules_path,
            ),
        )
    return AdmissionsIntelligenceService(
        official_gateway=official_gateway,
        official_repository=library_repository,
        case_gateway=JsonCaseLibrarySourceGateway(
            path=Path(effective_settings.case_library_path)
        ),
        llm_client=llm_client or OpenAIClient(settings=effective_settings),
    )
