"""MCP exports."""

from admitpilot.platform.mcp.contracts import MCPRequest, MCPResponse
from admitpilot.platform.mcp.method_specs import METHOD_CATALOG, MethodContract
from admitpilot.platform.mcp.schemas import (
    MethodSchema,
    MethodSchemaRegistry,
    build_default_method_schema_registry,
)
from admitpilot.platform.mcp.server_registry import (
    MCPMethodStub,
    MCPServerRegistry,
    MCPServerStub,
    build_default_mcp_server_registry,
)

__all__ = [
    "MCPRequest",
    "MCPResponse",
    "METHOD_CATALOG",
    "MCPMethodStub",
    "MCPServerRegistry",
    "MCPServerStub",
    "MethodContract",
    "MethodSchema",
    "MethodSchemaRegistry",
    "build_default_mcp_server_registry",
    "build_default_method_schema_registry",
]
