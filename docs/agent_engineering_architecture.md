# AdmitPilot Agent Engineering Architecture

- 文档日期：`2026-04-19`
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

尚未具备：
- 真实官网抓取与解析
- 生产级数据库、缓存、对象存储
- 规则 DSL、排期器、证据抽取器
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
- `AIE`：招生情报与快照
- `SAE`：选校评估与风险排序
- `DTA`：时间线与里程碑计划
- `CDS`：文书支持与一致性检查

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

当前默认入口：
- CLI：`python -m admitpilot.main`
- API：`python -m uvicorn admitpilot.api.main:app --reload`

## 4. 模块边界

建议后续继续按以下边界推进，避免多人改同一层：

- AIE 边界：
  - `src/admitpilot/agents/aie/*`
  - 负责学校/项目目录、抓取、解析、快照、diff

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
