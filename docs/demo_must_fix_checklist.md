# AdmitPilot Demo 必修整改清单

- 文档日期：`2026-04-19`
- 适用范围：当前仓库基线 `src/admitpilot`
- 目标：在课程 demo 前，优先修复会直接影响流程正确性、结果可信度、可解释性的缺陷

## Demo 出门条件

1. `时间线` 单意图请求不能再出现 `DTA` 被依赖阻塞跳过的情况。
2. `文书` 单意图请求不能再在缺失上游上下文时生成看似真实的文书事实。
3. `Reach / Match / Safety` 分层语义必须与分数方向一致，不能误导用户。
4. AIE 历史证据池不能重复写入同一批官方记录。
5. 回归测试与最小 smoke test 必须覆盖以上场景。

## 整改优先级

1. `P1` 修复 PAO 路由依赖闭包
2. `P1` 修复 SAE 分层阈值语义
3. `P1` 修复 CDS 降级路径中的事实伪造
4. `P2` 修复 AIE 官方历史记忆重复写入

## 1. PAO 路由依赖闭包

- 责任模块：`src/admitpilot/pao/router.py`
- 问题描述：
  当前 `build_timeline` 依赖 `evaluate_strategy`，`draft_documents` 依赖 `evaluate_strategy + build_timeline`，但路由器只在命中 `strategy` 关键词时才加入 `evaluate_strategy`。这会导致：
  - 只问“时间线”时，`DTA` 被跳过
  - 只问“文书”时，`CDS` 在缺少 `sae/dta` 的情况下走降级路径
- Demo 风险：
  直接破坏 proposal 中的标准链路 `AIE -> SAE -> DTA -> CDS`，属于演示级阻断问题。
- 必做修改：
  1. 在意图识别后补全任务依赖闭包，而不是只按关键词直接拼任务。
  2. 若命中 `timeline`，自动补入 `strategy`。
  3. 若命中 `documents`，自动补入 `strategy + timeline`。
  4. 保证任务顺序仍为 `collect_intelligence -> evaluate_strategy -> build_timeline -> draft_documents`。
  5. 保留真正的降级逻辑，但仅用于运行时失败或上游异常，不用于正常单意图请求。
- 验收标准：
  1. 查询“请给我做申请时间线”时，结果至少包含 `AIE + SAE + DTA` 成功执行。
  2. 查询“请帮我准备文书”时，结果至少包含 `AIE + SAE + DTA + CDS` 成功执行。
  3. 上述两个场景不再出现 `missing_task:evaluate_strategy`、`missing_memory:sae`、`missing_memory:dta`。
- 必补测试：
  - 在 `tests/test_orchestrator.py` 中新增 `timeline-only` 与 `documents-only` happy path 测试。

## 2. SAE 分层阈值语义

- 责任模块：`src/admitpilot/agents/sae/service.py`
- 问题描述：
  `overall_score` 越高代表规则更匹配、语义更契合、风险更低，但当前 `_tier_from_score()` 却把低分映射为 `safety`，高分映射为 `reach`。
- Demo 风险：
  会直接输出错误的选校分层，影响用户理解，也会污染 DTA 和 CDS 的下游结果。
- 必做修改：
  1. 重新定义 `_tier_from_score()` 的阈值映射，使分数方向与 `reach / match / safety` 语义一致。
  2. 若继续沿用当前分数定义，建议使用：
     - `overall_score < 0.60 -> reach`
     - `0.60 <= overall_score < 0.72 -> match`
     - `overall_score >= 0.72 -> safety`
  3. 检查 `summary`、`reasons`、`ranking_order` 是否仍与新的 tier 语义一致。
- 验收标准：
  1. 更高 `overall_score` 的学校不能被标为比更低分学校更“冲刺”。
  2. 示例输出中，tier 与常识一致，且排序与分层不矛盾。
- 必补测试：
  - 为 `_tier_from_score()` 增加边界值测试。
  - 为 `evaluate()` 增加“高分为 safety、低分为 reach”的行为测试。

## 3. CDS 降级路径真实性

- 责任模块：`src/admitpilot/agents/cds/service.py`
- 关联模块：`src/admitpilot/agents/cds/agent.py`
- 问题描述：
  在缺失 `sae` / `dta` 上游数据时，CDS 仍会构造如下事实槽位：
  - `申请动机与长期职业目标一致`
  - `优先项目顺序: 待补充`
  - `关键里程碑数量=0`
  这些内容看起来像真实事实，但其实没有证据支撑。
- Demo 风险：
  与 proposal 中的真实性、可解释性、治理要求冲突，容易在演示中被质疑“系统在编造材料”。
- 必做修改：
  1. 在 CDS 识别到上游上下文缺失时，显式进入 `abstain / missing_evidence` 路径。
  2. 不再生成伪事实；缺失信息必须明确标记为“待补充”或“缺少上游证据”。
  3. 若保留 `fact_slots`，则 `source` 应标注为 `missing_upstream_context` 或等价语义。
  4. `interview_talking_points` 不能再引用不存在的项目优先级或里程碑数量。
  5. `review_checklist` 中应显式要求先补齐上游策略与时间线。
- 验收标准：
  1. 在缺失 `sae/dta` 输入时，CDS 输出中不再出现伪造动机、伪造排序、伪造执行证明。
  2. 降级输出必须让评审一眼看出“当前缺证据，不能直接用于文书定稿”。
- 必补测试：
  - 增加降级输入场景测试，断言输出包含缺证据标识，且不包含伪事实文本。

## 4. AIE 官方历史记忆去重

- 责任模块：`src/admitpilot/agents/aie/service.py`
- 问题描述：
  `_resolve_official_snapshot()` 在一次 fresh fetch 中对同一批 `records` 调用了两次 `_official_long_memory.extend(records)`。
- Demo 风险：
  会让历史证据池膨胀，后续预测置信度与证据基础失真。虽然不一定立刻让 demo 崩溃，但会削弱结果可信度。
- 必做修改：
  1. 删除重复写入，只保留一次 `extend(records)`。
  2. 检查是否需要去重策略，避免同一天重复抓取继续写入相同 `version_id`。
  3. 若保留内存历史池，至少按 `school + cycle + page_type + version_id` 做幂等保护。
- 验收标准：
  1. 单次拉取 1 所学校时，历史池新增条数应等于 gateway 实际返回记录数。
  2. 不再出现“一次抓取新增 4 条，但源数据只有 2 条”的现象。
- 必补测试：
  - 新增测试，断言一次官方抓取后 `_official_long_memory` 的增量与返回记录数一致。

## 最小验证清单

1. 运行测试：

```bash
$env:PYTHONPATH='src'; python -m pytest -q
```

2. 手工 smoke test：

```bash
$env:PYTHONPATH='src'; python -m admitpilot.main
```

3. 定向验证场景：
  - 查询：`请给我做申请时间线`
  - 查询：`请帮我准备文书`
  - 检查是否仍有 `SKIPPED`、`degraded_tasks`、伪事实槽位、反向分层结果

## 建议执行顺序

1. 先修 `router.py`，否则后续很多结果都处于错误调用链路上。
2. 再修 `sae/service.py`，先保证“分层语义正确”。
3. 然后修 `cds/service.py`，堵住真实性风险。
4. 最后修 `aie/service.py`，补齐数据一致性与回归测试。

## 备注

- 本清单只覆盖 demo 前必须关掉的问题，不包含生产化改造项。
- `datetime.utcnow()` 弃用 warning、`.pytest_cache` 权限 warning 当前不列入 demo 阻断项，但建议在 demo 后尽快清理。
