from admitpilot.agents.sae.semantic import (
    FakeSemanticMatcher,
    SemanticMatchResult,
    build_semantic_matcher,
)
from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.config import AdmitPilotSettings
from admitpilot.core.schemas import AIEAgentOutput, UserProfile
from admitpilot.platform.llm.openai import OpenAIClient


def _intel() -> AIEAgentOutput:
    return {
        "cycle": "2026",
        "as_of_date": "2026-04-20",
        "target_schools": ["NUS"],
        "target_program": "MCOMP_CS",
        "official_status_by_school": {"NUS": "official_found"},
        "official_records": [],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [],
        "evidence_levels": {"NUS": "official_primary"},
        "official_confidence": 0.8,
        "case_confidence": 0.5,
        "cache_hit_count": 0,
        "prediction_used": False,
    }


def test_fake_semantic_matcher_is_deterministic() -> None:
    matcher = FakeSemanticMatcher()
    profile = UserProfile(
        major_interest="Computer Science",
        experiences=["research in machine learning"],
    )
    first = matcher.match(profile, "NUS", "MCOMP_CS")
    second = matcher.match(profile, "NUS", "MCOMP_CS")
    assert first.score == second.score
    assert first.breakdown == second.breakdown


def test_strategic_admissions_service_accepts_injected_matcher() -> None:
    class ConstMatcher:
        def match(
            self,
            user_profile: UserProfile,
            school: str,
            program: str,
        ) -> SemanticMatchResult:
            del user_profile, school, program
            return SemanticMatchResult(score=0.88, breakdown={"method": "test_const"})

    service = StrategicAdmissionsService(semantic_matcher=ConstMatcher())
    report = service.evaluate(
        UserProfile(
            major_interest="Computer Science",
            academic_metrics={"gpa": 3.8},
            language_scores={"ielts": 7.0},
            experiences=["computer science"],
        ),
        _intel(),
    )
    nus = next(item for item in report.recommendations if item.school == "NUS")
    assert nus.semantic_score == 0.88
    assert nus.semantic_breakdown.get("method") == "test_const"


def test_build_embedding_matcher_uses_local_fallback_without_api_key() -> None:
    matcher = build_semantic_matcher(
        "embedding",
        llm_client=OpenAIClient(settings=AdmitPilotSettings(run_mode="test")),
    )
    profile = UserProfile(
        major_interest="Computer Science",
        experiences=["research in machine learning"],
    )

    result = matcher.match(profile, "NUS", "MCOMP_CS")

    assert 0.25 <= result.score <= 0.9
    assert result.breakdown.get("method") == "local_hashing_embedding"
