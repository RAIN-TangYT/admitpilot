# AdmitPilot Current Implementation Snapshot

- 文档日期：`2026-04-20`
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
- AIE 运行时默认读取 `data/official_library/official_library.json`
- AIE 已完成学校/项目目录、官网抓取、页面解析、快照 diff 主链路
- `refresh_official_library.py` 已可真实执行 live 官方页刷新，且只更新官方库，不更新案例库
- 基础测试已覆盖 orchestrator、AIE、SAE、CDS、settings、app factory、API health

当前项目尚未完成：
- AIE 更复杂官网结构、反爬页面与边界规则适配
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

- `src/admitpilot/domain/catalog.py`
  - 当前学校、项目、官网域名白名单、默认页面类型的单一真源

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

## 6. 当前 AIE 学校与项目目录

当前 AIE 学校和项目范围以 `src/admitpilot/domain/catalog.py` 为准。

### 6.1 HKU

- `MSCS` -> `Master of Science in Computer Science`
- `MDS` -> `Master of Data Science`
- `MECIC` -> `Master of Science in Electronic Commerce and Internet Computing`
- `MSFTDA` -> `Master of Science in Financial Technology and Data Analytics`
- `MSAI` -> `Master of Science in Artificial Intelligence`

### 6.2 CUHK

- `MSCS` -> `MSc in Computer Science`
- `MSAI` -> `MSc in Artificial Intelligence`
- `MSIE` -> `MSc in Information Engineering`
- `MSISTM` -> `MSc in Information Science and Technology Management`
- `MSELT` -> `MSc in E-Commerce and Logistics Technologies`
- `MSFT` -> `MSc in Financial Technology`

### 6.3 HKUST

- `MSCS` -> `Master of Science in Computer Science`
- `MSAI` -> `MSc in Artificial Intelligence`
- `MSBDT` -> `MSc in Big Data Technology`
- `MSIT` -> `MSc in Information Technology`
- `MSDDM` -> `MSc in Data-Driven Modeling`

### 6.4 NUS

- `MSCS` -> `Master of Science in Computer Science`
- `MSAI` -> `Master of Science in Artificial Intelligence`
- `MCOMP_CS` -> `Master of Computing (Computer Science Specialisation)`
- `MCOMP_IS` -> `Master of Computing (Information Systems Specialisation)`
- `MCOMP_ISEC` -> `Master of Computing (Infocomm Security Specialisation)`
- `MCOMP_GENERAL` -> `Master of Computing (General Track)`
- `MCOMP_AI` -> `Master of Computing in Artificial Intelligence`
- `MSDFT` -> `Master of Science in Digital FinTech`
- `MSBA` -> `Master of Science in Business Analytics`
- `MTECH_AIS` -> `Master of Technology in Artificial Intelligence Systems`
- `MTECH_SE` -> `Master of Technology in Software Engineering`
- `MTECH_EBA` -> `Master of Technology in Enterprise Business Analytics`
- `MTECH_DL` -> `Master of Technology in Digital Leadership`
- `MS_AIFS` -> `Master of Science (AI for Science)`
- `MS_AII` -> `Master of Science (Artificial Intelligence & Innovation)`
- `EM_AIDT` -> `Executive Master in AI & Digital Transformation`

### 6.5 NTU

- `MSCS` -> `Master of Science in Computer Science`
- `MCAAI` -> `Master of Computing in Applied AI`
- `MSAI` -> `Master of Science in Artificial Intelligence`
- `MSDS` -> `Master of Science in Data Science`
- `MSCYBER` -> `Master of Science in Cyber Security (MSCS)`
- `MSBT` -> `Master of Science in Blockchain Technology`

说明：
- 为兼容当前 demo 与历史 fixture，`NUS / NTU / HKUST` 仍保留 `MSCS` 等旧代码项。
- `NTU` 的 `Master of Science in Cyber Security (MSCS)` 在内部使用 `MSCYBER`，避免与 `MSCS=Computer Science` 冲突。
- 当前所有学校默认页面类型仍为 `requirements` 与 `deadline`。

## 7. 当前 AIE live 官方支持矩阵

以下状态基于 `2026-04-20` 的真实执行结果，判定标准如下：

- `支持`
  - AIE live 能稳定抓到 `requirements + deadline` 两类官方页，并写入官方库
- `部分支持`
  - AIE live 只能稳定抓到其中一类官方页，当前结果通常是 `mixed`
- `不支持`
  - 当前没有 live 官方源配置，或现有抓取器无法稳定拿到可解析官方页

本轮实际执行命令：

```bash
$env:PYTHONPATH='src'
python -m admitpilot.debug.refresh_official_library --cycle 2026
```

该命令只会更新：

- `data/official_library/official_library.json`

不会更新：

- 案例库
- `tests/fixtures`

### 7.1 支持

- `HKU`
  - `MSCS`
  - `MDS`
  - `MECIC`
  - `MSFTDA`
  - `MSAI`
- `CUHK`
  - `MSCS`
  - `MSAI`
  - `MSIE`
  - `MSISTM`
  - `MSELT`
  - `MSFT`
- `HKUST`
  - `MSAI`
  - `MSBDT`
  - `MSIT`
- `NUS`
  - `MCOMP_CS`
  - `MCOMP_IS`
  - `MCOMP_ISEC`
  - `MCOMP_GENERAL`
  - `MCOMP_AI`
  - `MSDFT`
- `NTU`
  - `MSBT`

### 7.2 部分支持

- `HKUST`
  - `MSDDM`
- `NTU`
  - `MSAI`
  - `MCAAI`
  - `MSDS`
  - `MSCYBER`

说明：

- `部分支持` 代表当前 live 执行能抓到部分官方页，但还不能稳定形成完整的 `requirements + deadline` 双页快照。

### 7.3 不支持

- `NUS`
  - `MSCS`
  - `MSAI`
  - `MSBA`
  - `MTECH_AIS`
  - `MTECH_SE`
  - `MTECH_EBA`
  - `MTECH_DL`
  - `MS_AIFS`
  - `MS_AII`
  - `EM_AIDT`
- `NTU`
  - `MSCS`
- `HKUST`
  - `MSCS`

说明：

- `NUS/NTU/HKUST` 下的 `MSCS` 属于历史兼容代码，当前 live 运行不再把它们作为默认真实项目入口。
- 部分 `NUS` 项目官网页面虽然存在，但当前 `httpx` 抓取路径会被站点反爬或挑战页拦截，因此暂未纳入 live 官方源。

## 8. 当前质量状态

当前已验证通过：

```bash
$env:PYTHONPATH='src'
python -m admitpilot.debug.refresh_official_library --cycle 2026
python -m ruff check src/admitpilot tests
python -m mypy
python -m pytest -q
python -m admitpilot.main
```

说明：
- 仍可能出现 `.pytest_cache` 权限 warning，这属于本地目录权限问题，不影响当前代码正确性

## 9. 当前已知限制

- AIE 运行时默认读取官方库；`fixture` 仅保留给测试使用
- AIE live 还不能覆盖全部目录项目，尤其是部分 `NUS` 项目仍受官网反爬影响
- SAE 仍是示意性评分框架
- DTA 仍是规则化排期，不是完整调度器
- CDS 仍是支持包生成器，不是最终文书定稿器
- 平台层目前是“可插拔接口 + 内存实现”，不是生产基础设施

## 10. 当前提交到 GitHub 的解释口径

如果现在提交到 GitHub，推荐描述为：

> 一个面向留学申请场景的多代理原型系统，已完成核心编排链路、统一配置、基础 API 骨架，以及基于官方库的 AIE 情报链路；live 官方页刷新已接入，但真实外部数据源覆盖、生产化存储与高级决策模块仍在实施中。

不建议描述为：
- “已完成真实产品”
- “已覆盖全部院校项目的真实招生官网抓取”
- “已具备生产级文书能力”
- “已完成全部 Phase”
