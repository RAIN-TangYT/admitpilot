"""MCP request/response contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPRequest:
    """All MCP requests carry trace and tool IDs."""

    method: str
    params: dict[str, Any]
    trace_id: str
    tool_run_id: str
    idempotency_key: str
    result_version: int = 1


@dataclass(slots=True)
class MCPResponse:
    """MCP response envelope."""

    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""
