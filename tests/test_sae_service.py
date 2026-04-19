from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import UserProfile


def _build_intelligence() -> dict[str, object]:
    return {
        "target_schools": ["HKUST"],
        "target_program": "MSCS",
        "official_status_by_school": {"HKUST": "official_found"},
        "forecast_signals": [],
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
