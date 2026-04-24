"""Application factory and dependency assembly."""

from __future__ import annotations

from dataclasses import dataclass

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.runtime import build_runtime_aie_service
from admitpilot.agents.base import BaseAgent
from admitpilot.agents.cds.agent import CDSAgent
from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.agents.dta.agent import DTAAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.agents.sae.agent import SAEAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.config import AdmitPilotSettings, load_settings
from admitpilot.pao.orchestrator import PrincipalApplicationOrchestrator
from admitpilot.platform import PlatformCommonBundle, build_default_platform_common_bundle
from admitpilot.platform.llm.openai import OpenAIClient


@dataclass(slots=True)
class AdmitPilotApplication:
    """Assembled application object used by CLI and API entrypoints."""

    settings: AdmitPilotSettings
    platform_bundle: PlatformCommonBundle
    agents: dict[str, BaseAgent]
    orchestrator: PrincipalApplicationOrchestrator


def build_default_agents(settings: AdmitPilotSettings | None = None) -> dict[str, BaseAgent]:
    """Construct the default agent set for the configured runtime mode."""

    effective_settings = settings or load_settings()
    llm_client = OpenAIClient(settings=effective_settings)
    return {
        "aie": AIEAgent(
            service=build_runtime_aie_service(
                settings=effective_settings,
                llm_client=llm_client,
            )
        ),
        "sae": SAEAgent(
            service=StrategicAdmissionsService(
                llm_client=llm_client,
                settings=effective_settings,
            )
        ),
        "dta": DTAAgent(service=DynamicTimelineService(llm_client=llm_client)),
        "cds": CDSAgent(service=CoreDocumentService(llm_client=llm_client)),
    }


def build_application(settings: AdmitPilotSettings | None = None) -> AdmitPilotApplication:
    """Assemble the application runtime from settings."""

    effective_settings = settings or load_settings()
    platform_bundle = build_default_platform_common_bundle(settings=effective_settings)
    agents = build_default_agents(settings=effective_settings)
    orchestrator = PrincipalApplicationOrchestrator(
        agents=agents,
        platform_bundle=platform_bundle,
        settings=effective_settings,
    )
    return AdmitPilotApplication(
        settings=effective_settings,
        platform_bundle=platform_bundle,
        agents=agents,
        orchestrator=orchestrator,
    )
