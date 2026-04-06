"""DTA 业务服务实现。"""

from __future__ import annotations

from typing import Any

from admitpilot.agents.dta.schemas import Milestone, RiskMarker, TimelinePlan, WeekTask
from admitpilot.core.schemas import AIEAgentOutput, SAEAgentOutput


class DynamicTimelineService:
    """负责将策略结果转化为可执行周计划。"""

    DEFAULT_WEEKS = 8

    def build_plan(
        self,
        strategy: SAEAgentOutput,
        intelligence: AIEAgentOutput,
        constraints: dict[str, Any],
    ) -> TimelinePlan:
        """基于优先级与约束生成动态执行板。"""
        timezone = str(constraints.get("timezone", "UTC"))
        cycle = str(constraints.get("cycle", "2026"))
        schools = intelligence.get("target_schools", [])
        recommendations = strategy.get("recommendations", [])
        milestone_graph = self._build_milestone_graph(
            recommendations=recommendations, schools=schools
        )
        milestones = self._schedule_milestones(
            milestone_graph=milestone_graph,
            constraints=constraints,
            total_weeks=self._resolve_total_weeks(constraints),
        )
        weeks = self._build_weekly_plan(
            milestones=milestones,
            total_weeks=self._resolve_total_weeks(constraints),
            schools=schools,
        )
        risk_markers = self._build_risk_markers(
            milestones=milestones,
            official_status_by_school=intelligence.get("official_status_by_school", {}),
        )
        document_instructions = self._build_document_instructions(
            milestones=milestones, schools=schools
        )
        return TimelinePlan(
            title=f"{cycle}申请季执行板 ({timezone})",
            milestones=milestones,
            weeks=weeks,
            risk_markers=risk_markers,
            document_instructions=document_instructions,
        )

    def _build_milestone_graph(
        self, recommendations: list[dict[str, Any]], schools: list[str]
    ) -> list[Milestone]:
        active_schools = schools or [
            item.get("school", "") for item in recommendations if item.get("school")
        ]
        school_scope = [item for item in active_schools if item]
        milestones = [
            Milestone(key="scope_lock", title="锁定项目池与优先级", due_week=1),
            Milestone(
                key="doc_pack_v1",
                title="完成 SoP/CV 第一版",
                due_week=3,
                depends_on=["scope_lock"],
            ),
            Milestone(
                key="submission_batch_1",
                title="完成第一批网申提交",
                due_week=6,
                depends_on=["doc_pack_v1"],
            ),
            Milestone(
                key="interview_prep",
                title="完成面试问题集与模拟",
                due_week=7,
                depends_on=["submission_batch_1"],
            ),
        ]
        if school_scope and len(school_scope) >= 4:
            milestones.append(
                Milestone(
                    key="buffer_window",
                    title="预留缓冲周处理补件与系统波动",
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
        delayed = bool(constraints.get("has_delay", False))
        scheduled: list[Milestone] = []
        for item in milestone_graph:
            due_week = item.due_week + 1 if delayed else item.due_week
            item.due_week = min(max(due_week, 1), total_weeks)
            scheduled.append(item)
        return scheduled

    def _build_weekly_plan(
        self, milestones: list[Milestone], total_weeks: int, schools: list[str]
    ) -> list[WeekTask]:
        weeks: list[WeekTask] = []
        for week in range(1, total_weeks + 1):
            week_milestones = [item.title for item in milestones if item.due_week == week]
            items = week_milestones or [f"推进第 {week} 周标准申请任务"]
            risks: list[str] = []
            if week >= total_weeks - 1:
                risks.append("截止期密集，建议冻结非必要改动")
            weeks.append(
                WeekTask(
                    week=week,
                    focus="里程碑推进" if week_milestones else "常规推进",
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
                    message="部分学校当前季信息未完全发布",
                    mitigation="每周同步官方页面更新，触发策略与排期重算",
                )
            )
        for item in milestones:
            if item.key == "submission_batch_1":
                markers.append(
                    RiskMarker(
                        week=item.due_week,
                        level="red",
                        message="首批提交窗口，系统拥堵与材料缺失风险上升",
                        mitigation="提前 5-7 天完成提交并进行双人核验",
                    )
                )
        return markers

    def _build_document_instructions(
        self, milestones: list[Milestone], schools: list[str]
    ) -> list[str]:
        school_scope = ",".join(schools) if schools else "目标学校"
        instructions = [
            f"按 {school_scope} 维度维护 SoP/CV 版本矩阵。",
            "每次里程碑完成后更新事实槽位与变更日志。",
        ]
        if any(item.key == "interview_prep" for item in milestones):
            instructions.append("在面试准备节点前完成英文一分钟自述与项目匹配问答模板。")
        return instructions

    def _resolve_total_weeks(self, constraints: dict[str, Any]) -> int:
        weeks = int(constraints.get("timeline_weeks", self.DEFAULT_WEEKS))
        return min(max(weeks, 4), 16)
