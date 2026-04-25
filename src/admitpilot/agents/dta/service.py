"""DTA 业务服务实现。"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from admitpilot.agents.dta.deadlines import apply_deadline_reverse_plan, extract_official_deadlines
from admitpilot.agents.dta.prompts import SYSTEM_PROMPT
from admitpilot.agents.dta.replan import apply_replan
from admitpilot.agents.dta.scheduler import schedule_milestones
from admitpilot.agents.dta.schemas import Milestone, RiskMarker, TimelinePlan, WeekTask
from admitpilot.config import AdmitPilotSettings
from admitpilot.core.english import english_items, english_or
from admitpilot.core.schemas import AIEAgentOutput, SAEAgentOutput
from admitpilot.platform.llm.openai import OpenAIClient


class DynamicTimelineService:
    """Convert strategy output into an executable weekly plan."""

    DEFAULT_WEEKS = 8

    def __init__(self, llm_client: OpenAIClient | None = None) -> None:
        self.llm_client = llm_client or OpenAIClient(settings=AdmitPilotSettings(run_mode="test"))

    def build_plan(
        self,
        strategy: SAEAgentOutput,
        intelligence: AIEAgentOutput,
        constraints: dict[str, Any],
    ) -> TimelinePlan:
        """Build a dynamic execution board from priority and constraint inputs."""
        timezone = str(constraints.get("timezone", "UTC"))
        cycle = str(constraints.get("cycle", "2026"))
        schools = intelligence.get("target_schools", [])
        recommendations = strategy.get("recommendations", [])
        milestone_graph = self._build_milestone_graph(
            strategy=strategy, recommendations=recommendations, schools=schools
        )
        deadlines = extract_official_deadlines(intelligence.get("official_records", []))
        milestone_graph = apply_deadline_reverse_plan(
            milestones=milestone_graph,
            deadlines=deadlines,
            as_of_date=self._resolve_as_of_date(intelligence),
            total_weeks=self._resolve_total_weeks(constraints),
        )
        milestone_graph = schedule_milestones(milestone_graph)
        milestones = self._schedule_milestones(
            milestone_graph=milestone_graph,
            constraints=constraints,
            total_weeks=self._resolve_total_weeks(constraints),
        )
        replan = apply_replan(
            milestones=milestones,
            constraints=constraints,
            total_weeks=self._resolve_total_weeks(constraints),
        )
        weeks = self._build_weekly_plan(
            milestones=replan.milestones,
            total_weeks=self._resolve_total_weeks(constraints),
            schools=schools,
        )
        risk_markers = self._build_risk_markers(
            milestones=replan.milestones,
            official_status_by_school=intelligence.get("official_status_by_school", {}),
        )
        risk_markers.extend(replan.risks)
        if not replan.feasible:
            risk_markers.append(
                RiskMarker(
                    week=1,
                    level="red",
                    message="The current constraints make the schedule infeasible.",
                    mitigation=(
                        "Adjust the start week, unblock critical tasks, "
                        "or reduce the target scope and re-run the plan."
                    ),
                )
            )
        document_instructions = self._build_document_instructions(
            milestones=replan.milestones, schools=schools
        )
        milestones, weeks, risk_markers, document_instructions = self._llm_refine_plan(
            strategy=strategy,
            intelligence=intelligence,
            constraints=constraints,
            milestones=milestones,
            weeks=weeks,
            risk_markers=risk_markers,
            document_instructions=document_instructions,
        )
        return TimelinePlan(
            title=f"{cycle} application execution board ({timezone})",
            milestones=replan.milestones,
            weeks=weeks,
            risk_markers=risk_markers,
            document_instructions=document_instructions,
        )

    def _build_milestone_graph(
        self,
        strategy: SAEAgentOutput,
        recommendations: list[dict[str, Any]],
        schools: list[str],
    ) -> list[Milestone]:
        """Build a milestone dependency graph.

        Front-load milestones based on SAE gap actions.
        """
        active_schools = schools or [
            item.get("school", "") for item in recommendations if item.get("school")
        ]
        school_scope = [item for item in active_schools if item]

        milestones = [
            Milestone(key="scope_lock", title="Lock portfolio scope and priority", due_week=1),
        ]

        gap_actions = strategy.get("gap_actions", [])
        language_keywords = ["english", "ielts", "toefl", "language"]
        background_keywords = [
            "research",
            "internship",
            "project",
            "course",
            "evidence",
            "outcome",
        ]
        normalized_actions = [str(action).lower() for action in gap_actions]
        has_language_gap = any(
            keyword in action for action in normalized_actions for keyword in language_keywords
        )
        has_bg_gap = any(
            keyword in action for action in normalized_actions for keyword in background_keywords
        )

        if has_language_gap:
            milestones.append(
                Milestone(
                    key="language_test",
                    title="Complete standardized English test score",
                    due_week=2,
                    depends_on=["scope_lock"],
                )
            )

        if has_bg_gap:
            milestones.append(
                Milestone(
                    key="background_enhancement",
                    title="Complete core background enhancement outputs",
                    due_week=4,
                    depends_on=["scope_lock"],
                )
            )

        milestones.extend(
            [
                Milestone(
                    key="doc_pack_v1",
                    title="Complete first SOP/CV draft",
                    due_week=3 if not has_bg_gap else 5,
                    depends_on=["scope_lock"],
                ),
                Milestone(
                    key="submission_batch_1",
                    title="Submit first application batch",
                    due_week=6,
                    depends_on=["doc_pack_v1"],
                ),
                Milestone(
                    key="interview_prep",
                    title="Complete interview question bank and mock practice",
                    due_week=7,
                    depends_on=["submission_batch_1"],
                ),
            ]
        )

        if school_scope and len(school_scope) >= 4:
            milestones.append(
                Milestone(
                    key="buffer_window",
                    title="Reserve buffer week for supplements and portal issues",
                    due_week=8,
                    depends_on=["submission_batch_1"],
                )
            )
        return milestones

    def _schedule_milestones(
        self,
        milestone_graph: list[Milestone],
        constraints: dict[str, Any],
        total_weeks: int,
    ) -> list[Milestone]:
        """Schedule milestones.

        TODO: Add topological ordering, reverse deadline planning, and auto-replan.
        """
        delayed = bool(constraints.get("has_delay", False))
        scheduled: list[Milestone] = []
        for item in milestone_graph:
            due_week = item.due_week + 1 if delayed else item.due_week
            item.due_week = min(max(due_week, 1), total_weeks)
            scheduled.append(item)
        return scheduled

    def _resolve_as_of_date(self, intelligence: AIEAgentOutput) -> date:
        as_of_date = str(intelligence.get("as_of_date", ""))
        try:
            return date.fromisoformat(as_of_date)
        except ValueError:
            return date.today()

    def _build_weekly_plan(
        self, milestones: list[Milestone], total_weeks: int, schools: list[str]
    ) -> list[WeekTask]:
        weeks: list[WeekTask] = []
        for week in range(1, total_weeks + 1):
            week_milestones = [item.title for item in milestones if item.due_week == week]
            items = week_milestones or [f"Advance standard week {week} application tasks"]
            risks: list[str] = []
            if week >= total_weeks - 1:
                risks.append("Deadline cluster ahead; freeze non-essential edits.")
            weeks.append(
                WeekTask(
                    week=week,
                    focus="Milestone execution" if week_milestones else "Standard execution",
                    items=items,
                    risks=risks,
                    school_scope=schools,
                )
            )
        return weeks

    def _build_risk_markers(
        self, milestones: list[Milestone], official_status_by_school: dict[str, str]
    ) -> list[RiskMarker]:
        markers: list[RiskMarker] = []
        if any(status != "official_found" for status in official_status_by_school.values()):
            markers.append(
                RiskMarker(
                    week=2,
                    level="yellow",
                    message="Some schools have incomplete current-cycle official information.",
                    mitigation="Refresh official pages weekly and re-run strategy or timeline.",
                )
            )
        for item in milestones:
            if item.key == "submission_batch_1":
                markers.append(
                    RiskMarker(
                        week=item.due_week,
                        level="red",
                        message="First submission window raises portal and material-missing risk.",
                        mitigation="Submit 5-7 days early and run a two-person verification.",
                    )
                )
        return markers

    def _build_document_instructions(
        self, milestones: list[Milestone], schools: list[str]
    ) -> list[str]:
        school_scope = ", ".join(schools) if schools else "target schools"
        instructions = [
            f"Maintain an SOP/CV version matrix by school for {school_scope}.",
            "Update fact slots and the change log after each milestone.",
        ]
        if any(item.key == "interview_prep" for item in milestones):
            instructions.append(
                "Prepare a one-minute English self-introduction and program-fit Q&A template."
            )
        return instructions

    def _resolve_total_weeks(self, constraints: dict[str, Any]) -> int:
        weeks = int(constraints.get("timeline_weeks", self.DEFAULT_WEEKS))
        return min(max(weeks, 4), 16)

    def _llm_refine_plan(
        self,
        strategy: SAEAgentOutput,
        intelligence: AIEAgentOutput,
        constraints: dict[str, Any],
        milestones: list[Milestone],
        weeks: list[WeekTask],
        risk_markers: list[RiskMarker],
        document_instructions: list[str],
    ) -> tuple[list[Milestone], list[WeekTask], list[RiskMarker], list[str]]:
        if not self.llm_client.enabled:
            return milestones, weeks, risk_markers, document_instructions
        payload = {
            "constraints": constraints,
            "ranking_order": strategy.get("ranking_order", []),
            "strengths": strategy.get("strengths", []),
            "weaknesses": strategy.get("weaknesses", []),
            "gap_actions": strategy.get("gap_actions", []),
            "official_status_by_school": intelligence.get("official_status_by_school", {}),
            "milestones": [
                {"key": item.key, "title": item.title, "due_week": item.due_week}
                for item in milestones
            ],
            "weeks": [
                {
                    "week": week_entry.week,
                    "focus": week_entry.focus,
                    "items": week_entry.items,
                }
                for week_entry in weeks
            ],
            "risk_markers": [
                {"week": item.week, "level": item.level, "message": item.message}
                for item in risk_markers
            ],
            "document_instructions": document_instructions,
        }
        prompt = "\n".join(
            [
                (
                    "You are a strict admissions timeline planner. "
                    "Use strengths, weaknesses, and gap_actions to generate "
                    "specific executable weekly_focus and week_items for each week."
                ),
                (
                    "Return valid JSON only. Avoid unescaped quotation marks inside strings, "
                    "and ensure brackets and commas are valid."
                ),
                (
                    'Return format: {"milestone_titles":{"scope_lock":"..."},'
                    '"weekly_focus":{"1":"..."},'
                    '"week_items":{"1":["..."]},"risk_markers":[{"week":2,"level":"yellow","message":"...","mitigation":"..."}],'
                    '"document_instructions":["..."]}'
                ),
                "Do not output markdown. All text values must be English.",
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
            return milestones, weeks, risk_markers, document_instructions
        milestone_titles = result.get("milestone_titles", {})
        if isinstance(milestone_titles, dict):
            for item in milestones:
                title = english_or(milestone_titles.get(item.key))
                if title:
                    item.title = title
        weekly_focus = result.get("weekly_focus", {})
        week_items = result.get("week_items", {})
        for week_entry in weeks:
            if isinstance(weekly_focus, dict):
                focus = english_or(weekly_focus.get(str(week_entry.week)))
                if focus:
                    week_entry.focus = focus
            if isinstance(week_items, dict):
                items = week_items.get(str(week_entry.week))
                normalized = english_items(items)
                if normalized:
                    week_entry.items = normalized
        llm_risks = result.get("risk_markers", [])
        if isinstance(llm_risks, list):
            normalized_risks: list[RiskMarker] = []
            for raw in llm_risks:
                if not isinstance(raw, dict):
                    continue
                try:
                    week = int(raw.get("week", 0))
                except (TypeError, ValueError):
                    continue
                message = english_or(raw.get("message"))
                mitigation = english_or(raw.get("mitigation"))
                level = english_or(raw.get("level"), "yellow")
                if week > 0 and message and mitigation:
                    normalized_risks.append(
                        RiskMarker(
                            week=week,
                            level=level,
                            message=message,
                            mitigation=mitigation,
                        )
                    )
            if normalized_risks:
                risk_markers = normalized_risks
        llm_instructions = result.get("document_instructions")
        normalized_instructions = english_items(llm_instructions)
        if normalized_instructions:
            document_instructions = normalized_instructions
        return milestones, weeks, risk_markers, document_instructions
