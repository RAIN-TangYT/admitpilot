"""MCP exports."""

from admitpilot.platform.mcp.contracts import MCPRequest, MCPResponse
from admitpilot.platform.mcp.method_specs import METHOD_CATALOG
from admitpilot.platform.mcp.schemas import MethodSpec
from admitpilot.platform.mcp.server_registry import MCPServerRegistry

__all__ = [
    "MCPRequest",
    "MCPResponse",
    "METHOD_CATALOG",
    "MCPServerRegistry",
    "MethodSpec",
]
