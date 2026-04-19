# admitpilot

AdmitPilot 是一个面向留学申请场景的多代理编排原型。系统由 `PAO` 统一调度
`AIE / SAE / DTA / CDS` 四类代理，当前聚焦 `NUS / NTU / HKU / CUHK / HKUST`
五校泛计算机项目的情报、策略、时间线与文书支持。

当前仓库状态是“可演示原型”，不是生产应用。核心 CLI 流程与测试可运行，但
真实官网抓取、持久化后端、规则引擎、排期器与文书证据系统仍在实施中。

## 当前基线

- 默认 LLM 提供方：OpenAI
- 默认模型：`gpt-5.4-nano`
- 已验证命令：
  - `python -m pytest -q`
  - `python -m admitpilot.main`
- 推荐运行环境：`admitpilot` conda 环境

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

当前以以下三份文档作为主要事实来源：

- `docs/Project_Proposal_Group 26 (TANG Yutong, CHEN Jinghao, ZHANG Yufei, SHI Junren).docx`
- `docs/implementation_plan.md`
- `docs/progress.md`

其余 `docs/*.md` 若与代码不一致，应视为待清理或待重写的辅助文档，不应作为当前实现真相来源。

## 环境准备

```bash
conda activate admitpilot
python -m pip install -r requirements.txt
```

可选地在项目根目录创建 `.env`，参考 `.env.example`：

```env
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.4-nano
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=30
```

## 运行方式

CLI demo：

```bash
$env:PYTHONPATH='src'
python -m admitpilot.main
```

API：

```bash
$env:PYTHONPATH='src'
python -m uvicorn admitpilot.api.main:app --reload
```

## 质量检查

当前已验证通过：

```bash
$env:PYTHONPATH='src'
python -m pytest -q
```

以下检查建议在提交前继续收敛，但当前基线尚未完全清零：

```bash
$env:PYTHONPATH='src'
python -m ruff check .
python -m mypy
```

## 当前限制

- `AIE` 仍以 stub gateway 为主，尚未完成真实官网抓取与解析。
- `SAE` 仍包含规则与语义匹配占位逻辑。
- `DTA` 尚未完成拓扑排序、deadline 逆排与自动重排。
- `CDS` 尚未接入真实经历证据抽取与一致性图谱。
- 平台层默认仍是内存适配器，未落地 PostgreSQL / Redis / Object Storage。

## PyCharm 说明

- Working Directory 指向项目根目录
- 将 `src` 标记为 Sources Root，或设置 `PYTHONPATH=src`
- 可直接运行模块 `admitpilot.main` 或 `admitpilot.api.main`
