"""Deterministic rule scoring for SAE."""

from __future__ import annotations

from dataclasses import dataclass

from admitpilot.agents.sae.rules import ProgramRule
from admitpilot.core.schemas import AIEAgentOutput, UserProfile


@dataclass(frozen=True)
class RuleScoreResult:
    score: float
    breakdown: dict[str, float]
    notes: list[str]


class RuleScorer:
    """Compute explainable rule_score from YAML rules + profile + AIE signals."""

    def score(
        self,
        *,
        user_profile: UserProfile,
        intelligence: AIEAgentOutput,
        school: str,
        program: str,
        rule: ProgramRule | None,
    ) -> RuleScoreResult:
        gpa = float(user_profile.academic_metrics.get("gpa", 3.5))
        ielts = float(user_profile.language_scores.get("ielts", 7.0))
        base = min(1.0, (gpa / 4.0) * 0.7 + (ielts / 9.0) * 0.3)
        breakdown: dict[str, float] = {"base_profile": base}
        notes: list[str] = []

        if rule is None:
            breakdown["missing_rule_file"] = -0.05
            base -= 0.05
            notes.append("missing_rule_file")

        status = intelligence.get("official_status_by_school", {}).get(school, "predicted")
        if status != "official_found":
            breakdown["official_incomplete"] = -0.05
            base -= 0.05
            notes.append("official_incomplete")

        if rule is not None:
            hard_gpa = float(rule.hard_thresholds.get("gpa_min", 0.0))
            hard_ielts = float(rule.hard_thresholds.get("ielts_min", 0.0))
            if gpa and hard_gpa and gpa < hard_gpa:
                breakdown["hard_gpa_gap"] = -0.25
                base -= 0.25
                notes.append("hard_gpa_gap")
            if ielts and hard_ielts and ielts < hard_ielts:
                breakdown["hard_ielts_gap"] = -0.2
                base -= 0.2
                notes.append("hard_ielts_gap")
            if not ielts:
                penalty = float(rule.missing_input_penalties.get("ielts", 0.05))
                breakdown["missing_ielts"] = -penalty
                base -= penalty
                notes.append("missing_ielts")

            profile_text = (
                f"{user_profile.major_interest} {' '.join(user_profile.experiences)}"
            ).lower()
            has_background_match = any(
                token.lower() in profile_text for token in rule.recommended_backgrounds
            )
            if has_background_match:
                breakdown["background_alignment"] = 0.08
                base += 0.08
                notes.append("background_alignment")
            else:
                breakdown["background_mismatch"] = -0.06
                base -= 0.06
                notes.append("background_mismatch")

        score = max(0.0, min(base, 1.0))
        breakdown["final"] = score
        return RuleScoreResult(score=score, breakdown=breakdown, notes=notes)
