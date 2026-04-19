"""MCP server registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.mcp.method_specs import METHOD_CATALOG
from admitpilot.platform.mcp.schemas import (
    MethodSchemaRegistry,
    build_default_method_schema_registry,
)


@dataclass(slots=True)
class MCPMethodStub:
    """Single MCP method stub."""

    server: str
    method: str
    description: str
    todo: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class MCPServerStub:
    """Single MCP server stub."""

    name: str
    methods: dict[str, MCPMethodStub] = field(default_factory=dict)

    def register_method(self, method_stub: MCPMethodStub) -> None:
        self.methods[method_stub.method] = method_stub


@dataclass(slots=True)
class MCPServerRegistry:
    """MCP server registry."""

    schema_registry: MethodSchemaRegistry
    servers: dict[str, MCPServerStub] = field(default_factory=dict)

    def register_method(self, method_stub: MCPMethodStub) -> None:
        server = self.servers.get(method_stub.server)
        if server is None:
            server = MCPServerStub(name=method_stub.server)
            self.servers[method_stub.server] = server
        server.register_method(method_stub)

    def get_server(self, name: str) -> MCPServerStub | None:
        return self.servers.get(name)


def build_default_mcp_server_registry(
    schema_registry: MethodSchemaRegistry | None = None,
) -> MCPServerRegistry:
    effective_schema_registry = schema_registry or build_default_method_schema_registry()
    registry = MCPServerRegistry(schema_registry=effective_schema_registry)
    for contract in METHOD_CATALOG:
        registry.register_method(
            MCPMethodStub(
                server=contract.server,
                method=contract.method,
                description=contract.description,
                todo=(
                    "补齐 handler 实现",
                    "接入鉴权与审计中间件",
                    "接入超时与重试策略",
                ),
            )
        )
    return registry
