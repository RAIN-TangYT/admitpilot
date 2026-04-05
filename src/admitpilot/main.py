"""命令行示例入口。"""

from __future__ import annotations

from admitpilot.core.schemas import UserProfile
from admitpilot.pao.contracts import OrchestrationRequest
from admitpilot.pao.orchestrator import PrincipalApplicationOrchestrator


def main() -> None:
    """运行一次端到端编排示例。"""
    orchestrator = PrincipalApplicationOrchestrator()
    request = OrchestrationRequest(
        user_query="我需要完成2026申请季的选校、时间规划和文书准备",
        profile=UserProfile(
            name="Demo Applicant",
            degree_level="Master",
            major_interest="Computer Science",
            target_regions=["Singapore", "Hong Kong"],
            target_schools=["NUS", "NTU", "HKU", "CUHK", "HKUST"],
            target_programs=["MSCS"],
        ),
        constraints={
            "timezone": "Asia/Shanghai",
            "cycle": "2026",
            "target_schools": ["NUS", "NTU", "HKU", "CUHK", "HKUST"],
            "target_program": "MSCS",
        },
    )
    response = orchestrator.invoke(request)
    print(response.summary)
    for result in response.results:
        print(f"{result.agent}: {result.output}")


if __name__ == "__main__":
    main()
