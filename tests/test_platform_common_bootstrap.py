from datetime import datetime

from admitpilot.platform import build_default_platform_common_bundle
from admitpilot.platform.common import ErrorCode
from admitpilot.platform.governance import build_default_governance_suite
from admitpilot.platform.mcp import (
    build_default_mcp_server_registry,
    build_default_method_schema_registry,
)
from admitpilot.platform.memory import (
    MemoryNamespace,
    VersionedRecord,
    build_default_memory_adapters,
)


def test_method_schema_registry_validates_required_fields() -> None:
    registry = build_default_method_schema_registry()
    missing = registry.validate_required_fields(
        method="official.fetch_pages",
        payload={"schools": ["NUS"], "program": "MSCS"},
    )
    assert "cycle" in missing
    assert "domains_whitelist" in missing
    assert "as_of_date" in missing


def test_mcp_server_registry_builds_server_stubs() -> None:
    registry = build_default_mcp_server_registry()
    intelligence_server = registry.get_server("intelligence-mcp")
    assert intelligence_server is not None
    assert "official.fetch_pages" in intelligence_server.methods


def test_memory_adapter_bundle_supports_session_and_versioned_records() -> None:
    bundle = build_default_memory_adapters()
    bundle.session_store.set("s1", {"step": "route"}, ttl_seconds=60)
    assert bundle.session_store.get("s1") == {"step": "route"}
    record = VersionedRecord(
        tenant_id="t1",
        user_id="u1",
        application_id="a1",
        cycle="2026",
        namespace=MemoryNamespace.STRATEGY,
        version_id="v1",
        as_of_date="2026-01-01",
        payload={"ranking": ["NUS", "NTU"]},
        created_at=datetime.utcnow(),
    )
    version_id = bundle.versioned_store.upsert(record)
    latest = bundle.versioned_store.get_latest(
        namespace=MemoryNamespace.STRATEGY,
        tenant_id="t1",
        user_id="u1",
        application_id="a1",
        cycle="2026",
    )
    assert version_id == "v1"
    assert latest is not None
    assert latest.payload["ranking"] == ["NUS", "NTU"]


def test_governance_suite_supports_acl_and_pii_redaction() -> None:
    suite = build_default_governance_suite()
    assert suite.acl.can_read("aie", "official") is True
    assert suite.acl.can_write("sae", "official") is False
    redacted, pii_map = suite.pii_redactor.redact(
        {"name": "Alice", "gpa": "3.8", "email": "a@example.com"}
    )
    assert redacted["name"] == "***REDACTED***"
    assert redacted["gpa"] == "3.8"
    assert pii_map["email"] == "a@example.com"


def test_platform_common_bundle_initialization() -> None:
    bundle = build_default_platform_common_bundle()
    assert bundle.tool_registry.validate_access("official_fetch", "aie") is True
    assert bundle.mcp_servers.get_server("document-mcp") is not None
    assert ErrorCode.AUTH_001 in bundle.error_codes
