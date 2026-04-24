"""Fact slot extraction from user artifacts and upstream context."""

from __future__ import annotations

from admitpilot.agents.cds.schemas import NarrativeFactSlot
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput
from admitpilot.core.user_artifacts import UserArtifactsBundle


def build_fact_slots(
    *,
    artifacts: UserArtifactsBundle,
    strategy: SAEAgentOutput,
    timeline: DTAAgentOutput,
) -> list[NarrativeFactSlot]:
    """Build structured fact slots grounded in user evidence."""
    ranking = strategy.get("ranking_order", [])
    milestones = timeline.get("milestones", [])

    verified_projects = [item for item in artifacts.of_type("project") if item.verified]
    all_projects = artifacts.of_type("project")
    project_signal = (
        "; ".join(item.title for item in verified_projects[:2])
        if verified_projects
        else ("; ".join(item.title for item in all_projects[:2]) if all_projects else "缺少项目证据")
    )
    motivation_source = verified_projects[0].source_ref if verified_projects else "artifact:project"
    motivation_status = "verified" if verified_projects else ("inferred" if all_projects else "missing")

    facts = [
        NarrativeFactSlot(
            slot_id="motivation_core",
            value=f"核心动机由项目经历支撑: {project_signal}",
            source_ref=motivation_source,
            status=motivation_status,
            verified=motivation_status == "verified",
        ),
        NarrativeFactSlot(
            slot_id="program_fit",
            value=f"优先项目顺序: {', '.join(ranking[:3]) or '待补充'}",
            source_ref="sae_ranking",
            status="inferred" if ranking else "missing",
            verified=False,
        ),
        NarrativeFactSlot(
            slot_id="execution_proof",
            value=f"关键里程碑数量={len(milestones)}",
            source_ref="dta_milestones",
            status="inferred" if len(milestones) > 0 else "missing",
            verified=False,
        ),
    ]
    language_artifacts = artifacts.of_type("language")
    if language_artifacts:
        top = language_artifacts[0]
        facts.append(
            NarrativeFactSlot(
                slot_id="language_readiness",
                value=f"语言证据: {top.title}",
                source_ref=top.source_ref,
                status="verified" if top.verified else "inferred",
                verified=top.verified,
            )
        )
    return facts
