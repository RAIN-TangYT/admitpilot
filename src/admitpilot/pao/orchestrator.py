"""PAO orchestrator and graph execution."""

from __future__ import annotations

import re
import traceback
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any, cast
from uuid import uuid4

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.runtime import build_runtime_aie_service
from admitpilot.agents.base import BaseAgent
from admitpilot.agents.cds.agent import CDSAgent
from admitpilot.agents.cds.service import CoreDocumentService
from admitpilot.agents.dta.agent import DTAAgent
from admitpilot.agents.dta.service import DynamicTimelineService
from admitpilot.agents.sae.agent import SAEAgent
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.config import AdmitPilotSettings, load_settings
from admitpilot.core.english import contains_cjk, english_items, english_or
from admitpilot.core.schemas import (
    AgentResult,
    AgentTask,
    AIEAgentOutput,
    ApplicationContext,
    CDSAgentOutput,
    DTAAgentOutput,
    SAEAgentOutput,
    SharedMemory,
    UserProfile,
)
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG
from admitpilot.pao.contracts import (
    OrchestrationEvent,
    OrchestrationRequest,
    OrchestrationResponse,
)
from admitpilot.pao.router import IntentRouter
from admitpilot.pao.schemas import PaoGraphState, RoutePlan
from admitpilot.platform import PlatformCommonBundle, build_default_platform_common_bundle
from admitpilot.platform.llm.openai import OpenAIClient
from admitpilot.platform.runtime import RuntimeStateMachine, TaskStatus, WorkflowStatus

ImportedStateGraph: Any = None

try:
    from langgraph.graph import END, START
    from langgraph.graph import StateGraph as _ImportedStateGraph
except ModuleNotFoundError:
    START = "__start__"
    END = "__end__"

    class _CompiledStateGraph:
        def __init__(
            self,
            nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
            edges: dict[str, str],
            conditional_edges: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]],
        ) -> None:
            self._nodes = nodes
            self._edges = edges
            self._conditional_edges = conditional_edges

        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            current = self._edges[START]
            current_state = state
            while current != END:
                current_state = self._nodes[current](current_state)
                if current in self._conditional_edges:
                    decider, mapping = self._conditional_edges[current]
                    current = mapping[decider(current_state)]
                else:
                    current = self._edges[current]
            return current_state

    class FallbackStateGraph:
        def __init__(self, _state_type: Any) -> None:
            self._nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
            self._edges: dict[str, str] = {}
            self._conditional_edges: dict[
                str,
                tuple[Callable[[dict[str, Any]], str], dict[str, str]],
            ] = {}

        def add_node(self, name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
            self._nodes[name] = fn

        def add_edge(self, source: str, target: str) -> None:
            self._edges[source] = target

        def add_conditional_edges(
            self,
            source: str,
            decider: Callable[[dict[str, Any]], str],
            mapping: dict[str, str],
        ) -> None:
            self._conditional_edges[source] = (decider, mapping)

        def compile(self) -> _CompiledStateGraph:
            return _CompiledStateGraph(self._nodes, self._edges, self._conditional_edges)
else:
    ImportedStateGraph = _ImportedStateGraph


def _new_state_graph(state_type: Any) -> Any:
    if ImportedStateGraph is not None:
        return ImportedStateGraph(state_type)
    return FallbackStateGraph(state_type)


@dataclass
class PrincipalApplicationOrchestrator:
    """PAO: route, dispatch, aggregate, and persist shared context."""

    router: IntentRouter = field(default_factory=IntentRouter)
    agents: dict[str, BaseAgent] = field(default_factory=dict)
    platform_bundle: PlatformCommonBundle | None = None
    settings: AdmitPilotSettings | None = None
    _graph: Any = field(init=False, repr=False)
    _workflow_state_machine: RuntimeStateMachine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = load_settings()
        if not self.agents:
            self.agents = self._build_default_agents(self.settings)
        if self.platform_bundle is None:
            self.platform_bundle = build_default_platform_common_bundle(settings=self.settings)
        self._workflow_state_machine = RuntimeStateMachine()
        self._graph = self._build_graph()

    def _build_default_agents(self, settings: AdmitPilotSettings) -> dict[str, BaseAgent]:
        llm_client = OpenAIClient(settings=settings)
        return {
            "aie": AIEAgent(
                service=build_runtime_aie_service(
                    settings=settings,
                    llm_client=llm_client,
                )
            ),
            "sae": SAEAgent(
                service=StrategicAdmissionsService(
                    llm_client=llm_client,
                    settings=settings,
                )
            ),
            "dta": DTAAgent(service=DynamicTimelineService(llm_client=llm_client)),
            "cds": CDSAgent(service=CoreDocumentService(llm_client=llm_client)),
        }

    def _build_graph(self) -> Any:
        graph = _new_state_graph(PaoGraphState)
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
        trace_id = f"trace-{uuid4().hex}"
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.start_span(
                name="pao.invoke",
                trace_id=trace_id,
                attrs={"query": request.user_query},
            )
            self.platform_bundle.metrics_collector.inc("workflow_invocations_total")
        initial_state = self._build_initial_state(request=request, trace_id=trace_id)
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

    def stream(self, request: OrchestrationRequest) -> Iterator[OrchestrationEvent]:
        """Run PAO and emit backend stage events after each real agent execution."""

        trace_id = f"trace-{uuid4().hex}"
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.start_span(
                name="pao.stream",
                trace_id=trace_id,
                attrs={"query": request.user_query},
            )
            self.platform_bundle.metrics_collector.inc("workflow_invocations_total")
        state = self._build_initial_state(request=request, trace_id=trace_id)
        state = self._intake_node(state)
        state = self._route_node(state)
        yield OrchestrationEvent(
            event="workflow_started",
            data={
                "trace_id": trace_id,
                "stages": [
                    {"agent": task.agent, "task": task.name}
                    for task in state["pending_tasks"]
                ],
            },
        )
        while state["pending_tasks"]:
            task = state["pending_tasks"][0]
            yield OrchestrationEvent(
                event="stage_started",
                data={"trace_id": trace_id, "agent": task.agent, "task": task.name},
            )
            state = self._dispatch_node(state)
            result = state["results"][-1]
            yield OrchestrationEvent(
                event="stage_completed",
                data={
                    "trace_id": trace_id,
                    "agent": result.agent,
                    "task": result.task,
                    "status": result.status.value,
                    "success": result.success,
                    "result": result,
                },
            )
        state = self._aggregate_node(state)
        if self.platform_bundle is not None:
            self.platform_bundle.trace_collector.end_span(
                name="pao.stream",
                trace_id=trace_id,
                attrs={"workflow_status": state["workflow_status"].value},
            )
        yield OrchestrationEvent(
            event="workflow_completed",
            data={
                "trace_id": trace_id,
                "response": OrchestrationResponse(
                    summary=state["final_summary"],
                    results=state["results"],
                    context=state["context"],
                ),
            },
        )

    def _build_initial_state(
        self, *, request: OrchestrationRequest, trace_id: str
    ) -> PaoGraphState:
        context = ApplicationContext(
            user_query=self._build_agent_user_query(
                query=request.user_query,
                plan=RoutePlan(intent="", tasks=[], rationale=""),
            ),
            profile=self._english_profile(request.profile),
            constraints=self._english_context_value(request.constraints),
            shared_memory=cast(SharedMemory, {}),
            decisions={"trace_id": trace_id, "events": []},
        )
        return {
            "query": request.user_query,
            "context": context,
            "workflow_status": WorkflowStatus.NEW,
            "route_plan": RoutePlan(intent="", tasks=[], rationale=""),
            "pending_tasks": [],
            "current_task": None,
            "results": [],
            "final_summary": "",
        }

    def _intake_node(self, state: PaoGraphState) -> PaoGraphState:
        next_status = self._workflow_state_machine.transition(
            current=state["workflow_status"],
            target=WorkflowStatus.INTENT_PARSED,
        )
        return {**state, "workflow_status": next_status}

    def _route_node(self, state: PaoGraphState) -> PaoGraphState:
        plan = self._prepare_agent_plan(
            plan=self.router.build_plan(state["query"]),
            query=state["query"],
        )
        context = self._clone_context(state["context"])
        context.user_query = self._build_agent_user_query(
            query=state["query"],
            plan=plan,
        )
        next_status = self._workflow_state_machine.transition(
            current=state["workflow_status"],
            target=WorkflowStatus.PLAN_BUILT,
        )
        return {
            **state,
            "workflow_status": next_status,
            "route_plan": plan,
            "pending_tasks": list(plan.tasks),
            "context": context,
        }

    def _dispatch_node(self, state: PaoGraphState) -> PaoGraphState:
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
            task=task,
            context=context,
            prior_results=state["results"],
        )
        profile_incomplete_block = self._should_skip_degrade_for_profile(
            task=task,
            blockers=blockers,
            prior_results=state["results"],
        )
        if blockers and task.can_degrade and not profile_incomplete_block:
            degraded = context.decisions.setdefault("degraded_tasks", {})
            degraded[task.name] = blockers
        if blockers and (not task.can_degrade or profile_incomplete_block):
            result = self._build_skipped_result(
                task=task,
                agent_name=task.agent,
                reason="dependency_blocked",
                blocked_by=blockers,
            )
            self._write_shared_memory(context=context, result=result)
            return {
                **state,
                "workflow_status": workflow_status,
                "pending_tasks": pending_tasks,
                "current_task": task,
                "results": [*state["results"], result],
                "context": context,
            }
        agent = self.agents.get(task.agent)
        if agent is None:
            result = self._build_failed_result(
                task=task,
                agent_name=task.agent,
                reason="agent_not_registered",
                message=f"Agent is not registered: {task.agent}",
            )
            if self.platform_bundle is not None:
                self.platform_bundle.trace_collector.start_span(
                    name=f"agent.{task.agent}.run",
                    trace_id=trace_id,
                    attrs={"task": task.name},
                )
                self.platform_bundle.metrics_collector.inc("task_dispatch_total")
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
                "results": [*state["results"], result],
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
            if not self.platform_bundle.capability_manager.allowed_agent(task.agent):
                result = self._build_failed_result(
                    task=task,
                    agent_name=task.agent,
                    reason="capability_denied",
                    message=f"agent {task.agent} not allowed by policy",
                )
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
                    "results": [*state["results"], result],
                    "context": context,
                }
            token = self.platform_bundle.capability_manager.issue(
                principal=task.agent,
                scopes={"execute"},
            )
            if not self.platform_bundle.capability_manager.validate(
                token=token,
                required_scope="execute",
            ):
                result = self._build_failed_result(
                    task=task,
                    agent_name=task.agent,
                    reason="capability_denied",
                    message=f"token rejected for agent {task.agent}",
                )
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
                    "results": [*state["results"], result],
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
            allowed, policy_reason = self.platform_bundle.governance_engine.policy_validate(
                str(result.output)
            )
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
        final_summary = self._build_final_summary(
            state=state,
            workflow_status=final_status.value,
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )
        return {**state, "workflow_status": final_status, "final_summary": final_summary}

    def _route_decision(self, state: PaoGraphState) -> str:
        return "dispatch" if state["pending_tasks"] else "aggregate"

    def _dispatch_decision(self, state: PaoGraphState) -> str:
        return "dispatch" if state["pending_tasks"] else "aggregate"

    def _clone_context(self, context: ApplicationContext) -> ApplicationContext:
        return ApplicationContext(
            user_query=english_or(context.user_query, "Application planning request."),
            profile=self._english_profile(context.profile),
            constraints=self._english_context_value(context.constraints),
            shared_memory=cast(SharedMemory, deepcopy(dict(context.shared_memory))),
            decisions=deepcopy(dict(context.decisions)),
        )

    def _prepare_agent_plan(self, plan: RoutePlan, query: str) -> RoutePlan:
        query_targets = self._extract_query_targets(query)
        tasks: list[AgentTask] = []
        for task in plan.tasks:
            if task.agent != "aie":
                tasks.append(task)
                continue
            payload = dict(task.payload)
            if schools := query_targets.get("target_schools"):
                payload.setdefault("target_schools", schools)
            if program_by_school := query_targets.get("target_program_by_school"):
                payload.setdefault("target_program_by_school", program_by_school)
            if unsupported := query_targets.get("unsupported_program_by_school"):
                payload.setdefault("unsupported_program_by_school", unsupported)
            tasks.append(replace(task, payload=payload))
        return RoutePlan(intent=plan.intent, tasks=tasks, rationale=plan.rationale)

    def _build_agent_user_query(self, query: str, plan: RoutePlan) -> str:
        english_query = english_or(query)
        if english_query:
            return english_query
        query_targets = self._extract_query_targets(query)
        parts = ["Application planning request."]
        if plan.rationale:
            parts.append(plan.rationale)
        if plan.tasks:
            task_names = ", ".join(task.name for task in plan.tasks)
            parts.append(f"Requested agent tasks: {task_names}.")
        if schools := query_targets.get("target_schools"):
            parts.append(f"Target schools mentioned by the user: {', '.join(schools)}.")
        if program_by_school := query_targets.get("target_program_by_school"):
            program_parts = [
                f"{school}/{program}" for school, program in program_by_school.items()
            ]
            parts.append(f"Target programs mentioned by the user: {', '.join(program_parts)}.")
        if unsupported := query_targets.get("unsupported_program_by_school"):
            unsupported_parts = [
                f"{school}/{program}" for school, program in unsupported.items()
            ]
            parts.append(f"Unsupported program hints: {', '.join(unsupported_parts)}.")
        return " ".join(parts)

    def _extract_query_targets(self, query: str) -> dict[str, Any]:
        catalog = DEFAULT_ADMISSIONS_CATALOG
        schools = catalog.extract_school_codes_from_text(query)
        program_by_school: dict[str, str] = {}
        unsupported_program_by_school: dict[str, str] = {}
        query_mentions_program = catalog.has_program_intent(query)
        program_hint = english_or(catalog.extract_program_hint(query), "unsupported_program")
        for school in schools:
            query_programs = catalog.extract_program_codes_from_text(
                query,
                school_code=school,
            )
            if query_programs:
                program_by_school[school] = query_programs[0]
                continue
            if query_mentions_program:
                unsupported_program_by_school[school] = program_hint
        return {
            "target_schools": schools,
            "target_program_by_school": program_by_school,
            "unsupported_program_by_school": unsupported_program_by_school,
        }

    def _english_profile(self, profile: UserProfile) -> UserProfile:
        return UserProfile(
            name=english_or(profile.name),
            degree_level=english_or(profile.degree_level),
            major_interest=english_or(profile.major_interest),
            target_regions=english_items(profile.target_regions),
            academic_metrics=self._english_context_value(profile.academic_metrics),
            language_scores=self._english_context_value(profile.language_scores),
            experiences=english_items(profile.experiences),
            target_schools=self._normalize_profile_schools(profile.target_schools),
            target_programs=self._normalize_profile_programs(profile.target_programs),
            risk_preference=english_or(profile.risk_preference, "balanced"),
        )

    def _normalize_profile_schools(self, schools: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in schools:
            code = DEFAULT_ADMISSIONS_CATALOG.normalize_school_code(str(item))
            if code is None or code in seen:
                continue
            normalized.append(code)
            seen.add(code)
        return normalized

    def _normalize_profile_programs(self, programs: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in programs:
            code = DEFAULT_ADMISSIONS_CATALOG.normalize_program_code(str(item))
            text = code or english_or(item)
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized

    def _english_context_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return english_or(value)
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for raw_key, raw_value in value.items():
                key = english_or(raw_key)
                if not key:
                    continue
                sanitized[key] = self._english_context_value(raw_value)
            return sanitized
        if isinstance(value, list):
            sanitized_list = [
                sanitized
                for item in value
                if (sanitized := self._english_context_value(item)) not in ("", [], {})
            ]
            return sanitized_list
        if isinstance(value, tuple):
            return self._english_context_value(list(value))
        if contains_cjk(value):
            return ""
        return value

    def _resolve_blockers(
        self,
        task: AgentTask,
        context: ApplicationContext,
        prior_results: list[AgentResult],
    ) -> list[str]:
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
        if task.name == "evaluate_strategy":
            blockers.extend(self._missing_profile_blockers(context.profile))
        return blockers

    def _missing_profile_blockers(self, profile: UserProfile) -> list[str]:
        blockers: list[str] = []
        if not profile.degree_level.strip():
            blockers.append("missing_profile:degree_level")
        if not profile.major_interest.strip():
            blockers.append("missing_profile:major_interest")
        if not profile.target_schools:
            blockers.append("missing_profile:target_schools")
        if not profile.target_programs:
            blockers.append("missing_profile:target_programs")
        if not profile.experiences:
            blockers.append("missing_profile:experiences")
        if not self._is_positive_number(profile.academic_metrics.get("gpa")):
            blockers.append("missing_profile:academic_metrics.gpa")
        if not self._has_valid_language_score(profile.language_scores):
            blockers.append("missing_profile:language_scores")
        return blockers

    def _is_positive_number(self, value: Any) -> bool:
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False

    def _has_valid_language_score(self, language_scores: dict[str, Any]) -> bool:
        for key in ("ielts", "toefl", "toefl_ibt"):
            if self._is_positive_number(language_scores.get(key)):
                return True
        return False

    def _should_skip_degrade_for_profile(
        self,
        task: AgentTask,
        blockers: list[str],
        prior_results: list[AgentResult],
    ) -> bool:
        if not task.can_degrade:
            return False
        if any(item.startswith("missing_profile:") for item in blockers):
            return True
        if "failed_task:evaluate_strategy" not in blockers:
            return False
        results_by_task = {item.task: item for item in prior_results}
        sae_result = results_by_task.get("evaluate_strategy")
        if sae_result is None:
            return False
        return any(item.startswith("missing_profile:") for item in sae_result.blocked_by)

    def _build_failed_result(
        self,
        task: AgentTask,
        agent_name: str,
        reason: str,
        message: str,
        trace: list[str] | None = None,
    ) -> AgentResult:
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
        return AgentResult(
            agent=agent_name,
            task=task.name,
            success=False,
            status=TaskStatus.SKIPPED,
            output={"error": reason, "message": "Dependencies are not satisfied; task skipped."},
            confidence=0.0,
            trace=[f"{agent_name}:{task.name}:{reason}"],
            blocked_by=blocked_by,
        )

    def _write_shared_memory(self, context: ApplicationContext, result: AgentResult) -> None:
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
            value=result.output,
            source=result.agent,
            confidence=result.confidence,
            evidence_level=result.evidence_level,
            lineage=lineage,
        )
        self.platform_bundle.versioned_memory.append(
            namespace=namespace,
            key=key,
            value=result.output,
            source=result.agent,
            confidence=result.confidence,
            evidence_level=result.evidence_level,
            lineage=lineage,
        )
        if key == "cds":
            self.platform_bundle.artifact_store.put(
                namespace=namespace,
                object_id=f"{result.task}:{len(lineage)}",
                payload=result.output,
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
        cycle = str(context.constraints.get("cycle", "unknown"))
        applicant = context.profile.name.strip() or "anonymous"
        return f"application:{cycle}:{applicant}"

    def _append_event(self, context: ApplicationContext, event: str) -> None:
        events = context.decisions.setdefault("events", [])
        if isinstance(events, list):
            events.append(event)

    def _build_final_summary(
        self,
        state: PaoGraphState,
        workflow_status: str,
        success_count: int,
        failed_count: int,
        skipped_count: int,
    ) -> str:
        profile_summary = self._build_profile_completion_summary(state["results"])
        if profile_summary:
            return profile_summary
        intelligent_summary = self._build_intelligence_only_summary(state["results"])
        if intelligent_summary:
            return intelligent_summary
        parts = [
            (
                f"PAO processed {len(state['results'])} agent tasks: "
                f"success={success_count} failed={failed_count} skipped={skipped_count} "
                f"workflow={workflow_status}."
            )
        ]
        for item in state["results"]:
            parts.append(
                f"[{item.agent.upper()}] {item.task}: "
                f"status={item.status.value} confidence={item.confidence:.2f}"
            )
        return " ".join(parts)

    def _build_profile_completion_summary(self, results: list[AgentResult]) -> str:
        missing_fields = self._collect_missing_profile_fields(results)
        if not missing_fields:
            return ""
        labels = [self._profile_field_label(item) for item in missing_fields]
        return (
            "The applicant profile is incomplete, so SAE and downstream tasks are paused. "
            f"Complete these fields and retry: {', '.join(labels)}."
        )

    def _collect_missing_profile_fields(self, results: list[AgentResult]) -> list[str]:
        ordered_keys = [
            "degree_level",
            "major_interest",
            "target_schools",
            "target_programs",
            "academic_metrics.gpa",
            "language_scores",
            "experiences",
        ]
        seen: set[str] = set()
        missing: list[str] = []
        for result in results:
            for blocker in result.blocked_by:
                if not blocker.startswith("missing_profile:"):
                    continue
                key = blocker.split(":", 1)[1]
                if key in seen:
                    continue
                seen.add(key)
                missing.append(key)
        order_map = {key: idx for idx, key in enumerate(ordered_keys)}
        return sorted(missing, key=lambda item: order_map.get(item, len(order_map)))

    def _profile_field_label(self, key: str) -> str:
        labels = {
            "degree_level": "degree level",
            "major_interest": "major interest",
            "target_schools": "target schools",
            "target_programs": "target programs",
            "academic_metrics.gpa": "GPA",
            "language_scores": "language score (IELTS/TOEFL)",
            "experiences": "experience materials",
        }
        return labels.get(key, key)

    def _build_intelligence_only_summary(self, results: list[AgentResult]) -> str:
        if len(results) != 1:
            return ""
        result = results[0]
        if result.agent != "aie" or result.task != "collect_intelligence":
            return ""
        if result.status != TaskStatus.SUCCESS:
            return ""
        output = cast(AIEAgentOutput, result.output)
        cycle = str(output.get("cycle", ""))
        target_program_by_school = output.get("target_program_by_school", {})
        unsupported_program_by_school = output.get("unsupported_program_by_school", {})
        source_urls_by_school = output.get("official_source_urls_by_school", {})
        status_by_school = output.get("official_status_by_school", {})
        official_records = output.get("official_records", [])
        lines = [f"AIE official intelligence summary ({cycle} cycle)"]
        for school in output.get("target_schools", []):
            program = target_program_by_school.get(
                school,
                unsupported_program_by_school.get(school, str(output.get("target_program", ""))),
            )
            status = status_by_school.get(school, "predicted")
            lines.append(
                f"- {school} / {program}: {self._status_summary_label(status)}"
            )
            if status == "unsupported_program":
                continue
            school_records = [
                item
                for item in official_records
                if item.get("school") == school and item.get("program") == program
            ]
            merged_fields = self._merge_extracted_fields(school_records)
            if deadline := str(merged_fields.get("application_deadline", "")).strip():
                lines.append(f"  Deadline: {deadline}")
            if languages := merged_fields.get("language_requirements", []):
                if isinstance(languages, list) and languages:
                    lines.append(
                        f"  Language requirements: {', '.join(str(item) for item in languages[:4])}"
                    )
            if materials := merged_fields.get("required_materials", []):
                if isinstance(materials, list) and materials:
                    lines.append(
                        f"  Required materials: {', '.join(str(item) for item in materials[:4])}"
                    )
            if academic := str(merged_fields.get("academic_requirement", "")).strip():
                lines.append(f"  Academic requirement: {self._truncate_text(academic, limit=120)}")
            resolved_urls = self._resolve_official_source_urls(
                school_records=school_records,
                configured_urls=source_urls_by_school.get(school, {}),
            )
            for url_label, url in resolved_urls:
                if url_label == "official":
                    lines.append(f"  Official source: {url}")
                else:
                    lines.append(f"  Official source ({url_label}): {url}")
        return "\n".join(lines)

    def _merge_extracted_fields(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        ordered_records = sorted(
            records,
            key=lambda item: 0 if str(item.get("page_type", "")).lower() == "requirements" else 1,
        )
        merged: dict[str, Any] = {}
        for record in ordered_records:
            raw_fields = record.get("extracted_fields", {})
            if not isinstance(raw_fields, dict):
                continue
            for key, value in raw_fields.items():
                if value in ("", [], None):
                    continue
                if isinstance(value, list):
                    current = merged.get(key)
                    if not isinstance(current, list):
                        current = []
                    for item in value:
                        if item in ("", None):
                            continue
                        if item not in current:
                            current.append(item)
                    if current:
                        merged[key] = current
                    continue
                if key not in merged:
                    merged[key] = value
        raw_languages = merged.get("language_requirements")
        if isinstance(raw_languages, list):
            sanitized_languages = self._sanitize_language_requirements(raw_languages)
            if sanitized_languages:
                merged["language_requirements"] = sanitized_languages
            else:
                merged.pop("language_requirements", None)
        return merged

    def _sanitize_language_requirements(self, values: list[Any]) -> list[str]:
        sanitized: list[str] = []
        seen: set[str] = set()
        for item in values:
            normalized = " ".join(str(item).split())
            if not normalized:
                continue
            ielts_match = re.fullmatch(
                r"IELTS\s*([0-9]+(?:\.[0-9])?)",
                normalized,
                flags=re.IGNORECASE,
            )
            if ielts_match:
                score = float(ielts_match.group(1))
                if not (0.0 <= score <= 9.0):
                    continue
                normalized = f"IELTS {ielts_match.group(1)}"
            else:
                toefl_match = re.fullmatch(
                    r"TOEFL(?:\s|-)?IBT?\s*([0-9]{2,3})|TOEFL\s*([0-9]{2,3})",
                    normalized,
                    flags=re.IGNORECASE,
                )
                if toefl_match:
                    score_text = toefl_match.group(1) or toefl_match.group(2)
                    if score_text is None:
                        continue
                    score = int(score_text)
                    if not (60 <= score <= 677):
                        continue
                    normalized = f"TOEFL {score}"
            if normalized in seen:
                continue
            seen.add(normalized)
            sanitized.append(normalized)
        return sanitized

    def _status_summary_label(self, status: str) -> str:
        labels = {
            "official_found": "current-cycle official pages found",
            "mixed": "partial official pages found; information may be incomplete",
            "predicted": "forecast from historical records; current-cycle official pages missing",
            "unsupported_program": "program is outside the supported catalog (unsupported_program)",
        }
        return labels.get(status, status)

    def _resolve_official_source_urls(
        self,
        school_records: list[dict[str, Any]],
        configured_urls: Any,
    ) -> list[tuple[str, str]]:
        resolved_by_type: dict[str, str] = {}
        fallback_url = ""
        for item in school_records:
            raw_url = str(item.get("source_url", "")).strip()
            if not raw_url:
                continue
            page_type = str(item.get("page_type", "")).strip().lower()
            if page_type in {"requirements", "deadline"} and page_type not in resolved_by_type:
                resolved_by_type[page_type] = raw_url
            if not fallback_url:
                fallback_url = raw_url
        if isinstance(configured_urls, dict):
            for page_type in ("requirements", "deadline"):
                raw_configured = configured_urls.get(page_type, "")
                configured = str(raw_configured).strip()
                if configured and page_type not in resolved_by_type:
                    resolved_by_type[page_type] = configured
        if resolved_by_type.get("requirements") and resolved_by_type.get("deadline"):
            requirements_url = resolved_by_type["requirements"]
            deadline_url = resolved_by_type["deadline"]
            if requirements_url == deadline_url:
                return [("official", requirements_url)]
            return [("requirements", requirements_url), ("deadline", deadline_url)]
        if resolved_by_type.get("requirements"):
            return [("requirements", resolved_by_type["requirements"])]
        if resolved_by_type.get("deadline"):
            return [("deadline", resolved_by_type["deadline"])]
        if fallback_url:
            return [("official", fallback_url)]
        return []

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."
