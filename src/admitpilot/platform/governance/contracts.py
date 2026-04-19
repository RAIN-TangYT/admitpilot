"""Governance hooks for policy validation and compatibility exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from admitpilot.platform.types import AgentRole


class NamespaceAclManager(Protocol):
    """Namespace read/write access control."""

    def can_read(self, agent: AgentRole, namespace: str) -> bool:
        """Return whether the agent may read a namespace."""

    def can_write(self, agent: AgentRole, namespace: str) -> bool:
        """Return whether the agent may write a namespace."""


class PiiRedactor(Protocol):
    """PII redaction hook."""

    def redact(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        """Return redacted payload and the extracted PII map."""


@dataclass(slots=True)
class AuditEvent:
    """Audit event payload."""

    event_id: str
    trace_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuditSink(Protocol):
    """Audit persistence hook."""

    def write(self, event: AuditEvent) -> str:
        """Persist an audit event."""

    def list_by_trace(self, trace_id: str) -> list[AuditEvent]:
        """List events by trace id."""


@dataclass(slots=True)
class ApprovalRequest:
    """Approval workflow request."""

    approval_id: str
    application_id: str
    artifact_ref: str
    approval_type: str
    status: str = "pending"
    reviewer: str = ""
    comment: str = ""


class ApprovalWorkflow(Protocol):
    """Approval workflow persistence."""

    def create(self, request: ApprovalRequest) -> str:
        """Create an approval request."""

    def resolve(self, approval_id: str, status: str, reviewer: str, comment: str = "") -> None:
        """Resolve an approval request."""

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """Return an approval request."""


@dataclass(slots=True)
class InMemoryNamespaceAclManager:
    """In-memory ACL manager."""

    read_policies: dict[tuple[AgentRole, str], bool] = field(default_factory=dict)
    write_policies: dict[tuple[AgentRole, str], bool] = field(default_factory=dict)

    def can_read(self, agent: AgentRole, namespace: str) -> bool:
        return self.read_policies.get((agent, namespace), False)

    def can_write(self, agent: AgentRole, namespace: str) -> bool:
        return self.write_policies.get((agent, namespace), False)


@dataclass(slots=True)
class SimplePiiRedactor:
    """Simple in-memory redactor."""

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
    """In-memory audit sink."""

    events: list[AuditEvent] = field(default_factory=list)

    def write(self, event: AuditEvent) -> str:
        self.events.append(event)
        return event.event_id

    def list_by_trace(self, trace_id: str) -> list[AuditEvent]:
        return [item for item in self.events if item.trace_id == trace_id]


@dataclass(slots=True)
class InMemoryApprovalWorkflow:
    """In-memory approval workflow."""

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
    """Compatibility governance bundle expected by tests."""

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


@dataclass(slots=True)
class GovernanceEngine:
    """Simple policy gate and audit trail used by the orchestrator runtime."""

    blocked_terms: tuple[str, ...] = ("fabricate", "fake", "作弊", "伪造")
    _audit: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def policy_validate(self, text: str) -> tuple[bool, str]:
        lowered = text.lower()
        for term in self.blocked_terms:
            if term.lower() in lowered:
                return False, f"policy_blocked:{term}"
        return True, "ok"

    def redact_pii(self, payload: dict[str, Any]) -> dict[str, Any]:
        redacted, _ = SimplePiiRedactor().redact(payload)
        return redacted

    def audit(self, event: str, details: dict[str, Any]) -> None:
        self._audit.append(
            {"event": event, "details": details, "at": datetime.utcnow().isoformat()}
        )

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)
