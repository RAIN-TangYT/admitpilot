# AdmitPilot 实施进度记录

- 文档日期：`2026-04-19`
- 对应计划：`docs/implementation_plan.md`
- 用途：记录每一步的实际修复动作、测试结果、阻塞项与下一步安排

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
| Phase 2 | Step 05-10 | `pending` | AIE 从 stub 到真实招生情报服务 |
| Phase 3 | Step 11-14 | `pending` | SAE 从示意打分到可解释策略引擎 |
| Phase 4 | Step 15-17 | `pending` | DTA 从静态周计划到真实逆排调度器 |
| Phase 5 | Step 18-21 | `pending` | CDS 从模板生成到可审计文书支持 |
| Phase 6 | Step 22-26 | `pending` | 平台层生产化 |
| Phase 7 | Step 27-30 | `pending` | 产品接口、异步执行与上线准备 |

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

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 06. 实现官网抓取客户端

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 07. 实现官网页面解析器

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 08. 增加快照版本与 diff 机制

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 09. 接入案例数据归一化流程

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 10. 完成 AIE 真实集成

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

---

## Phase 3. SAE 从示意打分到可解释策略引擎

### Step 11. 设计学校项目规则文件

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 12. 实现规则打分引擎

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 13. 引入可替换的语义匹配适配器

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 14. 输出证据化推荐解释

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

---

## Phase 4. DTA 从静态周计划到真实逆排调度器

### Step 15. 实现拓扑排序与里程碑调度器

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 16. 加入真实 deadline 逆排

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 17. 实现延误重排与冲突检测

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

---

## Phase 5. CDS 从模板生成到可审计文书支持

### Step 18. 建立申请者证据模型

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 19. 实现事实槽位提取与缺证据 abstain

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 20. 设计可差异化的文书模板层

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 21. 实现跨文档一致性检查器

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

---

## Phase 6. 平台层生产化

### Step 22. 引入 Postgres 版版本化存储

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 23. 引入 Redis 版会话缓存

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 24. 引入对象存储适配器

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 25. 把治理与能力控制真正串入执行链路

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 26. 建立结构化日志、trace 与指标

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

---

## Phase 7. 产品接口、异步执行与上线准备

### Step 27. 建立应用级持久化模型与业务 API

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 28. 把编排执行改成异步任务

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 29. 准备真实依赖的本地集成环境

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：

### Step 30. 上线前验收、回归与发布清单

- 状态：`pending`
- 开始时间：
- 完成时间：
- 负责人：
- 改动文件：
- 实际修复动作：
- 测试：
- 偏差说明：
- 阻塞项：
- 下一步：
