# admitpilot

admitpilot 是一个面向留学申请场景的多代理编排项目，核心由 PAO 统一调度 AIE、SAE、DTA、CDS 四类代理完成情报、策略、时间线与文书支持。
当前系统重点覆盖 NUS、NTU、HKU、CUHK、HKUST 五校泛计算机项目。

## 目录结构

- `src/admitpilot/core`：跨模块共享契约与上下文
- `src/admitpilot/pao`：编排层，请求/响应契约、路由与执行图
- `src/admitpilot/agents`：各业务代理实现
- `src/admitpilot/platform`：公共区协议与初始化骨架（MCP/tool/memory/runtime/security/governance/observability）
- `docs`：技术架构文档
- `tests`：测试用例

## 架构文档

- `docs/agent_engineering_architecture.md`：Agent Engineering 技术架构设计与分工 TODO

## 环境要求

- Python 3.11+

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行方式

```bash
$env:PYTHONPATH='src'; python -m admitpilot.main
```

## 公共区初始化（骨架）

```python
from admitpilot.platform import build_default_platform_common_bundle

bundle = build_default_platform_common_bundle()
print(bundle.tool_registry.validate_access("official_fetch", "aie"))
```

说明：
- 当前是初始化定义设计，主要用于分工开发与联调，不是生产实现。
- 后续将逐步替换内存适配器为 Redis/PostgreSQL/S3 等后端。

## 质量检查

建议默认使用 `admitpilot` conda 环境：

```bash
conda activate admitpilot
```

```bash
$env:PYTHONPATH='src'; python -m ruff check .
$env:PYTHONPATH='src'; python -m mypy
$env:PYTHONPATH='src'; python -m pytest
```

## PyCharm 运行说明

- 在 PyCharm 中将项目根目录设置为 Working Directory
- 在 Run/Debug Configuration 中将 `src` 标记为 Sources Root，或在环境变量中添加 `PYTHONPATH=src`
- 入口可直接使用模块方式运行 `admitpilot.main`
