from admitpilot.agents.sae.service import StrategicAdmissionsService
from admitpilot.core.schemas import AIEAgentOutput, UserProfile


def _intel(official: bool) -> AIEAgentOutput:
    status = "official_found" if official else "predicted"
    return {
        "cycle": "2026",
        "as_of_date": "2026-04-20",
        "target_schools": ["NUS"],
        "target_program": "MCOMP_CS",
        "official_status_by_school": {"NUS": status},
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


def test_recommendation_includes_evidence_and_aie_citations() -> None:
    service = StrategicAdmissionsService()
    profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 3.8},
        language_scores={"ielts": 7.0},
        experiences=["computer science research"],
    )
    report = service.evaluate(profile, _intel(True))
    rec = next(r for r in report.recommendations if r.school == "NUS")
    assert rec.evidence
    assert any("AIE:official_status_by_school" in item for item in rec.evidence)
    assert any("rule_breakdown:" in item for item in rec.evidence)
    assert any("semantic:" in item for item in rec.evidence)
    assert isinstance(rec.gaps, list)
    assert isinstance(rec.risk_flags, list)
    assert isinstance(rec.missing_inputs, list)


def test_gaps_when_rule_hard_fail() -> None:
    service = StrategicAdmissionsService()
    profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 3.0},
        language_scores={"ielts": 7.0},
        experiences=["computer science"],
    )
    report = service.evaluate(profile, _intel(True))
    rec = next(r for r in report.recommendations if r.school == "NUS")
    assert any("GPA" in gap for gap in rec.gaps)
