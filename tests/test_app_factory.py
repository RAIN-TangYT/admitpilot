from typing import cast

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.gateways import (
    JsonCaseLibrarySourceGateway,
    OfficialLibrarySourceGateway,
)
from admitpilot.agents.aie.realtime import RealtimeOfficialSourceGateway
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.sae.agent import SAEAgent
from admitpilot.agents.sae.semantic import EmbeddingSemanticMatcher, FakeSemanticMatcher
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
    assert isinstance(aie_agent.service.official_gateway, RealtimeOfficialSourceGateway)
    assert isinstance(aie_agent.service.official_repository, JsonOfficialSnapshotRepository)
    assert isinstance(aie_agent.service.case_gateway, JsonCaseLibrarySourceGateway)
    library_gateway = aie_agent.service.official_gateway.library_gateway
    assert isinstance(library_gateway.repository, JsonOfficialSnapshotRepository)
    repository = library_gateway.repository
    assert str(repository.path).endswith("official_library.json")
    sae_agent = cast(SAEAgent, application.agents["sae"])
    assert isinstance(sae_agent.service.semantic_matcher, EmbeddingSemanticMatcher)


def test_build_application_keeps_test_mode_llm_disabled_without_api_key() -> None:
    settings = AdmitPilotSettings(run_mode="test")

    application = build_application(settings=settings)
    aie_agent = cast(AIEAgent, application.agents["aie"])
    sae_agent = cast(SAEAgent, application.agents["sae"])

    assert application.settings.run_mode == "test"
    assert application.platform_bundle.settings.run_mode == "test"
    assert aie_agent.service.llm_client.enabled is False
    assert isinstance(aie_agent.service.official_repository, JsonOfficialSnapshotRepository)
    repository = aie_agent.service.official_repository
    assert str(repository.path).endswith("official_library.json")
    assert isinstance(sae_agent.service.semantic_matcher, FakeSemanticMatcher)
