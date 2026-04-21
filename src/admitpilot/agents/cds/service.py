"""CDS 业务服务实现。"""

from __future__ import annotations

from typing import Any

from admitpilot.agents.cds.consistency import check_consistency
from admitpilot.agents.cds.facts import build_fact_slots
from admitpilot.agents.cds.schemas import (
    ConsistencyIssue,
    DocumentDraft,
    DocumentSupportPack,
    InterviewCue,
    NarrativeFactSlot,
)
from admitpilot.agents.cds.templates import build_cv_outline, build_sop_outline
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput
from admitpilot.core.user_artifacts import UserArtifactsBundle, parse_user_artifacts


class CoreDocumentService:
    """负责文书叙事与面试素材生成。"""

    def build_support_pack(
        self,
        strategy: SAEAgentOutput,
        timeline: DTAAgentOutput,
        user_artifacts_payload: list[dict[str, str | bool]] | None = None,
    ) -> DocumentSupportPack:
        """根据策略和时间线输出文书与面试支持包。"""
        recommendations = strategy.get("recommendations", [])
        schools = [str(item.get("school", "")) for item in recommendations if item.get("school")]
        school_scope = schools or ["NUS", "NTU", "HKU", "CUHK", "HKUST"]
        artifacts = self._load_user_artifacts(user_artifacts_payload)
        fact_slots = self._build_fact_slots(
            strategy=strategy, timeline=timeline, artifacts=artifacts
        )
        abstain, abstain_reason = self._should_abstain(fact_slots=fact_slots)
        drafts = (
            []
            if abstain
            else self._build_document_drafts(
                schools=school_scope,
                fact_slots=fact_slots,
                strategy=strategy,
                timeline=timeline,
            )
        )
        interview_cues = self._build_interview_cues(
            recommendations=recommendations, timeline=timeline
        )
        issues = self._check_cross_document_consistency(drafts=drafts)
        if abstain:
            issues.insert(
                0,
                ConsistencyIssue(
                    severity="high",
                    message=f"核心证据缺失，CDS abstain: {abstain_reason}",
                    impacted_documents=["sop", "cv", "interview"],
                ),
            )
        checklist = self._build_review_checklist(issues=issues)
        if abstain:
            checklist.insert(0, "先补齐核心证据（project/research + source_ref）再生成正式草稿")
        return DocumentSupportPack(
            drafts=drafts,
            interview_cues=interview_cues,
            consistency_issues=issues,
            review_checklist=checklist,
        )

    def _build_fact_slots(
        self,
        strategy: SAEAgentOutput,
        timeline: DTAAgentOutput,
        artifacts: UserArtifactsBundle,
    ) -> list[NarrativeFactSlot]:
        return build_fact_slots(artifacts=artifacts, strategy=strategy, timeline=timeline)

    def _load_user_artifacts(
        self, payload: list[dict[str, str | bool]] | None
    ) -> UserArtifactsBundle:
        if not payload:
            return UserArtifactsBundle()
        return parse_user_artifacts(payload)

    def _should_abstain(self, fact_slots: list[NarrativeFactSlot]) -> tuple[bool, str]:
        required = {"motivation_core", "execution_proof"}
        status_by_slot = {item.slot_id: item.status for item in fact_slots}
        missing = sorted(key for key in required if status_by_slot.get(key) == "missing")
        if missing:
            return True, f"missing_core_slots={','.join(missing)}"
        return False, ""

    def _build_document_drafts(
        self,
        schools: list[str],
        fact_slots: list[NarrativeFactSlot],
        strategy: SAEAgentOutput,
        timeline: DTAAgentOutput,
    ) -> list[DocumentDraft]:
        drafts: list[DocumentDraft] = []
        for school in schools:
            sop_outline, sop_risks = build_sop_outline(
                school=school, strategy=strategy, timeline=timeline, fact_slots=fact_slots
            )
            drafts.append(
                DocumentDraft(
                    document_type="sop",
                    target_school=school,
                    version="v0",
                    content_outline=sop_outline,
                    fact_slots=fact_slots,
                    risks=sop_risks,
                    review_status="needs_human_review",
                )
            )
        cv_outline, cv_risks = build_cv_outline(
            strategy=strategy, timeline=timeline, fact_slots=fact_slots
        )
        drafts.append(
            DocumentDraft(
                document_type="cv",
                target_school="shared",
                version="v0",
                content_outline=cv_outline,
                fact_slots=fact_slots,
                risks=cv_risks,
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
        has_cv = any(item.document_type == "cv" for item in drafts)
        has_sop = any(item.document_type == "sop" for item in drafts)
        issues: list[ConsistencyIssue] = check_consistency(drafts)
        if not has_cv or not has_sop:
            issues.append(
                ConsistencyIssue(
                    severity="high",
                    message="核心文档缺失，无法进行跨文档一致性审查",
                    impacted_documents=["sop", "cv"],
                )
            )
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
