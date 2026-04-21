from pathlib import Path

from admitpilot.agents.sae.rules import load_program_rules
from admitpilot.agents.sae.scoring import RuleScorer
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
        "evidence_levels": {},
        "official_confidence": 0.8,
        "case_confidence": 0.6,
        "cache_hit_count": 0,
        "prediction_used": False,
    }


def test_rule_scorer_penalizes_hard_threshold_miss() -> None:
    rules = load_program_rules(Path("data/program_rules"))
    rule = rules["NUS:MCOMP_CS"]
    scorer = RuleScorer()
    profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 3.0},
        language_scores={"ielts": 7.0},
        experiences=["software engineering internship"],
    )
    result = scorer.score(
        user_profile=profile,
        intelligence=_intel(True),
        school="NUS",
        program="MCOMP_CS",
        rule=rule,
    )
    assert result.breakdown.get("hard_gpa_gap", 0.0) < 0
    assert "hard_gpa_gap" in result.notes


def test_rule_scorer_rewards_background_alignment() -> None:
    rules = load_program_rules(Path("data/program_rules"))
    rule = rules["NUS:MCOMP_CS"]
    scorer = RuleScorer()
    profile = UserProfile(
        major_interest="Computer Science",
        academic_metrics={"gpa": 3.8},
        language_scores={"ielts": 7.5},
        experiences=["computer science research project"],
    )
    result = scorer.score(
        user_profile=profile,
        intelligence=_intel(True),
        school="NUS",
        program="MCOMP_CS",
        rule=rule,
    )
    assert result.breakdown.get("background_alignment", 0.0) > 0
    assert "background_alignment" in result.notes
