"""MCP 方法目录定义。

仅定义契约，不提供具体实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from admitpilot.platform.types import AgentRole


@dataclass(slots=True)
class MethodContract:
    """MCP 方法契约。"""

    server: str
    method: str
    description: str
    owner_agents: tuple[AgentRole, ...]
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    todo: tuple[str, ...] = field(default_factory=tuple)


METHOD_CATALOG: tuple[MethodContract, ...] = (
    MethodContract(
        server="intelligence-mcp",
        method="official.fetch_pages",
        description="抓取目标学校项目官方页面。",
        owner_agents=("aie",),
        input_fields=("schools", "program", "cycle", "domains_whitelist", "as_of_date"),
        output_fields=("raw_docs",),
        todo=(
            "接入 robots 与频率控制",
            "接入官方域名白名单策略",
            "接入抓取失败重试与熔断",
        ),
    ),
    MethodContract(
        server="intelligence-mcp",
        method="official.parse_requirements",
        description="从原始页面中抽取申请要求与 DDL。",
        owner_agents=("aie",),
        input_fields=("raw_doc_refs", "extract_targets"),
        output_fields=("structured_records",),
        todo=("接入 HTML/PDF 多模态解析", "建立字段级置信度评分"),
    ),
    MethodContract(
        server="intelligence-mcp",
        method="official.snapshot_diff",
        description="对比快照版本并返回政策变化。",
        owner_agents=("aie", "pao"),
        input_fields=("baseline_snapshot_id", "candidate_snapshot_id"),
        output_fields=("delta", "policy_change_flag"),
        todo=("实现结构化 diff 规则", "接入变更订阅事件总线"),
    ),
    MethodContract(
        server="knowledge-mcp",
        method="retrieve.hybrid",
        description="结构化与向量检索混合召回证据。",
        owner_agents=("aie", "sae", "dta", "cds"),
        input_fields=("query_text", "sql_filters", "blend_weights"),
        output_fields=("evidence_bundle", "coverage_score"),
        todo=("统一 rerank 策略", "补充召回失败降级路径"),
    ),
    MethodContract(
        server="strategy-mcp",
        method="strategy.rule_evaluate",
        description="基于硬规则进行候选人与项目匹配。",
        owner_agents=("sae",),
        input_fields=("user_profile", "official_requirements", "rule_profile"),
        output_fields=("rule_scores_by_school", "hard_fail_flags"),
        todo=("实现规则 DSL", "落地可配置权重中心"),
    ),
    MethodContract(
        server="strategy-mcp",
        method="strategy.risk_rank",
        description="风险感知排序并生成 Reach/Match/Safety。",
        owner_agents=("sae",),
        input_fields=("rule_scores", "semantic_scores", "uncertainty_signals"),
        output_fields=("recommendations", "ranking_order"),
        todo=("引入历史结果回归校准",),
    ),
    MethodContract(
        server="timeline-mcp",
        method="timeline.plan_build",
        description="根据排序与 DDL 构建里程碑与周计划。",
        owner_agents=("dta",),
        input_fields=("ranking_order", "deadline_nodes", "constraints"),
        output_fields=("milestone_graph", "weekly_plan", "risk_markers"),
        todo=("接入 DAG 调度器", "增加自动重排策略"),
    ),
    MethodContract(
        server="document-mcp",
        method="document.draft_compose",
        description="按学校生成文书草稿框架。",
        owner_agents=("cds",),
        input_fields=("target_school", "doc_type", "fact_slots", "style_profile"),
        output_fields=("draft_id", "outline", "draft_text_ref"),
        todo=("接入模板中心", "接入人审前置规则"),
    ),
    MethodContract(
        server="document-mcp",
        method="document.consistency_check",
        description="跨文档一致性检查。",
        owner_agents=("cds", "pao"),
        input_fields=("draft_ids", "fact_slots"),
        output_fields=("issues", "consistency_score"),
        todo=("接入事实图谱比对", "接入高风险表述拦截"),
    ),
    MethodContract(
        server="governance-mcp",
        method="governance.policy_validate",
        description="输出前策略合规校验。",
        owner_agents=("pao",),
        input_fields=("agent_output", "policy_profile"),
        output_fields=("allow", "violations"),
        todo=("接入可配置策略中心", "接入阻断与告警联动"),
    ),
)
