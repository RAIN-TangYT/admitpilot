"""Platform common bundle bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.common import ErrorCode
from admitpilot.platform.governance import GovernanceSuite, build_default_governance_suite
from admitpilot.platform.governance.contracts import GovernanceEngine
from admitpilot.platform.mcp import (
    MCPServerRegistry,
    MethodSchemaRegistry,
    build_default_mcp_server_registry,
    build_default_method_schema_registry,
)
from admitpilot.platform.memory import MemoryAdapterBundle, build_default_memory_adapters
from admitpilot.platform.observability.contracts import MetricsCollector, TraceCollector
from admitpilot.platform.security.capability import CapabilityManager
from admitpilot.platform.tools import ToolRegistry, build_default_tool_registry


@dataclass(slots=True)
class PlatformCommonBundle:
    """Shared platform bundle used by tests and orchestrator runtime."""

    method_schemas: MethodSchemaRegistry
    mcp_servers: MCPServerRegistry
    tool_registry: ToolRegistry
    memory_adapters: MemoryAdapterBundle
    governance: GovernanceSuite
    trace_collector: TraceCollector
    metrics_collector: MetricsCollector
    capability_manager: CapabilityManager
    governance_engine: GovernanceEngine
    error_codes: tuple[ErrorCode, ...] = field(default_factory=lambda: tuple(ErrorCode))

    @property
    def server_registry(self) -> MCPServerRegistry:
        return self.mcp_servers

    @property
    def session_memory(self):
        return self.memory_adapters.session_store

    @property
    def versioned_memory(self):
        return self.memory_adapters.versioned_store

    @property
    def artifact_store(self):
        return self.memory_adapters.artifact_store


def build_default_platform_common_bundle() -> PlatformCommonBundle:
    method_schemas = build_default_method_schema_registry()
    return PlatformCommonBundle(
        method_schemas=method_schemas,
        mcp_servers=build_default_mcp_server_registry(schema_registry=method_schemas),
        tool_registry=build_default_tool_registry(),
        memory_adapters=build_default_memory_adapters(),
        governance=build_default_governance_suite(),
        trace_collector=TraceCollector(),
        metrics_collector=MetricsCollector(),
        capability_manager=CapabilityManager(
            policy={"aie": {"execute"}, "sae": {"execute"}, "dta": {"execute"}, "cds": {"execute"}}
        ),
        governance_engine=GovernanceEngine(),
    )
