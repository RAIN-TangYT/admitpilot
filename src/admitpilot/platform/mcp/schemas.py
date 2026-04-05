"""MCP 方法级 schema 初始化定义。

当前只做字段级最小校验，后续可替换为 JSON Schema 引擎。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admitpilot.platform.mcp.method_specs import METHOD_CATALOG, MethodContract


@dataclass(slots=True)
class MethodSchema:
    """方法 schema 抽象。"""

    method: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = field(default_factory=tuple)
    todo: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class MethodSchemaRegistry:
    """方法 schema 注册中心。"""

    schemas: dict[str, MethodSchema] = field(default_factory=dict)

    def register(self, schema: MethodSchema) -> None:
        self.schemas[schema.method] = schema

    def get(self, method: str) -> MethodSchema | None:
        return self.schemas.get(method)

    def validate_required_fields(self, method: str, payload: dict[str, Any]) -> list[str]:
        """返回缺失字段列表。"""
        schema = self.get(method)
        if schema is None:
            return ["<unknown_method>"]
        missing = [field for field in schema.required_fields if field not in payload]
        return missing


def build_default_method_schema_registry() -> MethodSchemaRegistry:
    """基于 method catalog 构建默认 schema 注册中心。"""

    registry = MethodSchemaRegistry()
    for contract in METHOD_CATALOG:
        registry.register(_schema_from_contract(contract))
    return registry


def _schema_from_contract(contract: MethodContract) -> MethodSchema:
    return MethodSchema(
        method=contract.method,
        required_fields=contract.input_fields,
        optional_fields=(),
        todo=(
            "接入 JSON Schema 校验器",
            "接入字段级别类型与枚举约束",
        ),
    )
