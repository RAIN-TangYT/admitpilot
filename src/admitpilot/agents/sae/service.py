"""SAE 业务服务实现。"""

from __future__ import annotations

from admitpilot.agents.sae.schemas import ProgramRecommendation, StrategicReport
from admitpilot.core.schemas import AIEAgentOutput, UserProfile


class StrategicAdmissionsService:
    """负责候选项目评估与风险排序。"""

    def evaluate(self, user_profile: UserProfile, intelligence: AIEAgentOutput) -> StrategicReport:
        """输出分层推荐、优劣势和差距分析。"""
        strengths = ["学术基础稳定", "申请方向明确"]
        weaknesses = ["高难度项目竞争激烈"]
        gaps = ["需进一步强化差异化叙事与项目契合证据"]
        recommendations = [
            ProgramRecommendation(
                school="Sample Top School",
                program=user_profile.major_interest or "Computer Science",
                tier="reach",
                risk_score=0.78,
                reason="项目竞争强，建议作为冲刺院校。",
            ),
            ProgramRecommendation(
                school="Sample Core School",
                program=user_profile.major_interest or "Computer Science",
                tier="match",
                risk_score=0.52,
                reason="背景与历史录取样本较匹配。",
            ),
            ProgramRecommendation(
                school="Sample Stable School",
                program=user_profile.major_interest or "Computer Science",
                tier="safety",
                risk_score=0.33,
                reason="要求匹配度高，可作为保底组合。",
            ),
        ]
        summary = (
            f"基于 AIE 官方更新 {intelligence['official_update_count']} 条、"
            f"案例样本 {intelligence['case_memory_count']} 条，"
            f"官方状态 {intelligence['official_status']}，完成分层推荐与风险排序。"
        )
        return StrategicReport(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            gaps=gaps,
            recommendations=recommendations,
        )
