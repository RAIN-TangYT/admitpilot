"""PAO task router."""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.core.schemas import AgentTask
from admitpilot.pao.schemas import RoutePlan


@dataclass
class IntentRouter:
    """Parse intent and build executable agent tasks."""

    default_intent: str = "composite_application_support"
    prerequisite_intents: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "timeline": ("strategy",),
            "documents": ("strategy", "timeline"),
        }
    )
    intent_keywords: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "intelligence": (
                "信息",
                "政策",
                "官网",
                "official",
                "requirement",
                "deadline",
                "截止",
                "截止时间",
                "ddl",
                "要求",
                "更新",
            ),
            "strategy": ("选校", "匹配", "定位", "风险", "reach", "match", "safety"),
            "timeline": ("时间线", "计划", "排期", "规划", "milestone", "任务"),
            "documents": ("文书", "ps", "sop", "cv", "面试", "叙事"),
        }
    )

    def build_plan(self, query: str) -> RoutePlan:
        """根据用户请求构造可执行路由计划。"""
        lowered = query.lower()
        matched = {
            intent
            for intent, keywords in self.intent_keywords.items()
            if any(keyword.lower() in lowered for keyword in keywords)
        }
        if not matched:
            matched = {"intelligence", "strategy", "timeline", "documents"}

        selected = self._expand_prerequisite_intents(matched)

        tasks = [
            AgentTask(
                name="collect_intelligence",
                description="Collect and normalize admissions intelligence.",
                agent="aie",
            )
        ]
        if "strategy" in selected:
            tasks.append(
                AgentTask(
                    name="evaluate_strategy",
                    description="Evaluate school tiers and risk-aware ranking.",
                    agent="sae",
                    depends_on=["collect_intelligence"],
                    required_memory=["aie"],
                )
            )
        if "timeline" in selected:
            tasks.append(
                AgentTask(
                    name="build_timeline",
                    description="Generate the weekly application execution plan.",
                    agent="dta",
                    depends_on=["evaluate_strategy"],
                    required_memory=["aie", "sae"],
                )
            )
        if "documents" in selected:
            tasks.append(
                AgentTask(
                    name="draft_documents",
                    description="Draft document and interview support materials.",
                    agent="cds",
                    depends_on=["evaluate_strategy", "build_timeline"],
                    required_memory=["sae", "dta"],
                    can_degrade=True,
                )
            )

        rationale = f"Matched intents: {', '.join(sorted(matched))}"
        expanded = sorted(selected - matched)
        if expanded:
            rationale += f"; added prerequisite intents: {', '.join(expanded)}"
        return RoutePlan(intent=self.default_intent, tasks=tasks, rationale=rationale)

    def _expand_prerequisite_intents(self, selected: set[str]) -> set[str]:
        expanded = set(selected)
        changed = True
        while changed:
            changed = False
            for intent in list(expanded):
                for dependency in self.prerequisite_intents.get(intent, ()):
                    if dependency not in expanded:
                        expanded.add(dependency)
                        changed = True
        return expanded
