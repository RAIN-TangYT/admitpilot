"""AIE 模块导出。"""

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.gateways import (
    CatalogOfficialSourceGateway,
    FixtureCaseSourceGateway,
    JsonCaseLibrarySourceGateway,
    NullCaseSourceGateway,
    OfficialLibrarySourceGateway,
)
from admitpilot.agents.aie.repositories import (
    InMemoryCaseSnapshotRepository,
    InMemoryOfficialSnapshotRepository,
)
from admitpilot.agents.aie.runtime import build_runtime_aie_service
from admitpilot.agents.aie.service import AdmissionsIntelligenceService

StubOfficialSourceGateway = CatalogOfficialSourceGateway
StubCaseSourceGateway = FixtureCaseSourceGateway

__all__ = [
    "AIEAgent",
    "AdmissionsIntelligenceService",
    "CatalogOfficialSourceGateway",
    "FixtureCaseSourceGateway",
    "JsonCaseLibrarySourceGateway",
    "NullCaseSourceGateway",
    "OfficialLibrarySourceGateway",
    "StubOfficialSourceGateway",
    "StubCaseSourceGateway",
    "InMemoryOfficialSnapshotRepository",
    "InMemoryCaseSnapshotRepository",
    "build_runtime_aie_service",
]
