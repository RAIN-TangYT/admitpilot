"""Schemas for MCP method definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MethodSpec:
    """MCP method spec for registry and authorization."""

    name: str
    description: str
    allowed_agents: set[str] = field(default_factory=set)
