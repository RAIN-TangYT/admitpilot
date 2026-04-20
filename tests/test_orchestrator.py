from typing import Any, cast

from admitpilot.config import AdmitPilotSettings
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


def _build_orchestrator() -> PrincipalApplicationOrchestrator:
    return PrincipalApplicationOrchestrator(
        settings=AdmitPilotSettings(run_mode="test", openai_api_key="")
    )


def _complete_profile() -> UserProfile:
    return UserProfile(
        degree_level="bachelor",
        major_interest="Computer Science",
        target_regions=["Hong Kong", "Singapore"],
        academic_metrics={"gpa": 3.8},
        language_scores={"ielts": 7.5},
        experiences=["research project", "internship"],
        target_schools=["NUS", "HKU"],
        target_programs=["MSCS"],
        risk_preference="balanced",
    )


def test_orchestrator_happy_path() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="我需要选校、时间线和文书支持",
            profile=_complete_profile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    assert len(response.results) >= 3
    assert response.context is not None
    assert "aie" in response.context.shared_memory


def test_orchestrator_expands_strategy_for_timeline_only_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请给我做申请时间线",
            profile=_complete_profile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    agents = [result.agent for result in response.results]
    assert agents == ["aie", "sae", "dta"]
    assert all(result.status == TaskStatus.SUCCESS for result in response.results)
    assert response.context is not None
    assert not response.context.decisions.get("degraded_tasks")


def test_orchestrator_expands_full_chain_for_documents_only_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请帮我准备文书",
            profile=_complete_profile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )
    agents = [result.agent for result in response.results]
    assert agents == ["aie", "sae", "dta", "cds"]
    assert all(result.status == TaskStatus.SUCCESS for result in response.results)
    assert response.context is not None
    assert not response.context.decisions.get("degraded_tasks")


def test_orchestrator_handles_unknown_agent() -> None:
    orchestrator = _build_orchestrator()
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
    orchestrator = _build_orchestrator()
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
    orchestrator = _build_orchestrator()
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


def test_orchestrator_requests_profile_completion_before_sae() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请帮我做选校定位",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie", "sae"]
    sae_result = response.results[1]
    assert sae_result.status == TaskStatus.SKIPPED
    assert any(item.startswith("missing_profile:") for item in sae_result.blocked_by)
    assert "请补充以下字段后重试" in response.summary
    assert "GPA" in response.summary
    assert "语言成绩" in response.summary


def test_orchestrator_skips_cds_instead_of_degrade_when_profile_incomplete() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="我需要选校、时间线和文书支持",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    agents = [result.agent for result in response.results]
    assert agents == ["aie", "sae", "dta", "cds"]
    statuses = [result.status for result in response.results]
    assert statuses == [
        TaskStatus.SUCCESS,
        TaskStatus.SKIPPED,
        TaskStatus.SKIPPED,
        TaskStatus.SKIPPED,
    ]
    assert response.context is not None
    degraded = response.context.decisions.get("degraded_tasks", {})
    assert "draft_documents" not in degraded
    assert "已暂停SAE择校及下游任务" in response.summary


def test_orchestrator_returns_readable_intelligence_summary_for_official_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我 HKUST MSc in Information Technology 的官网要求和 deadline",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["HKUST"]
    assert aie_output["target_program_by_school"]["HKUST"] == "MSIT"
    assert any(
        isinstance(item.get("extracted_fields"), dict) and item["extracted_fields"]
        for item in aie_output["official_records"]
    )
    assert "AIE 官网情报摘要" in response.summary
    assert "HKUST / MSIT" in response.summary
    assert "截止时间" in response.summary


def test_orchestrator_routes_chinese_deadline_query_to_aie_only() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我HKU的MSCS的截止时间",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["HKU"]
    assert aie_output["target_program_by_school"]["HKU"] == "MSCS"
    assert aie_output["official_status_by_school"]["HKU"] == "official_found"
    assert "AIE 官网情报摘要" in response.summary
    assert "截止时间" in response.summary


def test_orchestrator_handles_chinese_school_name_official_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我香港大学 Master of Data Science 的官网要求和 deadline",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["HKU"]
    assert aie_output["target_program_by_school"]["HKU"] == "MDS"
    assert aie_output["official_status_by_school"]["HKU"] == "official_found"
    assert "HKU / MDS" in response.summary
    assert "截止时间" in response.summary


def test_orchestrator_maps_ais_alias_to_mtech_ais_for_nus_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我NUS的AIS的官网要求和截至时间",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["NUS"]
    assert aie_output["target_program_by_school"]["NUS"] == "MTECH_AIS"
    assert "NUS / MTECH_AIS" in response.summary


def test_orchestrator_returns_configured_source_url_when_no_structured_records() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我 NUS MSBA 的官网要求和 deadline",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["NUS"]
    assert aie_output["target_program_by_school"]["NUS"] == "MSBA"
    assert (
        aie_output["official_source_urls_by_school"]["NUS"]["requirements"]
        == "https://masters.nus.edu.sg/programmes/master-of-science-in-business-analytics"
    )
    assert "官方来源" in response.summary
    assert "master-of-science-in-business-analytics" in response.summary


def test_merge_extracted_fields_prefers_requirements_and_dedupes_lists() -> None:
    orchestrator = _build_orchestrator()

    merged = orchestrator._merge_extracted_fields(
        [
            {
                "page_type": "deadline",
                "extracted_fields": {
                    "language_requirements": ["IELTS 5", "TOEFL 90", "TOEFL 908"]
                },
            },
            {
                "page_type": "requirements",
                "extracted_fields": {
                    "language_requirements": ["IELTS 6.0", "IELTS 5", "TOEFL 90"]
                },
            },
        ]
    )

    assert merged["language_requirements"] == ["IELTS 6.0", "IELTS 5", "TOEFL 90"]


def test_orchestrator_returns_unsupported_program_for_unknown_program_query() -> None:
    orchestrator = _build_orchestrator()
    response = orchestrator.invoke(
        OrchestrationRequest(
            user_query="请告诉我香港大学 Master of Quantum Computing 的官网要求和 deadline",
            profile=UserProfile(),
            constraints={"cycle": "2026", "timezone": "Asia/Shanghai"},
        )
    )

    assert [result.agent for result in response.results] == ["aie"]
    assert response.context is not None
    aie_output = response.context.shared_memory["aie"]
    assert aie_output["target_schools"] == ["HKU"]
    assert "HKU" not in aie_output["target_program_by_school"]
    assert aie_output["unsupported_program_by_school"]["HKU"] != ""
    assert aie_output["official_status_by_school"]["HKU"] == "unsupported_program"
    assert aie_output["official_records"] == []
    assert "unsupported_program" in response.summary
