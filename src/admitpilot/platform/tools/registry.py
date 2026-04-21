"""Tool registry aligned with MCP method specs."""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.mcp.schemas import MethodSpec


@dataclass
class ToolRegistry:
    """Registry that validates agent access to methods."""

    methods: dict[str, MethodSpec] = field(default_factory=dict)

    def register(self, spec: MethodSpec) -> None:
        self.methods[spec.name] = spec

    def validate_access(self, method: str, agent: str) -> bool:
        spec = self.methods.get(method)
        if spec is None:
            return False
        return agent in spec.allowed_agents
