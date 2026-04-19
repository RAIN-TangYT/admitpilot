from typing import cast

from admitpilot.agents.dta.agent import DTAAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.core.schemas import (
    AgentTask,
    AIEAgentOutput,
    ApplicationContext,
    SAEAgentOutput,
    SharedMemory,
    UserProfile,
)
from admitpilot.platform.llm.openai import OpenAIClient


def main() -> None:
    llm_client = OpenAIClient()
    dta_agent = DTAAgent(service=DynamicTimelineService(llm_client=llm_client))

    # 模拟上游 SAE 传递的数据 (带有明显的 gap_actions 语言和背景提升要求)
    sae_output: SAEAgentOutput = {
        "summary": "申请者具备基础学术能力，但需要补齐语言和科研短板。",
        "gap_actions": ["备考雅思争取7.0以上", "完成一段后端或机器学习相关的科研项目"],
        "strengths": ["GPA 良好"],
        "weaknesses": ["无顶会科研经历", "语言成绩尚未达标"],
        "recommendations": [
            {"school": "NUS", "program": "MSCS", "tier": "reach"},
            {"school": "HKU", "program": "MSCS", "tier": "match"},
        ],
        "ranking_order": ["NUS", "HKU"],
        "model_breakdown": {"rule": 0.45, "semantic": 0.35, "risk": 0.2},
    }

    # 模拟上游 AIE 传递的数据
    aie_output: AIEAgentOutput = {
        "cycle": "2026",
        "as_of_date": "2026-04-19",
        "official_status_by_school": {"NUS": "predicted", "HKU": "official_found"},
        "target_schools": ["NUS", "HKU"],
        "target_program": "MSCS",
        "official_records": [],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [],
        "evidence_levels": {"NUS": "forecast_with_history", "HKU": "official_primary"},
        "official_confidence": 0.5,
        "case_confidence": 0.0,
        "cache_hit_count": 0,
        "prediction_used": True,
    }

    context = ApplicationContext(
        user_query="帮我规划 2026 Fall 的港新计算机硕士申请方案，目前还没考雅思也没科研",
        profile=UserProfile(
            name="Test User",
            degree_level="bachelor",
            major_interest="Computer Science",
            target_schools=["NUS", "HKU"],
            target_programs=["MSCS"],
            academic_metrics={"gpa": 3.72},
            language_scores={},
            experiences=[],
            risk_preference="balanced",
        ),
        constraints={"cycle": "2026", "timeline_weeks": 10, "timezone": "Asia/Shanghai"},
        shared_memory=cast(SharedMemory, {"sae": sae_output, "aie": aie_output}),
    )

    task = AgentTask(
        name="build_timeline",
        description="timeline",
        agent="dta",
        depends_on=["evaluate_strategy"],
        required_memory=["aie", "sae"],
    )

    result = dta_agent.run(task=task, context=context)

    print("=== DTA Test Input Context ===")
    print("1. User Profile:")
    print(f"   Name: {context.profile.name}")
    print(f"   Major Interest: {context.profile.major_interest}")
    print(f"   GPA: {context.profile.academic_metrics.get('gpa')}")
    print("2. SAE Gap Actions (Strategy Output):")
    for action in sae_output.get("gap_actions", []):
        print(f"   - {action}")
    print("3. Timeline Constraints:")
    print(f"   Weeks: {context.constraints.get('timeline_weeks')}")
    print("=" * 30 + "\n")

    print("=== DTA Agent Output ===")
    print(f"Success: {result.success}, Confidence: {result.confidence:.2f}")

    if result.success:
        print("\n--- Board Title ---")
        print(result.output.get("board_title"))

        print("\n--- Milestones ---")
        for m in result.output.get("milestones", []):
            print(
                f"  [{m.get('due_week')}w] {m.get('title')} "
                f"(key: {m.get('key')}) - depends: {m.get('depends_on')}"
            )

        print("\n--- Weekly Plan ---")
        for w in result.output.get("weekly_plan", []):
            print(f"  Week {w.get('week')}: {w.get('focus')}")
            for item in w.get("items", []):
                print(f"    - {item}")
            for risk in w.get("risks", []):
                print(f"    ! Risk: {risk}")

        print("\n--- Risk Markers ---")
        for rm in result.output.get("risk_markers", []):
            print(
                f"  Week {rm.get('week')} [{rm.get('level')}]: "
                f"{rm.get('message')} -> {rm.get('mitigation')}"
            )

        print("\n--- Document Instructions ---")
        for ins in result.output.get("document_instructions", []):
            print(f"  * {ins}")


if __name__ == "__main__":
    main()
