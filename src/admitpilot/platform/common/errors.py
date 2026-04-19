"""Shared platform error codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    AUTH_001 = "AUTH_001"
    AUTH_002 = "AUTH_002"
    AUTH_003 = "AUTH_003"
    REQ_001 = "REQ_001"
    REQ_002 = "REQ_002"
    REQ_003 = "REQ_003"
    DATA_001 = "DATA_001"
    DATA_002 = "DATA_002"
    DATA_003 = "DATA_003"
    SYS_001 = "SYS_001"
    SYS_002 = "SYS_002"
    SYS_003 = "SYS_003"
    AGENT_NOT_REGISTERED = "AGENT_NOT_REGISTERED"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"


@dataclass(frozen=True, slots=True)
class ErrorDescriptor:
    """Metadata for a well-known platform error code."""

    code: ErrorCode
    category: str
    retryable: bool
    default_message: str


_ERROR_DESCRIPTORS: dict[ErrorCode, ErrorDescriptor] = {
    ErrorCode.AUTH_001: ErrorDescriptor(
        code=ErrorCode.AUTH_001,
        category="auth",
        retryable=False,
        default_message="token 无效",
    ),
    ErrorCode.AUTH_002: ErrorDescriptor(
        code=ErrorCode.AUTH_002,
        category="auth",
        retryable=False,
        default_message="方法越权",
    ),
    ErrorCode.AUTH_003: ErrorDescriptor(
        code=ErrorCode.AUTH_003,
        category="auth",
        retryable=False,
        default_message="scope 越权",
    ),
    ErrorCode.REQ_001: ErrorDescriptor(
        code=ErrorCode.REQ_001,
        category="request",
        retryable=False,
        default_message="schema 校验失败",
    ),
    ErrorCode.REQ_002: ErrorDescriptor(
        code=ErrorCode.REQ_002,
        category="request",
        retryable=False,
        default_message="必填字段缺失",
    ),
    ErrorCode.REQ_003: ErrorDescriptor(
        code=ErrorCode.REQ_003,
        category="request",
        retryable=False,
        default_message="幂等键冲突",
    ),
    ErrorCode.DATA_001: ErrorDescriptor(
        code=ErrorCode.DATA_001,
        category="data",
        retryable=False,
        default_message="数据不存在",
    ),
    ErrorCode.DATA_002: ErrorDescriptor(
        code=ErrorCode.DATA_002,
        category="data",
        retryable=False,
        default_message="版本冲突",
    ),
    ErrorCode.DATA_003: ErrorDescriptor(
        code=ErrorCode.DATA_003,
        category="data",
        retryable=False,
        default_message="证据不足",
    ),
    ErrorCode.SYS_001: ErrorDescriptor(
        code=ErrorCode.SYS_001,
        category="system",
        retryable=True,
        default_message="上游超时",
    ),
    ErrorCode.SYS_002: ErrorDescriptor(
        code=ErrorCode.SYS_002,
        category="system",
        retryable=True,
        default_message="依赖服务不可用",
    ),
    ErrorCode.SYS_003: ErrorDescriptor(
        code=ErrorCode.SYS_003,
        category="system",
        retryable=False,
        default_message="降级执行触发",
    ),
}


def get_error_descriptor(code: ErrorCode) -> ErrorDescriptor:
    """Return a known error descriptor or synthesize a generic one."""

    descriptor = _ERROR_DESCRIPTORS.get(code)
    if descriptor is not None:
        return descriptor
    return ErrorDescriptor(
        code=code,
        category="platform",
        retryable=False,
        default_message=code.value,
    )


@dataclass(slots=True)
class PlatformError(Exception):
    """Typed platform error with code."""

    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"
