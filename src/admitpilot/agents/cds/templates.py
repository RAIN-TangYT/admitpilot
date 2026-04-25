"""Template layer for school-specific document outlines."""

from __future__ import annotations

from typing import Any

from admitpilot.agents.cds.schemas import NarrativeFactSlot
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput

_SCHOOL_FOCUS = {
    "NUS": "course depth and systems engineering practice",
    "NTU": "AI mathematical foundations and engineering delivery",
    "HKU": "algorithmic ability and cross-domain application",
    "CUHK": "theoretical foundation and research potential",
    "HKUST": "technical leadership and industry translation",
}


def build_sop_outline(
    school: str,
    strategy: SAEAgentOutput,
    timeline: DTAAgentOutput,
    fact_slots: list[NarrativeFactSlot],
) -> tuple[list[str], list[str]]:
    """Build school-specific SOP outline and draft risks."""
    focus = _SCHOOL_FOCUS.get(school.upper(), "program fit and personal growth loop")
    recommendation = _find_recommendation(strategy, school)
    gaps = recommendation.get("gaps", []) if isinstance(recommendation, dict) else []
    risk_flags = recommendation.get("risk_flags", []) if isinstance(recommendation, dict) else []
    missing_inputs = (
        recommendation.get("missing_inputs", []) if isinstance(recommendation, dict) else []
    )
    deadline_hint = _deadline_hint(timeline)

    verified_facts = [item.slot_id for item in fact_slots if item.status == "verified"]
    inferred_facts = [item.slot_id for item in fact_slots if item.status == "inferred"]
    outline = [
        f"{school} positioning: emphasize {focus}.",
        f"Personal evidence line: verified={','.join(verified_facts) or 'none'}.",
        f"Capability-to-course mapping with submission deadline={deadline_hint}.",
        "Career goals linked to program resources and applicant evidence.",
    ]
    if inferred_facts:
        outline.append(f"Fact slots requiring verification: {','.join(inferred_facts)}.")

    risks: list[str] = []
    for item in gaps:
        risks.append(f"gap:{item}")
    for flag in risk_flags:
        risks.append(f"risk_flag:{flag}")
    for field_name in missing_inputs:
        risks.append(f"missing_input:{field_name}")
    if not risks:
        risks = ["Human review required for program-fit narrative and evidence alignment."]
    return outline, risks


def build_cv_outline(
    strategy: SAEAgentOutput,
    timeline: DTAAgentOutput,
    fact_slots: list[NarrativeFactSlot],
) -> tuple[list[str], list[str]]:
    """Build shared CV outline with upstream constraints."""
    ranking = strategy.get("ranking_order", [])
    weekly_plan = timeline.get("weekly_plan", [])
    verified_count = sum(1 for item in fact_slots if item.status == "verified")
    outline = [
        "Education aligned to target program directions.",
        "Project experience ordered by impact and relevance.",
        "Internship and research entries with quantified outcomes.",
        f"Application priority mapping: {', '.join(ranking[:3]) or 'to be confirmed'}.",
        f"Execution cadence alignment: weekly_plan_count={len(weekly_plan)}.",
    ]
    risks = [
        "Avoid conflicts with the SOP timeline.",
        "Keep unverified facts out of the final version.",
    ]
    if verified_count == 0:
        risks.append("No verified evidence is available; CV can only be a draft structure.")
    return outline, risks


def _find_recommendation(strategy: SAEAgentOutput, school: str) -> dict[str, Any]:
    for item in strategy.get("recommendations", []):
        if str(item.get("school", "")).upper() == school.upper():
            return item
    return {}


def _deadline_hint(timeline: DTAAgentOutput) -> str:
    for milestone in timeline.get("milestones", []):
        if str(milestone.get("key", "")) == "submission_batch_1":
            return f"week-{milestone.get('due_week', '?')}"
    return "unknown"
