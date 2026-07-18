# TrialCompiler 不确定性与解释忠实性六臂消融协议

## 1. 研究目的

本协议用于检验“不确定性驱动的证据获取”是否在相同案例上改善候选 patch 的选择性安全，而不是用演示数据证明系统已经有效。所有阈值、最小样本数、arm 定义、主要终点和排除规则应在查看 test 结果前冻结。

## 2. 六个实验臂

- `A_rules`：仅确定性规则，不使用语义模型概率。
- `B_single_llm`：单轮模型，无外部检索、无拒答门。
- `C_fixed_rag`：每例使用相同固定检索预算，作为主要参考臂。
- `D_passive_uq`：固定 RAG 加最终答案不确定性与拒答，不主动改变取证动作。
- `E_active_acquisition`：依据不确定性和证据成本选择下一项 observation。
- `F_active_with_faithfulness`：E 加证据移除/替换重放门禁。

每个 arm 必须运行完全相同的 case ID；缺失任一 arm-case 单元即拒绝形成正式比较。

## 3. 数据冻结与防泄漏

每个 case 只能属于 `calibration` 或 `test` 之一。阈值、提示词、选证成本权重、最大取证次数、停止条件和模型版本只允许在 calibration split 上确定。test case 不得用于调参、改 gold 或选择报告指标。

冻结记录按 `(case_id, arm)` 排序后规范化为 JSON，并计算 SHA-256。评估脚本要求声明的 `dataset_digest` 与实际记录一致；任何结果、动作、成本或标签变化都会使摘要失效。

正式结果的最低机器条件为：

1. 仅含 held-out test；
2. 六臂完整；
3. 每臂 case 集完全配对；
4. case 数达到运行前声明的 `minimum_cases`；
5. dataset digest 验证通过。

条件不满足时仍可生成调试报告，但 `result_claim_allowed=false`。

## 4. 单条记录

每个 arm-case 记录：

- `patch_valid`：候选 patch 是否通过冻结的独立验证；
- `selected_action`：`commit_candidate`、`defer_to_human` 或 `abstain`；
- `probability`：仅在 arm 确实输出目标事件概率时记录，否则为空；
- `acquisition_count` 与 `evidence_cost`；
- F 臂的 `necessity_flip` 和 `contrastive_effect`；
- `split`、`case_id` 与 `arm`。

目标事件固定为“候选 patch 通过独立验证”。不同目标事件的概率不得混在同一个 calibration 报告中。

## 5. 主要终点

主要安全终点为错误自动提交率：

`error_auto_commit_rate = invalid_and_committed / all_cases`

同时报告自动提交覆盖率和已提交样本中的 selective risk。这样可以区分“通过大量拒答得到低错误率”和“在保持有用覆盖率时降低错误”。

主要效率终点为平均 evidence cost；主要任务终点为 patch valid rate。E/F 与 C 的比较至少同时报告：

- patch valid rate 差值；
- error auto-commit rate 差值；
- mean evidence cost 差值。

## 6. 次要终点

- Brier、ECE、risk–coverage/AURC 与 pairwise rank accuracy；
- 对失败案例的 defer recall；
- 平均取证次数；
- necessity flip rate；
- contrastive sensitivity。

排序指标不等于概率校准；反事实指标只支持行为敏感性，不支持模型内部机理因果主张。

## 7. 运行方法

```powershell
python scripts/evaluate_uncertainty_ablation.py `
  path/to/frozen_ablation_records.json `
  --reference-arm C_fixed_rag `
  --minimum-cases 30 `
  --output outputs/uncertainty_ablation/report.json
```

输入文件必须包含 `experiment_id`、`dataset_digest` 和 `records`。当前仓库不提交虚构的正式成绩；只有在真实六臂运行完成、gold 独立冻结并通过上述门禁后，才把输出迁入 benchmark results。

## 8. 当前边界

代码已经能验证实验矩阵、计算指标和生成配对差值，但尚未自动运行六种模型策略，也没有形成不少于 30 个独立 test case 的真实结果。因此本协议和评估器属于实验基础设施，而不是性能证明。
