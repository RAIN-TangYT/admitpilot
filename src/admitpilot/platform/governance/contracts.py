"""治理层协议与初始化定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from admitpilot.platform.types import AgentRole


class NamespaceAclManager(Protocol):
    """Namespace 读写控制接口。"""

    def can_read(self, agent: AgentRole, namespace: str) -> bool:
        """校验读权限。"""

    def can_write(self, agent: AgentRole, namespace: str) -> bool:
        """校验写权限。"""


class PiiRedactor(Protocol):
    """PII 脱敏接口。"""

    def redact(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        """返回脱敏后的负载与映射信息。"""


@dataclass(slots=True)
class AuditEvent:
    """审计事件定义。"""

    event_id: str
    trace_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuditSink(Protocol):
    """审计写入接口。"""

    def write(self, event: AuditEvent) -> str:
        """写入事件并返回 event_id。"""

    def list_by_trace(self, trace_id: str) -> list[AuditEvent]:
        """按 trace 查询事件。"""


@dataclass(slots=True)
class ApprovalRequest:
    """审批请求定义。"""

    approval_id: str
    application_id: str
    artifact_ref: str
    approval_type: str
    status: str = "pending"
    reviewer: str = ""
    comment: str = ""


class ApprovalWorkflow(Protocol):
    """审批流程接口。"""

    def create(self, request: ApprovalRequest) -> str:
        """创建审批请求。"""

    def resolve(self, approval_id: str, status: str, reviewer: str, comment: str = "") -> None:
        """更新审批结果。"""

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """查询审批状态。"""


@dataclass(slots=True)
class InMemoryNamespaceAclManager:
    """内存 ACL 管理器。"""

    read_policies: dict[tuple[AgentRole, str], bool] = field(default_factory=dict)
    write_policies: dict[tuple[AgentRole, str], bool] = field(default_factory=dict)

    def can_read(self, agent: AgentRole, namespace: str) -> bool:
        return self.read_policies.get((agent, namespace), False)

    def can_write(self, agent: AgentRole, namespace: str) -> bool:
        return self.write_policies.get((agent, namespace), False)


@dataclass(slots=True)
class SimplePiiRedactor:
    """简单脱敏器（占位实现）。"""

    pii_keys: tuple[str, ...] = ("name", "email", "phone", "passport", "id_number")

    def redact(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        redacted: dict[str, Any] = {}
        pii_map: dict[str, str] = {}
        for key, value in payload.items():
            if key.lower() in self.pii_keys:
                pii_map[key] = str(value)
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted, pii_map


@dataclass(slots=True)
class InMemoryAuditSink:
    """内存审计落地器。"""

    events: list[AuditEvent] = field(default_factory=list)

    def write(self, event: AuditEvent) -> str:
        self.events.append(event)
        return event.event_id

    def list_by_trace(self, trace_id: str) -> list[AuditEvent]:
        return [item for item in self.events if item.trace_id == trace_id]


@dataclass(slots=True)
class InMemoryApprovalWorkflow:
    """内存审批流程。"""

    requests: dict[str, ApprovalRequest] = field(default_factory=dict)

    def create(self, request: ApprovalRequest) -> str:
        self.requests[request.approval_id] = request
        return request.approval_id

    def resolve(self, approval_id: str, status: str, reviewer: str, comment: str = "") -> None:
        request = self.requests[approval_id]
        request.status = status
        request.reviewer = reviewer
        request.comment = comment

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self.requests.get(approval_id)


@dataclass(slots=True)
class GovernanceSuite:
    """治理初始化集合。"""

    acl: NamespaceAclManager
    pii_redactor: PiiRedactor
    audit_sink: AuditSink
    approval_workflow: ApprovalWorkflow
    todo: tuple[str, ...] = field(
        default_factory=lambda: (
            "替换为策略中心与签名验真",
            "审计写入切换到持久化存储",
            "审批流程接入通知与 SLA",
        )
    )


def build_default_governance_suite() -> GovernanceSuite:
    acl = InMemoryNamespaceAclManager()
    _apply_default_acl_policies(acl)
    return GovernanceSuite(
        acl=acl,
        pii_redactor=SimplePiiRedactor(),
        audit_sink=InMemoryAuditSink(),
        approval_workflow=InMemoryApprovalWorkflow(),
    )


def _apply_default_acl_policies(acl: InMemoryNamespaceAclManager) -> None:
    read_matrix: dict[AgentRole, tuple[str, ...]] = {
        "pao": ("application", "official", "case", "strategy", "timeline", "artifact", "audit"),
        "aie": ("application", "official", "case"),
        "sae": ("application", "official", "case", "strategy"),
        "dta": ("application", "official", "strategy", "timeline"),
        "cds": ("application", "strategy", "timeline", "artifact"),
    }
    write_matrix: dict[AgentRole, tuple[str, ...]] = {
        "pao": ("application", "audit"),
        "aie": ("official", "case"),
        "sae": ("strategy",),
        "dta": ("timeline",),
        "cds": ("artifact",),
    }
    for agent, namespaces in read_matrix.items():
        for namespace in namespaces:
            acl.read_policies[(agent, namespace)] = True
    for agent, namespaces in write_matrix.items():
        for namespace in namespaces:
            acl.write_policies[(agent, namespace)] = True
