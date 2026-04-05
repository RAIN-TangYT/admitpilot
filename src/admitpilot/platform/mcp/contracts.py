"""MCP 协议骨架。

设计目标：
1) 统一跨 MCP Server 的请求/响应封装
2) 固化 trace 与 lineage 字段，支撑审计与回放
3) 为后续 JSON Schema 校验预留字段
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

EvidenceLevel = Literal[
    "official_primary",
    "official_snapshot",
    "high_cred_case",
    "inferred",
]
RpcStatus = Literal["ok", "error", "partial"]

ParamsT = TypeVar("ParamsT")
ResultT = TypeVar("ResultT")


@dataclass(slots=True)
class RpcMeta:
    """MCP 请求元数据。"""

    trace_id: str
    tenant_id: str
    user_id: str
    application_id: str
    cycle: str
    agent_id: str
    tool_run_id: str
    schema_version: str = "v1"
    idempotency_key: str = ""


@dataclass(slots=True)
class MCPRequest(Generic[ParamsT]):
    """JSON-RPC 风格请求包。"""

    jsonrpc: str
    id: str
    method: str
    params: ParamsT
    meta: RpcMeta


@dataclass(slots=True)
class MCPResult(Generic[ResultT]):
    """MCP 成功响应数据体。"""

    status: RpcStatus
    result: ResultT
    confidence: float
    evidence_level: EvidenceLevel
    result_version: str
    lineage: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class MCPError:
    """MCP 错误体。"""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPResponse(Generic[ResultT]):
    """JSON-RPC 风格响应包。"""

    jsonrpc: str
    id: str
    result: MCPResult[ResultT] | None = None
    error: MCPError | None = None
