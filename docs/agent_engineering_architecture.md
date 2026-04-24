# AdmitPilot Agent Engineering Architecture

- 文档日期：`2026-04-24`
- 文档定位：当前代码基线的高层架构说明
- 规范优先级：
  - 产品目标与课程背景：`docs/Project_Proposal_Group 26 (TANG Yutong, CHEN Jinghao, ZHANG Yufei, SHI Junren).docx`
  - 实施路线：`docs/implementation_plan.md`
  - 实际进展：`docs/progress.md`

本文件只回答三个问题：系统现在怎么分层、模块边界在哪里、下一阶段应该按什么边界继续开发。

## 1. 当前系统定位

AdmitPilot 当前是一个“可演示的多代理申请支持原型”，不是生产系统。

已具备：
- `PAO` 编排主流程
- `AIE / SAE / DTA / CDS` 四代理串联
- 配置层、应用工厂、FastAPI 健康检查骨架
- 基础平台层骨架：memory / runtime / governance / security / observability
- OpenAI 默认模型接入：`gpt-5.4-nano`
- AIE 运行时默认读取官方库：`data/official_library/official_library.json`
- AIE 运行时默认读取案例库：`data/case_library/case_library.json`
- AIE live 官方刷新入口：`refresh_official_library.py`
- demo 默认按“学校 -> 项目”组合运行，而不是统一单项目
- SAE 规则打分、可替换语义匹配与证据化解释
- DTA 拓扑调度、deadline 逆排、延误重排与冲突检测
- CDS 用户证据模型、fact slots、模板层与一致性检查

尚未具备：
- 全量院校项目的 live 官方页覆盖
- 生产级数据库、缓存、对象存储
- 异步 worker、业务 API 与上线发布清单
- 生产级治理闸门与可观测链路

## 2. 分层结构

### 2.1 Control Plane

路径：`src/admitpilot/pao`

职责：
- 接收用户请求
- 路由意图
- 生成任务链
- 调用各代理
- 聚合结果并维护共享上下文

核心文件：
- `router.py`
- `orchestrator.py`
- `contracts.py`
- `schemas.py`

### 2.2 Agent Plane

路径：`src/admitpilot/agents`

职责：
- `AIE`：招生情报、官方库刷新与快照
- `SAE`：规则化选校评估、语义匹配与风险排序
- `DTA`：时间线、deadline 逆排与里程碑计划
- `CDS`：证据化文书支持、模板提纲与一致性检查

每个 agent 当前基本结构：
- `agent.py`：代理入口
- `service.py`：业务核心
- `schemas.py`：结构化输出
- `prompts.py`：LLM prompt

### 2.3 Platform Plane

路径：`src/admitpilot/platform`

职责：
- runtime 状态机
- memory 协议与默认内存实现
- governance / capability 骨架
- observability 骨架
- mcp / tool registry

当前状态：
- 接口与默认内存实现基本齐全
- 生产后端尚未接入

### 2.4 App / API Plane

路径：
- `src/admitpilot/app.py`
- `src/admitpilot/api`
- `src/admitpilot/config`

职责：
- 统一 settings 加载
- 构建应用对象
- 暴露 CLI 与 API 启动入口

## 3. 当前调用链

标准链路：

1. `PAO` 固定先调用 `AIE`
2. `SAE` 基于 `AIE` 输出生成策略
3. `DTA` 基于 `AIE + SAE` 生成计划
4. `CDS` 基于 `SAE + DTA` 生成文书支持包

当前默认 demo 组合：

- `NUS -> MCOMP_CS`
- `NTU -> MSAI`
- `HKU -> MSCS`
- `CUHK -> MSCS`
- `HKUST -> MSIT`

当前默认入口：
- CLI：`python -m admitpilot.main`
- API：`python -m uvicorn admitpilot.api.main:app --reload`
- 官方库刷新：`python -m admitpilot.debug.refresh_official_library --cycle 2026`

运行时数据基线：

- AIE official：`data/official_library/official_library.json`
- AIE case：`data/case_library/case_library.json`
- AIE test official shadow：`.pytest-local/runtime_official_library.test.json`
- SAE matcher：非 test 模式默认 `embedding`，test 模式默认 `fake`

## 4. 模块边界

建议后续继续按以下边界推进，避免多人改同一层：

- AIE 边界：
  - `src/admitpilot/agents/aie/*`
  - 负责学校/项目目录、live 抓取、解析、官方库、快照、diff

- SAE 边界：
  - `src/admitpilot/agents/sae/*`
  - 负责规则打分、语义匹配、证据化推荐

- DTA 边界：
  - `src/admitpilot/agents/dta/*`
  - 负责 DAG、deadline 逆排、延误重排

- CDS 边界：
  - `src/admitpilot/agents/cds/*`
  - 负责事实槽位、模板层、一致性检查

- Platform 边界：
  - `src/admitpilot/platform/*`
  - 负责存储、权限、审计、trace、metrics

- App/API 边界：
  - `src/admitpilot/app.py`
  - `src/admitpilot/api/*`
  - `src/admitpilot/config/*`
  - 负责统一装配与外部接口

## 5. 不应再作为真相来源的内容

以下内容不应再单独维护在旧文档里：
- 已修复的 demo 阻断问题清单
- 过期的分层语义
- 与当前代码不一致的路由描述
- 与 Qwen / DashScope 相关的旧配置说明

这些内容如果需要记录：
- 进度写入 `docs/progress.md`
- 路线写入 `docs/implementation_plan.md`
- 对外说明写入 `README.md`

## 6. 触发条件 / 输入输出 / 汇总机制（结构化表）

本节与当前代码实现逐项对齐，主要对应：
- `src/admitpilot/pao/router.py`
- `src/admitpilot/pao/orchestrator.py`
- `src/admitpilot/core/schemas.py`
- `src/admitpilot/agents/*/agent.py`

### 6.1 PAO 触发条件（Intent -> Task）

| 用户问题命中意图 | 关键词（示例） | 直接触发任务 | 自动补全依赖后最终任务 |
| --- | --- | --- | --- |
| `intelligence` | `官网` `deadline` `截止` `要求` `政策` `更新` | `collect_intelligence` | `collect_intelligence` |
| `strategy` | `选校` `匹配` `定位` `风险` `reach/match/safety` | `evaluate_strategy` | `collect_intelligence -> evaluate_strategy` |
| `timeline` | `时间线` `计划` `排期` `规划` `milestone` | `build_timeline` | `collect_intelligence -> evaluate_strategy -> build_timeline` |
| `documents` | `文书` `ps` `sop` `cv` `面试` `叙事` | `draft_documents` | `collect_intelligence -> evaluate_strategy -> build_timeline -> draft_documents` |
| 未命中任何关键词 | 无 | 默认全链路 | `collect_intelligence -> evaluate_strategy -> build_timeline -> draft_documents` |

补充说明：
- `timeline` 会自动补全 `strategy` 依赖。
- `documents` 会自动补全 `strategy + timeline` 依赖。
- 多意图同时命中时，取并集后再做依赖闭包。

### 6.2 任务依赖、共享内存要求与降级行为

| 任务名 | Agent | depends_on | required_memory | can_degrade | 依赖不满足时行为 |
| --- | --- | --- | --- | --- | --- |
| `collect_intelligence` | `aie` | `[]` | `[]` | `false` | 正常执行（无上游依赖） |
| `evaluate_strategy` | `sae` | `["collect_intelligence"]` | `["aie"]` | `false` | 生成 `SKIPPED` 结果，不执行 agent |
| `build_timeline` | `dta` | `["evaluate_strategy"]` | `["aie","sae"]` | `false` | 生成 `SKIPPED` 结果，不执行 agent |
| `draft_documents` | `cds` | `["evaluate_strategy","build_timeline"]` | `["sae","dta"]` | `true` | 默认记录 `degraded_tasks` 后继续执行；若 `SAE` 因 `missing_profile:*` 被阻断，则不降级、直接 `SKIPPED` |

阻断判定来源：
- 缺任务：`missing_task:<task>`
- 上游失败：`failed_task:<task>`
- 缺共享内存：`missing_memory:<namespace>`

### 6.3 Agent 输入输出契约（基于 `ApplicationContext` + `SharedMemory`）

| Agent | `run()` 直接输入 | 读取的上游共享内存 | 输出写回键 | 主要输出结构（`core/schemas.py`） |
| --- | --- | --- | --- | --- |
| `AIE` | `task`, `context.user_query`, `context.profile`, `context.constraints` | 无强制上游依赖 | `shared_memory["aie"]` | `AIEAgentOutput` |
| `SAE` | `task`, `context.profile` | `shared_memory["aie"]` | `shared_memory["sae"]` | `SAEAgentOutput` |
| `DTA` | `task`, `context.constraints` | `shared_memory["aie"]`, `shared_memory["sae"]` | `shared_memory["dta"]` | `DTAAgentOutput` |
| `CDS` | `task` | `shared_memory["sae"]`, `shared_memory["dta"]` | `shared_memory["cds"]` | `CDSAgentOutput` |

关键输出字段（摘要）：
- `AIEAgentOutput`：`target_schools`、`target_program_by_school`、`official_status_by_school`、`official_records`、`official_source_urls_by_school`、`forecast_signals`。
- `SAEAgentOutput`：`recommendations`、`ranking_order`、`gap_actions`、`model_breakdown`。
- `DTAAgentOutput`：`milestones`、`weekly_plan`、`risk_markers`、`document_instructions`。
- `CDSAgentOutput`：`document_drafts`、`interview_talking_points`、`consistency_issues`、`review_checklist`。

### 6.4 PAO 汇总与用户回传机制

| 汇总分支 | 触发条件 | `summary` 形式 | 对用户暴露内容 |
| --- | --- | --- | --- |
| 用户画像补全提示分支 | 任一任务被 `missing_profile:*` 阻断 | 生成“用户画像信息不完整，已暂停SAE择校及下游任务”提示 | 明确列出需补充字段（学历层次、专业方向、目标院校、目标项目、GPA、语言成绩、经历素材） |
| AIE 情报摘要分支 | 本轮仅 1 个结果，且为 `aie:collect_intelligence:SUCCESS` | 生成“`AIE 官网情报摘要（<cycle>申请季）`”多行摘要 | 每校展示状态、截止时间、语言/材料/学术要求（如有）、官方 URL |
| 通用执行摘要分支 | 其余所有场景 | 生成“已处理 N 个任务 + success/failed/skipped + 每任务状态与置信度” | 展示链路执行结果与健康度 |

`OrchestrationResponse` 始终返回：
- `summary`：面向用户的可读摘要。
- `results`：每个 agent task 的结构化执行结果（含 `status/confidence/trace/blocked_by`）。
- `context`：包含 `shared_memory`（AIE/SAE/DTA/CDS 结构化产物）与 `decisions`（如 `trace_id`、`degraded_tasks`、事件日志）。

这意味着：
- UI/CLI 可以只读 `summary` 做自然语言展示。
- 调试、联调、评审可直接读取 `results + context.shared_memory` 获取可追溯的结构化细节。
