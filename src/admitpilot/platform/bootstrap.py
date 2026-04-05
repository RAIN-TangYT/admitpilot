"""平台公共区初始化总装配。"""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.common import ErrorCode
from admitpilot.platform.governance import GovernanceSuite, build_default_governance_suite
from admitpilot.platform.mcp import (
    MCPServerRegistry,
    MethodSchemaRegistry,
    build_default_mcp_server_registry,
    build_default_method_schema_registry,
)
from admitpilot.platform.memory import MemoryAdapterBundle, build_default_memory_adapters
from admitpilot.platform.observability import ObservabilitySuite, build_default_observability_suite
from admitpilot.platform.tools import ToolRegistry, build_default_tool_registry


@dataclass(slots=True)
class PlatformCommonBundle:
    """公共区初始化集合。"""

    method_schemas: MethodSchemaRegistry
    mcp_servers: MCPServerRegistry
    tool_registry: ToolRegistry
    memory_adapters: MemoryAdapterBundle
    governance: GovernanceSuite
    observability: ObservabilitySuite
    error_codes: tuple[ErrorCode, ...] = field(default_factory=lambda: tuple(ErrorCode))
    todo: tuple[str, ...] = field(
        default_factory=lambda: (
            "将 bundle 注入 PAO runtime 启动流程",
            "把 in-memory 适配器替换为生产后端实现",
            "建立跨组件健康检查与启动前校验",
        )
    )


def build_default_platform_common_bundle() -> PlatformCommonBundle:
    """构建默认公共区初始化集合。"""

    method_schemas = build_default_method_schema_registry()
    return PlatformCommonBundle(
        method_schemas=method_schemas,
        mcp_servers=build_default_mcp_server_registry(schema_registry=method_schemas),
        tool_registry=build_default_tool_registry(),
        memory_adapters=build_default_memory_adapters(),
        governance=build_default_governance_suite(),
        observability=build_default_observability_suite(),
    )
