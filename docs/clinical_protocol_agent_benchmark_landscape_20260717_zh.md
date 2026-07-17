# 临床试验方案 Agent、公开基准与 TrialCompiler 定位复核

## 1. 结论先行

这个领域并不是空白。公开研究已经较成熟地覆盖了以下任务：

1. 从方案或 SAP 中抽取结构化信息；
2. 生成入排标准、方案章节或知情同意书；
3. 预测试验结果、失败原因和设计属性；
4. 用多 Agent 循环优化试验科学设计；
5. 从 SAP/Protocol 复现统计设计并生成可执行 R 代码；
6. 用人工规则评价生成文档的法规符合性和事实准确性。

但是，截至本次核查，尚未发现一个已经成熟开放、拥有稳定排行榜、并完整评价下列链路的公共基准：

```text
受控项目事实及版本
-> 事实与章节/表格/关联文件的依赖图
-> 跨文档一致性检查
-> 区分真实冲突、合法映射和状态差异
-> 单项变更的影响范围召回
-> 候选红线与旧值残留检查
-> 专业人员审批后生效
-> 审核经验按适用范围治理和复用
```

因此，TrialCompiler 不能宣称“临床方案生成领域首创”，也不能把普通 RAG 写作或多 Agent 当成独占创新。更稳妥、也更有说服力的定位是：

> TrialCompiler 面向临床试验方案及关联文件的受控文档工程，把已确认设计事实、文档依赖、确定性测试、语义复核、变更传播、证据溯源和人工批准连接成一条可审计链路。

这是一条已经有强近邻、但尚未被一个公开 benchmark 完整覆盖的细分方向。

## 2. 对“已经成熟甚至已经刷榜”的判断

### 2.1 已经较成熟的方向

#### InformBench / InformGen：最接近的文档生成基准

InformBench 包含 900 项试验的 Protocol 与 ICF 文档，用于评价从方案生成知情同意书时的法规符合性和事实准确性。InformGen 采用文档解析、检索增强、人工介入和行内来源引用；论文报告其在 18 条法规规则上的符合性接近 100%，人工评估事实准确率超过 90%。

它证明三个判断已经不再新颖：

- “临床文档很长，所以需要 RAG”；
- “生成内容必须引用来源”；
- “高风险临床文档需要 human-in-the-loop”。

它也给 TrialCompiler 留下了清晰边界：InformBench 的核心任务是 `Protocol -> ICF`，并不完整评价多种关联文件之间的依赖图、事实版本传播、合法时间轴映射和旧值残留。

#### AutoTrial、CTBench 与 TrialBench：局部设计和预测任务

AutoTrial 针对入排标准生成；CTBench 针对基线特征列表预测；TrialBench 覆盖试验时长、脱落、严重不良事件、失败原因、获批和入排标准设计等预测任务。这些方向已经有明确数据集、指标和模型基线，不能作为 TrialCompiler 的主创新点。

#### TrialMind / TrialReviewBench：专家基准和人机协作

TrialReviewBench 用系统综述和关联研究构造人工基准，TrialMind 覆盖检索、筛选和数据抽取，并用用户研究评价人机协作。它与 TrialCompiler 的任务不同，但说明“专家标注集 + 普通 LLM 基线 + 人机协作增益 + 时间节省”已经是可信的实验范式。

### 2.2 正在形成，但尚未成熟开放的方向

#### TrialDesignBench：最值得直接学习的 benchmark 工程

TrialDesignBench 当前主要任务是：给定 SAP 或 Protocol，让 Agent 抽取或推导统计设计，并生成 `output.json` 和可重复执行的 `output.R`。其代码已经实现：

- 独立 benchmark workspace；
- PDF 到结构化 Markdown 的转换；
- 固定任务 prompt；
- Agent 运行目录和产物保存；
- 模型、配置和运行元数据记录。

其公开案例提案进一步规定：

- 闭卷，仅允许使用输入文档；
- 每个事实必须追溯到章节和页码；
- 将问题分为直接抽取与需要推导；
- 对输入、方法、计算结果分别评分；
- 同时设置 `Add` 和高风险 `Deduct` 条件；
- 派生问题必须提供可执行、可复核的 R 代码。

但是其设计生成任务仍标为开发中，公开排行榜仍是预览状态。因此它是一个非常有价值的正在形成的基准，而不是一个已经稳定刷榜多年的成熟赛道。

#### ClinicalReTrial：最值得学习的多 Agent 循环

ClinicalReTrial 将失败试验的优化拆为：

```text
失败分析
-> 候选修改生成
-> 安全验证
-> 候选探索与评估
-> 试验成功概率奖励
-> 本试验迭代规则
-> 跨试验全局知识池
```

代码中确实存在 enrollment、safety、efficacy 三类 Agent，以及 Analysis、Augment、Validator、Exploration、奖励计算和全局知识池，不只是论文概念图。

但它解决的是“如何修改科学设计以提高预测成功率”。它并不负责把一个已经由医学、统计和注册人员确认的变更，安全地同步到方案正文、SoA、SAP、ICF、CRF 等文件中。二者可以借鉴架构，但不能混为同一任务。

### 2.3 目前未确认存在成熟公开排行榜的方向

本次没有找到专门针对以下综合任务的公开稳定 leaderboard：

- Protocol、SAP、ICF、SoA、CRF、注册记录之间的事实一致性；
- 合法口径映射与真实冲突的分类；
- 事实版本变更后的完整影响召回；
- 旧值残留和未同步关联文件检测；
- 自动修改是否越过专业审批边界；
- 事实、规则、来源和批准状态的联合治理。

商业系统可能已实现部分能力，但商业宣传不能代替公开任务定义、测试集、金标准和可复现实验。

## 3. NCT04683926 案例在研究体系中的位置

医学同学提供的 `NCT04683926 / OMNI-PAIN-103` 案例不是训练数据，而是第一套公开文档 benchmark case。它应被用于以下六类任务：

| 任务 | 例子 | 期望行为 |
|---|---|---|
| 事实抽取 | 样本量、终点、访视、给药和 PK 采样 | 输出规范值、状态和来源 |
| 真冲突检测 | 给药前后 1 小时 `No water` 与 `water only` | 高风险告警并阻止自动确认 |
| 边界差异 | `>3 days` 与 `3 days` | 提示差异并交人工裁定 |
| 合法映射 | Protocol Day 1/4/7/10 与 CRF 各 Period Day 1 | 识别映射，不误报冲突 |
| 状态区分 | 计划 32、目标 PK 完成 24、实际入组 24 | 保留 planned/target/actual 语义 |
| 合成变更传播 | 最终 PK 采样 32 h -> 36 h | 召回受影响章节和文件，检测旧值残留 |

第二个 Week 12 -> Week 16 ZIP 是仓库已有合成案例的运行封装，只能作为开发回归测试，不能作为第二个独立外部案例，也不能与 NCT04683926 一起声称“两项真实验证”。

## 4. TrialCompiler 应吸收的具体实现

### 4.1 从 TrialDesignBench 吸收 benchmark case 契约

每个案例固定包含：

```text
case_manifest
input_documents
document_versions
gold_fact_sheet
gold_relations
gold_findings
synthetic_amendments
scoring_rubric
expected_artifacts
adjudication_notes
```

每条 rubric 同时记录：

- 任务 ID；
- 输入范围；
- 期望输出；
- 来源页码；
- 加分条件；
- 高风险扣分条件；
- 是否必须人工升级；
- 可接受误差或语义等价规则。

### 4.2 从 InformBench 吸收法规与事实双层评价

将总评价拆为：

```text
S = w_f S_factuality
  + w_c S_compliance
  + w_p S_provenance
  + w_d S_dependency
  + w_i S_impact
  + w_g S_governance
  - P_unsafe
```

其中：

- `S_factuality`：事实值、语境和状态是否正确；
- `S_compliance`：必备内容和规则是否满足；
- `S_provenance`：来源文件、位置和版本是否准确；
- `S_dependency`：事实到章节、表格、文件的边是否正确；
- `S_impact`：变更影响集合的 precision/recall；
- `S_governance`：候选、确认、批准和适用范围是否守界；
- `P_unsafe`：无证据改值、把合法映射报成冲突、越权自动批准等高风险惩罚。

### 4.3 从 ClinicalReTrial 吸收循环，但更换奖励目标

TrialCompiler 不应以“试验成功概率”作为奖励。更合理的循环是：

```text
事实提取 Agent
-> 依赖构建 Agent
-> 确定性测试器
-> 语义审阅 Agent
-> 变更影响 Agent
-> 质量与权限 Gate
-> 人工裁定
-> 经确认的规则/案例记忆
```

循环的目标不是让 Agent 自主改变试验设计，而是提高证据覆盖率、冲突召回、合法映射识别、影响召回和审核效率，同时压低错误自动修改率。

## 5. 建议的公开 benchmark 设计

### 5.1 数据单元

以“研究”为切分单位，不能把同一研究的不同文件随机拆进训练集和测试集。每个研究至少包含 Protocol，并尽量配对 SAP、ICF、注册记录和结果记录。

### 5.2 六类任务

1. `T1 Fact Extraction`：抽取规范事实、状态、单位和来源；
2. `T2 Consistency Review`：检测真冲突并控制误报；
3. `T3 Semantic Mapping`：识别不同时间轴、术语和文件目的之间的合法映射；
4. `T4 State Resolution`：区分计划值、目标值、修订值和实际值；
5. `T5 Change Impact`：在合成或公开 amendment 下召回受影响节点；
6. `T6 Controlled Revision`：生成候选红线，但保留证据、权限和人工批准。

### 5.3 核心指标

| 维度 | 指标 |
|---|---|
| 事实 | exact match、单位归一化准确率、semantic F1 |
| 冲突 | precision、recall、F1、高风险漏报率 |
| 合法映射 | false-positive conflict rate |
| 来源 | source document / page / section accuracy |
| 依赖图 | edge precision、edge recall、graph edit distance |
| 变更影响 | impacted-node precision、recall、旧值残留召回率 |
| 治理 | unsafe auto-change rate、required-escalation recall |
| 稳定性 | 多次运行一致率、结构化输出有效率 |
| 工程 | 成本、延迟、人工审核时间、人工修改量 |

高风险任务不能只报告一个平均 F1。应单列高风险漏报、错误自动修改和错误批准；这些错误可设置为 benchmark 阻断条件。

### 5.4 基线

建议至少比较：

1. regex / deterministic rules only；
2. vanilla LLM；
3. LLM + flat RAG；
4. structured extraction + single reviewer；
5. TrialCompiler full pipeline；
6. full pipeline 去掉 dependency graph、deterministic tests、human gate 或 governed memory 的消融版本。

## 6. 对比赛叙事的影响

### 不应该再说

- “我们首次用 AI 写临床试验方案”；
- “我们首次让 Agent 审核临床文档”；
- “RAG、引用来源或多 Agent 本身就是创新”；
- “一个公开案例跑通就证明系统可用”。

### 可以有证据地说

- 我们把结构化事实、跨文档依赖、文档单元测试和增量变更传播组合成受控文档工程；
- 系统区分确定性错误、语义冲突、合法映射和需要专家判断的边界问题；
- 所有候选事实和修改均带来源、版本、状态、影响范围和人工批准记录；
- 我们参考公开 benchmark 的 case contract 和 rubric 方法，构建可复现的 TrialDocBench；
- NCT04683926 是第一项公开研究案例，Week 12 -> 16 是独立标记的合成回归测试；
- 后续结果将与规则、普通 LLM、RAG 和消融基线比较，而不只展示一份看起来合理的生成文本。

## 7. 下一步优先级

1. 用现有 NCT04683926 完成端到端 baseline，保存每一步结构化产物和运行轨迹；
2. 将当前 10 项 reviewed tests 扩展成逐条可评分 rubric，加入高风险扣分条件；
3. 再建立 4-9 个公开研究案例，确保疾病、阶段、设计和文档组合具有差异；
4. 把 InformBench 作为 Protocol-to-ICF 的外部邻近基准，而不是直接并入内部 gold；
5. 把 ICH M11 字段映射到 Trial Fact Sheet，减少自定义 schema 的任意性；
6. 先跑规则、vanilla LLM、RAG 三条基线，再评价多 Agent 是否真的带来增益；
7. 由医学、统计或注册背景人员复核 gold，并记录分歧和 adjudication，而不是把单一 AI 输出直接称为金标准。

## 8. 主要参考

- TrialDesignBench: <https://trialdesignbench.org/>
- TrialDesignBench source: <https://github.com/BBSW-org/TrialDesignBench>
- TrialDesignBench KN189 case proposal: <https://github.com/BBSW-org/TrialDesignBench/issues/39>
- InformGen / InformBench: <https://arxiv.org/abs/2504.00934>
- InformBench dataset: <https://huggingface.co/datasets/zifeng-ai/InformBench>
- ClinicalReTrial: <https://arxiv.org/abs/2601.00290>
- ClinicalReTrial source: <https://github.com/xingsixue123/ClinicalFailureReasonReTrial>
- AutoTrial: <https://aclanthology.org/2023.emnlp-main.766/>
- CTBench: <https://arxiv.org/abs/2406.17888>
- TrialBench: <https://www.nature.com/articles/s41597-025-05680-8>
- TrialMind / TrialReviewBench: <https://www.nature.com/articles/s41746-025-01840-7>
- From RAGs to riches: <https://pubmed.ncbi.nlm.nih.gov/40013826/>
- ClinicalTrials.gov results QC criteria: <https://clinicaltrials.gov/submit-studies/prs-help/results-quality-control-review-criteria>
- ICH M11 Clinical electronic Structured Harmonised Protocol: <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/m11-clinical-electronic-structured-harmonised-protocol>

