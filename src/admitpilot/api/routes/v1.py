"""Versioned demo API routes for the AdmitPilot workbench."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from admitpilot.api.store import AuthenticatedUser, DemoApiStore
from admitpilot.app import AdmitPilotApplication
from admitpilot.core.schemas import AgentResult, ApplicationContext, UserProfile
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG
from admitpilot.pao.contracts import OrchestrationRequest, OrchestrationResponse
from admitpilot.platform.runtime import TaskStatus

MissingField = dict[str, Any]

PROFILE_FIELD_SPECS: dict[str, MissingField] = {
    "degree_level": {
        "key": "degree_level",
        "label": "Degree level",
        "required": True,
        "help_text": "Use bachelor, master, or undergraduate.",
    },
    "major_interest": {
        "key": "major_interest",
        "label": "Major interest",
        "required": True,
        "help_text": "Used to match programs and document materials.",
    },
    "target_schools": {
        "key": "target_schools",
        "label": "Target schools",
        "required": True,
        "help_text": "Select at least one target school.",
    },
    "target_programs": {
        "key": "target_programs",
        "label": "Target programs",
        "required": True,
        "help_text": "Select at least one target program.",
    },
    "academic_metrics.gpa": {
        "key": "academic_metrics.gpa",
        "label": "GPA",
        "required": True,
        "help_text": "Enter a GPA greater than 0, such as 3.72.",
    },
    "language_scores": {
        "key": "language_scores",
        "label": "Language score",
        "required": True,
        "help_text": "Enter an IELTS, TOEFL, or TOEFL iBT score.",
    },
    "experiences": {
        "key": "experiences",
        "label": "Experience materials",
        "required": True,
        "help_text": (
            "Provide at least one research, internship, course project, "
            "or competition experience."
        ),
    },
}

PROFILE_FIELD_ORDER = tuple(PROFILE_FIELD_SPECS.keys())


def build_v1_router(application: AdmitPilotApplication, store: DemoApiStore) -> APIRouter:
    """Create the v1 demo API router."""

    router = APIRouter(prefix="/api/v1", tags=["v1"])

    @router.get("/catalog")
    def catalog() -> dict[str, Any]:
        return _catalog_payload()

    @router.get("/demo-profile")
    def demo_profile() -> dict[str, Any]:
        return _demo_request_payload(
            cycle=application.settings.default_cycle,
            timezone=application.settings.timezone,
        )

    @router.post("/auth/login")
    def login(payload: dict[str, Any]) -> dict[str, Any]:
        user = store.authenticate(
            email=str(payload.get("email") or ""),
            password=str(payload.get("password") or ""),
        )
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = store.create_session(user)
        return {
            "token": token,
            "user": _user_payload(user),
        }

    @router.get("/auth/me")
    def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = _require_user(store=store, authorization=authorization)
        return {"user": _user_payload(user)}

    @router.post("/auth/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = _bearer_token(authorization)
        if token:
            store.delete_session(token)
        return {"status": "logged_out"}

    @router.post("/profile/validate")
    def validate_profile(payload: dict[str, Any]) -> dict[str, Any]:
        profile = _profile_from_payload(_mapping(payload.get("profile", payload)))
        missing_fields = _missing_profile_fields(profile)
        status = "needs_profile_input" if missing_fields else "delivered"
        return _base_response(
            status=status,
            summary=(
                "The applicant profile is incomplete. Complete the required fields "
                "before running AdmitPilot."
                if missing_fields
                else "The applicant profile is ready for the demo run."
            ),
            missing_profile_fields=missing_fields,
            results=[],
            trace_id=f"trace-{uuid4().hex}",
        )

    @router.post("/orchestrations")
    def run_orchestration(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = _require_user(store=store, authorization=authorization)
        profile = _profile_from_payload(_mapping(payload.get("profile", {})))
        missing_fields = _missing_profile_fields(profile)
        trace_id = f"trace-{uuid4().hex}"
        if missing_fields:
            response_payload = _needs_profile_input_response(
                missing_fields=missing_fields,
                trace_id=trace_id,
            )
            run_summary = store.create_run(
                user=user,
                request_payload=dict(payload),
                response_payload=response_payload,
            )
            response_payload["run_id"] = run_summary["run_id"]
            return response_payload

        request = _orchestration_request_from_payload(payload=payload, profile=profile)
        try:
            response = application.orchestrator.invoke(request)
        except Exception as exc:  # pragma: no cover - defensive API boundary
            return _base_response(
                status="failed",
                summary=f"PAO orchestration failed: {exc}",
                missing_profile_fields=[],
                results=[],
                trace_id=trace_id,
            )

        response_payload = _orchestration_response_payload(
            response=response,
            profile=profile,
            fallback_trace_id=trace_id,
        )
        run_summary = store.create_run(
            user=user,
            request_payload=dict(payload),
            response_payload=response_payload,
        )
        response_payload["run_id"] = run_summary["run_id"]
        return response_payload

    @router.websocket("/orchestrations/ws")
    async def run_orchestration_ws(websocket: WebSocket, token: str = "") -> None:
        async def _send_event(payload: dict[str, Any]) -> None:
            await websocket.send_json(payload)
            # Yield once so outbound WS frames flush before next sync dispatch step blocks the loop.
            await asyncio.sleep(0)

        await websocket.accept()
        user = _user_from_token(store=store, token=token)
        if user is None:
            await _send_event(
                {
                    "event": "workflow_failed",
                    "data": {
                        "status": "failed",
                        "summary": "Authentication required.",
                    },
                }
            )
            await websocket.close(code=1008)
            return
        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except Exception:
            await _send_event(
                {
                    "event": "workflow_failed",
                    "data": {
                        "status": "failed",
                        "summary": "Invalid orchestration payload.",
                    },
                }
            )
            await websocket.close(code=1003)
            return

        if not isinstance(payload, Mapping):
            await _send_event(
                {
                    "event": "workflow_failed",
                    "data": {
                        "status": "failed",
                        "summary": "Invalid orchestration payload.",
                    },
                }
            )
            await websocket.close(code=1003)
            return

        profile = _profile_from_payload(_mapping(payload.get("profile", {})))
        missing_fields = _missing_profile_fields(profile)
        trace_id = f"trace-{uuid4().hex}"
        if missing_fields:
            response_payload = _needs_profile_input_response(
                missing_fields=missing_fields,
                trace_id=trace_id,
            )
            run_summary = store.create_run(
                user=user,
                request_payload=dict(payload),
                response_payload=response_payload,
            )
            response_payload["run_id"] = run_summary["run_id"]
            await _send_event(
                {
                    "event": "workflow_completed",
                    "data": {"trace_id": trace_id, "response": response_payload},
                }
            )
            await websocket.close(code=1000)
            return

        request = _orchestration_request_from_payload(payload=payload, profile=profile)
        try:
            for event in application.orchestrator.stream(request):
                if event.event == "stage_completed":
                    result = event.data.get("result")
                    await _send_event(
                        {
                            "event": event.event,
                            "data": {
                                "trace_id": event.data.get("trace_id"),
                                "agent": event.data.get("agent"),
                                "task": event.data.get("task"),
                                "status": event.data.get("status"),
                                "success": event.data.get("success"),
                                "result": (
                                    _agent_result_payload(result, profile=profile)
                                    if isinstance(result, AgentResult)
                                    else None
                                ),
                            },
                        }
                    )
                    continue
                if event.event == "workflow_completed":
                    response = event.data.get("response")
                    if not isinstance(response, OrchestrationResponse):
                        raise TypeError("Invalid PAO workflow response")
                    response_payload = _orchestration_response_payload(
                        response=response,
                        profile=profile,
                        fallback_trace_id=trace_id,
                    )
                    run_summary = store.create_run(
                        user=user,
                        request_payload=dict(payload),
                        response_payload=response_payload,
                    )
                    response_payload["run_id"] = run_summary["run_id"]
                    await _send_event(
                        {
                            "event": event.event,
                            "data": {
                                "trace_id": response_payload["trace_id"],
                                "response": response_payload,
                            },
                        }
                    )
                    continue
                await _send_event({"event": event.event, "data": event.data})
        except WebSocketDisconnect:
            return
        except Exception as exc:  # pragma: no cover - defensive WebSocket boundary
            await _send_event(
                {
                    "event": "workflow_failed",
                    "data": {
                        "status": "failed",
                        "summary": f"PAO orchestration failed: {exc}",
                    },
                }
            )
        await websocket.close(code=1000)

    @router.get("/runs")
    def list_runs(
        authorization: str | None = Header(default=None),
        limit: int = 20,
    ) -> dict[str, Any]:
        user = _require_user(store=store, authorization=authorization)
        return {"runs": store.list_runs(user=user, limit=limit)}

    @router.get("/runs/{run_id}")
    def get_run(
        run_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = _require_user(store=store, authorization=authorization)
        run = store.get_run(user=user, run_id=run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run": run}

    @router.delete("/runs/{run_id}")
    def delete_run(
        run_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = _require_user(store=store, authorization=authorization)
        deleted = store.delete_run(user=user, run_id=run_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"status": "deleted", "run_id": run_id}

    return router


def _user_payload(user: AuthenticatedUser) -> dict[str, Any]:
    return {
        "id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
    }


def _require_user(
    *,
    store: DemoApiStore,
    authorization: str | None,
) -> AuthenticatedUser:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = store.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def _user_from_token(*, store: DemoApiStore, token: str) -> AuthenticatedUser | None:
    stripped = token.strip()
    if not stripped:
        return None
    return store.get_user_by_token(stripped)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def _base_response(
    *,
    status: str,
    summary: str,
    missing_profile_fields: list[MissingField],
    results: list[dict[str, Any]],
    trace_id: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": status,
        "summary": summary,
        "missing_profile_fields": missing_profile_fields,
        "results": results,
        "trace_id": trace_id,
    }
    if context is not None:
        response["context"] = context
    return response


def _needs_profile_input_response(
    *, missing_fields: list[MissingField], trace_id: str
) -> dict[str, Any]:
    return _base_response(
        status="needs_profile_input",
        summary=(
            "The applicant profile is incomplete. Complete the required fields "
            "before running AdmitPilot."
        ),
        missing_profile_fields=missing_fields,
        results=[],
        trace_id=trace_id,
    )


def _orchestration_request_from_payload(
    *, payload: Mapping[str, Any], profile: UserProfile
) -> OrchestrationRequest:
    return OrchestrationRequest(
        user_query=str(payload.get("user_query") or "Run AdmitPilot demo orchestration"),
        profile=profile,
        constraints=dict(_mapping(payload.get("constraints", {}))),
    )


def _orchestration_response_payload(
    *,
    response: OrchestrationResponse,
    profile: UserProfile,
    fallback_trace_id: str,
) -> dict[str, Any]:
    response_trace_id = _trace_id_from_context(response.context) or fallback_trace_id
    return _base_response(
        status=_response_status(response.results),
        summary=_orchestration_summary(response.results),
        missing_profile_fields=[],
        results=[_agent_result_payload(item, profile=profile) for item in response.results],
        trace_id=response_trace_id,
        context=_context_payload(response.context, profile=profile),
    )


def _catalog_payload() -> dict[str, Any]:
    schools: list[dict[str, Any]] = []
    for school_code in DEFAULT_ADMISSIONS_CATALOG.all_school_codes():
        school = DEFAULT_ADMISSIONS_CATALOG.get_school(school_code)
        if school is None:
            continue
        schools.append(
            {
                "code": school.code,
                "display_name": school.display_name,
                "region": school.region,
                "programs": [
                    {
                        "code": program.code,
                        "display_name": program.display_name,
                        "slug": program.slug,
                    }
                    for program in school.programs.values()
                ],
            }
        )
    return {
        "schools": schools,
        "default_schools": list(DEFAULT_ADMISSIONS_CATALOG.all_school_codes()),
        "default_portfolio": DEFAULT_ADMISSIONS_CATALOG.default_program_portfolio(),
    }


def _demo_request_payload(*, cycle: str, timezone: str) -> dict[str, Any]:
    default_portfolio = {
        "NUS": "MTECH_AIS",
        "NTU": "MSAI",
        "HKU": "MSCS",
        "CUHK": "MSCS",
        "HKUST": "MSAI",
    }
    target_schools = list(default_portfolio.keys())
    target_programs = list(dict.fromkeys(default_portfolio.values()))
    user_artifacts = [
        {
            "artifact_id": "proj-ml-001",
            "title": "Machine Learning Research Project",
            "source_ref": "portfolio:ml-project-report",
            "evidence_type": "project",
            "date_range": "2025-03 to 2025-08",
            "details": (
                "Built a reproducible course-research pipeline for admission "
                "outcome prediction, with feature analysis and model evaluation."
            ),
            "verified": True,
        },
        {
            "artifact_id": "intern-backend-001",
            "title": "Backend Engineering Internship",
            "source_ref": "portfolio:internship-certificate",
            "evidence_type": "internship",
            "date_range": "2025-06 to 2025-09",
            "details": (
                "Implemented FastAPI services, monitoring dashboards, and API "
                "tests for a data product used by internal operations teams."
            ),
            "verified": True,
        },
        {
            "artifact_id": "lang-ielts-001",
            "title": "IELTS Overall 7.5",
            "source_ref": "ielts:trf-demo",
            "evidence_type": "language",
            "date_range": "2025-10",
            "details": "IELTS overall 7.5 with no band below 6.5.",
            "verified": True,
        },
    ]
    profile = {
        "name": "Demo Applicant",
        "degree_level": "bachelor",
        "major_interest": "Computer Science",
        "target_regions": ["Singapore", "Hong Kong"],
        "academic_metrics": {"gpa": 3.72},
        "language_scores": {"ielts": 7.5},
        "experiences": [
            "Machine learning research project on admission outcome prediction",
            "Backend engineering internship using FastAPI and observability tooling",
            "Distributed systems course project with fault-tolerant task scheduling",
        ],
        "target_schools": target_schools,
        "target_programs": target_programs,
        "risk_preference": "balanced",
    }
    constraints = {
        "cycle": cycle,
        "timezone": timezone,
        "timeline_weeks": 8,
        "target_schools": target_schools,
        "target_program_by_school": default_portfolio,
        "user_artifacts": user_artifacts,
    }
    return {
        "user_query": (
            "I need school selection, timeline planning, and document preparation "
            "for the 2026 application cycle."
        ),
        "profile": profile,
        "constraints": constraints,
    }


def _profile_from_payload(payload: Mapping[str, Any]) -> UserProfile:
    academic_metrics = dict(_mapping(payload.get("academic_metrics", {})))
    language_scores = dict(_mapping(payload.get("language_scores", {})))
    return UserProfile(
        name=str(payload.get("name") or ""),
        degree_level=str(payload.get("degree_level") or ""),
        major_interest=str(payload.get("major_interest") or ""),
        target_regions=_string_list(payload.get("target_regions")),
        academic_metrics=academic_metrics,
        language_scores=language_scores,
        experiences=_string_list(payload.get("experiences")),
        target_schools=_string_list(payload.get("target_schools")),
        target_programs=_string_list(payload.get("target_programs")),
        risk_preference=str(payload.get("risk_preference") or "balanced"),
    )


def _missing_profile_fields(profile: UserProfile) -> list[MissingField]:
    missing_keys: list[str] = []
    if not profile.degree_level.strip():
        missing_keys.append("degree_level")
    if not profile.major_interest.strip():
        missing_keys.append("major_interest")
    if not profile.target_schools:
        missing_keys.append("target_schools")
    if not profile.target_programs:
        missing_keys.append("target_programs")
    if not _is_positive_number(profile.academic_metrics.get("gpa")):
        missing_keys.append("academic_metrics.gpa")
    if not _has_language_score(profile.language_scores):
        missing_keys.append("language_scores")
    if not profile.experiences:
        missing_keys.append("experiences")
    order_map = {key: index for index, key in enumerate(PROFILE_FIELD_ORDER)}
    return [
        dict(PROFILE_FIELD_SPECS[key])
        for key in sorted(missing_keys, key=lambda item: order_map[item])
    ]


def _agent_result_payload(
    result: AgentResult, profile: UserProfile | None = None
) -> dict[str, Any]:
    return {
        "agent": result.agent,
        "task": result.task,
        "status": result.status.value,
        "success": result.success,
        "confidence": result.confidence,
        "evidence_level": result.evidence_level,
        "lineage": result.lineage,
        "trace": result.trace,
        "blocked_by": result.blocked_by,
        "output": _english_agent_output(result.agent, result.output, profile),
    }


def _orchestration_summary(results: list[AgentResult]) -> str:
    success_count = sum(1 for item in results if item.success)
    failed_count = sum(1 for item in results if item.status == TaskStatus.FAILED)
    skipped_count = sum(
        1 for item in results if item.status in {TaskStatus.SKIPPED, TaskStatus.DEGRADED}
    )
    workflow_status = _response_status(results).upper()
    return (
        f"PAO completed {len(results)} agent tasks: "
        f"success={success_count} failed={failed_count} skipped={skipped_count}. "
        f"Workflow status: {workflow_status}."
    )


def _english_agent_output(
    agent: str, output: Mapping[str, Any], profile: UserProfile | None
) -> dict[str, Any]:
    data = dict(_mapping(output))
    if agent == "sae":
        return _english_sae_output(data, profile)
    if agent == "dta":
        return _english_dta_output(data)
    if agent == "cds":
        return _english_cds_output(data)
    return _sanitize_english(data)


def _english_sae_output(
    output: Mapping[str, Any], profile: UserProfile | None
) -> dict[str, Any]:
    recommendations = [
        _english_recommendation(item) for item in _record_list(output.get("recommendations"))
    ]
    ranking_order = _string_list(output.get("ranking_order"))
    model_breakdown = dict(_mapping(output.get("model_breakdown", {})))
    tier_counts = _tier_counts(recommendations)
    top_choices = ", ".join(ranking_order[:3]) or "n/a"
    strengths = _profile_strengths(profile, recommendations)
    weaknesses = _strategy_weaknesses(recommendations)
    gap_actions = _strategy_gap_actions(recommendations)
    return {
        "summary": (
            f"Evaluated {len(recommendations)} target programs. "
            f"Top choices: {top_choices}. Tier mix: {tier_counts}."
        ),
        "model_breakdown": model_breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "gap_actions": gap_actions,
        "recommendations": recommendations,
        "ranking_order": ranking_order,
    }


def _english_recommendation(item: Mapping[str, Any]) -> dict[str, Any]:
    school = _safe_text(item.get("school"), "School")
    program = _safe_text(item.get("program"), "Program")
    tier = _safe_text(item.get("tier"), "review")
    rule_score = _score_value(item.get("rule_score"))
    semantic_score = _score_value(item.get("semantic_score"))
    risk_score = _score_value(item.get("risk_score"))
    overall_score = _score_value(item.get("overall_score"))
    rule_notes = _string_list(item.get("rule_notes"))
    evidence = _string_list(item.get("evidence"))
    risk_flags = [_risk_label(flag) for flag in _string_list(item.get("risk_flags"))]
    recommendation = _sanitize_english(dict(item))
    recommendation.update(
        {
            "school": school,
            "program": program,
            "tier": tier,
            "rule_score": rule_score,
            "semantic_score": semantic_score,
            "risk_score": risk_score,
            "overall_score": overall_score,
            "reasons": [
                (
                    f"{school} {program} is a {tier} option with overall score "
                    f"{_score_text(overall_score)}."
                ),
                (
                    f"Scoring blend: rule {_score_text(rule_score)}, "
                    f"semantic {_score_text(semantic_score)}, "
                    f"risk {_score_text(risk_score)}."
                ),
                (
                    f"Rule notes: {_humanized_join(rule_notes) or 'baseline profile match'}; "
                    f"evidence signals: {len(evidence)}."
                ),
            ],
            "gaps": _recommendation_gaps(item),
            "risk_flags": risk_flags,
        }
    )
    return recommendation


def _recommendation_gaps(item: Mapping[str, Any]) -> list[str]:
    raw_gaps = _string_list(item.get("gaps"))
    rule_notes = _string_list(item.get("rule_notes"))
    gaps = [
        _safe_text(gap, "Align the experience narrative with program expectations.")
        for gap in raw_gaps
    ]
    if not gaps and "background_mismatch" in rule_notes:
        gaps.append("Experience narrative is not fully aligned with preferred background keywords.")
    if "official_incomplete" in rule_notes:
        gaps.append("Verify program-specific prerequisites against the latest official page.")
    return gaps


def _profile_strengths(
    profile: UserProfile | None, recommendations: list[dict[str, Any]]
) -> list[str]:
    strengths: list[str] = []
    if profile is not None:
        gpa = profile.academic_metrics.get("gpa")
        if _is_positive_number(gpa):
            strengths.append(f"Academic baseline is competitive with GPA {_number_text(gpa)}.")
        language = _language_score_text(profile)
        if language:
            strengths.append(f"English readiness is documented through {language}.")
        if profile.experiences:
            strengths.append(
                f"Experience evidence covers {len(profile.experiences)} research, "
                "engineering, or systems materials."
            )
    match_count = sum(1 for item in recommendations if item.get("tier") == "match")
    if match_count:
        strengths.append(f"{match_count} programs are currently classified as match options.")
    return strengths or ["Profile evidence is sufficient for a structured strategy review."]


def _strategy_weaknesses(recommendations: list[dict[str, Any]]) -> list[str]:
    reach_count = sum(1 for item in recommendations if item.get("tier") == "reach")
    risk_flags = _top_risk_flags(recommendations)
    weaknesses = [
        "Application narratives still need quantified outcomes for projects and internships."
    ]
    if reach_count:
        weaknesses.append(
            f"{reach_count} reach option requires stronger school-specific positioning."
        )
    if risk_flags:
        weaknesses.append(f"Risk signals to monitor: {', '.join(risk_flags[:4])}.")
    return weaknesses


def _strategy_gap_actions(recommendations: list[dict[str, Any]]) -> list[str]:
    schools = [
        str(item.get("school"))
        for item in recommendations
        if item.get("tier") in {"reach", "match"} and item.get("school")
    ]
    top_schools = ", ".join(schools[:5]) or "the target portfolio"
    return [
        "Add measurable outcomes to the ML research project, backend internship, "
        "and distributed systems project.",
        f"Build one school-specific evidence map for {top_schools}.",
        "Prepare recommender prompts that cite research rigor, engineering impact, "
        "ownership, and reliability evidence.",
    ]


def _english_dta_output(output: Mapping[str, Any]) -> dict[str, Any]:
    raw_milestones = _record_list(output.get("milestones"))
    milestones = [_english_milestone(item) for item in raw_milestones]
    raw_weeks = _record_list(output.get("weekly_plan"))
    total_weeks = max(len(raw_weeks), 8)
    weekly_plan = [_english_week(item, milestones, total_weeks) for item in raw_weeks]
    risk_markers = [_english_risk_marker(item) for item in _record_list(output.get("risk_markers"))]
    school_scope = _school_scope_from_weeks(raw_weeks)
    return {
        "board_title": "2026 application execution board",
        "milestones": milestones,
        "weekly_plan": weekly_plan,
        "risk_markers": risk_markers,
        "document_instructions": _document_instructions(school_scope),
    }


def _english_milestone(item: Mapping[str, Any]) -> dict[str, Any]:
    key = _safe_text(item.get("key"), "milestone")
    title_by_key = {
        "scope_lock": "Lock target portfolio and priority order",
        "language_test": "Complete standardized English test score",
        "background_enhancement": "Complete core background enhancement outputs",
        "doc_pack_v1": "Complete first SOP/CV draft package",
        "submission_batch_1": "Submit the first application batch",
        "interview_prep": "Complete interview question bank and mock practice",
        "buffer_window": "Reserve buffer week for supplements and corrections",
    }
    return {
        "key": key,
        "title": title_by_key.get(key, _humanize_token(key)),
        "due_week": item.get("due_week"),
        "status": _safe_text(item.get("status"), "planned"),
        "depends_on": _string_list(item.get("depends_on")),
    }


def _english_week(
    item: Mapping[str, Any], milestones: list[dict[str, Any]], total_weeks: int
) -> dict[str, Any]:
    week = int(item.get("week") or 0)
    school_scope = _string_list(item.get("school_scope"))
    due_titles = [
        str(milestone["title"])
        for milestone in milestones
        if int(milestone.get("due_week") or 0) == week
    ]
    return {
        "week": week,
        "focus": _week_focus(week),
        "items": _week_items(week, school_scope, due_titles),
        "school_scope": school_scope,
        "risks": _week_risks(week, total_weeks, _string_list(item.get("risks"))),
    }


def _week_focus(week: int) -> str:
    focus_by_week = {
        1: "Portfolio lock and evidence map",
        2: "Quantified evidence package",
        3: "Program alignment and SOP structure",
        4: "Background enhancement and recommender evidence",
        5: "SOP/CV first complete draft",
        6: "First submission batch",
        7: "Interview preparation",
        8: "Buffer, corrections, and final checks",
    }
    return focus_by_week.get(week, "Application execution")


def _week_items(week: int, school_scope: list[str], due_titles: list[str]) -> list[str]:
    schools = ", ".join(school_scope) or "all target schools"
    base_items = {
        1: [
            f"Lock school and program priority order for {schools}.",
            "Create a fact-slot map for every target program.",
        ],
        2: [
            "Convert ML research and backend internship into quantified evidence bullets.",
            "List missing metrics, source files, and recommender proof points.",
        ],
        3: [
            "Build the course and prerequisite alignment sheet for each program.",
            "Draft the SOP structure: motivation, evidence, fit, and goals.",
        ],
        4: [
            "Complete background enhancement artifacts and update verified evidence.",
            "Send recommender prompts with concrete examples and metrics.",
        ],
        5: [
            "Finish SOP/CV version one and create school-specific variants.",
            "Run consistency checks across timeline, facts, and document claims.",
        ],
        6: [
            "Submit the first application batch after final material verification.",
            "Archive receipts, portal screenshots, and submitted file versions.",
        ],
        7: [
            "Prepare interview answers for project fit, execution proof, and risk handling.",
            "Run mock interview practice and revise weak answers.",
        ],
        8: [
            "Handle supplements, final corrections, and deadline buffer tasks.",
            "Freeze non-essential edits and preserve a final evidence log.",
        ],
    }
    items = list(base_items.get(week, ["Advance standard application execution tasks."]))
    items.extend(f"Complete milestone: {title}." for title in due_titles)
    return items


def _week_risks(week: int, total_weeks: int, raw_risks: list[str]) -> list[str]:
    risks = [
        _safe_text(item, "Deadline cluster risk; freeze non-essential edits.")
        for item in raw_risks
    ]
    if week >= total_weeks - 1 and not risks:
        risks.append("Deadline cluster risk; freeze non-essential edits.")
    return risks


def _english_risk_marker(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "week": item.get("week"),
        "level": _safe_text(item.get("level"), "yellow"),
        "message": _safe_text(
            item.get("message"),
            "Some official program information or submission windows need monitoring.",
        ),
        "mitigation": _safe_text(
            item.get("mitigation"),
            "Refresh official pages weekly and re-run strategy or timeline updates.",
        ),
    }


def _document_instructions(school_scope: list[str]) -> list[str]:
    schools = ", ".join(school_scope) or "the target schools"
    return [
        f"Maintain an SOP/CV version matrix by school for {schools}.",
        "Update fact slots and the change log after every milestone.",
        "Prepare a one-minute English self-introduction before interview practice.",
    ]


def _english_cds_output(output: Mapping[str, Any]) -> dict[str, Any]:
    drafts = [_english_draft(item) for item in _record_list(output.get("document_drafts"))]
    return {
        "document_drafts": drafts,
        "interview_talking_points": _interview_points(drafts),
        "consistency_issues": [
            _english_consistency_issue(item)
            for item in _record_list(output.get("consistency_issues"))
        ],
        "review_checklist": _review_checklist(),
    }


def _english_draft(item: Mapping[str, Any]) -> dict[str, Any]:
    fact_slots = [_english_fact_slot(slot) for slot in _record_list(item.get("fact_slots"))]
    document_type = _safe_text(item.get("document_type"), "document")
    target_school = _safe_text(item.get("target_school"), "shared")
    return {
        "document_type": document_type,
        "target_school": target_school,
        "version": _safe_text(item.get("version"), "v0"),
        "content_outline": _document_outline(document_type, target_school, fact_slots),
        "fact_slots": fact_slots,
        "risks": _draft_risks(_string_list(item.get("risks"))),
        "review_status": _safe_text(item.get("review_status"), "needs_human_review"),
    }


def _document_outline(
    document_type: str, target_school: str, fact_slots: list[dict[str, Any]]
) -> list[str]:
    motivation = _slot_value(fact_slots, "motivation_core")
    program_fit = _slot_value(fact_slots, "program_fit")
    execution = _slot_value(fact_slots, "execution_proof")
    if document_type == "cv":
        return [
            "Education: position GPA, major interest, and relevant coursework for CS/AI programs.",
            "Research and project experience: order entries by relevance and measurable impact.",
            (
                "Backend internship and systems work: list stack, ownership, metrics, "
                "and reliability impact."
            ),
            f"Application priority mapping: {program_fit}.",
            f"Execution alignment: {execution}.",
        ]
    return [
        f"{target_school} positioning: connect CS/AI interests to the target program.",
        f"Motivation: anchor the story in verified evidence from {motivation}.",
        "Experience arc: ML research, backend engineering, and distributed systems reliability.",
        f"Program fit: map courses, project resources, and school keywords to {program_fit}.",
        "Career goal: define graduate study objectives and post-program direction.",
    ]


def _english_fact_slot(slot: Mapping[str, Any]) -> dict[str, Any]:
    slot_id = _safe_text(slot.get("slot_id"), "fact_slot")
    raw_value = str(slot.get("value") or "")
    value_by_slot = {
        "motivation_core": f"Core motivation evidence: {_after_colon(raw_value)}",
        "program_fit": f"Priority order: {_after_colon(raw_value)}",
        "execution_proof": (
            f"Execution plan uses {_extract_first_number(raw_value) or 'multiple'} milestones"
        ),
        "language_readiness": f"Language evidence: {_after_colon(raw_value)}",
    }
    return {
        "slot_id": slot_id,
        "value": value_by_slot.get(slot_id, _safe_text(raw_value, _humanize_token(slot_id))),
        "source_ref": _safe_text(slot.get("source_ref"), "unknown"),
        "status": _safe_text(slot.get("status"), "inferred"),
        "verified": bool(slot.get("verified")),
    }


def _draft_risks(raw_risks: list[str]) -> list[str]:
    if not raw_risks:
        return ["Human review required before final submission."]
    risks: list[str] = []
    for risk in raw_risks:
        if risk.startswith("risk_flag:"):
            risks.append(f"Risk flag: {_risk_label(risk.split(':', 1)[1])}.")
        elif risk.startswith("missing_input:"):
            risks.append(f"Missing input: {_humanize_token(risk.split(':', 1)[1])}.")
        elif risk.startswith("gap:"):
            risks.append("Gap: align the narrative with program background expectations.")
        else:
            risks.append(_safe_text(risk, "Human review required before final submission."))
    return risks


def _interview_points(drafts: list[dict[str, Any]]) -> list[str]:
    targets = [str(item.get("target_school")) for item in drafts if item.get("target_school")]
    school_text = ", ".join(targets[:3]) or "the target programs"
    return [
        f"Why this program: connect {school_text} to verified project evidence and coursework.",
        (
            "Best-fit experience: explain the ML research project with problem, "
            "method, metric, and result."
        ),
        "Execution proof: describe how the timeline turns milestones into submitted materials.",
        (
            "Risk handling: explain how quantified evidence and recommender examples "
            "close current gaps."
        ),
    ]


def _english_consistency_issue(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "severity": _safe_text(item.get("severity"), "medium"),
        "message": _safe_text(
            item.get("message"),
            "Some inferred fact slots require verification before final documents.",
        ),
        "impacted_documents": _string_list(item.get("impacted_documents")),
    }


def _review_checklist() -> list[str]:
    return [
        "Resolve consistency warnings before polishing.",
        "Verify every fact slot against the original artifact or source.",
        "Keep SOP, CV, recommendation prompts, and interview stories on the same timeline.",
        "Show school-specific program fit in every SOP variant.",
        "Quantify project outcomes, system metrics, and research results where possible.",
        "Standardize school, program, course, and document naming.",
        "Confirm every metric has a source, baseline, unit, and date range.",
        "Check that the story closes the loop: motivation, ability, evidence, fit, and goals.",
    ]


def _response_status(results: list[AgentResult]) -> str:
    if not results:
        return "failed"
    if any(item.status == TaskStatus.FAILED for item in results):
        return "failed"
    if any(item.status in {TaskStatus.SKIPPED, TaskStatus.DEGRADED} for item in results):
        return "partial_delivered"
    return "delivered"


def _context_payload(
    context: ApplicationContext | None, profile: UserProfile | None = None
) -> dict[str, Any]:
    if context is None:
        return {}
    shared_memory: dict[str, Any] = {}
    for key, value in context.shared_memory.items():
        if key in {"aie", "sae", "dta", "cds"}:
            shared_memory[key] = _english_agent_output(key, _mapping(value), profile)
        else:
            shared_memory[key] = _sanitize_english(value)
    return {
        "shared_memory": shared_memory,
        "decisions": _sanitize_english(context.decisions),
    }


def _trace_id_from_context(context: ApplicationContext | None) -> str | None:
    if context is None:
        return None
    trace_id = context.decisions.get("trace_id")
    return str(trace_id) if trace_id else None


def _record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _sanitize_english(value: Any, fallback: str = "English summary unavailable") -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize_english(item, fallback) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_english(item, fallback) for item in value]
    if isinstance(value, str):
        return _safe_text(value, fallback)
    return value


def _safe_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text or _has_cjk(text):
        return fallback
    return text


def _has_cjk(text: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in text)


def _score_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _score_text(value: Any) -> str:
    numeric = _score_value(value)
    return f"{numeric:.3f}"


def _number_text(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _humanize_token(value: str) -> str:
    text = value.replace("_", " ").replace("-", " ").strip()
    return text.capitalize() if text else "Review required"


def _risk_label(value: str) -> str:
    text = value.split("（", 1)[0].split("(", 1)[0].strip()
    return _humanize_token(_safe_text(text, "review required"))


def _humanized_join(values: list[str]) -> str:
    return ", ".join(_humanize_token(value) for value in values if value)


def _tier_counts(recommendations: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in recommendations:
        tier = str(item.get("tier") or "review")
        counts[tier] = counts.get(tier, 0) + 1
    return ", ".join(f"{tier} {count}" for tier, count in counts.items()) or "n/a"


def _language_score_text(profile: UserProfile) -> str:
    labels = {"ielts": "IELTS", "toefl": "TOEFL", "toefl_ibt": "TOEFL iBT"}
    for key, label in labels.items():
        value = profile.language_scores.get(key)
        if _is_positive_number(value):
            return f"{label} {_number_text(value)}"
    return ""


def _top_risk_flags(recommendations: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for item in recommendations:
        flags.extend(str(flag) for flag in item.get("risk_flags", []) if flag)
    unique_flags = list(dict.fromkeys(flags))
    return [_humanize_token(flag) for flag in unique_flags]


def _school_scope_from_weeks(weeks: list[dict[str, Any]]) -> list[str]:
    for week in weeks:
        scope = _string_list(week.get("school_scope"))
        if scope:
            return scope
    return []


def _slot_value(fact_slots: list[dict[str, Any]], slot_id: str) -> str:
    for item in fact_slots:
        if item.get("slot_id") == slot_id:
            return str(item.get("value") or "n/a")
    return "n/a"


def _after_colon(value: str) -> str:
    if ":" in value:
        value = value.split(":", 1)[1]
    text = value.strip()
    return _safe_text(text, "verified applicant evidence")


def _extract_first_number(value: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", value)
    return match.group(0) if match else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.splitlines() if item.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _has_language_score(language_scores: Mapping[str, Any]) -> bool:
    return any(
        _is_positive_number(language_scores.get(key))
        for key in ("ielts", "toefl", "toefl_ibt")
    )
