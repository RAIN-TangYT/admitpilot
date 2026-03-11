from admitpilot.core.schemas import AgentTask, UserProfile
from admitpilot.pao.contracts import OrchestrationRequest
from admitpilot.pao.orchestrator import PrincipalApplicationOrchestrator
from admitpilot.pao.schemas import RoutePlan


class UnknownAgentRouter:
    def build_plan(self, query: str) -> RoutePlan:
        return RoutePlan(
            intent="unknown_agent_test",
            tasks=[AgentTask(name="x", description="x", agent="ghost")],
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
    orchestrator.router = UnknownAgentRouter()
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
