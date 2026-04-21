"""Platform common bundle bootstrap."""

from __future__ import annotations

from dataclasses import dataclass

from admitpilot.platform.governance.contracts import GovernanceEngine
from admitpilot.platform.mcp.method_specs import METHOD_CATALOG
from admitpilot.platform.mcp.server_registry import MCPServerRegistry
from admitpilot.platform.memory.adapters import (
    ArtifactObjectStore,
    SessionMemoryStore,
    VersionedMemoryStore,
)
from admitpilot.platform.observability.contracts import MetricsCollector, TraceCollector
from admitpilot.platform.security.capability import CapabilityManager
from admitpilot.platform.tools.registry import ToolRegistry


@dataclass
class PlatformCommonBundle:
    """Composable shared platform services."""

    server_registry: MCPServerRegistry
    tool_registry: ToolRegistry
    session_memory: SessionMemoryStore
    versioned_memory: VersionedMemoryStore
    artifact_store: ArtifactObjectStore
    capability_manager: CapabilityManager
    governance_engine: GovernanceEngine
    trace_collector: TraceCollector
    metrics_collector: MetricsCollector


def build_default_platform_common_bundle() -> PlatformCommonBundle:
    """Build a default in-memory platform bundle."""
    registry = ToolRegistry()
    for spec in METHOD_CATALOG.values():
        registry.register(spec)
    server_registry = MCPServerRegistry()
    server_registry.register("default", set(METHOD_CATALOG.keys()))
    return PlatformCommonBundle(
        server_registry=server_registry,
        tool_registry=registry,
        session_memory=SessionMemoryStore(),
        versioned_memory=VersionedMemoryStore(),
        artifact_store=ArtifactObjectStore(),
        capability_manager=CapabilityManager(
            policy={"aie": {"execute"}, "sae": {"execute"}, "dta": {"execute"}, "cds": {"execute"}}
        ),
        governance_engine=GovernanceEngine(),
        trace_collector=TraceCollector(),
        metrics_collector=MetricsCollector(),
    )
