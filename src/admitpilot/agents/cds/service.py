"""CDS 业务服务实现。"""

from __future__ import annotations

from typing import Any

from admitpilot.agents.cds.schemas import (
    ConsistencyIssue,
    DocumentDraft,
    DocumentSupportPack,
    InterviewCue,
    NarrativeFactSlot,
)
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput


class CoreDocumentService:
    """负责文书叙事与面试素材生成。"""

    def build_support_pack(
        self, strategy: SAEAgentOutput, timeline: DTAAgentOutput
    ) -> DocumentSupportPack:
        """根据策略和时间线输出文书与面试支持包。"""
        recommendations = strategy.get("recommendations", [])
        schools = [str(item.get("school", "")) for item in recommendations if item.get("school")]
        school_scope = schools or ["NUS", "NTU", "HKU", "CUHK", "HKUST"]
        fact_slots = self._build_fact_slots(strategy=strategy, timeline=timeline)
        drafts = self._build_document_drafts(schools=school_scope, fact_slots=fact_slots)
        interview_cues = self._build_interview_cues(
            recommendations=recommendations, timeline=timeline
        )
        issues = self._check_cross_document_consistency(drafts=drafts)
        checklist = self._build_review_checklist(issues=issues)
        return DocumentSupportPack(
            drafts=drafts,
            interview_cues=interview_cues,
            consistency_issues=issues,
            review_checklist=checklist,
        )

    def _build_fact_slots(
        self, strategy: SAEAgentOutput, timeline: DTAAgentOutput
    ) -> list[NarrativeFactSlot]:
        """事实槽位构建骨架。

        TODO: 接入用户真实经历解析与证据引用系统。
        """
        ranking = strategy.get("ranking_order", [])
        milestones = timeline.get("milestones", [])
        return [
            NarrativeFactSlot(
                slot_id="motivation_core",
                value="申请动机与长期职业目标一致",
                source="user_profile",
                verified=False,
            ),
            NarrativeFactSlot(
                slot_id="program_fit",
                value=f"优先项目顺序: {', '.join(ranking[:3]) or '待补充'}",
                source="sae_ranking",
                verified=False,
            ),
            NarrativeFactSlot(
                slot_id="execution_proof",
                value=f"关键里程碑数量={len(milestones)}",
                source="dta_milestones",
                verified=False,
            ),
        ]

    def _build_document_drafts(
        self, schools: list[str], fact_slots: list[NarrativeFactSlot]
    ) -> list[DocumentDraft]:
        drafts: list[DocumentDraft] = []
        for school in schools:
            drafts.append(
                DocumentDraft(
                    document_type="sop",
                    target_school=school,
                    version="v0",
                    content_outline=["动机与问题意识", "能力证据", "课程与资源匹配", "职业目标"],
                    fact_slots=fact_slots,
                    risks=["动机表述过泛", "项目匹配证据不足"],
                    review_status="needs_human_review",
                )
            )
        drafts.append(
            DocumentDraft(
                document_type="cv",
                target_school="shared",
                version="v0",
                content_outline=["教育背景", "项目经历", "实习与科研", "技能与成果"],
                fact_slots=fact_slots,
                risks=["量化指标不足", "与 SoP 事实不一致"],
                review_status="needs_human_review",
            )
        )
        return drafts

    def _build_interview_cues(
        self, recommendations: list[dict[str, Any]], timeline: DTAAgentOutput
    ) -> list[InterviewCue]:
        first_school = "目标项目"
        if recommendations:
            first_school = str(recommendations[0].get("school", first_school))
        weekly_count = len(timeline.get("weekly_plan", []))
        return [
            InterviewCue(
                question="为什么选择这个项目？",
                cue=f"从 {first_school} 的课程与研究资源切入，映射个人目标。",
            ),
            InterviewCue(
                question="你如何证明执行力？",
                cue=f"用 {weekly_count} 周执行板中的里程碑交付证明计划落地能力。",
            ),
        ]

    def _check_cross_document_consistency(
        self, drafts: list[DocumentDraft]
    ) -> list[ConsistencyIssue]:
        """一致性检查骨架。

        TODO: 用事实图和实体对齐做自动化校验。
        """
        issues: list[ConsistencyIssue] = []
        has_cv = any(item.document_type == "cv" for item in drafts)
        has_sop = any(item.document_type == "sop" for item in drafts)
        if not has_cv or not has_sop:
            issues.append(
                ConsistencyIssue(
                    severity="high",
                    message="核心文档缺失，无法进行跨文档一致性审查",
                    impacted_documents=["sop", "cv"],
                )
            )
        for draft in drafts:
            if any(slot.verified is False for slot in draft.fact_slots):
                issues.append(
                    ConsistencyIssue(
                        severity="medium",
                        message=f"{draft.document_type}:{draft.target_school} 存在未核验事实槽位",
                        impacted_documents=[f"{draft.document_type}:{draft.target_school}"],
                    )
                )
                break
        return issues

    def _build_review_checklist(self, issues: list[ConsistencyIssue]) -> list[str]:
        checklist = [
            "核验所有事实槽位与原始证明材料一致",
            "确认 SoP/CV/面试话术中的时间线一致",
            "检查每所学校版本是否体现差异化项目匹配",
        ]
        if issues:
            checklist.insert(0, "优先解决一致性告警后再进入下一轮润色")
        return checklist
