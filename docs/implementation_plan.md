# AdmitPilot 实施计划（当前按课堂/答辩演示目标执行）

- 文档日期：`2026-04-25`
- 适用代码基线：`src/admitpilot`
- 文档目标：把当前课程 demo 原型推进到可稳定答辩演示的版本；上线相关内容保留为后续扩展参考
- 执行原则：每一步都要小、具体、可验证；每一步完成后必须先通过测试，再进入下一步

## 当前范围裁剪（课堂/答辩演示）

1. 当前执行终点仍为 `Phase 5 / Step 21`，`AIE -> SAE -> DTA -> CDS` 稳定演示链路已完成。
2. `Phase 1-5` 已完成课堂/答辩演示范围收口。
3. `Phase 6-7` 保留在本文件中，作为未来真实应用化的预留步骤；本轮答辩范围内默认不执行。
4. 运行时基线以当前仓库状态为准：AIE 默认采用 `live-first` 官网抓取，并在字段校正失败或字段缺失时回退到 `data/official_library/official_library.json`；AIE 默认读取 `data/case_library/case_library.json`；`fixture` 仅保留测试使用；`refresh_official_library.py` 是官方库刷新入口。
5. SAE 默认使用 embedding matcher；测试与单测场景保留 deterministic fake matcher；无 API key 时 embedding matcher 使用本地 hashing fallback，保证离线演示可运行。
6. 如果后续目标仍仅限课堂演示，不扩展部署、数据库、异步 worker 等生产化内容；如果目标转向真实应用化，从 `Phase 6 / Step 22` 开始。

## 0. 执行约束

1. 所有命令默认在 PowerShell 中执行。
2. 所有 Python 命令都必须先进入 `admitpilot` conda 环境。
3. 每一步只做该步骤要求的改动，不顺手做大重构。
4. 每一步至少新增或更新 1 个自动化测试。
5. 所有外部依赖接入都必须先做可离线运行的 fixture/mock 测试，再做真实集成。
6. 没有通过测试，不允许进入下一步。

## 1. 通用执行模板

每一步都按以下模板交付：

1. 修改指定文件，不扩散改动范围。
2. 补充对应测试文件。
3. 运行该步骤的定向测试。
4. 若该步骤改动了核心链路，再运行一次相关集成测试。
5. 在提交说明中写清“改了什么、如何验证、还未覆盖什么”。

通用命令模板：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest <target-tests> -q
```

---

## Phase 1. 基础设施与运行边界固化

### Step 01. 引入统一配置层

- 目标：把散落在代码里的环境变量读取、默认值和运行模式收敛到单一配置对象。
- 主要文件：
  - `src/admitpilot/config/__init__.py`
  - `src/admitpilot/config/settings.py`
  - `.env.example`
  - `tests/test_settings.py`
- 给 AI 开发者的指令：
  - 创建 `AdmitPilotSettings`，集中管理 LLM、数据库、缓存、对象存储、运行模式、时区、日志级别等配置。
  - 不要直接在业务模块里继续调用 `os.getenv()`；改为从 settings 对象读取。
  - 为 `demo`, `test`, `staging`, `prod` 提供明确的模式字段。
  - 在 `.env.example` 中补齐所有必需环境变量说明。
- 验证测试：
  - 新增 `tests/test_settings.py`，覆盖默认值、环境变量覆盖、缺失关键变量时报错。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_settings.py -q
```

- 通过标准：
  - 业务代码不再直接读取环境变量。
  - 配置对象可被单元测试独立构造。

### Step 02. 统一时间与时区工具

- 目标：移除 `datetime.utcnow()` 的分散使用，统一为 timezone-aware UTC 时间。
- 主要文件：
  - `src/admitpilot/platform/common/time.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `src/admitpilot/platform/security/capability.py`
  - `src/admitpilot/platform/observability/contracts.py`
  - `src/admitpilot/platform/governance/contracts.py`
  - `src/admitpilot/platform/memory/adapters.py`
  - `tests/test_time_utils.py`
- 给 AI 开发者的指令：
  - 创建统一工具函数，如 `utc_now()`, `ensure_utc()`, `to_iso_utc()`。
  - 替换项目中的 `datetime.utcnow()` 调用。
  - 不修改业务语义，只做时间源标准化。
- 验证测试：
  - 新增 `tests/test_time_utils.py`，验证返回值带 `tzinfo=UTC`。
  - 跑全量测试并确认不再出现 `utcnow()` 弃用 warning。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_time_utils.py tests/test_aie_service.py tests/test_orchestrator.py -q
```

- 通过标准：
  - 核心模块不再直接使用 `datetime.utcnow()`。
  - 测试日志中不再出现相关弃用 warning。

### Step 03. 创建应用工厂与依赖注入入口

- 目标：让 `demo/test/prod` 可以按配置切换依赖，而不是在 orchestrator 内硬编码构造。
- 主要文件：
  - `src/admitpilot/app.py`
  - `src/admitpilot/platform/bootstrap.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `tests/test_app_factory.py`
- 给 AI 开发者的指令：
  - 新增 `build_application(settings)` 或等价工厂，统一装配 agents、memory、governance、llm client。
  - `PrincipalApplicationOrchestrator` 应接受外部注入的 bundle 和 agent 集合。
  - `main.py` 改为调用应用工厂，不再直接 new 默认对象。
- 验证测试：
  - 新增 `tests/test_app_factory.py`，验证不同运行场景能装配预期依赖。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_app_factory.py tests/test_orchestrator.py -q
```

- 通过标准：
  - 测试中可以显式注入 fake gateway / fake repository。
  - 应用装配不依赖全局状态。

### Step 04. 建立真实应用 API 骨架

- 目标：从“脚本入口”升级为“可作为服务启动的应用入口”。
- 主要文件：
  - `src/admitpilot/api/__init__.py`
  - `src/admitpilot/api/main.py`
  - `src/admitpilot/api/routes/health.py`
  - `tests/test_api_health.py`
- 给 AI 开发者的指令：
  - 使用 FastAPI 创建最小 API 应用。
  - 先只加 `/health` 与 `/ready` 两个只读端点。
  - 不要在这一步引入业务接口，只把服务骨架搭起来。
  - 若缺少依赖，再更新 `requirements.txt`。
- 验证测试：
  - 新增 API 测试，断言 `/health` 返回 200 和版本/状态字段。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_api_health.py -q
```

- 通过标准：
  - 能以服务方式启动。
  - 健康检查不依赖外部系统。

---

## Phase 2. AIE 从 stub 到真实招生情报服务

### Step 05. 固化学校与项目目录

- 目标：把支持学校、项目、地区、页面类型从硬编码常量提取为统一目录。
- 主要文件：
  - `src/admitpilot/domain/catalog.py`
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_catalog.py`
- 给 AI 开发者的指令：
  - 创建统一的 school/program catalog。
  - 每个学校至少定义：标准代号、官网域名白名单、支持项目、地区、默认页面类型。
  - AIE/SAE 不要再各自维护重复的 `SUPPORTED_SCHOOLS`。
- 验证测试：
  - 新增 `tests/test_catalog.py`，验证学校代码归一化、非法学校过滤、项目范围查询。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_catalog.py tests/test_aie_service.py -q
```

- 通过标准：
  - 项目支持范围只有一份真源。
  - AIE/SAE 的学校归一化逻辑都走 catalog。

### Step 06. 实现官网抓取客户端

- 目标：为 AIE 接入真实官方页面抓取能力，但测试保持离线可跑。
- 主要文件：
  - `src/admitpilot/agents/aie/fetchers.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `tests/fixtures/official_pages/*.html`
  - `tests/test_official_fetcher.py`
- 给 AI 开发者的指令：
  - 新增可注入的 HTTP fetch client，支持超时、重试、User-Agent、域名白名单。
  - gateway 要能切换 `fixture mode` 和 `live mode`。
  - 测试只用本地 fixture，不直接打外网。
- 验证测试：
  - 用本地 html fixture 验证抓取客户端能返回页面内容和元信息。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_official_fetcher.py -q
```

- 通过标准：
  - fetch 层和解析层解耦。
  - 非白名单域名会被拒绝。

### Step 07. 实现官网页面解析器

- 目标：把官网 HTML 解析成结构化 requirements/deadline/policy 记录。
- 主要文件：
  - `src/admitpilot/agents/aie/parsers.py`
  - `src/admitpilot/agents/aie/schemas.py`
  - `tests/test_official_parsers.py`
  - `tests/fixtures/official_pages/*.html`
- 给 AI 开发者的指令：
  - 先只支持最关键的两类页面：requirements 与 deadline。
  - 每条结构化记录至少包含：school, program, cycle, page_type, source_url, extracted_fields, parse_confidence。
  - 解析失败时要显式返回错误，而不是 silently ignore。
- 验证测试：
  - 为每种 fixture 页面写解析测试，验证 deadline、语言要求、申请材料字段可抽取。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_official_parsers.py -q
```

- 通过标准：
  - fixture 页面能稳定输出结构化字段。
  - 解析失败有明确错误码或异常类型。

### Step 08. 增加快照版本与 diff 机制

- 目标：让 AIE 能识别“官网变更”，而不是只存一份结果。
- 主要文件：
  - `src/admitpilot/agents/aie/snapshots.py`
  - `src/admitpilot/agents/aie/repositories.py`
  - `src/admitpilot/agents/aie/service.py`
  - `tests/test_snapshot_diff.py`
- 给 AI 开发者的指令：
  - 为官方页面快照设计 `content_hash`, `version_id`, `changed_fields`, `change_type`。
  - 新旧快照对比时，输出结构化 diff。
  - AIE summary 中要能说明“有无政策更新、更新了什么”。
- 验证测试：
  - 构造两版 fixture 页面，断言 diff 能识别 deadline 变化和 requirements 变化。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_snapshot_diff.py -q
```

- 通过标准：
  - 相同内容不会生成新版本。
  - 字段变更可被结构化追踪。

### Step 09. 接入案例数据归一化流程

- 目标：把第三方案例从 stub 升级为可清洗、可评分的标准化数据流。
- 主要文件：
  - `src/admitpilot/agents/aie/case_ingestion.py`
  - `src/admitpilot/agents/aie/gateways.py`
  - `tests/fixtures/cases/*.json`
  - `tests/test_case_ingestion.py`
- 给 AI 开发者的指令：
  - 设计案例原始输入到标准 `CaseRecord` 的清洗流程。
  - 把来源可信度、时间新鲜度、证据完整度、交叉验证一致性显式算出来。
  - 先基于 fixture 数据完成，不要直接依赖在线平台。
- 验证测试：
  - 新增案例清洗测试，验证字段映射、置信度分层、非法案例过滤。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_case_ingestion.py -q
```

- 通过标准：
  - 输入坏数据不会污染下游。
  - 案例记录带清晰的 source 和 confidence 元数据。

### Step 10. 完成 AIE 真实集成

- 目标：把官网抓取、解析、快照、案例清洗接回 `AdmissionsIntelligenceService`。
- 主要文件：
  - `src/admitpilot/agents/aie/service.py`
  - `src/admitpilot/agents/aie/agent.py`
  - `tests/test_aie_service_integration.py`
- 给 AI 开发者的指令：
  - 让 AIE service 走“catalog -> fetch -> parse -> snapshot -> case normalize -> pack output”完整路径。
  - 预测逻辑只在当前季官方信息不足时触发。
  - 输出必须清楚区分 `official`, `case`, `forecast`。
- 验证测试：
  - 新增集成测试，覆盖：
    - 官网已发布
    - 官网未发布但历史可预测
    - 官网更新触发 diff
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_aie_service.py tests/test_aie_service_integration.py -q
```

- 通过标准：
  - AIE 输出不再依赖 stub 常量决定学校发布状态。
  - `official_status_by_school` 能随 fixture 数据变化而变化。

---

## Phase 3. SAE 从示意打分到可解释策略引擎

### Step 11. 设计学校项目规则文件

- 目标：把 GPA/语言/先修课/偏好等规则从代码里抽到数据文件。
- 主要文件：
  - `data/program_rules/*.yaml`
  - `src/admitpilot/agents/sae/rules.py`
  - `tests/test_sae_rules.py`
- 给 AI 开发者的指令：
  - 为每个学校项目定义规则文件 schema。
  - 字段至少包括：硬门槛、软门槛、推荐背景、风险提示、缺失信息惩罚。
  - SAE 不能再靠硬编码默认 GPA/IELTS。
- 验证测试：
  - 用 2-3 个 yaml fixture 验证 schema 校验、字段加载和错误提示。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_sae_rules.py -q
```

- 通过标准：
  - 规则文件可独立校验。
  - 规则改动不需要改 Python 代码。

### Step 12. 实现规则打分引擎

- 目标：让 `rule_score` 由真实规则计算，而不是占位公式。
- 主要文件：
  - `src/admitpilot/agents/sae/scoring.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_rule_scoring.py`
- 给 AI 开发者的指令：
  - 新增 `RuleScorer`，显式处理：满足硬门槛、缺失语言、背景不匹配、官方信息未完整发布等情况。
  - 评分结果必须能返回 breakdown，而不是只有一个总分。
  - 先不要引入 LLM，让规则引擎先 deterministic。
- 验证测试：
  - 构造高背景、中背景、硬门槛不达标三类 profile。
  - 断言每类的 `rule_score` 和 `breakdown` 符合预期。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_sae_rule_scoring.py tests/test_sae_service.py -q
```

- 通过标准：
  - 规则分数可解释。
  - 硬门槛失败会显著影响推荐层级。

### Step 13. 引入可替换的语义匹配适配器

- 目标：把占位的 token overlap 逻辑替换成可插拔语义匹配接口。
- 主要文件：
  - `src/admitpilot/agents/sae/semantic.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_semantic.py`
- 给 AI 开发者的指令：
  - 定义 `SemanticMatcher` 接口，允许 fake matcher 与真实 embedding matcher 切换。
  - 默认测试用 fake matcher，返回确定性分数。
  - 真实 matcher 先只留接口和工厂，不在本步接在线模型。
- 验证测试：
  - 验证相同 profile 在 fake matcher 下输出稳定一致。
  - 验证 service 可注入 matcher。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_sae_semantic.py tests/test_sae_service.py -q
```

- 通过标准：
  - SAE 不再在 service 内硬编码语义打分逻辑。
  - 语义层可单测、可替换。

### Step 14. 输出证据化推荐解释

- 目标：让 SAE 的每条推荐都能回答“为什么是这个 tier/顺序”。
- 主要文件：
  - `src/admitpilot/agents/sae/schemas.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_explanations.py`
- 给 AI 开发者的指令：
  - 在 recommendation 输出中增加 `evidence`, `gaps`, `risk_flags`, `missing_inputs`。
  - 解释内容必须引用上游 AIE 与规则评分的具体依据。
  - 不允许只输出“分数高/低”这种泛解释。
- 验证测试：
  - 检查 recommendation 中存在证据字段，且至少引用一条官方状态或规则命中信息。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_sae_explanations.py tests/test_sae_service.py -q
```

- 通过标准：
  - 每条推荐都有结构化解释。
  - 下游 DTA/CDS 可以直接使用 `gaps` 和 `risk_flags`。

---

## Phase 4. DTA 从静态周计划到真实逆排调度器

### Step 15. 实现拓扑排序与里程碑调度器

- 目标：把当前占位的 due_week 赋值改成真实的依赖图调度。
- 主要文件：
  - `src/admitpilot/agents/dta/scheduler.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_scheduler.py`
- 给 AI 开发者的指令：
  - 提取独立调度器，支持依赖图拓扑排序。
  - 若存在循环依赖，抛出明确异常。
  - 先以周为粒度，不做日级精度。
- 验证测试：
  - 覆盖正常 DAG、循环依赖、缺失依赖节点三类用例。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_dta_scheduler.py -q
```

- 通过标准：
  - DTA 对依赖顺序的输出可预测、可验证。
  - 出错场景不会 silently 退化。

### Step 16. 加入真实 deadline 逆排

- 目标：让时间线围绕学校 deadline 逆向生成，而不是固定 8 周模板。
- 主要文件：
  - `src/admitpilot/agents/dta/deadlines.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_deadline_planning.py`
- 给 AI 开发者的指令：
  - 从 AIE 的官方记录中读取 deadline。
  - 以 deadline 为锚点逆推文书、标化、推荐信、提交缓冲等任务。
  - deadline 缺失时才回退到保守模板。
- 验证测试：
  - 构造有 deadline 与无 deadline 两类输入，验证计划周数和里程碑相对顺序。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_dta_deadline_planning.py -q
```

- 通过标准：
  - 同一申请季不同学校可以生成不同节奏。
  - 有 deadline 时不再使用固定 due_week。

### Step 17. 实现延误重排与冲突检测

- 目标：当用户晚启动或任务延期时，DTA 能自动重排并暴露风险。
- 主要文件：
  - `src/admitpilot/agents/dta/replan.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_replan.py`
- 给 AI 开发者的指令：
  - 支持基于 `has_delay`, `start_week`, `blocked_tasks` 做重排。
  - 对不可满足的计划输出 `red` 风险，而不是继续给出虚假可行计划。
  - 冲突检测至少覆盖：任务挤压、deadline 已过、缓冲不足。
- 验证测试：
  - 覆盖“可重排”“不可重排”“高风险但可继续”三类情况。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_dta_replan.py tests/test_orchestrator.py -q
```

- 通过标准：
  - 延迟输入会改变输出计划。
  - 无法按时完成时，系统会明确暴露不可行性。

---

## Phase 5. CDS 从模板生成到可审计文书支持

### Step 18. 建立申请者证据模型

- 目标：让 CDS 的事实槽位真正来自用户证据，而不是写死文本。
- 主要文件：
  - `src/admitpilot/core/user_artifacts.py`
  - `src/admitpilot/agents/cds/facts.py`
  - `tests/test_user_artifacts.py`
- 给 AI 开发者的指令：
  - 定义用户证据实体：课程、项目、实习、科研、获奖、语言成绩、推荐人信息。
  - 允许每条证据记录 `source_ref`, `verified`, `date_range`, `evidence_type`。
  - 暂不做 OCR/文档解析，先做结构化输入模型。
- 验证测试：
  - 测试证据实体校验、缺字段报错、verified 状态流转。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_user_artifacts.py -q
```

- 通过标准：
  - CDS 可接收明确的用户证据输入。
  - “事实”与“推断”开始分离。

### Step 19. 实现事实槽位提取与缺证据 abstain

- 目标：把 CDS 的事实槽位与缺证据行为标准化。
- 主要文件：
  - `src/admitpilot/agents/cds/facts.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_fact_slots.py`
  - `tests/test_cds_service.py`
- 给 AI 开发者的指令：
  - 从用户证据 + SAE + DTA 中提取 `motivation`, `program_fit`, `execution_proof` 等槽位。
  - 每个槽位必须标注 `verified / inferred / missing`。
  - 如果核心证据缺失，CDS 必须 abstain，而不是造句补齐。
- 验证测试：
  - 断言缺少核心证据时不生成正式草稿。
  - 断言有证据时 fact slot 的 `source_ref` 能回溯。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_cds_fact_slots.py tests/test_cds_service.py -q
```

- 通过标准：
  - CDS 不再生成无来源事实。
  - 每个槽位可追溯到输入证据。

### Step 20. 设计可差异化的文书模板层

- 目标：让 SoP/CV/Interview 输出能按学校策略差异化，而不是通用模板复制。
- 主要文件：
  - `src/admitpilot/agents/cds/templates.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_templates.py`
- 给 AI 开发者的指令：
  - 把文书输出拆成模板层和事实填充层。
  - 模板要能读取学校项目特征、SAE gaps、DTA 执行计划。
  - 不要直接生成大段自然语言终稿，先输出结构化提纲和段落意图。
- 验证测试：
  - 构造两所学校输入，断言生成的 outline 不完全相同。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_cds_templates.py -q
```

- 通过标准：
  - 学校差异能在输出结构里体现。
  - 输出仍保持结构化、可审阅。

### Step 21. 实现跨文档一致性检查器

- 目标：让 SoP/CV/Interview 的事实一致性不再只是占位规则。
- 主要文件：
  - `src/admitpilot/agents/cds/consistency.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_consistency.py`
- 给 AI 开发者的指令：
  - 实现基于 fact slots 的一致性校验。
  - 至少检查：时间线冲突、同一经历表述冲突、学校项目名称不一致、未验证事实混入终稿。
  - 输出结构化 issue 列表，附 impacted documents。
- 验证测试：
  - 构造至少三类冲突场景并断言能被检出。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_cds_consistency.py tests/test_cds_service.py -q
```

- 通过标准：
  - 一致性问题可重复触发、可解释。
  - review checklist 能引用具体 issue。

---

## Phase 6. 平台层生产化（课堂演示阶段暂缓）

### Step 22. 引入 Postgres 版版本化存储

- 目标：把 `VersionedMemoryStore` 从内存实现替换成真实数据库适配器。
- 主要文件：
  - `src/admitpilot/platform/memory/postgres_store.py`
  - `src/admitpilot/platform/memory/contracts.py`
  - `src/admitpilot/platform/bootstrap.py`
  - `tests/test_postgres_versioned_store.py`
- 给 AI 开发者的指令：
  - 定义 repository 接口和 Postgres 实现。
  - 保留当前 in-memory store 作为 test fallback。
  - 这一步只做 versioned store，不同时改 session/object store。
- 验证测试：
  - 写 repository contract tests，至少覆盖 append/get_latest/get_by_version。
  - 若本地没有 Postgres，用 fake adapter 先跑 contract tests；真实集成测试留到 Step 27。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_postgres_versioned_store.py tests/test_platform_common_bootstrap.py -q
```

- 通过标准：
  - orchestrator 可通过配置切换 in-memory / postgres 实现。
  - 版本记录字段完整保留。

### Step 23. 引入 Redis 版会话缓存

- 目标：把 session memory 从进程内缓存升级为可复用的外部缓存。
- 主要文件：
  - `src/admitpilot/platform/memory/redis_session_store.py`
  - `src/admitpilot/platform/bootstrap.py`
  - `tests/test_redis_session_store.py`
- 给 AI 开发者的指令：
  - 实现与现有 session store 等价的 Redis adapter。
  - 支持 TTL、namespace、JSON 序列化。
  - 不在本步修改 versioned store 逻辑。
- 验证测试：
  - 用 fake redis client 或内存替身写 adapter contract test。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_redis_session_store.py -q
```

- 通过标准：
  - session 行为与现有契约兼容。
  - adapter 层可单测，不依赖全局连接。

### Step 24. 引入对象存储适配器

- 目标：让文书草稿和大对象产物可持久化到对象存储。
- 主要文件：
  - `src/admitpilot/platform/memory/object_store.py`
  - `src/admitpilot/platform/bootstrap.py`
  - `tests/test_object_store.py`
- 给 AI 开发者的指令：
  - 实现 `ArtifactObjectStore` 的本地文件版和 S3/MinIO 版适配器。
  - 统一 object id、content type、metadata 处理。
  - CDS 的产出写入 object store 时要带 trace_id 和 version 信息。
- 验证测试：
  - 先用本地文件版写 contract tests，验证 put/get/overwrite/metadata。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_object_store.py -q
```

- 通过标准：
  - artifact 不再只存在内存中。
  - metadata 可用于审计追踪。

### Step 25. 把治理与能力控制真正串入执行链路

- 目标：让 ACL、PII redaction、capability token 不再只是定义，而是运行时强约束。
- 主要文件：
  - `src/admitpilot/pao/orchestrator.py`
  - `src/admitpilot/platform/governance/contracts.py`
  - `src/admitpilot/platform/security/capability.py`
  - `tests/test_governance_runtime.py`
- 给 AI 开发者的指令：
  - 在任务执行前校验 agent 对所需 namespace 的读写权限。
  - 在写入 memory / artifact 前执行 PII redaction 或白名单校验。
  - capability token 要与具体 method/scope 绑定，而不只是 agent 名称。
- 验证测试：
  - 覆盖：有权限、无权限、PII 命中、token scope 不匹配。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_governance_runtime.py tests/test_orchestrator.py -q
```

- 通过标准：
  - 无权限任务不能进入执行。
  - 敏感信息写入前可被拦截或脱敏。

### Step 26. 建立结构化日志、trace 与指标

- 目标：让真实应用具备调试、审计和运行监控基础。
- 主要文件：
  - `src/admitpilot/platform/observability/logger.py`
  - `src/admitpilot/platform/observability/contracts.py`
  - `src/admitpilot/api/main.py`
  - `tests/test_observability.py`
- 给 AI 开发者的指令：
  - 所有 API 请求与 orchestrator run 都要带 trace_id。
  - 记录结构化日志，至少包含：trace_id, user_id/application_id, agent, task, status, latency_ms。
  - 指标至少覆盖：请求量、任务成功率、任务耗时、AIE cache hit。
- 验证测试：
  - 用测试 logger/sink 验证 trace_id 贯穿 API 到 agent 执行。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_observability.py -q
```

- 通过标准：
  - 一次请求的日志链路可串起来。
  - 关键指标可被单测检查。

---

## Phase 7. 产品接口、异步执行与上线准备（课堂演示阶段暂缓）

### Step 27. 建立应用级持久化模型与业务 API

- 目标：把“单次 demo 请求”升级为“用户-申请-运行”的真实业务模型。
- 主要文件：
  - `src/admitpilot/repositories/applications.py`
  - `src/admitpilot/api/routes/applications.py`
  - `src/admitpilot/api/routes/orchestration.py`
  - `tests/test_application_api.py`
- 给 AI 开发者的指令：
  - 定义 `User`, `Application`, `OrchestrationRun` 的基础模型。
  - 提供创建申请、查询申请、触发编排、查询编排结果的 API。
  - 先不做复杂鉴权，但接口 schema 要为后续 auth 预留字段。
- 验证测试：
  - API 测试覆盖创建申请、触发 run、轮询结果。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_application_api.py -q
```

- 通过标准：
  - 用户可以围绕同一个 application 多次运行 orchestrator。
  - 结果有持久化 run 记录。

### Step 28. 把编排执行改成异步任务

- 目标：避免 API 调用阻塞，把 PAO 执行迁移到 worker 模式。
- 主要文件：
  - `src/admitpilot/workers/orchestration_worker.py`
  - `src/admitpilot/api/routes/orchestration.py`
  - `tests/test_orchestration_worker.py`
- 给 AI 开发者的指令：
  - 定义最小异步执行接口：提交任务、更新状态、读取结果。
  - 先用进程内队列或 fake queue 完成测试，不立即接 Celery。
  - API 返回 `run_id`，由 worker 更新状态。
- 验证测试：
  - 覆盖任务提交、成功完成、失败回写三类场景。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/test_orchestration_worker.py tests/test_application_api.py -q
```

- 通过标准：
  - API 层不再直接同步跑完整链路。
  - run 状态流转清晰可查询。

### Step 29. 准备真实依赖的本地集成环境

- 目标：为上线前联调准备一套本地或 CI 可跑的真实依赖环境。
- 主要文件：
  - `docker-compose.yml`
  - `.env.example`
  - `tests/integration/test_full_stack.py`
- 给 AI 开发者的指令：
  - 提供最小本地依赖：Postgres, Redis, MinIO。
  - 写一条端到端集成测试：创建 application -> 触发 run -> 写入 memory/artifact -> 查询结果。
  - 这一步只做集成环境，不做部署脚本。
- 验证测试：
  - 启动依赖后运行 integration test。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/integration/test_full_stack.py -q
```

- 通过标准：
  - 真实依赖环境下链路能跑通。
  - 可验证 artifact 和版本记录确实写入外部存储。

### Step 30. 上线前验收、回归与发布清单

- 目标：在进入 staging/prod 前形成稳定的发布标准。
- 主要文件：
  - `docs/release_checklist.md`
  - `tests/integration/test_e2e_user_flow.py`
  - `README.md`
- 给 AI 开发者的指令：
  - 编写 release checklist，覆盖配置、迁移、依赖健康、回滚策略、数据备份、观察指标。
  - 增加一条 e2e 用户流测试：
    - 创建申请
    - 拉取真实或 fixture 官方数据
    - 生成策略
    - 生成时间线
    - 生成文书支持
    - 查询 artifacts
  - 更新 README 的运行方式，区分 demo 模式和服务模式。
- 验证测试：
  - 运行 e2e 测试与全量回归。
  - 运行：

```powershell
conda activate admitpilot
$env:PYTHONPATH='src'
python -m pytest tests/integration/test_e2e_user_flow.py -q
python -m pytest -q
```

- 通过标准：
  - 有明确发布前检查单。
  - 一条真实用户链路可自动化回归。

---

## 2. 阶段性里程碑

### Milestone A. 可用原型后端

- 完成 Step 01-10
- 标志：
  - 配置、API 骨架、AIE 真实数据链路打通
  - demo 不再依赖固定 stub 输出

### Milestone B. 可答辩演示系统

- 完成 Step 11-21
- 标志：
  - SAE、DTA、CDS 的核心业务逻辑具备真实输入约束
  - 输出有结构化证据、风险解释和可展示的稳定结构
  - 可以围绕固定 demo 画像完成端到端演示

### Milestone C. 真实应用扩展准备

- 完成 Step 22-26
- 标志：
  - 平台层完成持久化、治理、观测
  - 运行时从“演示可用”扩展到“可长期运行”

### Milestone D. 可上线应用

- 完成 Step 27-30
- 标志：
  - API、异步 worker、真实依赖、e2e 回归、release checklist 全部就绪

---

## 3. 推荐执行顺序

1. 课堂演示阶段按 `Phase 3 -> Phase 4 -> Phase 5` 顺序执行，不进入 `Phase 6-7`。
2. 每一步单独开分支、单独跑定向测试。
3. 每完成一个 phase，再跑一次 `python -m pytest -q`。
4. 若某一步需要新增依赖，先更新 `requirements.txt`，再补测试，最后改业务代码。
5. 若某一步无法在离线测试中稳定验证，就先不要接真实外部服务。

## 4. 当前最先开始的三步

如果现在立刻开工，推荐按这个顺序：

1. Step 22：引入 Postgres 版版本化存储
2. Step 23：引入 Redis 版会话缓存
3. Step 24：引入对象存储适配器

原因：

- 当前 `Phase 1-5` 已完成课堂/答辩演示范围，继续推进时主要风险转向持久化、外部缓存、artifact 存储和运行时治理。
- 若仍只准备课堂演示，优先保持官方库、案例库和固定 demo 输入稳定，不进入生产化依赖接入。
