"""Template layer for school-specific document outlines."""

from __future__ import annotations

from typing import Any

from admitpilot.agents.cds.schemas import NarrativeFactSlot
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput

_SCHOOL_FOCUS = {
    "NUS": "强调课程深度与系统工程实践",
    "NTU": "强调AI数学基础与工程落地",
    "HKU": "强调算法能力与跨领域应用",
    "CUHK": "强调理论扎实与研究潜力",
    "HKUST": "强调技术领导力与产业转化",
}


def build_sop_outline(
    school: str,
    strategy: SAEAgentOutput,
    timeline: DTAAgentOutput,
    fact_slots: list[NarrativeFactSlot],
) -> tuple[list[str], list[str]]:
    """Build school-specific SOP outline and draft risks."""
    focus = _SCHOOL_FOCUS.get(school.upper(), "强调项目匹配与个人成长闭环")
    recommendation = _find_recommendation(strategy, school)
    gaps = recommendation.get("gaps", []) if isinstance(recommendation, dict) else []
    risk_flags = recommendation.get("risk_flags", []) if isinstance(recommendation, dict) else []
    missing_inputs = recommendation.get("missing_inputs", []) if isinstance(recommendation, dict) else []
    deadline_hint = _deadline_hint(timeline)

    verified_facts = [item.slot_id for item in fact_slots if item.status == "verified"]
    inferred_facts = [item.slot_id for item in fact_slots if item.status == "inferred"]
    outline = [
        f"{school}项目定位：{focus}",
        f"个人证据主线：verified={','.join(verified_facts) or 'none'}",
        f"能力映射与课程匹配（deadline={deadline_hint}）",
        "职业目标与项目资源闭环",
    ]
    if inferred_facts:
        outline.append(f"需补证据槽位：{','.join(inferred_facts)}")

    risks: list[str] = []
    for item in gaps:
        risks.append(f"gap:{item}")
    for flag in risk_flags:
        risks.append(f"risk_flag:{flag}")
    for field_name in missing_inputs:
        risks.append(f"missing_input:{field_name}")
    if not risks:
        risks = ["需人工复核项目匹配叙事是否与证据一致"]
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
        "教育背景（与目标项目方向一致）",
        "项目经历（按影响力与相关性排序）",
        "实习/科研（突出量化结果）",
        f"申请优先级映射：{', '.join(ranking[:3]) or '待补充'}",
        f"执行节奏对齐：周计划节点数={len(weekly_plan)}",
    ]
    risks = [
        "避免与 SoP 时间线冲突",
        "避免未验证事实进入最终版本",
    ]
    if verified_count == 0:
        risks.append("当前缺少 verified 证据，CV 仅可作为草稿结构")
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
