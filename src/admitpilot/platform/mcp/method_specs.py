"""Canonical MCP method catalog."""

from __future__ import annotations

from admitpilot.platform.mcp.schemas import MethodSpec


METHOD_CATALOG: dict[str, MethodSpec] = {
    "official_fetch": MethodSpec(
        name="official_fetch",
        description="Fetch official admissions pages",
        allowed_agents={"aie"},
    ),
    "strategy_rule_evaluate": MethodSpec(
        name="strategy_rule_evaluate",
        description="Evaluate school strategy rules",
        allowed_agents={"sae"},
    ),
    "timeline_replan": MethodSpec(
        name="timeline_replan",
        description="Replan timeline milestones",
        allowed_agents={"dta"},
    ),
    "document_consistency_check": MethodSpec(
        name="document_consistency_check",
        description="Check cross-document consistency",
        allowed_agents={"cds"},
    ),
}
