"""MCP server registry."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MCPServerRegistry:
    """Track MCP servers and method registrations."""

    servers: dict[str, set[str]] = field(default_factory=dict)

    def register(self, server: str, methods: set[str]) -> None:
        self.servers[server] = set(methods)

    def has_method(self, server: str, method: str) -> bool:
        return method in self.servers.get(server, set())
