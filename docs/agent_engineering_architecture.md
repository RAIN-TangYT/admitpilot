# AdmitPilot Agent Engineering 技术架构设计

## 1. 目标
- 将留学申请 multi-agent 系统拆分为可并行开发的技术模块。
- 先定义接口与契约，具体实现后续按小组分工完成。
- 保证全链路可追溯、可审计、可降级。

## 2. 架构分层
- Control Plane：PAO 编排、状态机、依赖门控、能力令牌签发。
- Agent Runtime Plane：AIE/SAE/DTA/CDS 任务执行与重试。
- Tool Plane：MCP 工具服务与方法目录。
- Memory Plane：分层记忆与版本化存储。
- Governance Plane：合规校验、PII、审计与审批闸门。

## 3. 代码映射
- 统一契约：`src/admitpilot/platform/runtime/contracts.py`
- Runtime 状态机：`src/admitpilot/platform/runtime/state_machine.py`
- Memory 协议与适配：`src/admitpilot/platform/memory/contracts.py`、`src/admitpilot/platform/memory/adapters.py`
- MCP 协议与目录：`src/admitpilot/platform/mcp/*`
- Tool Registry：`src/admitpilot/platform/tools/registry.py`
- Capability 权限：`src/admitpilot/platform/security/capability.py`
- 治理与可观测：`src/admitpilot/platform/governance/contracts.py`、`src/admitpilot/platform/observability/contracts.py`
- 公共装配入口：`src/admitpilot/platform/bootstrap.py`

## 4. 接口设计原则
- 所有 MCP 请求必须携带 `trace_id` 与 `tool_run_id`。
- 所有写入操作必须提供 `idempotency_key` 与 `result_version`。
- 所有 Agent 输出必须携带 `confidence + evidence_level + lineage`。
- 默认拒绝权限，按任务下发短时 capability token。
- Memory 按 namespace 隔离，禁止跨申请上下文污染。

## 5. 状态流转定义
- Workflow 主状态：
  - `NEW -> INTENT_PARSED -> PLAN_BUILT -> EXECUTING -> AGGREGATING -> DELIVERED`
  - 异常分支：`PARTIAL_DELIVERED`, `FAILED`
- Task 子状态：
  - `PENDING/READY/RUNNING/SUCCESS/FAILED/SKIPPED/DEGRADED`

## 6. 知识更新机制
- `discover -> fetch -> parse -> normalize -> quality_gate -> snapshot_publish -> index_refresh`
- 关键事件：
  - `official_snapshot_updated`
  - `strategy_recomputed`
  - `timeline_replanned`
  - `artifact_review_required`

## 7. 模块（AIE/SAE/DTA/CDS）
- PAO – Principal Application Orchestrator（主编排器）
  - 定位：系统的中心协调层，负责把用户请求拆解成可执行任务并路由给各子 Agent，最终聚合输出。
  - 职责：
    - 意图识别（intent recognition）
    - 任务拆解（task decomposition）
    - Agent 路由（agent routing）
    - 上下文管理（context management）
    - 最终响应聚合（final response aggregation）
  - 约束：所有 Agent 必须在共享 application context 下运行，PAO 确保复合请求被一致地处理与交付。
  - 典型编排流：
    - 用户提交自然语言请求
    - PAO 识别意图并拆解任务
    - AIE 提供招生事实、历史知识与案例证据
    - SAE 评估匹配度并产出选校策略
    - DTA 将策略转为逆向规划时间线
    - CDS 基于上游结果生成文书支持
    - PAO 聚合为一致的建议包
- AIE – Admissions Intelligence Engine（招生情报引擎）
  - 定位：系统的共享招生知识层，为下游决策与规划提供标准化的 admissions intelligence。
  - 维护：
    - Official Memory：来自大学官网、项目页、FAQ、DDL、历史要求快照等结构化信息
    - Case Memory：清洗后的 offer 案例、时间规律、来源可信度标注
  - 能力：检索当季招生信息、识别官方更新是否发布；当信息不完整时生成带置信度的预测；对外输出可复用的情报结构。
- SAE – Strategic Admissions Evaluator（策略评估引擎）
  - 定位：申请者-项目匹配与选校策略分析模块。
  - 输入：用户背景（Profile）+ AIE 的招生情报。
  - 输出：
    - Reach / Match / Safety 分组
    - 优劣势总结（strength–weakness summary）
    - 差距分析（gap analysis）
    - 风险感知的推荐顺序（risk-aware recommendation order）
  - 方法：结构化规则 + 语义匹配 + 风险感知排序的混合评估框架，确保可实现与可解释。
- DTA – Dynamic Timeline Architect（动态时间线规划模块）
  - 定位：将策略推荐转化为可执行的时间计划与执行板。
  - 输入：SAE 的优先级策略 + AIE 的时间信息 + PAO 管理的用户约束。
  - 输出：
    - 动态时间线/执行看板
    - 周粒度任务结构（week-level task structure）
    - 里程碑与风险标记（milestone and risk markers）
    - 面向 CDS 的文书准备指令（document preparation instructions）
  - 目标：把长期申请目标转化为可管理、可迭代、可适配的执行计划。
- CDS – Core Document Specialist（核心文书支持模块）
  - 定位：文书与面试相关的产出与改写支持，强调真实性与一致性。
  - 输入：用户经历素材 + SAE 选校与定位结果 + DTA 的时间计划。
  - 输出：
    - 个性化 PS/SoP 草稿（customized PS / SoP drafts）
    - 与策略动态对齐的 CV 内容（dynamically aligned CV content）
    - 面试要点与话术（interview talking points）
    - 叙事完整性反馈（narrative completion feedback）
  - 设计：以人为中心的 refinement 模块，保留人工审阅与用户最终确认。
