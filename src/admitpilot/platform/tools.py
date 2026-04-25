"""Tool registry implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from admitpilot.platform.mcp.method_specs import METHOD_CATALOG, MethodContract
from admitpilot.platform.types import AgentRole


class ToolLayer(StrEnum):
    """Tool layering metadata."""

    L0_GOVERNANCE = "L0_GOVERNANCE"
    L1_ACQUISITION = "L1_ACQUISITION"
    L2_RETRIEVAL = "L2_RETRIEVAL"
    L3_REASONING = "L3_REASONING"
    L4_GENERATION = "L4_GENERATION"


@dataclass(slots=True)
class ToolDefinition:
    """Single registered tool."""

    name: str
    layer: ToolLayer
    server: str
    method: str
    allowed_agents: tuple[AgentRole, ...]
    read_scopes: tuple[str, ...] = field(default_factory=tuple)
    write_scopes: tuple[str, ...] = field(default_factory=tuple)
    todo: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ToolRegistry:
    """Tool registry and access control."""

    tools: dict[str, ToolDefinition] = field(default_factory=dict)
    method_index: dict[str, MethodContract] = field(default_factory=dict)

    def register(self, tool: ToolDefinition) -> None:
        if not self.method_index:
            self.tools[tool.name] = tool
            return
        method_contract = self.method_index.get(tool.method)
        if method_contract is None:
            raise ValueError(f"unknown_mcp_method:{tool.method}")
        if method_contract.server != tool.server:
            raise ValueError(
                f"tool_server_mismatch:{tool.name}:{tool.server}!={method_contract.server}"
            )
        self.tools[tool.name] = tool

    def list_for_agent(self, agent: AgentRole) -> list[ToolDefinition]:
        return [item for item in self.tools.values() if agent in item.allowed_agents]

    def validate_access(self, tool_name: str, agent: AgentRole) -> bool:
        tool = self.tools.get(tool_name)
        if tool is None:
            return False
        return agent in tool.allowed_agents


def build_default_tool_registry() -> ToolRegistry:
    method_index = {item.method: item for item in METHOD_CATALOG}
    registry = ToolRegistry(method_index=method_index)
    registry.register(
        ToolDefinition(
            name="policy_validate",
            layer=ToolLayer.L0_GOVERNANCE,
            server="governance-mcp",
            method="governance.policy_validate",
            allowed_agents=("pao",),
            read_scopes=("shared:*",),
            write_scopes=("audit:*",),
        )
    )
    registry.register(
        ToolDefinition(
            name="official_fetch",
            layer=ToolLayer.L1_ACQUISITION,
            server="intelligence-mcp",
            method="official.fetch_pages",
            allowed_agents=("aie",),
            read_scopes=("application:*",),
            write_scopes=("official_raw:*",),
        )
    )
    registry.register(
        ToolDefinition(
            name="hybrid_retrieve",
            layer=ToolLayer.L2_RETRIEVAL,
            server="knowledge-mcp",
            method="retrieve.hybrid",
            allowed_agents=("aie", "sae", "dta", "cds"),
            read_scopes=("official:*", "case:*", "strategy:*", "timeline:*"),
            write_scopes=(),
        )
    )
    registry.register(
        ToolDefinition(
            name="risk_rank",
            layer=ToolLayer.L3_REASONING,
            server="strategy-mcp",
            method="strategy.risk_rank",
            allowed_agents=("sae",),
            read_scopes=("official:*", "case:*", "application:*"),
            write_scopes=("strategy:*",),
        )
    )
    registry.register(
        ToolDefinition(
            name="timeline_plan_build",
            layer=ToolLayer.L3_REASONING,
            server="timeline-mcp",
            method="timeline.plan_build",
            allowed_agents=("dta",),
            read_scopes=("strategy:*", "official:*"),
            write_scopes=("timeline:*",),
        )
    )
    registry.register(
        ToolDefinition(
            name="draft_compose",
            layer=ToolLayer.L4_GENERATION,
            server="document-mcp",
            method="document.draft_compose",
            allowed_agents=("cds",),
            read_scopes=("strategy:*", "timeline:*", "application:*"),
            write_scopes=("artifact:*",),
        )
    )
    return registry


__all__ = [
    "ToolDefinition",
    "ToolLayer",
    "ToolRegistry",
    "build_default_tool_registry",
]
