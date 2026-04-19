"""命令行示例入口。"""

from __future__ import annotations

from admitpilot.app import build_application
from admitpilot.config import load_settings
from admitpilot.core.schemas import UserProfile
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG
from admitpilot.pao.contracts import OrchestrationRequest


def main() -> None:
    """运行一次端到端编排示例。"""
    settings = load_settings()
    application = build_application(settings=settings)
    orchestrator = application.orchestrator
    default_portfolio = DEFAULT_ADMISSIONS_CATALOG.default_program_portfolio(
        ["NUS", "NTU", "HKU", "CUHK", "HKUST"]
    )
    request = OrchestrationRequest(
        user_query=f"我需要完成{settings.default_cycle}申请季的选校、时间规划和文书准备",
        profile=UserProfile(
            name="Demo Applicant",
            degree_level="Master",
            major_interest="Computing",
            target_regions=["Singapore", "Hong Kong"],
            target_schools=["NUS", "NTU", "HKU", "CUHK", "HKUST"],
            target_programs=list(dict.fromkeys(default_portfolio.values())),
        ),
        constraints={
            "timezone": settings.timezone,
            "cycle": settings.default_cycle,
            "target_schools": ["NUS", "NTU", "HKU", "CUHK", "HKUST"],
            "target_program_by_school": default_portfolio,
        },
    )
    response = orchestrator.invoke(request)
    print(response.summary)
    for result in response.results:
        print(f"{result.agent}: {result.output}")


if __name__ == "__main__":
    main()
