"""DTA 业务服务实现。"""

from __future__ import annotations

import json

from typing import Any

from admitpilot.agents.dta.prompts import SYSTEM_PROMPT
from admitpilot.agents.dta.schemas import Milestone, RiskMarker, TimelinePlan, WeekTask
from admitpilot.core.schemas import AIEAgentOutput, SAEAgentOutput
from admitpilot.platform.llm.qwen import QwenClient


class DynamicTimelineService:
    """负责将策略结果转化为可执行周计划。"""

    DEFAULT_WEEKS = 8

    def __init__(self, llm_client: QwenClient | None = None) -> None:
        self.llm_client = llm_client or QwenClient()

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
            strategy=strategy, recommendations=recommendations, schools=schools
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
            title=f"{cycle}申请季执行板 ({timezone})",
            milestones=milestones,
            weeks=weeks,
            risk_markers=risk_markers,
            document_instructions=document_instructions,
        )

    def _build_milestone_graph(
        self, strategy: SAEAgentOutput, recommendations: list[dict[str, Any]], schools: list[str]
    ) -> list[Milestone]:
        """构建里程碑依赖图骨架。
        
        基于 SAE 输出的 gap_actions 动态添加前置里程碑节点。
        """
        active_schools = schools or [
            item.get("school", "") for item in recommendations if item.get("school")
        ]
        school_scope = [item for item in active_schools if item]
        
        milestones = [
            Milestone(key="scope_lock", title="锁定项目池与优先级", due_week=1),
        ]
        
        # 动态解析 SAE 的 Gap Actions
        gap_actions = strategy.get("gap_actions", [])
        has_language_gap = any(kw in action for action in gap_actions for kw in ["语言", "雅思", "托福", "IELTS", "TOEFL"])
        has_bg_gap = any(kw in action for action in gap_actions for kw in ["科研", "实习", "项目", "课程"])
        
        if has_language_gap:
            milestones.append(
                Milestone(
                    key="language_test", 
                    title="完成语言标化考试出分", 
                    due_week=2, 
                    depends_on=["scope_lock"]
                )
            )
            
        if has_bg_gap:
            milestones.append(
                Milestone(
                    key="background_enhancement", 
                    title="完成背景提升核心产出 (项目/实习)", 
                    due_week=4, 
                    depends_on=["scope_lock"]
                )
            )

        milestones.extend([
            Milestone(
                key="doc_pack_v1",
                title="完成 SoP/CV 第一版",
                due_week=3 if not has_bg_gap else 5,
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
        ])
        
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
        """里程碑调度骨架。

        TODO: 实现拓扑排序 + deadline 逆排 + 自动重排。
        """
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
            "weeks": [{"week": item.week, "focus": item.focus, "items": item.items} for item in weeks],
            "risk_markers": [
                {"week": item.week, "level": item.level, "message": item.message}
                for item in risk_markers
            ],
            "document_instructions": document_instructions,
        }
        prompt = "\n".join(
            [
                "你是一个严格的留学时间线规划师。请结合该申请者的优劣势 (strengths/weaknesses) 和短板提升行动 (gap_actions)，为每个 week 生成具体、可执行的 weekly_focus 和 week_items。",
                "必须输出合法的 JSON 格式。避免在字符串中使用未转义的双引号，请检查括号与逗号是否闭合。",
                "请基于输入输出 JSON。",
                (
                    '返回格式：{"milestone_titles":{"scope_lock":"..."},"weekly_focus":{"1":"..."},'
                    '"week_items":{"1":["..."]},"risk_markers":[{"week":2,"level":"yellow","message":"...","mitigation":"..."}],'
                    '"document_instructions":["..."]}'
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
            return milestones, weeks, risk_markers, document_instructions
        milestone_titles = result.get("milestone_titles", {})
        if isinstance(milestone_titles, dict):
            for item in milestones:
                title = str(milestone_titles.get(item.key, "")).strip()
                if title:
                    item.title = title
        weekly_focus = result.get("weekly_focus", {})
        week_items = result.get("week_items", {})
        for item in weeks:
            if isinstance(weekly_focus, dict):
                focus = str(weekly_focus.get(str(item.week), "")).strip()
                if focus:
                    item.focus = focus
            if isinstance(week_items, dict):
                items = week_items.get(str(item.week))
                if isinstance(items, list):
                    normalized = [text for raw in items if (text := str(raw).strip())]
                    if normalized:
                        item.items = normalized
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
                message = str(raw.get("message", "")).strip()
                mitigation = str(raw.get("mitigation", "")).strip()
                level = str(raw.get("level", "yellow")).strip() or "yellow"
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
        if isinstance(llm_instructions, list):
            normalized_instructions = [text for raw in llm_instructions if (text := str(raw).strip())]
            if normalized_instructions:
                document_instructions = normalized_instructions
        return milestones, weeks, risk_markers, document_instructions
