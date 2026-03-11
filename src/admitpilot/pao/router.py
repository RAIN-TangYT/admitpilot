"""PAO 任务路由器实现。"""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.core.schemas import AgentTask
from admitpilot.pao.schemas import RoutePlan


@dataclass(slots=True)
class IntentRouter:
    """负责意图识别与任务拆解。"""

    default_intent: str = "composite_application_support"
    intent_keywords: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "intelligence": ("信息", "政策", "官网", "deadline", "要求", "更新"),
            "strategy": ("选校", "匹配", "定位", "风险", "reach", "match", "safety"),
            "timeline": ("时间线", "计划", "排期", "milestone", "任务"),
            "documents": ("文书", "ps", "sop", "cv", "面试", "叙事"),
        }
    )

    def build_plan(self, query: str) -> RoutePlan:
        """根据用户请求构造可执行路由计划。"""
        lowered = query.lower()
        selected = {
            intent
            for intent, keywords in self.intent_keywords.items()
            if any(keyword.lower() in lowered for keyword in keywords)
        }
        if not selected:
            selected = {"intelligence", "strategy", "timeline", "documents"}

        tasks = [AgentTask(name="collect_intelligence", description="收集并标准化招生情报", agent="aie")]
        if "strategy" in selected:
            tasks.append(AgentTask(name="evaluate_strategy", description="完成选校分层与风险排序", agent="sae"))
        if "timeline" in selected:
            tasks.append(AgentTask(name="build_timeline", description="生成周级执行计划", agent="dta"))
        if "documents" in selected:
            tasks.append(AgentTask(name="draft_documents", description="输出文书与面试素材建议", agent="cds"))

        rationale = f"匹配到意图: {', '.join(sorted(selected))}"
        return RoutePlan(intent=self.default_intent, tasks=tasks, rationale=rationale)
