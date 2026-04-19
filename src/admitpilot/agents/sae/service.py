"""SAE 业务服务实现。"""

from __future__ import annotations

import json

from admitpilot.agents.sae.prompts import SYSTEM_PROMPT
from admitpilot.agents.sae.schemas import ProgramRecommendation, StrategicReport
from admitpilot.core.schemas import AIEAgentOutput, UserProfile
from admitpilot.platform.llm.qwen import QwenClient


class StrategicAdmissionsService:
    """负责候选项目评估与风险排序。"""

    SUPPORTED_SCHOOLS = ("NUS", "NTU", "HKU", "CUHK", "HKUST")
    MODEL_BREAKDOWN = {"rule": 0.45, "semantic": 0.35, "risk": 0.20}

    def __init__(self, llm_client: QwenClient | None = None) -> None:
        self.llm_client = llm_client or QwenClient()

    def evaluate(self, user_profile: UserProfile, intelligence: AIEAgentOutput) -> StrategicReport:
        """输出分层推荐、优劣势和差距分析。"""
        target_schools = self._resolve_target_schools(
            intelligence=intelligence, user_profile=user_profile
        )
        target_program = intelligence.get("target_program", user_profile.major_interest or "MSCS")
        recommendations = [
            self._build_recommendation(
                school=school,
                target_program=target_program,
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
            f"完成 {len(recommendations)} 个项目评估，"
            f"官方未完全发布学校数={predicted_count}，输出风险感知排序。"
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
        normalized = [item.upper() for item in schools if item.upper() in self.SUPPORTED_SCHOOLS]
        return normalized or list(self.SUPPORTED_SCHOOLS)

    def _build_recommendation(
        self,
        school: str,
        target_program: str,
        user_profile: UserProfile,
        intelligence: AIEAgentOutput,
    ) -> ProgramRecommendation:
        rule_score = self._rule_match_score(
            user_profile=user_profile, intelligence=intelligence, school=school
        )
        semantic_score = self._semantic_match_score(
            user_profile=user_profile,
            target_program=target_program,
            school=school,
        )
        risk_score = self._risk_score(intelligence=intelligence, school=school)
        overall_score = (
            self.MODEL_BREAKDOWN["rule"] * rule_score
            + self.MODEL_BREAKDOWN["semantic"] * semantic_score
            + self.MODEL_BREAKDOWN["risk"] * (1 - risk_score)
        )
        tier = self._tier_from_score(overall_score=overall_score)
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
            ),
        )

    def _rule_match_score(
        self, user_profile: UserProfile, intelligence: AIEAgentOutput, school: str
    ) -> float:
        """规则匹配打分骨架。

        TODO: 接入可配置规则引擎（GPA/语言/先修课/硬门槛）。
        """
        gpa = float(user_profile.academic_metrics.get("gpa", 3.5))
        lang = float(user_profile.language_scores.get("ielts", 7.0))
        base = min(1.0, (gpa / 4.0) * 0.7 + (lang / 9.0) * 0.3)
        status = intelligence.get("official_status_by_school", {}).get(school, "predicted")
        if status != "official_found":
            base -= 0.05
        return max(0.0, min(base, 1.0))

    def _semantic_match_score(
        self, user_profile: UserProfile, target_program: str, school: str
    ) -> float:
        """语义匹配打分骨架。

        TODO: 用 embedding 检索与课程语义匹配替换该占位逻辑。
        """
        profile_signal = (
            f"{user_profile.major_interest} {' '.join(user_profile.experiences)}".lower()
        )
        school_signal = f"{school} {target_program}".lower()
        overlap = sum(
            1 for token in ("cs", "ai", "data", "system", "research") if token in profile_signal
        )
        school_bias = 0.05 if "hku" in school_signal else 0.0
        return max(0.25, min(0.9, 0.35 + overlap * 0.08 + school_bias))

    def _risk_score(self, intelligence: AIEAgentOutput, school: str) -> float:
        """风险打分骨架，数值越高风险越高。"""
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
        self, school: str, rule_score: float, semantic_score: float, risk_score: float
    ) -> list[str]:
        return [
            f"{school} 规则匹配得分={rule_score:.2f}",
            f"语义契合得分={semantic_score:.2f}",
            f"风险评估得分={risk_score:.2f}",
        ]

    def _summarize_strength_weakness(
        self, user_profile: UserProfile
    ) -> tuple[list[str], list[str]]:
        strengths = ["申请方向明确"]
        if user_profile.experiences:
            strengths.append("经历素材可形成证据链")
        weaknesses = ["高竞争项目仍需更强差异化表达"]
        if not user_profile.language_scores:
            weaknesses.append("语言成绩信息不完整")
        return strengths, weaknesses

    def _derive_gap_actions(
        self, user_profile: UserProfile, recommendations: list[ProgramRecommendation]
    ) -> list[str]:
        """差距分析骨架。

        TODO: 接入按学校项目的结构化 gap taxonomy。
        """
        actions = [
            "补齐项目契合证据（课程/项目/研究目标映射）",
            "准备 2-3 个可量化成果用于文书与面试",
        ]
        if not user_profile.language_scores:
            actions.append("尽快补充语言考试计划与目标分数")
        if any(item.tier == "reach" for item in recommendations):
            actions.append("为冲刺项目准备替代叙事版本与推荐顺序预案")
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
                "major_interest": user_profile.major_interest,
                "target_schools": user_profile.target_schools,
                "target_programs": user_profile.target_programs,
                "academic_metrics": user_profile.academic_metrics,
                "language_scores": user_profile.language_scores,
                "experiences": user_profile.experiences,
                "risk_preference": user_profile.risk_preference,
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
                "请基于输入生成 JSON。",
                (
                    '返回格式：{"summary":"...","strengths":["..."],"weaknesses":["..."],'
                    '"gap_actions":["..."],"reasons_by_school":{"NUS":["..."]}}'
                ),
                "不要输出 markdown。",
                json.dumps(payload, ensure_ascii=False, default=str),
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
        refined_summary = str(result.get("summary", "")).strip() or summary
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
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := str(item).strip())]
