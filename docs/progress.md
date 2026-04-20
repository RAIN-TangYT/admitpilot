# AdmitPilot 实施进度记录

- 文档日期：`2026-04-20`
- 对应计划：`docs/implementation_plan.md`

## 总览

| Phase | Step 范围 | 状态 | 备注 |
| --- | --- | --- | --- |
| Phase 1 | Step 01-04 | `done` | 基础配置、时间工具、应用工厂、API 骨架已完成（历史记录） |
| Phase 2 | Step 05-10 | `done` | AIE 数据链路与官方/案例库基线已完成（历史记录） |
| Phase 3 | Step 11-14 | `done` | Step 11-14 已完成并通过 pytest；下一步进入 Phase 4 |
| Phase 4 | Step 15-17 | `done` | Step 15-17 已完成并通过 pytest；下一步进入 Phase 5 |
| Phase 5 | Step 18-21 | `done` | Step 18-21 已完成并通过 pytest；Phase 5 完成 |
| Phase 6 | Step 22-26 | `skipped` | 当前答辩范围暂缓 |
| Phase 7 | Step 27-30 | `skipped` | 当前答辩范围暂缓 |

---

## Phase 2 补充执行记录

### 补充记录. 官方库与案例库字段校验

- 状态：`done`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/debug/refresh_official_library.py`
  - `src/admitpilot/debug/refresh_case_library.py`
  - `src/admitpilot/debug/check_library_fields.py`
  - `src/admitpilot/debug/library_validation.py`
  - `data/official_library/official_library.json`
  - `data/case_library/case_library.json`
- 实际修复动作：
  - 新增官方库/案例库刷新脚本与字段校验脚本。
  - 逐校处理官方页面反扒 fallback，最终官方库 `predicted=0`。
  - 生成案例库并通过字段校验。
- 测试：
  - 命令：`PYTHONPATH=src python3 -m admitpilot.debug.refresh_official_library --cycle 2026`
  - 结果：`passed`
  - 命令：`PYTHONPATH=src python3 -m admitpilot.debug.refresh_case_library --cycle 2026`
  - 结果：`passed`
  - 命令：`PYTHONPATH=src python3 -m admitpilot.debug.check_library_fields`
  - 结果：`passed`
- 偏差说明：
  - 当前执行机默认 `python3` 为 3.9，仅用于脚本刷新与静态校验，不作为全量测试环境。
- 下一步：
  - `Phase 4 / Step 15`

---

## Phase 3. SAE 从示意打分到可解释策略引擎

### Step 11. 设计学校项目规则文件

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/sae/rules.py`
  - `src/admitpilot/agents/sae/service.py`
  - `requirements.txt`
  - `data/program_rules/nus_mcomp_cs.yaml`
  - `data/program_rules/ntu_msai.yaml`
  - `data/program_rules/hku_mscs.yaml`
  - `data/program_rules/cuhk_mscs.yaml`
  - `data/program_rules/hkust_msit.yaml`
  - `tests/test_sae_rules.py`
  - `src/admitpilot/pao/schemas.py`
  - `src/admitpilot/pao/contracts.py`
  - `src/admitpilot/pao/orchestrator.py`
  - `.gitignore`
- 实际修复动作：
  - 新增规则加载与校验模块，定义统一 schema：`hard_thresholds / soft_thresholds / recommended_backgrounds / risk_flags / missing_input_penalties`。
  - 新增 5 校项目规则 YAML 文件。
  - SAE service 接入规则加载，并在 `rule_score` 里应用硬门槛/缺失输入/背景匹配调整。
  - 新增 `test_sae_rules.py` 覆盖规则加载、缺字段报错、非法分数类型报错。
  - `requirements.txt` 增加 `PyYAML` 依赖。
  - 为在 Python 3.9 解释器上跑通 LangGraph 的 `TypedDict` 类型解析，将 `PaoGraphState.current_task` 等 `X | None` 写法改为 `Optional[X]`。
  - 调整 PAO dispatch：先判断 agent 是否注册，再执行 capability 校验，避免未知 agent 误报 `capability_denied`。
  - 移除 `dataclass(slots=True)`（Python 3.10+ 特性）以兼容当前默认 Python 3.9 测试环境。
  - `.gitignore` 忽略本地 `.pytest_deps/`（仅用于本机离线安装 pytest 依赖）。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_sae_rules.py tests/test_orchestrator.py tests/test_aie_service.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 原计划默认 `conda admitpilot + Python 3.11`；当前执行机默认 Python 为 3.9，因此做了少量类型/ dataclass 兼容性调整以保证 pytest 可跑。
- 下一步：
  - `Step 12`

### Step 12. 实现规则打分引擎

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/sae/scoring.py`
  - `src/admitpilot/agents/sae/service.py`
  - `src/admitpilot/agents/sae/schemas.py`
  - `src/admitpilot/agents/sae/agent.py`
  - `tests/test_sae_rule_scoring.py`
- 实际修复动作：
  - 新增 `RuleScorer`，输出 `rule_breakdown` 与 `rule_notes`，将硬门槛/官方完整度/背景匹配等规则项显式落到 breakdown。
  - `ProgramRecommendation` 增加 `rule_breakdown` / `rule_notes` 字段；SAE agent 输出同步透出。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_sae_rule_scoring.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 原计划还包含 `tests/test_sae_service.py` 回归；当前仓库尚未存在该测试文件，因此用 `RuleScorer` 单测 + 全量 pytest 作为本步验收。
- 下一步：
  - `Step 13`

### Step 13. 引入可替换的语义匹配适配器

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/sae/semantic.py`
  - `src/admitpilot/agents/sae/service.py`
  - `tests/test_sae_semantic.py`
  - `tests/test_sae_service.py`
- 实际修复动作：
  - 定义 `SemanticMatcher` 协议、`SemanticMatchResult`、`FakeSemanticMatcher`（确定性 token overlap）、`EmbeddingSemanticMatcher`（占位未接线）、`build_semantic_matcher()` 工厂。
  - `StrategicAdmissionsService` 支持注入 `semantic_matcher`，默认使用 fake matcher；移除 service 内联的语义打分函数。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_sae_semantic.py tests/test_sae_service.py`
  - 结果：`passed`
- 下一步：
  - `Step 14`

### Step 14. 输出证据化推荐解释

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/sae/schemas.py`
  - `src/admitpilot/agents/sae/service.py`
  - `src/admitpilot/agents/sae/agent.py`
  - `tests/test_sae_explanations.py`
- 实际修复动作：
  - `ProgramRecommendation` 增加 `evidence`、`gaps`、`risk_flags`、`missing_inputs`、`semantic_breakdown`。
  - 在 `StrategicAdmissionsService` 中聚合 AIE 官方状态/证据等级、规则 breakdown/notes、语义 breakdown 生成可引用证据链；`reasons` 中补充 tier 与加权公式说明。
  - SAE agent 输出字典同步上述字段。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_sae_explanations.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 下一步：
  - `Phase 4 / Step 15`


## Phase 4. DTA 从静态周计划到真实逆排调度器

### Step 15. 实现拓扑排序与里程碑调度器

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/dta/scheduler.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_scheduler.py`
- 实际修复动作：
  - 新增 `schedule_milestones()`，执行 DAG 拓扑排序。
  - 对缺失依赖抛出 `MissingDependencyError`，对环依赖抛出 `CyclicDependencyError`。
  - DTA service 在排期前统一走调度器，避免依赖顺序漂移。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_dta_scheduler.py`
  - 结果：`passed`
- 下一步：
  - `Step 16`

### Step 16. 加入真实 deadline 逆排

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/dta/deadlines.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_deadline_planning.py`
- 实际修复动作：
  - 新增官方 deadline 提取：从 `official_records` 的 `extracted_fields` / `content` 中抽取 `YYYY-MM-DD`。
  - 新增 `apply_deadline_reverse_plan()`：按最早官方 deadline 逆推 `scope_lock/doc_pack/submission/interview` 节点。
  - 无 deadline 时保留原默认节奏作为保守回退。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_dta_deadline_planning.py`
  - 结果：`passed`
- 下一步：
  - `Step 17`

### Step 17. 实现延误重排与冲突检测

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/dta/replan.py`
  - `src/admitpilot/agents/dta/service.py`
  - `tests/test_dta_replan.py`
- 实际修复动作：
  - 新增 `apply_replan()`：根据 `has_delay/start_week/blocked_tasks` 做里程碑重排。
  - 增加冲突检测：任务挤压、关键任务阻塞、提交窗口缓冲不足、窗口不可执行。
  - 对不可行排期输出 `red` 风险并在 DTA plan 中显式标注。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_dta_replan.py tests/test_orchestrator.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 下一步：
  - `Phase 5 / Step 18`


## Phase 5. CDS 从模板生成到可审计文书支持

### Step 18. 建立申请者证据模型

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/core/user_artifacts.py`
  - `src/admitpilot/core/__init__.py`
  - `src/admitpilot/agents/cds/facts.py`
  - `src/admitpilot/agents/cds/service.py`
  - `src/admitpilot/agents/cds/agent.py`
  - `tests/test_user_artifacts.py`
- 实际修复动作：
  - 新增证据实体 `EvidenceArtifact` 与 `UserArtifactsBundle`，覆盖 `course/project/internship/research/award/language/referee`。
  - 每条证据包含 `source_ref`、`verified`、`date_range`、`evidence_type` 等字段，并支持状态更新（`mark_verified`）。
  - 新增 `parse_user_artifacts()`，在缺字段/非法 evidence_type 时显式报错。
  - CDS 增加 `facts` 层，从用户证据 + SAE + DTA 生成事实槽位，替换原纯占位文本。
  - CDS agent 支持从 `context.constraints["user_artifacts"]` 注入结构化证据。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_user_artifacts.py tests/test_orchestrator.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 偏差说明：
  - 当前仅接入结构化证据模型与槽位映射，OCR/附件解析仍按计划留待后续步骤。
- 下一步：
  - `Step 19`

### Step 19. 实现事实槽位提取与缺证据 abstain

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/cds/schemas.py`
  - `src/admitpilot/agents/cds/facts.py`
  - `src/admitpilot/agents/cds/service.py`
  - `src/admitpilot/agents/cds/agent.py`
  - `tests/test_cds_fact_slots.py`
  - `tests/test_cds_service.py`
- 实际修复动作：
  - `NarrativeFactSlot` 增加 `status`（`verified/inferred/missing`）与 `source_ref`，并保留 `verified` 兼容标识。
  - fact slot 提取改为基于用户证据、SAE、DTA 共同生成，并输出状态。
  - CDS 在核心槽位缺失时触发 abstain：不生成正式草稿，输出高优先级一致性问题与补证据检查项。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_cds_fact_slots.py tests/test_cds_service.py tests/test_orchestrator.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 下一步：
  - `Step 20`


### Step 20. 设计可差异化的文书模板层

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/cds/templates.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_templates.py`
- 实际修复动作：
  - 新增模板层：`build_sop_outline()` / `build_cv_outline()`，将学校特征、SAE gaps/risk_flags、DTA 里程碑注入文书提纲。
  - CDS service 改为“模板层 + fact slot 填充”生成 drafts，不再直接硬编码固定 outline。
  - 通过学校差异 focus（NUS/NTU/HKU/CUHK/HKUST）确保不同学校提纲结构可区分。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_cds_templates.py tests/test_cds_fact_slots.py tests/test_cds_service.py tests/test_orchestrator.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 下一步：
  - `Step 21`


### Step 21. 实现跨文档一致性检查器

- 状态：`done`
- 开始时间：`2026-04-20`
- 完成时间：`2026-04-20`
- 改动文件：
  - `src/admitpilot/agents/cds/consistency.py`
  - `src/admitpilot/agents/cds/service.py`
  - `tests/test_cds_consistency.py`
- 实际修复动作：
  - 新增一致性检查器 `check_consistency()`，至少覆盖：
    - 时间线冲突（`execution_proof` 跨文档值不一致）
    - 经历叙事冲突（`motivation_core` 跨文档值不一致）
    - 学校项目名称对齐风险（SOP 提纲未出现目标学校名）
    - 未完全核验证据混入草稿（`inferred/missing`）
  - CDS service 的一致性检查改为复用该检查器输出结构化 issue。
- 测试：
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q tests/test_cds_consistency.py tests/test_cds_templates.py tests/test_cds_fact_slots.py tests/test_cds_service.py tests/test_orchestrator.py`
  - 结果：`passed`
  - 命令：`PYTHONPATH=".pytest_deps:src" python3 -m pytest -q`
  - 结果：`passed`
- 下一步：
  - `Phase 6（按当前范围暂缓）`
