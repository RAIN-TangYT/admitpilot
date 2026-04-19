from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import AIEAgentOutput, UserProfile


def _build_intelligence() -> AIEAgentOutput:
    return {
        "cycle": "2026",
        "as_of_date": "2026-04-19",
        "target_schools": ["HKUST"],
        "target_program": "MULTI_PROGRAM_PORTFOLIO",
        "target_program_by_school": {"HKUST": "MSIT"},
        "official_status_by_school": {"HKUST": "official_found"},
        "official_records": [],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [],
        "evidence_levels": {"HKUST": "official_primary"},
        "official_confidence": 0.88,
        "case_confidence": 0.0,
        "cache_hit_count": 0,
        "prediction_used": False,
    }


def test_sae_tier_thresholds_follow_score_direction() -> None:
    service = StrategicAdmissionsService()

    assert service._tier_from_score(0.59) == "reach"
    assert service._tier_from_score(0.60) == "match"
    assert service._tier_from_score(0.71) == "match"
    assert service._tier_from_score(0.72) == "safety"


def test_sae_evaluate_maps_stronger_profile_to_safer_tier() -> None:
    service = StrategicAdmissionsService()
    intelligence = _build_intelligence()
    strong_profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 4.0},
        language_scores={"ielts": 9.0},
        experiences=["AI research", "data systems project"],
    )
    weak_profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 2.0},
        language_scores={"ielts": 5.5},
    )

    strong_report = service.evaluate(strong_profile, intelligence)
    weak_report = service.evaluate(weak_profile, intelligence)

    strong_recommendation = strong_report.recommendations[0]
    weak_recommendation = weak_report.recommendations[0]

    assert strong_recommendation.overall_score > weak_recommendation.overall_score
    assert strong_recommendation.tier == "safety"
    assert weak_recommendation.tier == "reach"


def test_sae_uses_program_mapping_per_school() -> None:
    service = StrategicAdmissionsService()
    intelligence: AIEAgentOutput = {
        **_build_intelligence(),
        "target_schools": ["NUS", "HKUST"],
        "target_program_by_school": {"NUS": "MCOMP_CS", "HKUST": "MSIT"},
        "official_status_by_school": {"NUS": "official_found", "HKUST": "official_found"},
        "evidence_levels": {"NUS": "official_primary", "HKUST": "official_primary"},
    }
    profile = UserProfile(
        major_interest="Computing",
        academic_metrics={"gpa": 3.8},
        language_scores={"ielts": 7.5},
    )

    report = service.evaluate(profile, intelligence)

    assert {item.school: item.program for item in report.recommendations} == {
        "NUS": "MCOMP_CS",
        "HKUST": "MSIT",
    }
