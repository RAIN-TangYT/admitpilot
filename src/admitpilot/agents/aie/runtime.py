"""Runtime assembly helpers for the AIE service."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

from admitpilot.agents.aie.gateways import (
    JsonCaseLibrarySourceGateway,
    OfficialLibrarySourceGateway,
)
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
    source_library_path = Path(effective_settings.official_library_path)
    runtime_library_path = Path(effective_settings.runtime_official_library_path)
    if effective_settings.is_test_mode and runtime_library_path != source_library_path:
        runtime_library_path.parent.mkdir(parents=True, exist_ok=True)
        if source_library_path.exists():
            copyfile(source_library_path, runtime_library_path)
    library_repository = JsonOfficialSnapshotRepository(
        path=runtime_library_path
    )
    return AdmissionsIntelligenceService(
        official_gateway=OfficialLibrarySourceGateway(repository=library_repository),
        official_repository=library_repository,
        case_gateway=JsonCaseLibrarySourceGateway(
            path=Path(effective_settings.case_library_path)
        ),
        llm_client=llm_client or OpenAIClient(settings=effective_settings),
    )
