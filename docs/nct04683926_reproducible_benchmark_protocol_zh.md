# NCT04683926 可复现测试流程

## 1. 测试目的

本测试验证 TrialCompiler 是否能把公开临床研究文件转换为可追踪事实层，识别单文档与跨文档不一致，并在一项关键事实变化后完成影响定位、候选修订、沙箱复检和人工审核门控。

案例为 NCT04683926 / OMNI-PAIN-103。它是一项已完成的 Phase 1、随机、开放、四治疗、四周期、四序列交叉试验。测试只使用公开 study-level 文件和明确标记的合成变更，不使用患者级数据。

本测试不是对临床设计作医学批准。AI 输出始终是候选意见；医学、统计、注册和质量判断必须由具备相应职责的人员完成。

## 2. 测试边界

系统允许：

- 提取带来源定位的候选事实；
- 区分计划值、执行值、结果值和历史版本；
- 检测数字、时间点、术语、日程和跨文件语义冲突；
- 建立事实到章节、表格和文件的依赖关系；
- 生成操作级候选修订；
- 在不覆盖正式文件的沙箱中重新检查；
- 形成 Decision Request 和人工审核包。

系统禁止：

- 将公开资料中的差异直接判为某一来源错误；
- 用模型猜测替代缺失的专业决策；
- 将合成变更伪装成真实方案修订；
- 在未解决专业决策时批准或覆盖正式版本；
- 把模型输出写入可复用经验库而不经过人工批准。

## 3. 基准包结构

基准包位于：

```text
benchmarks/trialdocbench/public_case_001_nct04683926/
├── README.md
├── source_manifest.tsv
├── source_documents/
├── gold/
│   ├── gold_tests.json
│   └── trial_fact_sheet_gold.tsv
└── synthetic_changes/
    └── pk_32h_to_36h.md
```

测试资产包括：

- Protocol；
- SAP；
- ICF；
- ClinicalTrials.gov 注册与结果记录；
- 27 条人工整理的 Trial Fact Sheet；
- 跨文档一致性与合法差异金标准；
- 完全合成的 `32 h -> 36 h` 最终 PK 采样时间变更。

`source_manifest.tsv` 是来源身份、类型、公开链接和本地路径的权威清单。`gold/` 只用于测试与评分，不应作为模型生成修订时的答案输入。

## 4. 环境固定

```powershell
cd D:\TrialCompiler
$env:PYTHONPATH = "src"
$py = "D:\miniconda\envs\iGEM\python.exe"
$ws = "outputs\repro_nct04683926"
$db = "$ws\memory.sqlite3"
```

复现实验记录必须额外保存：

- Git commit；
- Python 与依赖版本；
- 模型名称；
- Prompt 文件哈希；
- 运行时间；
- API 模式；
- 基准包来源文件哈希；
- 运行输出目录。

API 密钥只通过本地环境变量提供，不进入仓库、运行报告或审计日志。

## 5. 步骤一：校验基准包

```powershell
& $py -m pytest tests\test_trialdocbench_public_case.py -q
```

验收要求：

- manifest 中所有文件存在；
- 公开来源与合成资产明确分开；
- 27 条事实均具有 `source_ids`、`source_locator` 和状态；
- 合成变更没有进入基线事实；
- 金标准同时包含“应该报告的冲突”和“不得误报的合法差异”；
- 测试退出码为 0。

## 6. 步骤二：生成运行时 fixture

```powershell
& $py scripts\build_nct04683926_runtime_fixture.py
```

输出：

```text
data/fixtures/nct04683926_public_case.json
```

预期计数：

| 对象 | 数量 |
|---|---:|
| 公开来源 | 4 |
| Trial facts | 27 |
| 跨文档章节摘录 | 10 |
| 已确认事实 | 23 |
| 需人工复核事实 | 4 |

构建器必须排除合成来源 `SRC-MUT`。`32 h -> 36 h` 只能在变更测试阶段进入候选状态，不能污染基线。

## 7. 步骤三：初始化只读审查工作区

```powershell
& $py -m trialcompiler init `
  --workspace $ws `
  --document data\fixtures\nct04683926_public_case.json `
  --actor repro-owner

& $py -m trialcompiler status --workspace $ws
& $py -m trialcompiler facts --workspace $ws
```

预期生成：

```text
outputs/repro_nct04683926/
├── project.json
├── document.json
├── audit.jsonl
├── changes/
├── runs/
└── approvals/
```

验收要求：4 个公开来源、27 条事实、10 个章节、0 个 open change，且 `release_mode=review_only`。`audit.jsonl` 应包含 `workspace_initialized`。

## 8. 步骤四：运行基线审查

```powershell
$env:DASHSCOPE_API_KEY = "<LOCAL_SECRET>"

$baseline = & $py -m trialcompiler compile `
  --workspace $ws `
  --db $db `
  --actor repro-baseline `
  --llm on `
  --llm-model qwen-plus `
  --max-rounds 2 | ConvertFrom-Json
```

基线审查包含：

1. 确定性图检查；
2. 真实 LLM 语义审查；
3. 受治理的语义候选修订；
4. 候选修订证据范围检查；
5. D-agent 沙箱复检；
6. 无法安全自动处理的问题转为 Decision Request；
7. E-agent 生成人工审核报告。

每次运行输出：

```text
runs/<run-id>/
├── workflow_state.json
├── agent_trace.jsonl
├── semantic_review.json
├── semantic_repairs.json
├── decision_requests.json
├── impact_matrix.json
├── review_report.md
└── run_summary.json
```

LLM 输出具有随机性，因此 finding 数量不是固定断言。固定要求是：所有 finding 可追溯、未知来源 ID 被丢弃、语义修订不得覆盖未提供的原文、未确认问题不得被自动批准。

## 9. 步骤五：创建合成事实变更

```powershell
$newValue = "0; 0.5; 1; 1.5; 2; 2.5; 3; 3.5; 4; 6; 8; 12; 16; 24; 36"

$change = & $py -m trialcompiler change `
  --workspace $ws `
  --fact-id F015 `
  --value $newValue `
  --reason "SYNTHETIC BENCHMARK ONLY: move final nominal PK sample from 32 h to 36 h" `
  --actor benchmark-statistician | ConvertFrom-Json

$changeId = $change.change_id

& $py -m trialcompiler impact `
  --workspace $ws `
  --change-id $changeId
```

此时正式 `document.json` 仍保留 32 h。系统只能创建候选事实版本和影响矩阵。

金标准影响对象：

- Protocol；
- Schedule of Activities；
- SAP；
- ICF；
- 合成 CRF 映射；
- registry/results 描述。

现有运行命中 7 个章节，覆盖 6/6 对象类别。无关的 `32 participants` 必须保持不变，这是防止全局字符串替换的关键负对照。

## 10. 步骤六：编译候选变更

```powershell
$compiled = & $py -m trialcompiler compile `
  --workspace $ws `
  --change-id $changeId `
  --db $db `
  --actor repro-change-compile `
  --llm on `
  --llm-model qwen-plus `
  --max-rounds 2 | ConvertFrom-Json

$runId = $compiled.run_id
$runDir = Join-Path $ws "runs\$runId"
```

C-agent 不是让模型重写全文，而是生成带起止位置、原文、替换文本、事实 ID、来源 ID 和 finding ID 的操作级 edit。多个 edit 按章节合并；重叠、来源不足或原文不匹配的 edit 被阻断。

D-agent 在内存候选文档上重新运行确定性检查，比较修订前后 finding 集合，并输出：

- 旧值是否残留；
- 新值是否进入目标位置；
- 是否产生新增回归；
- 是否误改无关数字；
- 是否仍有专业判断未解决；
- 机器修订是否完整。

参考运行：

```text
outputs/nct04683926_adjusted_v2_20260718/
runs/run-20260717180303-10544e/
```

该运行结果：

| 指标 | 结果 |
|---|---:|
| Findings | 11 |
| 合并后的章节补丁 | 7 |
| 补丁冲突 | 0 |
| 确定性残留 | 0 |
| 新增确定性回归 | 0 |
| 质量分 | 1.0 |
| 专业 Decision Requests | 3 |
| 工作流状态 | awaiting_qualified_decisions |

质量分 1.0 只表示机器补丁通过当前自动检查，不表示临床内容已经批准。

## 11. 步骤七：专业决策门

```powershell
Get-Content "$runDir\decision_requests.json" -Encoding UTF8
```

每个请求只能由具备相应职责的审核者处理：

```powershell
& $py -m trialcompiler decision-request `
  --workspace $ws `
  --change-id $changeId `
  --request-id <REQUEST_ID> `
  --decision require_recompile `
  --reviewer qualified-reviewer `
  --note "现有证据不足以授权唯一文本；补充证据后重新编译。"
```

另一合法选择是 `accept_documented`，表示审核者接受已记录差异，并提供非空理由。未解决的 Decision Request 必须 100% 阻断 `approve`。

参考运行的 3 个请求涉及：

- Protocol、SAP 与 CRF 的双时间轴解释；
- 饮水规则的操作性冲突；
- SAP safety-only 描述与 PK 分析范围。

## 12. 步骤八：最终分支与报告

查看报告和审计：

```powershell
Get-Content "$runDir\review_report.md" -Encoding UTF8
Get-Content "$runDir\run_summary.json" -Encoding UTF8
& $py -m trialcompiler audit --workspace $ws --limit 50
```

最终有三条合法路径：

1. 专业审核者接受已记录差异，所有请求解决后批准候选；
2. 专业审核者要求补证，返回 C/D 循环重新编译；
3. 拒绝合成候选，保留公开源版本。

公开 benchmark 若没有真实专业审核者，默认采用第三条：

```powershell
& $py -m trialcompiler decide `
  --workspace $ws `
  --change-id $changeId `
  --decision reject `
  --reviewer benchmark-auditor `
  --note "Public benchmark complete; unresolved professional decisions remain."
```

系统不得把候选补丁静默写回正式 `document.json`。

## 13. 评价指标

### 13.1 来源与事实治理

- 来源文件存在率；
- 来源哈希匹配率；
- 事实来源定位完整率；
- 未确认事实误用率；
- 合成资产误混入公开事实率。

### 13.2 冲突检测

- finding precision / recall / F1；
- 合法差异误报率；
- 跨文档冲突召回率；
- 版本语义识别率；
- finding 到来源证据的可追溯率。

### 13.3 影响分析与修订

- gold 影响位置召回率；
- 目标对象类别覆盖率；
- 非目标编辑率；
- 旧值残留率；
- 操作级补丁 provenance 完整率；
- 补丁冲突率。

### 13.4 复检与人工门控

- 确定性残留 finding 数；
- 新增回归数；
- pending Decision Request 阻断批准率；
- 审核记录完整率；
- 正式文件静默覆盖次数。

## 14. 当前结果解释

现有留存运行能够证明：

- TrialCompiler 可以从版本化事实建立影响图；
- `32 h -> 36 h` 能传播到 7 个目标章节；
- 操作级补丁能保护无关的 `32 participants`；
- D-agent 能发现残留和新回归；
- 未解决专业问题会被提升为 Decision Request；
- 工作流不会因为机器检查通过而自动批准临床内容。

现阶段不能证明：

- 所有临床不一致均已被发现；
- 候选修订在医学或统计上必然正确；
- 一次模型运行的 finding 数可以代表稳定性能；
- 系统可以替代医学、统计、注册或质量审核者。

## 15. 尚缺的自动化

当前仓库已经验证基准包完整性，但还缺少将一次运行的 finding 自动对齐 `gold_tests.json` 并计算 precision、recall 和 F1 的独立 scorer。完成 scorer 前，运行指标与 gold 对照应分别报告，不能把“测试包校验通过”误写成“模型准确率已经验证”。
