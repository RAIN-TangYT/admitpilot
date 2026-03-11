"""CDS 业务服务实现。"""

from __future__ import annotations

from admitpilot.agents.cds.schemas import DocumentBlueprint, DocumentSupportPack, InterviewCue
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput


class CoreDocumentService:
    """负责文书叙事与面试素材生成。"""

    def build_support_pack(self, strategy: SAEAgentOutput, timeline: DTAAgentOutput) -> DocumentSupportPack:
        """根据策略和时间线输出文书与面试支持包。"""
        tiers = strategy.get("tiers", ["match"])
        week_count = timeline.get("week_count", 4)
        blueprints = [
            DocumentBlueprint(
                document_type="statement_of_purpose",
                narrative_focus="以学术问题驱动的成长叙事",
                evidence_points=["研究兴趣演化", "项目实践成果", "目标课程契合"],
                risks=["叙事空泛", "动机与项目匹配不足"],
            ),
            DocumentBlueprint(
                document_type="cv",
                narrative_focus="结果导向的经历排列",
                evidence_points=["量化成果", "技术栈与方法", "团队协作贡献"],
                risks=["项目描述冗长", "关键词与岗位不匹配"],
            ),
        ]
        interview_cues = [
            InterviewCue(question="为什么选择这个项目？", cue=f"围绕 tier={tiers[0]} 项目契合点回答。"),
            InterviewCue(question="你的差异化优势是什么？", cue=f"结合 {week_count} 周计划中的关键交付证明执行力。"),
        ]
        return DocumentSupportPack(blueprints=blueprints, interview_cues=interview_cues)
