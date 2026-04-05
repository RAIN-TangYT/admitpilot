from typing import Any, cast

from admitpilot.core.schemas import AgentTask, UserProfile
from admitpilot.pao.contracts import OrchestrationRequest
from admitpilot.pao.orchestrator import PrincipalApplicationOrchestrator
from admitpilot.pao.schemas import RoutePlan
from admitpilot.platform.runtime import TaskStatus


class UnknownAgentRouter:
    def build_plan(self, query: str) -> RoutePlan:
        return RoutePlan(
            intent="unknown_agent_test",
            tasks=[AgentTask(name="x", description="x", agent="ghost")],
            rationale=query,
        )


class MissingDependencyRouter:
    def build_plan(self, query: str) -> RoutePlan:
        return RoutePlan(
            intent="dependency_guard_test",
            tasks=[
                AgentTask(
                    name="evaluate_strategy",
                    description="缺少 AIE 上游依赖",
                    agent="sae",
                    depends_on=["collect_intelligence"],
                    required_memory=["aie"],
                )
            ],
            rationale=query,
        )


class DegradeOnlyDocumentsRouter:
    def build_plan(self, query: str) -> RoutePlan:
        return RoutePlan(
            intent="degrade_documents_test",
            tasks=[
                AgentTask(
                    name="draft_documents",
                    description="仅文书降级任务",
                    agent="cds",
                    depends_on=["evaluate_strategy", "build_timeline"],
                    required_memory=["sae", "dta"],
                    can_degrade=True,
                )
            ],
            rationale=query,
        )


def test_orchestrator_happy_path() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="我需要选校、时间线和文书支持",
            profile=UserProfile(major_interest="Computer Science"),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    assert len(response.results) >= 3
    assert response.context is not None
    assert "aie" in response.context.shared_memory


def test_orchestrator_handles_unknown_agent() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    orchestrator.router = cast(Any, UnknownAgentRouter())
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="触发未知代理",
            profile=UserProfile(),
            constraints={},
        )
    )
    assert len(response.results) == 1
    assert response.results[0].success is False
    assert response.results[0].output["error"] == "agent_not_registered"


def test_orchestrator_skips_task_when_dependency_not_met() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    orchestrator.router = cast(Any, MissingDependencyRouter())
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="测试依赖阻塞",
            profile=UserProfile(),
            constraints={},
        )
    )
    assert len(response.results) == 1
    result = response.results[0]
    assert result.status == TaskStatus.SKIPPED
    assert result.output["error"] == "dependency_blocked"
    assert "missing_task:collect_intelligence" in result.blocked_by
    assert "missing_memory:aie" in result.blocked_by


def test_orchestrator_allows_degrade_task_execution() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    orchestrator.router = cast(Any, DegradeOnlyDocumentsRouter())
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="测试降级执行",
            profile=UserProfile(),
            constraints={},
        )
    )
    assert len(response.results) == 1
    result = response.results[0]
    assert result.status == TaskStatus.SUCCESS
    assert result.success is True
    assert response.context is not None
    degraded = response.context.decisions.get("degraded_tasks", {})
    assert "draft_documents" in degraded
