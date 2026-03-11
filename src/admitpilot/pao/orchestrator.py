"""PAO 主编排器与 LangGraph 流程定义。"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Callable, cast

from langgraph.graph import END, START, StateGraph

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.agents.base import BaseAgent
from admitpilot.agents.cds.agent import CDSAgent
from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.agents.dta.agent import DTAAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.agents.sae.agent import SAEAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import (
    AIEAgentOutput,
    AgentTask,
    AgentResult,
    ApplicationContext,
    CDSAgentOutput,
    DTAAgentOutput,
    SAEAgentOutput,
)
from admitpilot.pao.contracts import OrchestrationRequest, OrchestrationResponse
from admitpilot.pao.router import IntentRouter
from admitpilot.pao.schemas import PaoGraphState, RoutePlan


@dataclass(slots=True)
class PrincipalApplicationOrchestrator:
    """PAO：统一负责意图识别、路由、上下文与结果聚合。"""

    router: IntentRouter = field(default_factory=IntentRouter)
    agents: dict[str, BaseAgent] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """完成默认代理注入与图编译。"""
        if not self.agents:
            self.agents = self._build_default_agents()
        self._graph = self._build_graph()

    def _build_default_agents(self) -> dict[str, BaseAgent]:
        """构建系统默认代理实例。"""
        return {
            "aie": AIEAgent(service=AdmissionsIntelligenceService()),
            "sae": SAEAgent(service=StrategicAdmissionsService()),
            "dta": DTAAgent(service=DynamicTimelineService()),
            "cds": CDSAgent(service=CoreDocumentService()),
        }

    def _build_graph(self) -> Callable[[PaoGraphState], PaoGraphState]:
        """定义并编译 LangGraph 执行图。"""
        graph = StateGraph(PaoGraphState)
        graph.add_node("intake", self._intake_node)
        graph.add_node("route", self._route_node)
        graph.add_node("dispatch", self._dispatch_node)
        graph.add_node("aggregate", self._aggregate_node)
        graph.add_edge(START, "intake")
        graph.add_edge("intake", "route")
        graph.add_conditional_edges(
            "route",
            self._route_decision,
            {"dispatch": "dispatch", "aggregate": "aggregate"},
        )
        graph.add_conditional_edges(
            "dispatch",
            self._dispatch_decision,
            {"dispatch": "dispatch", "aggregate": "aggregate"},
        )
        graph.add_edge("aggregate", END)
        return graph.compile()

    def invoke(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """执行完整编排流程并返回统一响应。"""
        context = ApplicationContext(
            user_query=request.user_query,
            profile=request.profile,
            constraints=request.constraints,
            shared_memory={},
        )
        initial_state: PaoGraphState = {
            "query": request.user_query,
            "context": context,
            "route_plan": RoutePlan(intent="", tasks=[], rationale=""),
            "pending_tasks": [],
            "current_task": None,
            "results": [],
            "final_summary": "",
        }
        state = self._graph.invoke(initial_state)
        return OrchestrationResponse(
            summary=state["final_summary"],
            results=state["results"],
            context=state["context"],
        )

    def _intake_node(self, state: PaoGraphState) -> PaoGraphState:
        """初始化编排状态。"""
        return {**state}

    def _route_node(self, state: PaoGraphState) -> PaoGraphState:
        """识别意图并构建任务计划。"""
        plan = self.router.build_plan(state["query"])
        return {**state, "route_plan": plan, "pending_tasks": list(plan.tasks)}

    def _dispatch_node(self, state: PaoGraphState) -> PaoGraphState:
        """执行单个任务并回写上下文。"""
        pending_tasks = list(state["pending_tasks"])
        task = pending_tasks.pop(0)
        context = self._clone_context(state["context"])
        agent = self.agents.get(task.agent)
        if agent is None:
            result = self._build_failed_result(
                task=task,
                agent_name=task.agent,
                reason="agent_not_registered",
                message=f"未注册代理: {task.agent}",
            )
        else:
            try:
                result = agent.run(task=task, context=context)
            except Exception as exc:
                result = self._build_failed_result(
                    task=task,
                    agent_name=task.agent,
                    reason="agent_execution_error",
                    message=str(exc),
                    trace=traceback.format_exc().splitlines(),
                )
        self._write_shared_memory(context=context, result=result)
        results = [*state["results"], result]
        return {
            **state,
            "pending_tasks": pending_tasks,
            "current_task": task,
            "results": results,
            "context": context,
        }

    def _aggregate_node(self, state: PaoGraphState) -> PaoGraphState:
        """聚合多代理结果并输出最终摘要。"""
        parts = [f"PAO已完成 {len(state['results'])} 个代理任务。"]
        for item in state["results"]:
            parts.append(f"[{item.agent.upper()}] {item.task}: confidence={item.confidence:.2f}")
        return {**state, "final_summary": " ".join(parts)}

    def _route_decision(self, state: PaoGraphState) -> str:
        """根据路由结果决定下一节点。"""
        return "dispatch" if state["pending_tasks"] else "aggregate"

    def _dispatch_decision(self, state: PaoGraphState) -> str:
        """根据剩余任务决定循环或收敛。"""
        return "dispatch" if state["pending_tasks"] else "aggregate"

    def _clone_context(self, context: ApplicationContext) -> ApplicationContext:
        """构建上下文副本，避免原地写入状态。"""
        return ApplicationContext(
            user_query=context.user_query,
            profile=context.profile,
            constraints=dict(context.constraints),
            shared_memory=cast(dict, dict(context.shared_memory)),
        )

    def _build_failed_result(
        self,
        task: AgentTask,
        agent_name: str,
        reason: str,
        message: str,
        trace: list[str] | None = None,
    ) -> AgentResult:
        """生成失败任务结果。"""
        return AgentResult(
            agent=agent_name,
            task=task.name,
            success=False,
            output={"error": reason, "message": message},
            confidence=0.0,
            trace=trace or [f"{agent_name}:{task.name}:{reason}:{message}"],
        )

    def _write_shared_memory(self, context: ApplicationContext, result: AgentResult) -> None:
        """按契约回写共享内存。"""
        if not result.success:
            return
        if result.agent == "aie":
            context.shared_memory["aie"] = cast(AIEAgentOutput, result.output)
        elif result.agent == "sae":
            context.shared_memory["sae"] = cast(SAEAgentOutput, result.output)
        elif result.agent == "dta":
            context.shared_memory["dta"] = cast(DTAAgentOutput, result.output)
        elif result.agent == "cds":
            context.shared_memory["cds"] = cast(CDSAgentOutput, result.output)
