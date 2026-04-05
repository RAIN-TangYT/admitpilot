from datetime import datetime, timedelta

from admitpilot.platform.mcp import METHOD_CATALOG
from admitpilot.platform.memory.contracts import MemoryNamespace, default_memory_topology
from admitpilot.platform.runtime import RuntimeStateMachine, WorkflowStatus
from admitpilot.platform.security import CapabilityToken, InMemoryCapabilityValidator
from admitpilot.platform.tools import build_default_tool_registry


def test_method_catalog_contains_key_methods() -> None:
    methods = {item.method for item in METHOD_CATALOG}
    assert "official.fetch_pages" in methods
    assert "strategy.risk_rank" in methods
    assert "timeline.plan_build" in methods
    assert "document.draft_compose" in methods
    assert "governance.policy_validate" in methods


def test_tool_registry_enforces_agent_access() -> None:
    registry = build_default_tool_registry()
    assert registry.validate_access("official_fetch", "aie") is True
    assert registry.validate_access("official_fetch", "sae") is False


def test_runtime_state_machine_transition_rules() -> None:
    state_machine = RuntimeStateMachine()
    assert state_machine.can_transition(WorkflowStatus.NEW, WorkflowStatus.INTENT_PARSED) is True
    assert state_machine.can_transition(WorkflowStatus.NEW, WorkflowStatus.DELIVERED) is False


def test_capability_validator_checks_expiration_and_method() -> None:
    now = datetime.utcnow()
    token = CapabilityToken(
        token_id="t1",
        subject="aie",
        allowed_methods=("official.fetch_pages",),
        allowed_scopes=("*",),
        expires_at=now + timedelta(minutes=5),
        issued_at=now,
    )
    validator = InMemoryCapabilityValidator()
    assert validator.validate_method(token, "official.fetch_pages", now=now) is True
    assert validator.validate_method(token, "strategy.risk_rank", now=now) is False


def test_memory_topology_defaults() -> None:
    topology = default_memory_topology()
    assert topology.session_backend == "redis"
    assert topology.relational_backend == "postgresql"
    assert MemoryNamespace.STRATEGY.value == "strategy"
