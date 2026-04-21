"""PAO 主编排器与 LangGraph 流程定义。"""

from __future__ import annotations

import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional, cast
from uuid import uuid4

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
    AgentResult,
    AgentTask,
    AIEAgentOutput,
    ApplicationContext,
    CDSAgentOutput,
    DTAAgentOutput,
    SharedMemory,
    SAEAgentOutput,
    SharedMemory,
)
from admitpilot.pao.contracts import OrchestrationRequest, OrchestrationResponse
from admitpilot.pao.router import IntentRouter
from admitpilot.pao.schemas import PaoGraphState, RoutePlan
from admitpilot.platform import PlatformCommonBundle, build_default_platform_common_bundle
from admitpilot.platform.runtime import RuntimeStateMachine, TaskStatus, WorkflowStatus


@dataclass
class PrincipalApplicationOrchestrator:
    """PAO：统一负责意图识别、路由、上下文与结果聚合。"""

    router: IntentRouter = field(default_factory=IntentRouter)
    agents: dict[str, BaseAgent] = field(default_factory=dict)
    platform_bundle: Optional[PlatformCommonBundle] = None
    _graph: Any = field(init=False, repr=False)
    _workflow_state_machine: RuntimeStateMachine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """完成默认代理注入与图编译。"""
        if not self.agents:
            self.agents = self._build_default_agents()
        if self.platform_bundle is None:
            self.platform_bundle = build_default_platform_common_bundle()
        self._workflow_state_machine = RuntimeStateMachine()
        self._graph = self._build_graph()

    def _build_default_agents(self) -> dict[str, BaseAgent]:
        """构建系统默认代理实例。"""
        return {
            "aie": AIEAgent(service=AdmissionsIntelligenceService()),
            "sae": SAEAgent(service=StrategicAdmissionsService()),
            "dta": DTAAgent(service=DynamicTimelineService()),
            "cds": CDSAgent(service=CoreDocumentService()),
        }

    def _build_graph(self) -> Any:
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
        trace_id = f"trace-{uuid4().hex}"
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.start_span(
                name="pao.invoke",
                trace_id=trace_id,
                attrs={"query": request.user_query},
            )
            self.platform_bundle.metrics_collector.inc("workflow_invocations_total")
        context = ApplicationContext(
            user_query=request.user_query,
            profile=request.profile,
            constraints=request.constraints,
            shared_memory=cast(SharedMemory, {}),
            decisions={"trace_id": trace_id, "events": []},
        )
        initial_state: PaoGraphState = {
            "query": request.user_query,
            "context": context,
            "workflow_status": WorkflowStatus.NEW,
            "route_plan": RoutePlan(intent="", tasks=[], rationale=""),
            "pending_tasks": [],
            "current_task": None,
            "results": [],
            "final_summary": "",
        }
        state = self._graph.invoke(initial_state)
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.end_span(
                name="pao.invoke",
                trace_id=trace_id,
                attrs={"workflow_status": state["workflow_status"].value},
            )
        return OrchestrationResponse(
            summary=state["final_summary"],
            results=state["results"],
            context=state["context"],
        )

    def _intake_node(self, state: PaoGraphState) -> PaoGraphState:
        """初始化编排状态。"""
        next_status = self._workflow_state_machine.transition(
            current=state["workflow_status"],
            target=WorkflowStatus.INTENT_PARSED,
        )
        return {**state, "workflow_status": next_status}

    def _route_node(self, state: PaoGraphState) -> PaoGraphState:
        """识别意图并构建任务计划。"""
        plan = self.router.build_plan(state["query"])
        next_status = self._workflow_state_machine.transition(
            current=state["workflow_status"],
            target=WorkflowStatus.PLAN_BUILT,
        )
        return {
            **state,
            "workflow_status": next_status,
            "route_plan": plan,
            "pending_tasks": list(plan.tasks),
        }

    def _dispatch_node(self, state: PaoGraphState) -> PaoGraphState:
        """执行单个任务并回写上下文。"""
        pending_tasks = list(state["pending_tasks"])
        task = pending_tasks.pop(0)
        context = self._clone_context(state["context"])
        trace_id = str(context.decisions.get("trace_id", "trace-unknown"))
        workflow_status = state["workflow_status"]
        if workflow_status == WorkflowStatus.PLAN_BUILT:
            workflow_status = self._workflow_state_machine.transition(
                current=workflow_status,
                target=WorkflowStatus.EXECUTING,
            )
        blockers = self._resolve_blockers(
            task=task, context=context, prior_results=state["results"]
        )
        if blockers and task.can_degrade:
            degraded = context.decisions.setdefault("degraded_tasks", {})
            degraded[task.name] = blockers
        if blockers and not task.can_degrade:
            result = self._build_skipped_result(
                task=task,
                agent_name=task.agent,
                reason="dependency_blocked",
                blocked_by=blockers,
            )
            self._write_shared_memory(context=context, result=result)
            results = [*state["results"], result]
            return {
                **state,
                "workflow_status": workflow_status,
                "pending_tasks": pending_tasks,
                "current_task": task,
                "results": results,
                "context": context,
            }
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.start_span(
                name=f"agent.{task.agent}.run",
                trace_id=trace_id,
                attrs={"task": task.name},
            )
            self.platform_bundle.metrics_collector.inc("task_dispatch_total")
            self.platform_bundle.governance_engine.audit(
                event="task_dispatched",
                details={"agent": task.agent, "task": task.name, "trace_id": trace_id},
            )
        agent = self.agents.get(task.agent)
        if agent is None:
            result = self._build_failed_result(
                task=task,
                agent_name=task.agent,
                reason="agent_not_registered",
                message=f"未注册代理: {task.agent}",
            )
        else:
            if self.platform_bundle is not None:
                if not self.platform_bundle.capability_manager.allowed_agent(task.agent):
                    result = self._build_failed_result(
                        task=task,
                        agent_name=task.agent,
                        reason="capability_denied",
                        message=f"agent {task.agent} not allowed by policy",
                    )
                    results = [*state["results"], result]
                    self.platform_bundle.trace_collector.end_span(
                        name=f"agent.{task.agent}.run",
                        trace_id=trace_id,
                        attrs={"status": result.status.value},
                    )
                    return {
                        **state,
                        "workflow_status": workflow_status,
                        "pending_tasks": pending_tasks,
                        "current_task": task,
                        "results": results,
                        "context": context,
                    }
                token = self.platform_bundle.capability_manager.issue(
                    principal=task.agent, scopes={"execute"}
                )
                if not self.platform_bundle.capability_manager.validate(
                    token=token, required_scope="execute"
                ):
                    result = self._build_failed_result(
                        task=task,
                        agent_name=task.agent,
                        reason="capability_denied",
                        message=f"token rejected for agent {task.agent}",
                    )
                    results = [*state["results"], result]
                    self.platform_bundle.trace_collector.end_span(
                        name=f"agent.{task.agent}.run",
                        trace_id=trace_id,
                        attrs={"status": result.status.value},
                    )
                    return {
                        **state,
                        "workflow_status": workflow_status,
                        "pending_tasks": pending_tasks,
                        "current_task": task,
                        "results": results,
                        "context": context,
                    }
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
        if self.platform_bundle is not None:
            output_text = str(result.output)
            allowed, policy_reason = self.platform_bundle.governance_engine.policy_validate(output_text)
            if not allowed:
                result = self._build_failed_result(
                    task=task,
                    agent_name=task.agent,
                    reason="policy_blocked",
                    message=policy_reason,
                )
        self._write_shared_memory(context=context, result=result)
        results = [*state["results"], result]
        if self.platform_bundle is not None:
            self.platform_bundle.metrics_collector.inc(
                f"task_status_{result.status.value.lower()}_total"
            )
            self.platform_bundle.trace_collector.end_span(
                name=f"agent.{task.agent}.run",
                trace_id=trace_id,
                attrs={"status": result.status.value, "task": task.name},
            )
        return {
            **state,
            "workflow_status": workflow_status,
            "pending_tasks": pending_tasks,
            "current_task": task,
            "results": results,
            "context": context,
        }

    def _aggregate_node(self, state: PaoGraphState) -> PaoGraphState:
        """聚合多代理结果并输出最终摘要。"""
        workflow_status = state["workflow_status"]
        if workflow_status == WorkflowStatus.PLAN_BUILT:
            workflow_status = self._workflow_state_machine.transition(
                current=workflow_status,
                target=WorkflowStatus.EXECUTING,
            )
        if workflow_status == WorkflowStatus.EXECUTING:
            workflow_status = self._workflow_state_machine.transition(
                current=workflow_status,
                target=WorkflowStatus.AGGREGATING,
            )
        success_count = sum(1 for item in state["results"] if item.status == TaskStatus.SUCCESS)
        failed_count = sum(1 for item in state["results"] if item.status == TaskStatus.FAILED)
        skipped_count = sum(1 for item in state["results"] if item.status == TaskStatus.SKIPPED)
        final_target = WorkflowStatus.DELIVERED
        if failed_count > 0 or skipped_count > 0:
            final_target = WorkflowStatus.PARTIAL_DELIVERED
        final_status = self._workflow_state_machine.transition(
            current=workflow_status,
            target=final_target,
        )
        parts = [
            (
                f"PAO已处理 {len(state['results'])} 个代理任务，"
                f"success={success_count} failed={failed_count} skipped={skipped_count} "
                f"workflow={final_status.value}。"
            )
        ]
        for item in state["results"]:
            detail = (
                f"[{item.agent.upper()}] {item.task}: "
                f"status={item.status} confidence={item.confidence:.2f}"
            )
            parts.append(detail)
        return {
            **state,
            "workflow_status": final_status,
            "final_summary": " ".join(parts),
        }

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
            shared_memory=cast(SharedMemory, deepcopy(dict(context.shared_memory))),
            decisions=cast(dict[str, Any], deepcopy(dict(context.decisions))),
        )

    def _resolve_blockers(
        self, task: AgentTask, context: ApplicationContext, prior_results: list[AgentResult]
    ) -> list[str]:
        """检查任务依赖与共享内存依赖是否满足。"""
        results_by_task = {item.task: item for item in prior_results}
        blockers: list[str] = []
        for dependency in task.depends_on:
            if dependency not in results_by_task:
                blockers.append(f"missing_task:{dependency}")
                continue
            dependency_result = results_by_task[dependency]
            if dependency_result.status != TaskStatus.SUCCESS:
                blockers.append(f"failed_task:{dependency}")
        for memory_key in task.required_memory:
            if memory_key not in context.shared_memory:
                blockers.append(f"missing_memory:{memory_key}")
        return blockers

    def _build_skipped_result(
        self,
        task: AgentTask,
        agent_name: str,
        reason: str,
        blocked_by: list[str],
    ) -> AgentResult:
        """生成被依赖阻塞的任务结果。"""
        return AgentResult(
            agent=agent_name,
            task=task.name,
            success=False,
            status=TaskStatus.SKIPPED,
            output={"error": reason, "message": "依赖未满足，任务被跳过"},
            confidence=0.0,
            trace=[f"{agent_name}:{task.name}:{reason}"],
            blocked_by=blocked_by,
        )

    def _resolve_blockers(
        self, task: AgentTask, context: ApplicationContext, prior_results: list[AgentResult]
    ) -> list[str]:
        """检查任务依赖与共享内存依赖是否满足。"""
        results_by_task = {item.task: item for item in prior_results}
        blockers: list[str] = []
        for dependency in task.depends_on:
            if dependency not in results_by_task:
                blockers.append(f"missing_task:{dependency}")
                continue
            dependency_result = results_by_task[dependency]
            if dependency_result.status != TaskStatus.SUCCESS:
                blockers.append(f"failed_task:{dependency}")
        for memory_key in task.required_memory:
            if memory_key not in context.shared_memory:
                blockers.append(f"missing_memory:{memory_key}")
        return blockers

    def _build_failed_result(
        self,
        task: AgentTask,
        agent_name: str,
        reason: str,
        message: str,
        trace: Optional[list[str]] = None,
    ) -> AgentResult:
        """生成失败任务结果。"""
        return AgentResult(
            agent=agent_name,
            task=task.name,
            success=False,
            status=TaskStatus.FAILED,
            output={"error": reason, "message": message},
            confidence=0.0,
            trace=trace or [f"{agent_name}:{task.name}:{reason}:{message}"],
        )

    def _build_skipped_result(
        self,
        task: AgentTask,
        agent_name: str,
        reason: str,
        blocked_by: list[str],
    ) -> AgentResult:
        """生成被依赖阻塞的任务结果。"""
        return AgentResult(
            agent=agent_name,
            task=task.name,
            success=False,
            status=TaskStatus.SKIPPED,
            output={"error": reason, "message": "依赖未满足，任务被跳过"},
            confidence=0.0,
            trace=[f"{agent_name}:{task.name}:{reason}"],
            blocked_by=blocked_by,
        )

    def _write_shared_memory(self, context: ApplicationContext, result: AgentResult) -> None:
        """按契约回写共享内存。"""
        if result.status != TaskStatus.SUCCESS:
            return
        key = ""
        if result.agent == "aie":
            key = "aie"
            context.shared_memory["aie"] = cast(AIEAgentOutput, result.output)
            self._append_event(context=context, event="official_snapshot_updated")
        elif result.agent == "sae":
            key = "sae"
            context.shared_memory["sae"] = cast(SAEAgentOutput, result.output)
            self._append_event(context=context, event="strategy_recomputed")
        elif result.agent == "dta":
            key = "dta"
            context.shared_memory["dta"] = cast(DTAAgentOutput, result.output)
            self._append_event(context=context, event="timeline_replanned")
        elif result.agent == "cds":
            key = "cds"
            context.shared_memory["cds"] = cast(CDSAgentOutput, result.output)
            self._append_event(context=context, event="artifact_review_required")
        if self.platform_bundle is None or not key:
            return
        namespace = self._memory_namespace(context)
        lineage = [f"{result.agent}:{result.task}"]
        self.platform_bundle.session_memory.put(
            namespace=namespace,
            key=key,
            value=cast(dict[str, Any], result.output),
            source=result.agent,
            confidence=result.confidence,
            evidence_level=result.evidence_level,
            lineage=lineage,
        )
        self.platform_bundle.versioned_memory.append(
            namespace=namespace,
            key=key,
            value=cast(dict[str, Any], result.output),
            source=result.agent,
            confidence=result.confidence,
            evidence_level=result.evidence_level,
            lineage=lineage,
        )
        if key == "cds":
            self.platform_bundle.artifact_store.put(
                namespace=namespace,
                object_id=f"{result.task}:{len(lineage)}",
                payload=cast(dict[str, Any], result.output),
            )
        self.platform_bundle.governance_engine.audit(
            event="memory_write",
            details={
                "namespace": namespace,
                "key": key,
                "agent": result.agent,
                "task": result.task,
            },
        )

    def _memory_namespace(self, context: ApplicationContext) -> str:
        """Build namespace to isolate memory by applicant and cycle."""
        cycle = str(context.constraints.get("cycle", "unknown"))
        applicant = context.profile.name.strip() or "anonymous"
        return f"application:{cycle}:{applicant}"

    def _append_event(self, context: ApplicationContext, event: str) -> None:
        """Append orchestrator domain events into context decisions."""
        events = context.decisions.setdefault("events", [])
        if isinstance(events, list):
            events.append(event)
