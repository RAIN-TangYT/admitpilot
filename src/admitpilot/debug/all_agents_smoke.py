from __future__ import annotations

from typing import cast

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.agents.cds.agent import CDSAgent
from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.agents.dta.agent import DTAAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.agents.sae.agent import SAEAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import AgentTask, ApplicationContext, SharedMemory, UserProfile
from admitpilot.platform.llm.qwen import QwenClient


def main() -> None:
    llm_client = QwenClient()
    context = ApplicationContext(
        user_query="帮我规划 2026 Fall 的港新计算机硕士申请方案",
        profile=UserProfile(
            name="Debug User",
            degree_level="bachelor",
            major_interest="Computer Science",
            target_schools=["NUS", "HKU", "CUHK"],
            target_programs=["MSCS"],
            academic_metrics={"gpa": 3.72},
            language_scores={"ielts": 7.5},
            experiences=["科研项目", "后端实习", "机器学习课程项目"],
            risk_preference="balanced",
        ),
        constraints={"cycle": "2026", "timeline_weeks": 8, "timezone": "Asia/Shanghai"},
        shared_memory=cast(SharedMemory, {}),
    )
    pipeline = [
        (
            "aie",
            AIEAgent(service=AdmissionsIntelligenceService(llm_client=llm_client)),
            AgentTask(name="collect_intelligence", description="collect", agent="aie"),
        ),
        (
            "sae",
            SAEAgent(service=StrategicAdmissionsService(llm_client=llm_client)),
            AgentTask(
                name="evaluate_strategy",
                description="evaluate",
                agent="sae",
                depends_on=["collect_intelligence"],
                required_memory=["aie"],
            ),
        ),
        (
            "dta",
            DTAAgent(service=DynamicTimelineService(llm_client=llm_client)),
            AgentTask(
                name="build_timeline",
                description="timeline",
                agent="dta",
                depends_on=["evaluate_strategy"],
                required_memory=["aie", "sae"],
            ),
        ),
        (
            "cds",
            CDSAgent(service=CoreDocumentService(llm_client=llm_client)),
            AgentTask(
                name="draft_documents",
                description="documents",
                agent="cds",
                depends_on=["build_timeline"],
                required_memory=["sae", "dta"],
            ),
        ),
    ]
    for memory_key, agent, task in pipeline:
        result = agent.run(task=task, context=context)
        context.shared_memory[memory_key] = result.output
        print(f"{memory_key}: success={result.success} confidence={result.confidence:.2f}")
        print(str(result.output)[:600])
        print("---")


if __name__ == "__main__":
    main()
