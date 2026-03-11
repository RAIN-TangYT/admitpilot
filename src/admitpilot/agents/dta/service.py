"""DTA 业务服务实现。"""

from __future__ import annotations

from typing import Any

from admitpilot.agents.dta.schemas import TimelinePlan, WeekTask


class DynamicTimelineService:
    """负责将策略结果转化为可执行周计划。"""

    def build_plan(self, priorities: list[str], constraints: dict[str, Any]) -> TimelinePlan:
        """基于优先级与约束生成动态执行板。"""
        timezone = constraints.get("timezone", "UTC")
        cycle = str(constraints.get("cycle", "2026"))
        milestones = priorities[:3] if priorities else ["完成首批学校提交准备"]
        weeks = [
            WeekTask(week=1, focus="策略对齐", items=["确认项目池", "建立申请台账"]),
            WeekTask(week=2, focus="材料准备", items=["整理经历证据", "形成PS初版框架"]),
            WeekTask(week=3, focus="质量提升", items=["进行首轮审校", "补齐薄弱证据"], risks=["时间冲突"]),
            WeekTask(week=4, focus="提交冲刺", items=["完成定稿", "执行提交前核验"], risks=["系统拥堵"]),
        ]
        return TimelinePlan(title=f"{cycle}申请季执行板 ({timezone})", milestones=milestones, weeks=weeks)
