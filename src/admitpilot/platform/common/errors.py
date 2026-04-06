"""Shared platform error codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    AGENT_NOT_REGISTERED = "AGENT_NOT_REGISTERED"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"


@dataclass(slots=True)
class PlatformError(Exception):
    """Typed platform error with code."""

    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"
