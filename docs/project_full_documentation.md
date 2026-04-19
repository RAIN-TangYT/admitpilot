# AdmitPilot Current Implementation Snapshot

- 文档日期：`2026-04-19`
- 适用范围：当前仓库代码基线
- 文档目的：给 GitHub 读者一个与代码一致的实现快照

## 1. 文档优先级

为了避免歧义，当前仓库文档按以下优先级理解：

1. `docs/Project_Proposal_Group 26 (TANG Yutong, CHEN Jinghao, ZHANG Yufei, SHI Junren).docx`
2. `docs/implementation_plan.md`
3. `docs/progress.md`
4. `README.md`
5. 本文件

如果本文件与前四者冲突，以上述前四者为准。

## 2. 当前实现到了哪里

当前项目已经完成：
- 多代理主流程可运行
- `AIE -> SAE -> DTA -> CDS` 默认链路可用
- OpenAI 默认模型接入完成，默认模型是 `gpt-5.4-nano`
- 配置层、应用工厂、API 健康检查骨架已接入
- 基础测试已覆盖 orchestrator、AIE、SAE、CDS、settings、app factory、API health

当前项目尚未完成：
- AIE 真实官网抓取与解析
- SAE 规则文件与语义检索
- DTA 拓扑排序、逆排与自动重排
- CDS 真实证据抽取与跨文档一致性引擎
- Postgres / Redis / 对象存储等生产依赖

## 3. 当前目录说明

- `src/admitpilot/main.py`
  - CLI demo 入口

- `src/admitpilot/app.py`
  - 应用工厂，负责装配 settings、platform bundle、agents、orchestrator

- `src/admitpilot/config`
  - 统一配置加载

- `src/admitpilot/api`
  - FastAPI 入口与 `/health`、`/ready` 路由

- `src/admitpilot/pao`
  - PAO 路由、编排、结果聚合

- `src/admitpilot/agents`
  - AIE、SAE、DTA、CDS 四代理

- `src/admitpilot/platform`
  - runtime / memory / governance / security / observability / mcp / tools

- `tests`
  - 当前回归测试

## 4. 当前运行方式

推荐使用 `admitpilot` conda 环境。

安装：

```bash
python -m pip install -r requirements.txt
```

CLI：

```bash
$env:PYTHONPATH='src'
python -m admitpilot.main
```

API：

```bash
$env:PYTHONPATH='src'
python -m uvicorn admitpilot.api.main:app --reload
```

## 5. 当前默认配置

参考 `.env.example`：

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4-nano
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=30
```

说明：
- 当前仓库已不再使用 `Qwen / DashScope`
- 若后续更换模型，应统一修改 settings、LLM client、README 与测试

## 6. 当前质量状态

当前已验证通过：

```bash
$env:PYTHONPATH='src'
python -m ruff check src/admitpilot tests
python -m mypy
python -m pytest -q
python -m admitpilot.main
```

说明：
- 仍可能出现 `.pytest_cache` 权限 warning，这属于本地目录权限问题，不影响当前代码正确性

## 7. 当前已知限制

- AIE 仍主要依赖 stub gateway
- SAE 仍是示意性评分框架
- DTA 仍是规则化排期，不是完整调度器
- CDS 仍是支持包生成器，不是最终文书定稿器
- 平台层目前是“可插拔接口 + 内存实现”，不是生产基础设施

## 8. 当前提交到 GitHub 的解释口径

如果现在提交到 GitHub，推荐描述为：

> 一个面向留学申请场景的多代理原型系统，已完成核心编排链路、统一配置、基础 API 骨架与回归测试；真实数据源、生产化存储与高级决策模块仍在实施中。

不建议描述为：
- “已完成真实产品”
- “已接入真实招生官网抓取”
- “已具备生产级文书能力”
- “已完成全部 Phase”
