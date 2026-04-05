"""MCP 协议与方法契约。"""

from admitpilot.platform.mcp.contracts import (
    MCPError,
    MCPRequest,
    MCPResponse,
    MCPResult,
    RpcMeta,
)
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
    "RpcMeta",
    "MCPRequest",
    "MCPResult",
    "MCPError",
    "MCPResponse",
    "MethodContract",
    "METHOD_CATALOG",
    "MethodSchema",
    "MethodSchemaRegistry",
    "build_default_method_schema_registry",
    "MCPMethodStub",
    "MCPServerStub",
    "MCPServerRegistry",
    "build_default_mcp_server_registry",
]
