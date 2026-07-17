# TrialCompiler 公开案例验证记录

## 验证目的

本轮验证不使用患者级数据，只使用 ClinicalTrials.gov 官方公开文件与人工复核的金标准。验证目标包括：

1. 已有临床文件之间的事实冲突能否被识别；
2. 确定性规则与 LLM 语义检查能否互补；
3. 计划值、实际值和完成值等合法状态差异是否会被误报；
4. 每条发现是否保留来源、章节、事实 ID 和人工审核入口。

## 案例与流程

### NCT03232983

输入包括公开 Protocol、SAP、ClinicalTrials.gov 注册及结果记录。人工金标准包含三项应报问题和一项负例：

- Protocol 封面试验编号与注册编号不同；
- Protocol 的 `AUC(0-infinity)` 与注册记录的 `AUC(0-10h)` 不同；
- 480 至 600 分钟的血糖采样频率表述不同；
- 最大计划入组数、目标完成数和实际入组数是不同状态，不应直接判为冲突。

第一次仅依赖 LLM 语义检查时，系统识别出后两项语义问题，但漏掉封面编号错误。该失败促使系统新增 NCT 编号确定性规则。重新运行后，三项应报问题全部命中，负例未被误报。

结果文件：

```text
benchmarks/trialdocbench/public_case_002_nct03232983/results/qwen_plus_run_20260718.json
```

### NCT03117738

输入包括公开 Protocol、SAP、ICF、ClinicalTrials.gov 注册及结果记录。人工金标准包含三项应报问题和一项负例：

- 早期 ICF、后期 Protocol/SAP 和最终注册结果中的人数语义不同；
- ICF 内部对随机访视的描述互相冲突，SAP 明确为 Visit 2 / Week -4；
- 早期 ICF 与后期 Protocol 的筛选时间窗不同；
- 每组计划人数、实际开始治疗人数和实际完成人数属于不同状态，不应机械判为冲突。

系统识别三项应报问题，且未误报负例。所有修改建议仍标记为 `requires_human_review`，系统不自动决定哪个版本在医学或法规意义上有效。

结果文件：

```text
benchmarks/trialdocbench/public_case_003_nct03117738/results/qwen_plus_run_20260718.json
```

## 本轮结果

| 案例 | 应报问题 | 命中 | 漏报 | 负例 | 正确未报 |
| --- | ---: | ---: | ---: | ---: | ---: |
| NCT03232983 | 3 | 3 | 0 | 1 | 1 |
| NCT03117738 | 3 | 3 | 0 | 1 | 1 |

以上结果只覆盖两套小规模、人工复核的公开案例，不能解释为系统具有普适的 100% 准确率。它证明的是：现有原型可以完成“结构化事实 → 确定性检查 → 语义检查 → 修订建议 → 人工审核包 → 金标评分”的完整链路。

## 暴露的问题

1. 纯 LLM 审核会漏掉简单但关键的编号错误，因此显式可计算规则不可省略。
2. LLM 可能把“早期计划、后期计划、实际结果”统一描述为不一致；最终处理必须结合版本和状态语义，不能自动覆盖原文。
3. 当前 fixture 是人工摘录的关键章节，不等于从整份 PDF 自动抽取后的端到端验证。
4. 当前评分按金标涉及章节与系统发现章节进行匹配；后续应增加盲法人工语义评分和更多案例。

## 可复现命令

```powershell
$env:PYTHONPATH = "src"

python -m trialcompiler init `
  --workspace outputs/public_case_002_runtime `
  --document data/fixtures/nct03232983_public_case.json `
  --actor benchmark --replace

python -m trialcompiler compile `
  --workspace outputs/public_case_002_runtime `
  --db outputs/public_case_002_runtime/memory.sqlite3 `
  --llm on --llm-model qwen-plus

python scripts/score_public_benchmark_runs.py `
  --gold benchmarks/trialdocbench/public_case_002_nct03232983/gold/gold_tests.json `
  --workspace outputs/public_case_002_runtime
```

将路径中的 `002` 和 fixture 名替换为 `003`，即可复现第二套案例。
