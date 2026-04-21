from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import AIEAgentOutput, UserProfile


def _intel() -> AIEAgentOutput:
    return {
        "cycle": "2026",
        "as_of_date": "2026-04-20",
        "target_schools": ["HKU", "NUS"],
        "target_program": "MSCS",
        "official_status_by_school": {"NUS": "official_found", "HKU": "predicted"},
        "official_records": [],
        "case_records": [],
        "case_patterns": [],
        "forecast_signals": [{"school": "HKU", "insight": "x", "confidence": 0.5, "basis": "b", "reason": "r"}],
        "evidence_levels": {},
        "official_confidence": 0.7,
        "case_confidence": 0.6,
        "cache_hit_count": 0,
        "prediction_used": True,
    }


def test_evaluate_returns_ranked_recommendations() -> None:
    service = StrategicAdmissionsService()
    profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 3.6},
        language_scores={"ielts": 7.0},
        experiences=["data science project"],
    )
    report = service.evaluate(profile, _intel())
    assert report.ranking_order
    assert len(report.recommendations) == 2
    for item in report.recommendations:
        assert item.evidence
        assert item.semantic_breakdown.get("method") == "fake_token_overlap"
