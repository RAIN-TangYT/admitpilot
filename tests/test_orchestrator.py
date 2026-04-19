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


def test_orchestrator_expands_strategy_for_timeline_only_query() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请给我做申请时间线",
            profile=UserProfile(major_interest="Computer Science"),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    agents = [result.agent for result in response.results]
    assert agents == ["aie", "sae", "dta"]
    assert all(result.status == TaskStatus.SUCCESS for result in response.results)
    assert response.context is not None
    assert not response.context.decisions.get("degraded_tasks")


def test_orchestrator_expands_full_chain_for_documents_only_query() -> None:
    orchestrator = PrincipalApplicationOrchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请帮我准备文书",
            profile=UserProfile(major_interest="Computer Science"),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    agents = [result.agent for result in response.results]
    assert agents == ["aie", "sae", "dta", "cds"]
    assert all(result.status == TaskStatus.SUCCESS for result in response.results)
    assert response.context is not None
    assert not response.context.decisions.get("degraded_tasks")


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
    assert result.output["document_drafts"] == []
    assert "缺少上游" in result.output["consistency_issues"][0]["message"]
    assert "申请动机与长期职业目标一致" not in str(result.output)
    assert "关键里程碑数量=0" not in str(result.output)
    assert response.context is not None
    degraded = response.context.decisions.get("degraded_tasks", {})
    assert "draft_documents" in degraded
