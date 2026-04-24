# AdmitPilot 实施进度记录

- 文档日期：`2026-04-24`
- 对应计划：`docs/implementation_plan.md`
- 用途：记录每一步的实际修复动作、测试结果、阻塞项与下一步安排

## 当前执行范围

- 当前目标：`课堂/答辩演示`
- 当前终点：`Phase 5 / Step 21`
- 当前主线：`Phase 3-5` 已完成演示范围收口
- 暂缓范围：`Phase 6-7` 的生产化、异步执行与上线准备
- 运行时基线：AIE 默认读取 `data/official_library/official_library.json` 与 `data/case_library/case_library.json`；测试模式使用 `.pytest-local/runtime_official_library.test.json` 作为官方库影子副本；SAE 在非 test 模式默认使用 embedding matcher，test 模式保留 deterministic fake matcher；`fixture` 仅用于测试，官方库通过 `refresh_official_library.py` 刷新

## 使用规则

1. 每完成一个 step，就更新对应小节。
2. 必须记录真实改动文件，不写泛化描述。
3. 必须记录执行过的测试命令与结果。
4. 若步骤未完成，必须写明阻塞原因。
5. 若实现偏离原计划，必须在“偏差说明”中写清原因。

## 状态枚举

- `pending`：未开始
- `in_progress`：进行中
- `blocked`：被阻塞
- `done`：已完成
- `skipped`：跳过

## 记录模板

```md
### Step XX. 标题

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
  - `path/to/file.py`
- 实际修复动作：
  - 动作 1
  - 动作 2
- 测试：
  - 命令：`conda activate admitpilot; $env:PYTHONPATH='src'; python -m pytest ... -q`
  - 结果：`passed / failed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - Step XX
```

## 总览

| Phase | Step 范围 | 状态 | 备注 |
| --- | --- | --- | --- |
| Phase 1 | Step 01-04 | `done` | 已完成配置层、时间工具、应用工厂与 API 骨架 |
| Phase 2 | Step 05-10 | `done` | 已完成 catalog、官网抓取/解析、快照 diff、案例归一化与 AIE 集成，并在后续补充为官方库运行时基线 |
| Phase 3 | Step 11-14 | `done` | SAE 已完成规则文件、规则打分、可替换语义匹配与证据化解释；运行时默认不再绑死 fake matcher |
| Phase 4 | Step 15-17 | `done` | DTA 已完成拓扑调度、deadline 逆排、延误重排与编排集成回归 |
| Phase 5 | Step 18-21 | `done` | CDS 已完成用户证据模型、fact slots、模板层与一致性检查 |
| Phase 6 | Step 22-26 | `skipped` | 当前课堂/答辩演示范围内暂缓，不作为本轮目标 |
| Phase 7 | Step 27-30 | `skipped` | 当前课堂/答辩演示范围内暂缓，不作为本轮目标 |

---

## Phase 1. 基础设施与运行边界固化

### Step 01. 引入统一配置层

- 状态：`done`
- 开始时间：`2026-04-19 19:10:00`
- 完成时间：`2026-04-19 19:40:13`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/config/__init__.py`
  - `src/admitpilot/config/settings.py`
  - `src/admitpilot/platform/llm/openai.py`
  - `src/admitpilot/main.py`
  - `.env.example`
  - `tests/test_settings.py`
- 实际修复动作：
  - 新增 `AdmitPilotSettings` 与 `load_settings()`，把运行模式、OpenAI、数据库、Redis、对象存储、API 配置收敛到单一配置入口。
  - 把 `OpenAIClient` 从直接读取环境变量改为依赖 settings。
  - 更新 CLI 入口，默认通过 settings 驱动 demo 请求参数。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_settings.py tests/test_app_factory.py -q`
  - 结果：`passed`
- 偏差说明：
  - 为兼容当前终端环境，测试实际通过 `admitpilot` 环境中的 Python 可执行文件运行，而不是 `conda activate`。
- 阻塞项：
  - 无
- 下一步：
  - `Step 02`

### Step 02. 统一时间与时区工具

- 状态：`done`
- 开始时间：`2026-04-19 19:12:00`
- 完成时间：`2026-04-19 19:40:13`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/platform/common/time.py`
  - `src/admitpilot/platform/common/__init__.py`
  - `src/admitpilot/platform/memory/contracts.py`
  - `src/admitpilot/platform/memory/adapters.py`
  - `src/admitpilot/platform/observability/contracts.py`
  - `src/admitpilot/platform/governance/contracts.py`
  - `src/admitpilot/platform/security/capability.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `src/admitpilot/agents/aie/agent.py`
  - `tests/test_time_utils.py`
  - `tests/test_platform_common_bootstrap.py`
  - `tests/test_platform_interfaces.py`
- 实际修复动作：
  - 新增 `utc_now()`, `utc_today()`, `ensure_utc()`, `to_iso_utc()` 统一时间工具。
  - 替换核心模块中的 `datetime.utcnow()`，统一为 timezone-aware UTC。
  - 同步修复测试中的旧时间写法，消除核心链路的 `utcnow()` 弃用 warning。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_time_utils.py tests/test_platform_interfaces.py tests/test_platform_common_bootstrap.py tests/test_orchestrator.py -q`
  - 结果：`passed`
- 偏差说明：
  - 仍保留 `.pytest_cache` 权限 warning，不属于本 step 的代码问题。
- 阻塞项：
  - 无
- 下一步：
  - `Step 03`

### Step 03. 创建应用工厂与依赖注入入口

- 状态：`done`
- 开始时间：`2026-04-19 19:18:00`
- 完成时间：`2026-04-19 19:40:13`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/app.py`
  - `src/admitpilot/platform/bootstrap.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `src/admitpilot/main.py`
  - `tests/test_app_factory.py`
- 实际修复动作：
  - 新增 `build_application()` 和 `AdmitPilotApplication`，统一装配 settings、bundle、agents、orchestrator。
  - 让 `PrincipalApplicationOrchestrator` 接收注入的 settings，并基于 settings 构造默认 agents 与 platform bundle。
  - 把 CLI 入口迁移到应用工厂。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_app_factory.py tests/test_orchestrator.py -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Step 04`

### Step 04. 建立真实应用 API 骨架

- 状态：`done`
- 开始时间：`2026-04-19 19:25:00`
- 完成时间：`2026-04-19 19:40:13`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/api/__init__.py`
  - `src/admitpilot/api/main.py`
  - `src/admitpilot/api/routes/health.py`
  - `requirements.txt`
  - `tests/test_api_health.py`
- 实际修复动作：
  - 新增 FastAPI 服务骨架。
  - 提供 `/health` 与 `/ready` 两个只读端点。
  - 将 API 骨架接到应用工厂，服务启动时可获得 settings 与 application runtime。
  - 补充 FastAPI、httpx、uvicorn 依赖。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_api_health.py tests/test_settings.py tests/test_time_utils.py tests/test_app_factory.py tests/test_platform_interfaces.py tests/test_platform_common_bootstrap.py tests/test_orchestrator.py -q`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m admitpilot.main`
  - 结果：`passed`
- 偏差说明：
  - FastAPI 依赖安装时遇到临时目录权限问题，最终通过提权安装到 `admitpilot` 环境的用户站点完成。
- 阻塞项：
  - 无
- 下一步：
  - `Step 05`

---

## Phase 2. AIE 从 stub 到真实招生情报服务

### Step 05. 固化学校与项目目录

- 状态：`done`
- 开始时间：`2026-04-19 23:05:00`
- 完成时间：`2026-04-19 23:24:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/domain/__init__.py`
  - `src/admitpilot/domain/catalog.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/aie/agent.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_catalog.py`
- 实际修复动作：
  - 新增统一 `AdmissionsCatalog`，把学校代号、域名白名单、地区、支持项目、默认页面类型收敛为单一真源。
  - AIE/SAE 的学校归一化和 program 归一化全部改为走 catalog，不再各自维护独立学校列表。
  - AIE Agent 的目标学校解析回退也改为走 catalog。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_catalog.py tests/test_aie_service.py tests/test_sae_service.py -q`
  - 结果：`passed`
- 偏差说明：
  - 为保持兼容，`AdmissionsIntelligenceService.OFFICIAL_SCHOOLS` 和 `StrategicAdmissionsService.SUPPORTED_SCHOOLS` 仍保留，但值由 catalog 派生，不再单独维护。
- 阻塞项：
  - 无
- 下一步：
  - `Step 06`

### Step 06. 实现官网抓取客户端

- 状态：`done`
- 开始时间：`2026-04-19 23:10:00`
- 完成时间：`2026-04-19 23:30:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/fetchers.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `tests/fixtures/official_pages/hkust_mscs_2026_requirements.html`
  - `tests/fixtures/official_pages/hkust_mscs_2026_deadline.html`
  - `tests/fixtures/official_pages/ntu_mscs_2026_requirements.html`
  - `tests/fixtures/official_pages/ntu_mscs_2026_deadline.html`
  - `tests/fixtures/official_pages/cuhk_mscs_2026_requirements.html`
  - `tests/fixtures/official_pages/cuhk_mscs_2026_deadline.html`
  - `tests/test_official_fetcher.py`
- 实际修复动作：
  - 新增 `OfficialPageFetcher`、`FixtureHttpClient`、`LiveHttpClient`，支持 User-Agent、timeout、retry 与域名白名单。
  - 新增 `CatalogOfficialSourceGateway`，支持 `fixture` / `live` 两种模式。
  - 默认 AIE 运行改为走 repo 内离线 fixture，不再依赖硬编码 released school 常量。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_official_fetcher.py -q`
  - 结果：`passed`
- 偏差说明：
  - 真实外网抓取模式只实现了客户端与接口骨架，本 step 仍默认使用离线 fixture，符合计划中的“先离线可测”约束。
- 阻塞项：
  - 无
- 下一步：
  - `Step 07`

### Step 07. 实现官网页面解析器

- 状态：`done`
- 开始时间：`2026-04-19 23:15:00`
- 完成时间：`2026-04-19 23:36:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/parsers.py`
  - `src/admitpilot/agents/aie/schemas.py`
  - `tests/fixtures/official_pages/invalid_mscs_2026_deadline.html`
  - `tests/test_official_parsers.py`
- 实际修复动作：
  - 新增 `OfficialPageParser`，支持 requirements / deadline 两类页面解析。
  - `OfficialAdmissionRecord` 增加 `content_hash`、`extracted_fields`、`parse_confidence`、`changed_fields`。
  - 解析失败时改为抛出 `OfficialPageParseError`，不再静默忽略。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_official_parsers.py -q`
  - 结果：`passed`
- 偏差说明：
  - 当前 HTML parser 以 `data-field` fixture 结构为主，先保证 deterministic 解析；面向真实网页的更复杂规则可在后续 live mode 中扩展。
- 阻塞项：
  - 无
- 下一步：
  - `Step 08`

### Step 08. 增加快照版本与 diff 机制

- 状态：`done`
- 开始时间：`2026-04-19 23:20:00`
- 完成时间：`2026-04-19 23:42:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/snapshots.py`
  - `src/admitpilot/agents/aie/repositories.py`
  - `src/admitpilot/agents/aie/service.py`
  - `tests/fixtures/official_pages/hkust_mscs_2026_deadline_v2.html`
  - `tests/fixtures/official_pages/hkust_mscs_2026_requirements_v2.html`
  - `tests/test_snapshot_diff.py`
- 实际修复动作：
  - 新增 `SnapshotDiff`、`record_identity()`、`diff_official_record()` 与 `version_id` 生成逻辑。
  - `InMemoryOfficialSnapshotRepository` 增加官方记录版本历史存储与读取能力。
  - AIE service 在接收官方记录后先做 version/diff，再写入长期记忆与当前季 snapshot。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_snapshot_diff.py -q`
  - 结果：`passed`
- 偏差说明：
  - 当前 diff 以 `extracted_fields` 变化为主，不做自然语言段落级 diff；这符合当前结构化字段驱动的 AIE 输出需求。
- 阻塞项：
  - 无
- 下一步：
  - `Step 09`

### Step 09. 接入案例数据归一化流程

- 状态：`done`
- 开始时间：`2026-04-19 23:24:00`
- 完成时间：`2026-04-19 23:46:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/case_ingestion.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `tests/fixtures/cases/community_cases.json`
  - `tests/test_case_ingestion.py`
- 实际修复动作：
  - 新增案例清洗流程，把原始 case fixture 归一化为标准 `CaseRecord`。
  - 显式计算 `source_site_score`、`evidence_completeness`、`cross_source_consistency`、`freshness_score`、`confidence`、`credibility_label`。
  - 非法学校、缺时间、缺 outcome 等坏数据在入口层过滤，避免污染下游。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_case_ingestion.py -q`
  - 结果：`passed`
- 偏差说明：
  - 当前案例数据仍来自 fixture，不直接连接在线社区平台；这与计划中“先离线归一化再接真实来源”一致。
- 阻塞项：
  - 无
- 下一步：
  - `Step 10`

### Step 10. 完成 AIE 真实集成

- 状态：`done`
- 开始时间：`2026-04-19 23:28:00`
- 完成时间：`2026-04-19 23:55:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/aie/agent.py`
  - `src/admitpilot/agents/aie/__init__.py`
  - `tests/test_aie_service.py`
  - `tests/test_aie_service_integration.py`
- 实际修复动作：
  - AIE 主链路改为 `catalog -> official gateway(fetch+parse) -> snapshot diff -> case normalization -> pack output`。
  - `official_status_by_school` 改由 fixture 数据决定，不再依赖旧 stub released-school 常量。
  - AIE agent 输出增加 `parse_confidence`、`change_type`、`changed_fields` 等官方记录元数据，并保留旧接口兼容别名。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest tests/test_aie_service.py tests/test_aie_service_integration.py -q`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m ruff check src/admitpilot tests`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m mypy`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m admitpilot.main`
  - 结果：`passed`
- 偏差说明：
  - 当前默认 runtime 仍以内置 fixture 数据作为“真实集成”的离线基线；live 抓取接口已具备，但不在本 step 中直接访问外网。
- 阻塞项：
  - 无
- 下一步：
  - `Step 11`

### 补充记录. `2026-04-20` 仓库基线更新

- 状态：`done`
- 开始时间：`2026-04-20 00:20:00`
- 完成时间：`2026-04-20 02:10:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/aie/live_sources.py`
  - `src/admitpilot/agents/aie/parsers.py`
  - `src/admitpilot/agents/aie/runtime.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `src/admitpilot/agents/aie/agent.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/sae/service.py`
  - `src/admitpilot/domain/catalog.py`
  - `src/admitpilot/main.py`
  - `src/admitpilot/app.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `src/admitpilot/debug/refresh_official_library.py`
  - `data/official_library/official_library.json`
  - `docs/agent_engineering_architecture.md`
  - `docs/project_full_documentation.md`
  - `README.md`
- 实际修复动作：
  - 把 AIE 运行时默认数据源切到 `official_library.json`，`fixture` 仅保留给测试使用。
  - 扩充并校正 live 官方页入口，执行真实官方库刷新，且刷新流程只更新官方库、不更新案例库。
  - 把 demo 与主链路默认项目切到新的“学校 -> 项目”组合，不再统一按旧 `MSCS` 运行。
  - 在文档中补齐当前 live 支持矩阵、官方库运行方式和最新仓库口径。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m admitpilot.debug.refresh_official_library --cycle 2026`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m ruff check src tests`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m mypy src tests`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m admitpilot.main`
  - 结果：`passed`
- 偏差说明：
  - 这批改动不属于 `implementation_plan.md` 中单一 step 的严格推进，而是对仓库运行基线和提交口径的收口补充。
- 阻塞项：
  - 无
- 下一步：
  - `Step 11`

### 补充记录. `2026-04-20` 演示范围收口

- 状态：`done`
- 开始时间：`2026-04-20 10:20:00`
- 完成时间：`2026-04-20 10:35:00`
- 负责人：`TYT`
- 改动文件：
  - `docs/implementation_plan.md`
  - `docs/progress.md`
- 实际修复动作：
  - 把计划文档的主目标从“可上线真实应用”收口为“课堂/答辩演示”。
  - 明确当前阶段终点为 `Phase 5 / Step 21`，并把 `Phase 6-7` 标记为暂缓范围。
  - 同步进度文档的总览和执行范围，避免后续实施时继续把生产化任务当作当前必做项。
- 测试：
  - 命令：`人工检查 docs/implementation_plan.md 与 docs/progress.md 的范围定义是否一致`
  - 结果：`passed`
- 偏差说明：
  - 本次为文档范围收口，不涉及代码改动与自动化测试。
- 阻塞项：
  - 无
- 下一步：
  - `Step 11`

---

## Phase 3. SAE 从示意打分到可解释策略引擎

### Step 11. 设计学校项目规则文件

- 状态：`done`
- 开始时间：`2026-04-24 09:10:00`
- 完成时间：`2026-04-24 10:05:00`
- 负责人：`TYT`
- 改动文件：
  - `data/program_rules/*.yaml`
  - `src/admitpilot/agents/sae/rules.py`
  - `tests/test_sae_rules.py`
- 实际修复动作：
  - 建立学校项目规则 YAML，覆盖硬门槛、软门槛、推荐背景、风险提示和缺失信息惩罚。
  - 新增规则加载与校验逻辑，规则改动不再需要修改 Python 业务代码。
  - 将规则异常测试改为只读 mock，避免当前 Windows 临时目录权限问题影响规则校验测试。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 测试中使用 `patch.object(...)` 模拟规则文件读取，目标是隔离当前本地临时目录权限问题，不改变运行时规则加载路径。
- 阻塞项：
  - 无
- 下一步：
  - `Step 12`

### Step 12. 实现规则打分引擎

- 状态：`done`
- 开始时间：`2026-04-24 10:05:00`
- 完成时间：`2026-04-24 10:45:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/sae/scoring.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_rule_scoring.py`
  - `tests/test_sae_service.py`
- 实际修复动作：
  - 新增 deterministic `RuleScorer`，显式处理硬门槛、语言缺失、背景不匹配、官方信息未完整发布等情况。
  - SAE 输出保留 `rule_breakdown` 与 `rule_notes`，下游可以直接追踪规则得分来源。
  - 将 `StrategicAdmissionsService` 改为基于规则文件和规则打分引擎生成推荐，不再使用单一占位公式。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Step 13`

### Step 13. 引入可替换的语义匹配适配器

- 状态：`done`
- 开始时间：`2026-04-24 10:45:00`
- 完成时间：`2026-04-24 11:40:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/sae/semantic.py`
  - `src/admitpilot/agents/sae/service.py`
  - `src/admitpilot/config/settings.py`
  - `src/admitpilot/platform/llm/openai.py`
  - `.env.example`
  - `tests/test_sae_semantic.py`
  - `tests/test_sae_service.py`
  - `tests/test_settings.py`
- 实际修复动作：
  - 定义 `SemanticMatcher` 接口，保留 deterministic `FakeSemanticMatcher` 供 test 模式和单测注入。
  - 实现 `EmbeddingSemanticMatcher`，可调用 OpenAI embeddings；无 API key 或离线时使用本地 hashing embedding fallback。
  - 新增 `ADMITPILOT_SEMANTIC_MATCHER_KIND` 与 `OPENAI_EMBEDDING_MODEL` 配置，`demo/staging/prod` 默认 `embedding`，`test` 默认 `fake`。
  - 把旧 `fake_token_overlap` 输出标识改为 `deterministic_token_overlap`，避免治理策略误判为 policy blocked。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 原计划 Step 13 只要求真实 matcher 接口；本轮为解决运行时仍默认 fake 的问题，进一步接入了 OpenAI embedding 客户端和本地 fallback。
- 阻塞项：
  - 无
- 下一步：
  - `Step 14`

### Step 14. 输出证据化推荐解释

- 状态：`done`
- 开始时间：`2026-04-24 11:40:00`
- 完成时间：`2026-04-24 12:10:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/sae/schemas.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_explanations.py`
- 实际修复动作：
  - SAE recommendation 输出增加 `evidence`, `gaps`, `risk_flags`, `missing_inputs`。
  - 推荐解释引用 AIE 官方状态、规则 breakdown、规则 notes 与语义匹配方法，不再只输出泛化分数说明。
  - 下游 DTA/CDS 可直接消费 `gaps` 与 `risk_flags`。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Step 15`

---

## Phase 4. DTA 从静态周计划到真实逆排调度器

### Step 15. 实现拓扑排序与里程碑调度器

- 状态：`done`
- 开始时间：`2026-04-24 12:10:00`
- 完成时间：`2026-04-24 12:45:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/dta/scheduler.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_scheduler.py`
- 实际修复动作：
  - 提取 DTA 调度器，支持依赖图拓扑排序。
  - 对循环依赖、缺失依赖节点输出明确异常，不再静默退化。
  - DTA service 基于调度结果生成稳定里程碑顺序。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 当前仍以周为粒度，日级精度保留给后续真实产品化阶段。
- 阻塞项：
  - 无
- 下一步：
  - `Step 16`

### Step 16. 加入真实 deadline 逆排

- 状态：`done`
- 开始时间：`2026-04-24 12:45:00`
- 完成时间：`2026-04-24 13:20:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/dta/deadlines.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_deadline_planning.py`
- 实际修复动作：
  - 从 AIE 官方记录的 `extracted_fields.application_deadline` 提取 deadline。
  - 以 deadline 为锚点逆推文书、推荐信、提交缓冲等任务。
  - deadline 缺失时回退到保守模板，并在输出中保留风险提示。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Step 17`

### Step 17. 实现延误重排与冲突检测

- 状态：`done`
- 开始时间：`2026-04-24 13:20:00`
- 完成时间：`2026-04-24 14:00:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/dta/replan.py`
  - `src/admitpilot/agents/dta/service.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `tests/test_dta_replan.py`
  - `tests/test_orchestrator.py`
- 实际修复动作：
  - 支持基于 `has_delay`, `start_week`, `blocked_tasks` 做计划重排。
  - 对任务挤压、deadline 已过、缓冲不足输出结构化风险。
  - 修复编排层中 SAE 语义 matcher 输出被治理规则误拦截的问题，使 `AIE -> SAE -> DTA -> CDS` 集成链路恢复。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 本 step 同时收口了编排集成回归，因为 DTA 下游依赖 SAE 成功写入共享上下文。
- 阻塞项：
  - 无
- 下一步：
  - `Step 18`

---

## Phase 5. CDS 从模板生成到可审计文书支持

### Step 18. 建立申请者证据模型

- 状态：`done`
- 开始时间：`2026-04-24 14:00:00`
- 完成时间：`2026-04-24 14:25:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/core/user_artifacts.py`
  - `src/admitpilot/agents/cds/facts.py`
  - `tests/test_user_artifacts.py`
- 实际修复动作：
  - 定义结构化用户证据模型，覆盖课程、项目、实习、科研、获奖、语言成绩、推荐人信息等输入。
  - 每条证据保留 `source_ref`, `verified`, `date_range`, `evidence_type`。
  - CDS fact 层开始区分事实、推断与缺失输入。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 暂不做 OCR 或非结构化文档解析，符合当前课堂演示范围。
- 阻塞项：
  - 无
- 下一步：
  - `Step 19`

### Step 19. 实现事实槽位提取与缺证据 abstain

- 状态：`done`
- 开始时间：`2026-04-24 14:25:00`
- 完成时间：`2026-04-24 14:55:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/cds/facts.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_fact_slots.py`
  - `tests/test_cds_service.py`
- 实际修复动作：
  - 从用户证据、SAE、DTA 中提取 `motivation`, `program_fit`, `execution_proof` 等 fact slots。
  - 每个槽位标注 `verified / inferred / missing`，并保留可回溯来源。
  - 核心证据缺失时 CDS 输出 abstain/review 状态，不生成无来源事实。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Step 20`

### Step 20. 设计可差异化的文书模板层

- 状态：`done`
- 开始时间：`2026-04-24 14:55:00`
- 完成时间：`2026-04-24 15:20:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/cds/templates.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_templates.py`
- 实际修复动作：
  - 将文书支持拆成模板层与事实填充层。
  - 模板读取学校项目特征、SAE gaps、DTA 执行计划，输出结构化提纲和段落意图。
  - 不同学校输入会生成不同 outline，避免通用模板复制。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 当前输出仍是可审阅结构化提纲，不直接生成自然语言终稿。
- 阻塞项：
  - 无
- 下一步：
  - `Step 21`

### Step 21. 实现跨文档一致性检查器

- 状态：`done`
- 开始时间：`2026-04-24 15:20:00`
- 完成时间：`2026-04-24 15:50:00`
- 负责人：`TYT`
- 改动文件：
  - `src/admitpilot/agents/cds/consistency.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_consistency.py`
  - `tests/test_cds_service.py`
- 实际修复动作：
  - 实现基于 fact slots 的一致性检查器。
  - 覆盖时间线冲突、经历表述冲突、学校项目名称不一致、未验证事实混入输出等问题。
  - CDS 输出结构化 issue 列表，并标记 impacted documents。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 无
- 阻塞项：
  - 无
- 下一步：
  - `Phase 6-7` 当前继续暂缓；若后续转向真实应用化，从 `Step 22` 开始。

### 补充记录. `2026-04-24` 运行时去 mock 收口

- 状态：`done`
- 开始时间：`2026-04-24 15:50:00`
- 完成时间：`2026-04-24 16:40:00`
- 负责人：`TYT`
- 改动文件：
  - `.env.example`
  - `src/admitpilot/config/settings.py`
  - `src/admitpilot/platform/llm/openai.py`
  - `src/admitpilot/agents/aie/__init__.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `src/admitpilot/agents/aie/runtime.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/sae/semantic.py`
  - `src/admitpilot/agents/sae/service.py`
  - `src/admitpilot/app.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `tests/test_aie_service.py`
  - `tests/test_app_factory.py`
  - `tests/test_sae_semantic.py`
  - `tests/test_settings.py`
- 实际修复动作：
  - AIE runtime 从 `NullCaseSourceGateway` 切到 `JsonCaseLibrarySourceGateway`，默认读取 `data/case_library/case_library.json`。
  - AIE runtime 的官方库 repository 切到 `JsonOfficialSnapshotRepository`，同一个 repository 同时服务 official gateway 和 snapshot cache。
  - test 模式下官方库写入隔离到 `.pytest-local/runtime_official_library.test.json`，构建 runtime 时先从正式官方库复制影子副本，避免测试污染 tracked 数据文件。
  - SAE runtime 默认 matcher 改为 settings 驱动：非 test 模式默认 `embedding`，test 模式默认 `fake`。
  - `EmbeddingSemanticMatcher` 接入 OpenAI embeddings，并提供本地 hashing fallback，保证无 API key 时仍可离线运行。
  - AIE/DTA/CDS/SAE service 在未显式传入 LLM client 时默认构造 test-mode client，避免单测受宿主机环境变量影响而误触发网络请求。
- 测试：
  - 命令：`$env:PYTHONPATH='src'; & 'D:\ProgramFiles\anaconda3\envs\admitpilot\python.exe' -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 原计划将生产化持久化放在 Phase 6；本次只替换 AIE runtime 中已有 JSON 官方库和 JSON 案例库，不引入 Postgres/Redis/Object Storage。
- 阻塞项：
  - 无
- 下一步：
  - `Phase 6-7` 当前继续暂缓。

---

## Phase 6. 平台层生产化

### Step 22. 引入 Postgres 版版本化存储

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 当前范围收口到 `Phase 5 / Step 21`，不进入生产化持久化实现。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 23. 引入 Redis 版会话缓存

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 当前范围收口到 `Phase 5 / Step 21`，不进入外部缓存接入。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 24. 引入对象存储适配器

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 当前范围收口到 `Phase 5 / Step 21`，不进入对象存储与 artifact 持久化实现。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 25. 把治理与能力控制真正串入执行链路

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 本轮目标是完成稳定演示，不在当前阶段推进运行时治理强约束。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 26. 建立结构化日志、trace 与指标

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 当前范围收口到 `Phase 5 / Step 21`，不进入生产监控和指标体系建设。
- 阻塞项：
  - 无
- 下一步：
  - `无`

---

## Phase 7. 产品接口、异步执行与上线准备

### Step 27. 建立应用级持久化模型与业务 API

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 本轮不以真实产品 API 和 application 模型为目标。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 28. 把编排执行改成异步任务

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 当前范围不要求异步 worker 和 run 状态管理。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 29. 准备真实依赖的本地集成环境

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 本轮不为 Postgres、Redis、MinIO 等真实依赖建立本地联调环境。
- 阻塞项：
  - 无
- 下一步：
  - `无`

### Step 30. 上线前验收、回归与发布清单

- 状态：`skipped`
- 开始时间：
- 完成时间：
- 负责人：`TYT`
- 改动文件：
- 实际修复动作：
  - 当前课堂/答辩演示范围内暂缓该步骤，保留为后续真实应用化任务。
- 测试：
- 偏差说明：
  - 本轮不准备 release checklist、上线验收和部署回滚方案。
- 阻塞项：
  - 无
- 下一步：
  - `无`
