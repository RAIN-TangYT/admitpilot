"""SAE 业务服务实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

from admitpilot.agents.sae.prompts import SYSTEM_PROMPT
from admitpilot.agents.sae.rules import ProgramRule, load_program_rules
from admitpilot.agents.sae.schemas import ProgramRecommendation, StrategicReport
from admitpilot.agents.sae.scoring import RuleScorer, RuleScoreResult
from admitpilot.agents.sae.semantic import (
    SemanticMatcher,
    SemanticMatchResult,
    build_semantic_matcher,
)
from admitpilot.config import AdmitPilotSettings
from admitpilot.core.english import english_items, english_or
from admitpilot.core.schemas import AIEAgentOutput, UserProfile
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG, AdmissionsCatalog
from admitpilot.platform.llm.openai import OpenAIClient


class StrategicAdmissionsService:
    """Evaluate candidate programs and rank risk-aware options."""

    MODEL_BREAKDOWN = {"rule": 0.45, "semantic": 0.35, "risk": 0.20}
    _DEFAULT_RULES_DIR = Path(__file__).resolve().parents[4] / "data" / "program_rules"

    def __init__(
        self,
        llm_client: OpenAIClient | None = None,
        settings: AdmitPilotSettings | None = None,
        catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG,
        rules: dict[str, ProgramRule] | None = None,
        semantic_matcher: SemanticMatcher | None = None,
    ) -> None:
        self.llm_client = llm_client or OpenAIClient(settings=AdmitPilotSettings(run_mode="test"))
        self.settings = settings
        self.catalog = catalog
        self.rules = rules if rules is not None else load_program_rules(self._DEFAULT_RULES_DIR)
        self.rule_scorer = RuleScorer()
        matcher_kind = cast(
            Literal["fake", "embedding"],
            settings.semantic_matcher_kind if settings is not None else "fake",
        )
        self.semantic_matcher: SemanticMatcher = (
            semantic_matcher
            if semantic_matcher is not None
            else build_semantic_matcher(
                matcher_kind,
                llm_client=self.llm_client,
                embedding_model=(
                    settings.openai_embedding_model
                    if settings is not None
                    else self.llm_client.embedding_model
                ),
            )
        )

    def evaluate(self, user_profile: UserProfile, intelligence: AIEAgentOutput) -> StrategicReport:
        """Return tiered recommendations, strengths, weaknesses, and gap actions."""
        target_schools = self._resolve_target_schools(
            intelligence=intelligence, user_profile=user_profile
        )
        target_program_by_school = self._resolve_target_programs_by_school(
            intelligence=intelligence,
            user_profile=user_profile,
            target_schools=target_schools,
        )
        recommendations = [
            self._build_recommendation(
                school=school,
                target_program=target_program_by_school[school],
                user_profile=user_profile,
                intelligence=intelligence,
            )
            for school in target_schools
        ]
        recommendations.sort(key=lambda item: item.overall_score, reverse=True)
        ranking_order = [f"{item.school}:{item.program}" for item in recommendations]
        strengths, weaknesses = self._summarize_strength_weakness(user_profile=user_profile)
        gap_actions = self._derive_gap_actions(
            user_profile=user_profile, recommendations=recommendations
        )
        official_status = intelligence.get("official_status_by_school", {})
        predicted_count = sum(
            1 for status in official_status.values() if status != "official_found"
        )
        summary = (
            f"Evaluated {len(recommendations)} target programs; "
            f"{predicted_count} schools do not yet have complete official release coverage. "
            "Returned a risk-aware ranking."
        )
        summary, strengths, weaknesses, gap_actions, recommendations = self._llm_refine_report(
            user_profile=user_profile,
            intelligence=intelligence,
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            gap_actions=gap_actions,
            recommendations=recommendations,
        )
        return StrategicReport(
            summary=summary,
            model_breakdown=dict(self.MODEL_BREAKDOWN),
            strengths=strengths,
            weaknesses=weaknesses,
            gap_actions=gap_actions,
            recommendations=recommendations,
            ranking_order=ranking_order,
        )

    def _resolve_target_schools(
        self, intelligence: AIEAgentOutput, user_profile: UserProfile
    ) -> list[str]:
        schools = intelligence.get("target_schools", [])
        if not schools:
            schools = user_profile.target_schools
        return self.catalog.normalize_school_scope(schools)

    def _resolve_target_programs_by_school(
        self,
        intelligence: AIEAgentOutput,
        user_profile: UserProfile,
        target_schools: list[str],
    ) -> dict[str, str]:
        portfolio = self.catalog.default_program_portfolio(target_schools)
        explicit_mapping = intelligence.get("target_program_by_school", {})
        if isinstance(explicit_mapping, dict):
            for raw_school, raw_program in explicit_mapping.items():
                school = self.catalog.normalize_school_code(str(raw_school))
                program = self.catalog.normalize_program_code(str(raw_program))
                if school is None or program is None:
                    continue
                if school in target_schools and self.catalog.is_supported_program(school, program):
                    portfolio[school] = program
        explicit_program = intelligence.get("target_program", "")
        normalized_explicit = self.catalog.normalize_program_code(str(explicit_program))
        if normalized_explicit is not None:
            for school in target_schools:
                if self.catalog.is_supported_program(school, normalized_explicit):
                    portfolio[school] = normalized_explicit
        profile_programs = [
            normalized
            for item in user_profile.target_programs
            if (normalized := self.catalog.normalize_program_code(item)) is not None
        ]
        for school in target_schools:
            if school in portfolio:
                continue
            for program in profile_programs:
                if self.catalog.is_supported_program(school, program):
                    portfolio[school] = program
                    break
        return {
            school: portfolio.get(school) or self.catalog.supported_programs(school)[0]
            for school in target_schools
        }

    def _build_recommendation(
        self,
        school: str,
        target_program: str,
        user_profile: UserProfile,
        intelligence: AIEAgentOutput,
    ) -> ProgramRecommendation:
        rule = self.rules.get(f"{school}:{target_program}")
        rule_result = self.rule_scorer.score(
            user_profile=user_profile,
            intelligence=intelligence,
            school=school,
            program=target_program,
            rule=rule,
        )
        rule_score = rule_result.score
        semantic_result = self.semantic_matcher.match(
            user_profile, school=school, program=target_program
        )
        semantic_score = semantic_result.score
        risk_score = self._risk_score(intelligence=intelligence, school=school)
        overall_score = (
            self.MODEL_BREAKDOWN["rule"] * rule_score
            + self.MODEL_BREAKDOWN["semantic"] * semantic_score
            + self.MODEL_BREAKDOWN["risk"] * (1 - risk_score)
        )
        tier = self._tier_from_score(overall_score=overall_score)
        evidence, gaps, risk_flags, missing_inputs = self._build_explanation_fields(
            school=school,
            target_program=target_program,
            user_profile=user_profile,
            intelligence=intelligence,
            rule=rule,
            rule_result=rule_result,
            semantic_result=semantic_result,
            tier=tier,
        )
        return ProgramRecommendation(
            school=school,
            program=target_program,
            tier=tier,
            rule_score=rule_score,
            semantic_score=semantic_score,
            risk_score=risk_score,
            overall_score=overall_score,
            reasons=self._build_reasons(
                school=school,
                rule_score=rule_score,
                semantic_score=semantic_score,
                risk_score=risk_score,
                rule_notes=rule_result.notes,
                tier=tier,
            ),
            rule_breakdown=rule_result.breakdown,
            rule_notes=rule_result.notes,
            evidence=evidence,
            gaps=gaps,
            risk_flags=risk_flags,
            missing_inputs=missing_inputs,
            semantic_breakdown=dict(semantic_result.breakdown),
        )

    def _build_explanation_fields(
        self,
        school: str,
        target_program: str,
        user_profile: UserProfile,
        intelligence: AIEAgentOutput,
        rule: ProgramRule | None,
        rule_result: RuleScoreResult,
        semantic_result: SemanticMatchResult,
        tier: str,
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        evidence: list[str] = []
        gaps: list[str] = []
        risk_flags: list[str] = []
        missing_inputs: list[str] = []
        status = intelligence.get("official_status_by_school", {}).get(school, "predicted")
        evidence.append(f"AIE:official_status_by_school[{school}]={status}")
        ev_level = intelligence.get("evidence_levels", {}).get(school)
        if ev_level:
            evidence.append(f"AIE:evidence_levels[{school}]={ev_level}")
        if intelligence.get("prediction_used"):
            evidence.append("AIE:prediction_used=true")
        for key, value in rule_result.breakdown.items():
            if key != "final":
                evidence.append(f"rule_breakdown:{key}={value}")
        if rule_result.notes:
            evidence.append(f"rule_notes:{','.join(rule_result.notes)}")

        method = semantic_result.breakdown.get("method", "semantic")
        evidence.append(f"semantic:method={method},score={semantic_result.score:.3f}")
        matched = semantic_result.breakdown.get("matched_keywords")
        if isinstance(matched, list) and matched:
            evidence.append(f"semantic:matched_keywords={','.join(str(x) for x in matched)}")

        evidence.append(f"tier={tier} from overall_score pipeline")

        if "hard_gpa_gap" in rule_result.notes:
            gaps.append(
                "GPA is below the hard rule threshold; add academic proof or improve GPA."
            )
        if "hard_ielts_gap" in rule_result.notes or "missing_ielts" in rule_result.notes:
            gaps.append("English test evidence is missing or below the rule threshold.")
        if "background_mismatch" in rule_result.notes:
            gaps.append("Experience narrative is not aligned with preferred background keywords.")
        if "missing_rule_file" in rule_result.notes:
            gaps.append(
                f"Missing YAML rule file for {school}:{target_program}; "
                "rule score uses a conservative fallback."
            )

        if rule is not None:
            risk_flags.extend(rule.risk_flags)
        if status != "official_found":
            risk_flags.append("official_incomplete")
        if intelligence.get("prediction_used"):
            risk_flags.append("upstream_prediction_used")

        if not user_profile.language_scores:
            missing_inputs.append("language_scores")
        if not user_profile.academic_metrics.get("gpa"):
            missing_inputs.append("gpa")
        if not user_profile.experiences:
            missing_inputs.append("experiences")

        return evidence, gaps, risk_flags, missing_inputs

    def _risk_score(self, intelligence: AIEAgentOutput, school: str) -> float:
        """Risk score skeleton. Higher values mean higher risk."""
        status = intelligence.get("official_status_by_school", {}).get(school, "predicted")
        forecast_count = len(intelligence.get("forecast_signals", []))
        if status == "official_found":
            return 0.42 + min(forecast_count * 0.01, 0.08)
        return 0.58 + min(forecast_count * 0.01, 0.12)

    def _tier_from_score(self, overall_score: float) -> str:
        if overall_score >= 0.72:
            return "match"
        if overall_score >= 0.6:
            return "reach"
        return "safety"

    def _build_reasons(
        self,
        school: str,
        rule_score: float,
        semantic_score: float,
        risk_score: float,
        rule_notes: list[str],
        tier: str,
    ) -> list[str]:
        notes = f"rule_notes={','.join(rule_notes)}" if rule_notes else "rule_notes=baseline"
        return [
            f"{school} tier={tier} (overall=0.45*rule+0.35*semantic+0.20*(1-risk))",
            f"{school} rule match score={rule_score:.2f}",
            notes,
            f"semantic fit score={semantic_score:.2f}",
            f"risk score={risk_score:.2f}",
        ]

    def _summarize_strength_weakness(
        self, user_profile: UserProfile
    ) -> tuple[list[str], list[str]]:
        strengths = ["Application direction is clear."]
        if user_profile.experiences:
            strengths.append("Experience materials can form an evidence chain.")
        weaknesses = ["High-competition programs still need sharper differentiation."]
        if not user_profile.language_scores:
            weaknesses.append("English test evidence is incomplete.")
        return strengths, weaknesses

    def _derive_gap_actions(
        self, user_profile: UserProfile, recommendations: list[ProgramRecommendation]
    ) -> list[str]:
        """Gap-action skeleton.

        TODO: Add school/program-specific gap taxonomy.
        """
        actions = [
            "Add program-fit evidence that maps courses, projects, and research goals.",
            "Prepare 2-3 quantified outcomes for documents and interviews.",
        ]
        if not user_profile.language_scores:
            actions.append("Add an English test plan and target score as soon as possible.")
        if any(item.tier == "reach" for item in recommendations):
            actions.append(
                "Prepare alternate narratives and priority-order backups for reach programs."
            )
        return actions

    def _llm_refine_report(
        self,
        user_profile: UserProfile,
        intelligence: AIEAgentOutput,
        summary: str,
        strengths: list[str],
        weaknesses: list[str],
        gap_actions: list[str],
        recommendations: list[ProgramRecommendation],
    ) -> tuple[str, list[str], list[str], list[str], list[ProgramRecommendation]]:
        if not self.llm_client.enabled:
            return summary, strengths, weaknesses, gap_actions, recommendations
        payload = {
            "profile": {
                "major_interest": english_or(user_profile.major_interest, "unspecified"),
                "target_schools": user_profile.target_schools,
                "target_programs": user_profile.target_programs,
                "academic_metrics": user_profile.academic_metrics,
                "language_scores": user_profile.language_scores,
                "experiences": [
                    english_or(item, "Applicant experience evidence")
                    for item in user_profile.experiences
                ],
                "risk_preference": english_or(user_profile.risk_preference, "balanced"),
            },
            "intelligence": {
                "target_program": intelligence.get("target_program", ""),
                "official_status_by_school": intelligence.get("official_status_by_school", {}),
                "forecast_signals": intelligence.get("forecast_signals", []),
            },
            "recommendations": [
                {
                    "school": item.school,
                    "program": item.program,
                    "tier": item.tier,
                    "rule_score": round(item.rule_score, 3),
                    "semantic_score": round(item.semantic_score, 3),
                    "risk_score": round(item.risk_score, 3),
                    "overall_score": round(item.overall_score, 3),
                    "reasons": item.reasons,
                }
                for item in recommendations
            ],
        }
        prompt = "\n".join(
            [
                (
                    "Generate JSON in English only. "
                    "Do not output markdown or any non-English narrative."
                ),
                (
                    'Return format: {"summary":"...","strengths":["..."],'
                    '"weaknesses":["..."],"gap_actions":["..."],'
                    '"reasons_by_school":{"NUS":["..."]}}'
                ),
                json.dumps(payload, ensure_ascii=True, default=str),
            ]
        )
        try:
            result = self.llm_client.chat_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0,
            )
        except RuntimeError:
            return summary, strengths, weaknesses, gap_actions, recommendations
        refined_summary = english_or(result.get("summary"), summary)
        refined_strengths = self._normalize_text_list(result.get("strengths")) or strengths
        refined_weaknesses = self._normalize_text_list(result.get("weaknesses")) or weaknesses
        refined_gap_actions = self._normalize_text_list(result.get("gap_actions")) or gap_actions
        reasons_by_school = result.get("reasons_by_school", {})
        if isinstance(reasons_by_school, dict):
            for item in recommendations:
                reasons = self._normalize_text_list(reasons_by_school.get(item.school))
                if reasons:
                    item.reasons = reasons
        return (
            refined_summary,
            refined_strengths,
            refined_weaknesses,
            refined_gap_actions,
            recommendations,
        )

    def _normalize_text_list(self, value: object) -> list[str]:
        return english_items(value)
