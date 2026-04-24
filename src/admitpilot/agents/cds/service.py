"""CDS 业务服务实现。"""

from __future__ import annotations

import json
from typing import Any

from admitpilot.agents.cds.consistency import check_consistency
from admitpilot.agents.cds.facts import build_fact_slots
from admitpilot.agents.cds.prompts import SYSTEM_PROMPT
from admitpilot.agents.cds.schemas import (
    ConsistencyIssue,
    DocumentDraft,
    DocumentSupportPack,
    InterviewCue,
    NarrativeFactSlot,
)
from admitpilot.agents.cds.templates import build_cv_outline, build_sop_outline
from admitpilot.config import AdmitPilotSettings
from admitpilot.core.schemas import DTAAgentOutput, SAEAgentOutput
from admitpilot.core.user_artifacts import UserArtifactsBundle, parse_user_artifacts
from admitpilot.platform.llm.openai import OpenAIClient


class CoreDocumentService:
    """负责文书叙事与面试素材生成。"""

    def __init__(self, llm_client: OpenAIClient | None = None) -> None:
        self.llm_client = llm_client or OpenAIClient(settings=AdmitPilotSettings(run_mode="test"))

    def build_support_pack(
        self,
        strategy: SAEAgentOutput,
        timeline: DTAAgentOutput,
        user_artifacts_payload: list[dict[str, str | bool]] | None = None,
    ) -> DocumentSupportPack:
        """根据策略和时间线输出文书与面试支持包。"""
        if self._missing_upstream_context(strategy=strategy, timeline=timeline):
            return self._build_missing_evidence_pack(strategy=strategy, timeline=timeline)
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
        drafts, interview_cues = self._llm_refine_support_pack(
            strategy=strategy,
            timeline=timeline,
            drafts=drafts,
            interview_cues=interview_cues,
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
        checklist = self._llm_refine_checklist(issues=issues, checklist=checklist)
        return DocumentSupportPack(
            drafts=drafts,
            interview_cues=interview_cues,
            consistency_issues=issues,
            review_checklist=checklist,
        )

    def _missing_upstream_context(
        self, strategy: SAEAgentOutput, timeline: DTAAgentOutput
    ) -> bool:
        has_strategy = bool(strategy.get("recommendations")) and bool(strategy.get("ranking_order"))
        has_timeline = bool(timeline.get("milestones")) and bool(timeline.get("weekly_plan"))
        return not (has_strategy and has_timeline)

    def _build_missing_evidence_pack(
        self, strategy: SAEAgentOutput, timeline: DTAAgentOutput
    ) -> DocumentSupportPack:
        missing_inputs: list[str] = []
        if not strategy.get("recommendations") or not strategy.get("ranking_order"):
            missing_inputs.append("选校策略")
        if not timeline.get("milestones") or not timeline.get("weekly_plan"):
            missing_inputs.append("时间线")
        missing_summary = "、".join(missing_inputs) or "上游上下文"
        issue = ConsistencyIssue(
            severity="high",
            message=f"缺少上游{missing_summary}，当前不生成正式文书草稿与面试材料",
            impacted_documents=["sop", "cv", "interview"],
        )
        checklist = [
            f"先补齐上游{missing_summary}，再生成个性化文书与面试材料",
            "补充可验证的经历事实、项目匹配证据与执行安排",
            "上游结果就绪后重新运行 CDS，避免基于缺证据内容继续润色",
        ]
        interview_cues = [
            InterviewCue(
                question="当前状态",
                cue=f"缺少{missing_summary}，暂不生成正式面试要点。",
            )
        ]
        return DocumentSupportPack(
            drafts=[],
            interview_cues=interview_cues,
            consistency_issues=[issue],
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

    def _llm_refine_support_pack(
        self,
        strategy: SAEAgentOutput,
        timeline: DTAAgentOutput,
        drafts: list[DocumentDraft],
        interview_cues: list[InterviewCue],
    ) -> tuple[list[DocumentDraft], list[InterviewCue]]:
        if not self.llm_client.enabled:
            return drafts, interview_cues
        payload = {
            "ranking_order": strategy.get("ranking_order", []),
            "strengths": strategy.get("strengths", []),
            "weaknesses": strategy.get("weaknesses", []),
            "gap_actions": strategy.get("gap_actions", []),
            "document_instructions": timeline.get("document_instructions", []),
            "drafts": [
                {
                    "document_type": item.document_type,
                    "target_school": item.target_school,
                    "content_outline": item.content_outline,
                    "risks": item.risks,
                }
                for item in drafts
            ],
            "interview_cues": [
                {"question": item.question, "cue": item.cue} for item in interview_cues
            ],
        }
        prompt = "\n".join(
            [
                "请基于输入输出 JSON。",
                (
                    '返回格式：{"drafts":[{"document_type":"sop","target_school":"NUS","content_outline":["..."],"risks":["..."]}],'
                    '"interview_cues":[{"question":"...","cue":"..."}]}'
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
            return drafts, interview_cues
        llm_drafts = result.get("drafts", [])
        if isinstance(llm_drafts, list):
            draft_lookup = {(item.document_type, item.target_school): item for item in drafts}
            for raw in llm_drafts:
                if not isinstance(raw, dict):
                    continue
                key = (
                    str(raw.get("document_type", "")).strip(),
                    str(raw.get("target_school", "")).strip(),
                )
                if key not in draft_lookup:
                    continue
                draft = draft_lookup[key]
                outlines = raw.get("content_outline")
                risks = raw.get("risks")
                if isinstance(outlines, list):
                    normalized_outlines = [text for item in outlines if (text := str(item).strip())]
                    if normalized_outlines:
                        draft.content_outline = normalized_outlines
                if isinstance(risks, list):
                    normalized_risks = [text for item in risks if (text := str(item).strip())]
                    if normalized_risks:
                        draft.risks = normalized_risks
        llm_cues = result.get("interview_cues", [])
        if isinstance(llm_cues, list):
            normalized_cues: list[InterviewCue] = []
            for raw in llm_cues:
                if not isinstance(raw, dict):
                    continue
                question = str(raw.get("question", "")).strip()
                cue = str(raw.get("cue", "")).strip()
                if question and cue:
                    normalized_cues.append(InterviewCue(question=question, cue=cue))
            if normalized_cues:
                interview_cues = normalized_cues
        return drafts, interview_cues

    def _llm_refine_checklist(
        self, issues: list[ConsistencyIssue], checklist: list[str]
    ) -> list[str]:
        if not self.llm_client.enabled:
            return checklist
        payload = {
            "issues": [
                {
                    "severity": item.severity,
                    "message": item.message,
                    "impacted_documents": item.impacted_documents,
                }
                for item in issues
            ],
            "checklist": checklist,
        }
        prompt = "\n".join(
            [
                "请基于输入输出 JSON。",
                '返回格式：{"review_checklist":["..."]}',
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
            return checklist
        llm_checklist = result.get("review_checklist", [])
        if not isinstance(llm_checklist, list):
            return checklist
        normalized = [text for item in llm_checklist if (text := str(item).strip())]
        return normalized or checklist
