# TrialCompiler 生成型方案工作流

## 为什么需要独立工作流

现有 A-F 工作流适合审核已经存在的临床文件、提出局部修订并验证修改是否传播完整。Metformin PAD 测试要求系统从历史证据、开发目标和运营约束出发生成一套新方案，任务边界明显不同。因此生成工作流不复用“先找缺陷再修复”的入口，而只共享证据治理、Trial Fact Sheet、质量门和审计机制。

## 受控阶段

```text
Phase 1 历史截断资料
  → G1 Evidence Planner
  → 阻塞问题、证据矩阵、候选事实、TBD、Synopsis
  → G2 Section Writers
  → 分章节候选方案
  → G3 Independent Quality Judge
  → 人工确认关键事实

Phase 2 合成申办方回答、监管沟通和中心可行性资料
  → 更新已确认事实
  → 增量重写受影响章节
  → A-F 文档审核与变更传播

Evaluator-only 隐藏材料
  → 仅由独立评分程序读取
  → 生成模型永远不可见
```

## 防泄漏机制

- Phase 1 只读取 `01_AI_VISIBLE_PHASE1`；
- Phase 2 才允许额外读取 `02_AI_VISIBLE_PHASE2`；
- `03_EVALUATOR_ONLY` 永不进入生成模型上下文；
- 每个可见文件记录 SHA-256；
- 对隐藏项目编号、参考研究名称和隐藏 JSON 键执行审计与移除；
- 输出明确记录 `phase2_materials_used` 与 `evaluator_materials_used`；
- 未确认值保持 `TBD`，不得伪装成已批准事实。

## 当前真实 API 结果

使用 `qwen-plus` 对 Phase 1 资料先执行 plan-only，再执行完整生成测试。系统生成：

- 5 个需要医学、统计、注册或运营人员回答的阻塞问题；
- 一组带来源定位的证据矩阵；
- 5 条候选 Trial Fact；
- 假设与 TBD 清单；
- Protocol Synopsis；
- 9 个候选方案章节；
- 独立质量门在完整草案中发现 7 项需修订问题，并判定为 `revise_before_human_review`。

运行记录保存在本地 `outputs/metformin_pad_phase1_plan_20260718/` 与
`outputs/metformin_pad_phase1_full_20260718/`。完整生成支持逐 agent、逐章节 checkpoint 和断点续跑；输出目录默认不进入 Git，以避免将大体积运行产物与产品代码混合。

## 当前边界

生成结果是候选草案，不是可直接执行或申报的临床试验方案。医学合理性、统计合理性、法规策略、运营可行性和正式批准均须由有权限的专业人员完成。当前原型首先验证受控生成、证据追溯、TBD 管理和隐藏评估隔离，不声称替代专业审评。
