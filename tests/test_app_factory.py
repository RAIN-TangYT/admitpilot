from typing import cast

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.gateways import NullCaseSourceGateway, OfficialLibrarySourceGateway
from admitpilot.agents.aie.repositories import (
    InMemoryOfficialSnapshotRepository,
    JsonOfficialSnapshotRepository,
)
from admitpilot.app import build_application
from admitpilot.config import AdmitPilotSettings


def test_build_application_uses_supplied_demo_settings() -> None:
    settings = AdmitPilotSettings(
        run_mode="demo",
        openai_api_key="demo-key",
        official_library_path="data/official_library/official_library.json",
    )

    application = build_application(settings=settings)
    aie_agent = cast(AIEAgent, application.agents["aie"])

    assert application.settings is settings
    assert application.platform_bundle.settings is settings
    assert application.orchestrator.settings is settings
    assert application.orchestrator.platform_bundle is application.platform_bundle
    assert application.orchestrator.agents is application.agents
    assert aie_agent.service.llm_client.enabled is True
    assert isinstance(aie_agent.service.official_gateway, OfficialLibrarySourceGateway)
    assert isinstance(aie_agent.service.official_repository, InMemoryOfficialSnapshotRepository)
    assert isinstance(aie_agent.service.case_gateway, NullCaseSourceGateway)
    library_gateway = aie_agent.service.official_gateway
    repository = cast(JsonOfficialSnapshotRepository, library_gateway.repository)
    assert str(repository.path).endswith("official_library.json")


def test_build_application_keeps_test_mode_llm_disabled_without_api_key() -> None:
    settings = AdmitPilotSettings(run_mode="test")

    application = build_application(settings=settings)
    aie_agent = cast(AIEAgent, application.agents["aie"])

    assert application.settings.run_mode == "test"
    assert application.platform_bundle.settings.run_mode == "test"
    assert aie_agent.service.llm_client.enabled is False
