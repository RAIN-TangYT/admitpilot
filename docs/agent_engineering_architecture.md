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
