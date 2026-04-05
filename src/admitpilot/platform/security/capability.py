"""Capability Token 接口定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(slots=True)
class CapabilityToken:
    """PAO 下发的短时能力令牌。"""

    token_id: str
    subject: str
    allowed_methods: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    expires_at: datetime
    issued_at: datetime
    constraints: dict[str, str] = field(default_factory=dict)

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


class CapabilityIssuer(Protocol):
    """能力令牌签发接口。"""

    def issue(
        self,
        subject: str,
        allowed_methods: tuple[str, ...],
        allowed_scopes: tuple[str, ...],
        ttl_seconds: int,
    ) -> CapabilityToken:
        """签发短时令牌。"""


class CapabilityValidator(Protocol):
    """能力令牌校验接口。"""

    def validate_method(self, token: CapabilityToken, method: str, now: datetime) -> bool:
        """校验方法级权限。"""

    def validate_scope(self, token: CapabilityToken, scope: str, now: datetime) -> bool:
        """校验数据域权限。"""


@dataclass(slots=True)
class InMemoryCapabilityValidator:
    """默认校验器。

    TODO:
    1) 接入签名验真与撤销列表
    2) 接入租户级策略中心
    """

    def validate_method(self, token: CapabilityToken, method: str, now: datetime) -> bool:
        if token.is_expired(now):
            return False
        return method in token.allowed_methods

    def validate_scope(self, token: CapabilityToken, scope: str, now: datetime) -> bool:
        if token.is_expired(now):
            return False
        if "*" in token.allowed_scopes:
            return True
        return scope in token.allowed_scopes
