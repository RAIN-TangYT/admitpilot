"""Runtime assembly helpers for the AIE service."""

from __future__ import annotations

from pathlib import Path

from admitpilot.agents.aie.gateways import NullCaseSourceGateway, OfficialLibrarySourceGateway
from admitpilot.agents.aie.repositories import (
    InMemoryOfficialSnapshotRepository,
    JsonOfficialSnapshotRepository,
)
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import AdmitPilotSettings, load_settings
from admitpilot.platform.llm.openai import OpenAIClient


def build_runtime_aie_service(
    settings: AdmitPilotSettings | None = None,
    llm_client: OpenAIClient | None = None,
) -> AdmissionsIntelligenceService:
    """Build the runtime AIE service that reads the persisted official library."""

    effective_settings = settings or load_settings()
    library_repository = JsonOfficialSnapshotRepository(
        path=Path(effective_settings.official_library_path)
    )
    return AdmissionsIntelligenceService(
        official_gateway=OfficialLibrarySourceGateway(repository=library_repository),
        official_repository=InMemoryOfficialSnapshotRepository(),
        case_gateway=NullCaseSourceGateway(),
        llm_client=llm_client or OpenAIClient(settings=effective_settings),
    )
