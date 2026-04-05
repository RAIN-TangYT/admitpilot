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

## 3. 代码映射（已搭接口骨架）
- 统一契约单一来源：
  - `src/admitpilot/platform/runtime/contracts.py`
  - 说明：`AgentTask/AgentResult/TaskStatus/WorkflowStatus` 为全系统唯一定义，`core.schemas` 仅复用。
- 公共类型：
  - `src/admitpilot/platform/types.py`
- MCP 协议：
  - `src/admitpilot/platform/mcp/contracts.py`
  - `src/admitpilot/platform/mcp/method_specs.py`
  - `src/admitpilot/platform/mcp/schemas.py`
  - `src/admitpilot/platform/mcp/server_registry.py`
- Tool Registry：
  - `src/admitpilot/platform/tools/registry.py`
- Memory 协议：
  - `src/admitpilot/platform/memory/contracts.py`
  - `src/admitpilot/platform/memory/adapters.py`
- Runtime 协议与状态机：
  - `src/admitpilot/platform/runtime/contracts.py`
  - `src/admitpilot/platform/runtime/state_machine.py`
- Capability 权限模型：
  - `src/admitpilot/platform/security/capability.py`
- 统一错误码：
  - `src/admitpilot/platform/common/errors.py`
- 公共区初始化：
  - `src/admitpilot/platform/bootstrap.py`
  - `src/admitpilot/platform/governance/contracts.py`
  - `src/admitpilot/platform/observability/contracts.py`

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
- 迁移规则已在 `runtime/state_machine.py` 预定义。

## 6. 知识更新机制（目标流程）
- `discover -> fetch -> parse -> normalize -> quality_gate -> snapshot_publish -> index_refresh`
- 官方快照变更触发事件：
  - `official_snapshot_updated`
  - `strategy_recomputed`
  - `timeline_replanned`
  - `artifact_review_required`

## 7. 反幻觉与防污染策略
- 证据门控：无证据事实不能输出确定性结论。
- 不确定性传递：AIE `predicted` 必须传递到 SAE/DTA/CDS。
- 上下文分区：事实区、推断区、草稿区分离写入。
- 冲突消解：官方快照优先级最高，覆盖历史推断。
- 输出双闸门：`consistency_check + policy_validate`。

## 8. 分工 TODO（可直接建任务）

### PAO（Principal Application Orchestrator）
- [ ] 完成 `WorkflowStatus` 全状态落盘与回放接口，支持 `PARTIAL_DELIVERED` 恢复执行。
- [ ] 接入 capability token 下发与 method/scope 校验拦截（调用前置）。
- [ ] 将任务依赖门控与 `can_degrade` 规则抽成独立策略模块，便于灰度配置。
- [ ] 实现统一聚合器输出模板（结论/证据/置信度/下一步动作/待确认项）。
- [ ] 完成跨 Agent 事件编排：`official_snapshot_updated -> strategy_recomputed -> timeline_replanned -> artifact_review_required`。

### AIE（Admissions Intelligence Engine）
- [ ] 对接真实官方源抓取链路（站点白名单、频控、失败重试、反爬策略）。
- [ ] 实现 `official.parse_requirements` 与字段级置信度评估。
- [ ] 实现快照版本化与 `official.snapshot_diff` 结构化变更检测。
- [ ] 建立 Case 清洗与可信度打标流水线（去重、异常样本过滤、来源评级）。
- [ ] 输出标准化 intelligence pack 并写入 `Official/Case Memory`，包含完整 lineage。

### SAE（Strategic Admissions Evaluator）
- [ ] 落地规则引擎（硬门槛、软条件、可配置权重）并接入 `strategy.rule_evaluate`。
- [ ] 落地语义匹配模块并接入 `strategy.semantic_match`（项目契合度向量检索）。
- [ ] 实现风险排序与 Reach/Match/Safety 分层策略。
- [ ] 输出 gap actions 与优先级动作清单，写入 `Strategy Memory` 版本表。
- [ ] 建立策略回归评估（采纳率、分层稳定性、风险校准误差）。

### DTA（Dynamic Timeline Architect）
- [ ] 对接学校级 deadline 解析，构建标准化 DDL 节点模型。
- [ ] 实现 DAG 排期与约束求解，支持延期事件触发 `timeline.replan`。
- [ ] 输出周级执行板、里程碑、风险标记与文书指令并版本化存储。
- [ ] 接入风险策略（拥堵风险、材料缺口、官方信息未发布）自动标注。
- [ ] 建立计划执行反馈闭环（完成率、逾期率、重排频次）。

### CDS（Core Document Specialist）
- [ ] 建立事实槽位同步机制（用户事实 + SAE + DTA 联合映射）。
- [ ] 按学校/项目生成 SoP/PS/CV 草稿框架与版本矩阵。
- [ ] 实现跨文档一致性检查（实体、时间线、量化数据一致）。
- [ ] 接入高风险表述拦截与人审前置闸门。
- [ ] 输出面试要点与 Q/A 包并挂接到文书版本。

### 跨 Agent 公共任务（平台联动）
- [x] 已完成 MCP 服务存根与 schema 注册初始化定义。
- [x] 已完成统一错误码目录初始化定义。
- [x] 已完成 `SessionMemoryStore/VersionedMemoryStore/ArtifactObjectStore` 内存适配器初始化定义。
- [x] 已完成 namespace ACL、PII 脱敏、审计日志与审批工作流初始化定义。
- [x] 已完成可观测性（trace/metrics）初始化定义。
- [ ] 将内存适配器切换到 Redis/PostgreSQL/S3 生产实现。
- [ ] 将治理能力接入策略中心、签名验真与审批通知。
- [ ] 将 trace/metrics 接入 OpenTelemetry/Prometheus 与告警系统。

## 9. 当前实现状态（截至当前版本）
- 已完成公共区 `PlatformCommonBundle` 总装配入口，可一次性初始化 MCP、tools、memory、governance、observability。
- 已完成 `tool registry <-> method catalog` 对齐校验，避免方法漂移。
- 已完成 PAO 工作流状态机接入和任务状态枚举统一收敛。
- 已具备分工开发基线：接口可调用、类型可检查、测试可回归。

## 10. 验收基线（首版）
- 所有 MCP 方法有可调用存根与契约校验。
- 关键 memory namespace 支持写入、版本读取、审计追踪。
- PAO 能跑通依赖门控、降级执行、状态流转。
- 至少 1 条从 AIE 到 CDS 的端到端链路可回放。
