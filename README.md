# admitpilot

AdmitPilot 是一个面向留学申请场景的多代理编排原型。系统由 `PAO` 统一调度
`AIE / SAE / DTA / CDS` 四类代理，当前聚焦 `NUS / NTU / HKU / CUHK / HKUST`
五校泛计算机项目的情报、策略、时间线与文书支持。

当前仓库状态是“可演示原型”，不是生产应用。核心 CLI 流程与测试可运行，
`Phase 1-5` 的答辩演示链路已收口；Web MVP 已加入 demo 登录与 SQLite
运行历史持久化。全量 live 官方页覆盖、异步任务与上线准备仍未进入当前范围。

## 当前基线

- 默认 LLM 提供方：OpenAI
- 默认模型：`gpt-5.4-nano`
- AIE 运行时默认读取：`data/official_library/official_library.json`
- AIE 案例库默认读取：`data/case_library/case_library.json`
- AIE 测试模式官方库写入隔离到：`.pytest-local/runtime_official_library.test.json`
- SAE 非 test 模式默认语义匹配：`embedding`；test 模式默认：`fake`
- 官方库刷新入口：`python -m admitpilot.debug.refresh_official_library --cycle 2026`
- 默认 demo 项目组合（CLI `python -m admitpilot.main`）：
  - `NUS -> MCOMP_CS`
  - `NTU -> MSAI`
  - `HKU -> MSCS`
  - `CUHK -> MSCS`
  - `HKUST -> MSIT`
- 默认 demo 项目组合（Web `/api/v1/demo-profile`）：
  - `NUS -> MTECH_AIS`
  - `NTU -> MSAI`
  - `HKU -> MSCS`
  - `CUHK -> MSCS`
  - `HKUST -> MSAI`
- 最近验证命令（`2026-04-25`）：
  - `python -m pytest -q`：通过
  - `python -m ruff check src tests`：通过
  - `python -m mypy src tests`：通过
- 推荐运行环境：`admitpilot` conda 环境
- Demo 登录账号：`demo@admitpilot.local`
- Demo 登录密码：`admitpilot-demo`
- Demo SQLite 数据库默认路径：`.admitpilot/admitpilot.sqlite3`

## 代码结构

- `src/admitpilot/core`：跨模块共享契约、上下文与 TypedDict 输出模型
- `src/admitpilot/pao`：编排层，请求契约、路由、执行图与结果聚合
- `src/admitpilot/agents`：AIE / SAE / DTA / CDS 业务代理
- `src/admitpilot/platform`：公共平台层，包括 memory、runtime、security、governance、observability
- `src/admitpilot/api`：FastAPI 入口与健康检查路由
- `src/admitpilot/config`：统一配置加载
- `tests`：回归测试
- `docs`：方案、实施计划与进度记录

## 文档约定

当前 `docs` 目录中的文档都应与代码基线保持一致。建议按以下角色理解：

- `docs/Project_Proposal_Group 26 (TANG Yutong, CHEN Jinghao, ZHANG Yufei, SHI Junren).docx`
  - 课程 proposal 与项目起点
- `docs/implementation_plan.md`
  - 从 demo 到真实应用的分步实施路线
- `docs/progress.md`
  - 实际落地进度与验证记录
- `docs/agent_engineering_architecture.md`
  - 当前代码基线的高层架构说明
- `docs/project_full_documentation.md`
  - 当前支持范围、live 支持矩阵与仓库状态快照

## 环境准备

```bash
conda activate admitpilot
python -m pip install -r requirements.txt
```

可选地在项目根目录创建 `.env`，参考 `.env.example`：

```env
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.4-nano
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=30
ADMITPILOT_SEMANTIC_MATCHER_KIND=
ADMITPILOT_CASE_LIBRARY_PATH=data/case_library/case_library.json
```

## 运行方式

CLI demo：

```bash
$env:PYTHONPATH='src'
python -m admitpilot.main
```

API：

```bash
python run_backend.py
```

前端工作台：

```bash
cd frontend
npm run dev
```

Web 演示流程：

1. 打开 `http://localhost:3000`。
2. 使用 `demo@admitpilot.local` / `admitpilot-demo` 登录。
3. 点击 `Load Demo Profile`。
4. 点击 `Run AdmitPilot`。
5. 前端通过 WebSocket `/api/v1/orchestrations/ws` 接收后端真实阶段事件；等待 AIE / SAE / DTA / CDS 依次进入 running / completed。
6. 在左侧 `Run History` 中点击任意历史记录，恢复该次 request 与 response。
7. 点击历史记录右侧删除按钮，可删除单条运行历史。

## 质量检查

当前已验证通过：

```bash
$env:PYTHONPATH='src'
python -m pytest -q
```

说明：
- `2026-04-25` 已验证 `pytest` / `ruff` / `mypy` 全量通过。

## 当前限制

- `AIE` 运行时默认读取官方库，`fixture` 仅保留给测试使用。
- `AIE` 运行时默认读取 JSON 案例库，不再使用空 case gateway。
- `AIE` 已支持 live 官方页刷新，但还没有覆盖全部目录项目；当前支持矩阵见 `docs/project_full_documentation.md`。
- `SAE` 已完成规则打分与可替换语义匹配；无 API key 时 embedding matcher 会使用本地 fallback。
- `DTA` 已完成拓扑排序、deadline 逆排与自动重排的演示范围实现。
- `CDS` 已完成结构化证据、fact slots、模板层与一致性检查的演示范围实现。
- Web MVP 已落地 demo 登录、Bearer session 与 SQLite 运行历史。
- Web 工作台运行链路已改为 WebSocket 阶段事件，最终完成后仍持久化完整 run response。
- 平台层默认仍是内存适配器，未落地 PostgreSQL / Redis / Object Storage。

## PyCharm 说明

- Working Directory 指向项目根目录
- 将 `src` 标记为 Sources Root，或设置 `PYTHONPATH=src`
- 可直接运行模块 `admitpilot.main` 或 `admitpilot.api.main`
