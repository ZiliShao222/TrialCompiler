# TrialCompiler 技术创新说明

> 2026-07-17 补充：根据医学资料包与竞品分析，TrialCompiler 的评测不应只看文本生成质量，而应围绕 TrialDocBench 指标体系衡量事实抽取、跨文件冲突召回、旧值残留检出、影响位置召回、过度修改控制、变更任务关闭、审计追溯完整、规则适用范围错误和受控经验复用。结构化指标见 `references/metadata/trialdocbench_metric_catalog.tsv`。

- 版本：v0.2
- 日期：2026-07-17
- 定位：比赛技术方案、架构设计与后续实验的统一依据

> 本文服从 [`product_definition_zh.md`](product_definition_zh.md) 的产品范围：当前只处理临床试验方案设计阶段的文档编制、一致性审核和变更影响分析，不处理患者病历筛查和临床数据清洗。

## 1. 技术问题

TrialCompiler 面对的不是普通的长文本生成，而是一个同时具有以下特征的文档工程问题：

1. 同一个研究事实会在多个章节、表格和下游文件中重复出现；
2. 事实、法规、企业模板和专家意见具有不同权威度、版本、权限和适用范围；
3. 核心事实变化后，需要定位全部直接和间接受影响的文档单元；
4. 生成结果必须经过证据检查、跨章节测试和专业人员审核；
5. 专家的修改经验需要复用，但错误、过期或越权经验不能进入后续任务；
6. 系统效果需要通过可复现实验量化，而不能只展示几段生成文本。

因此，系统的核心技术路线不是“更长的 Prompt”，而是：

```text
结构化事实与证据
  + 文档依赖图
  + 带治理边界的语义记忆
  + 评价器驱动的主动编译
  + 可回放评测 Harness
```

## 2. 技术创新总览

TrialCompiler 的技术贡献可以归纳为四个核心模块和两个支撑模块。

| 类型 | 模块 | 解决的问题 |
| --- | --- | --- |
| 核心创新 1 | Clinical Semantic Element | 知识不仅要语义相关，还要权威、有效、获批且适用 |
| 核心创新 2 | Governance-aware Coarse-to-Fine Retrieval | 降低语义相似但不可复用的错误记忆命中 |
| 核心创新 3 | Dependency-guided Incremental Compilation | 核心事实变化后只重建受影响的章节和文件 |
| 核心创新 4 | Human-governed Experience Compiler | 把专家审核轨迹转化为有条件、可撤销的程序性经验 |
| 支撑创新 1 | Evaluator-guided Active Compilation | 生成、测试、修复和质量判定形成有限循环 |
| 支撑创新 2 | TrialDocBench and Replay Harness | 量化每个技术模块对正确性、效率和接受率的贡献 |

多 Agent、RAG、飞书 Aily、ANN 和大语言模型是实现这些模块的技术手段，本身不作为主要原创点。

## 3. Clinical Semantic Element

### 3.1 已有方法的启发

Cortex 将可复用交互表示为 Semantic Element，并记录语义键、缓存值、静态性、使用频率、重新获取成本、内容大小和外部调用延迟。TrialCompiler 保留这种“结构化语义单元”思想，但不把一个高相似度缓存直接当成临床知识。

### 3.2 TrialCompiler 的扩展

每条临床知识除语义键和值外，还必须包含：

```text
document_type       适用文档类型
section_type        适用章节
jurisdiction        适用地区
therapeutic_area    治疗领域
authority           权威来源类型
source_ids          原始证据
version             来源版本
valid_from          生效时间
valid_until         失效时间
approval_status     人工审批状态
access_scope        权限范围
supersedes          替代关系
```

`element_type` 必须显式区分 `project_fact`、`rule_constraint` 和 `decision_capsule`：项目事实表示本研究采用的设计，规则约束表示编制和质量要求，经验胶囊表示经过批准的程序性审核经验。三类元素可以建立引用关系，但不能因为文字相似而相互替代。

其中，候选项目事实必须经历 `candidate -> confirmed -> effective` 的人工状态门；只有 `effective` 事实能够驱动正式章节编制和一致性测试。规则约束和经验胶囊分别使用独立的权威、适用范围和审批字段。

示例：

```json
{
  "semantic_key": "主要终点评估时间变化后的处理流程",
  "value": {
    "action": "遍历事实依赖图并重新编译受影响章节"
  },
  "element_type": "decision_capsule",
  "document_type": "protocol",
  "section_type": "any",
  "jurisdiction": "CN",
  "authority": "human_review",
  "approval_status": "approved",
  "source_ids": ["review-2026-001"],
  "valid_until": null
}
```

这种表示使知识可以被验证、撤销、替代、过期和按权限隔离，而不只是被 embedding 检索。

### 3.3 可检验假设

与普通文本块 RAG 相比，Clinical Semantic Element 应当降低：

- 错误地区知识准入率；
- 过期规则引用率；
- 未经批准经验调用率；
- 无法追溯来源的建议比例。

## 4. Governance-aware Coarse-to-Fine Retrieval

### 4.1 检索链路

```text
规范化键精确命中
  -> ANN / BM25 高召回粗筛
  -> 元数据硬门控
  -> 轻量语义等价模型精判
  -> verified hit / miss
```

粗筛只负责尽量不漏掉候选，不能直接构成记忆命中。精判回答的也不是“是否属于同一主题”，而是“旧经验能否在当前任务中直接复用”。

### 4.2 准入函数

候选记忆 `m` 对任务 `q` 的准入条件为：

```text
Admit(m, q)
= SemanticEquivalent(m, q)
  AND ScopeMatch(m, q)
  AND VersionValid(m)
  AND HumanApproved(m)
  AND AccessAllowed(m, q)
```

任何一个硬条件不满足，都必须在进入 Agent 上下文前拒绝。

### 4.3 精判输出

精判器输出结构化结果，而不是自由文本：

```json
{
  "admitted": false,
  "confidence": 0.91,
  "reasons": [
    "same topic but different jurisdiction",
    "source version has been superseded"
  ]
}
```

### 4.4 当前实现与目标实现

| 能力 | 当前 MVP | 后续目标 |
| --- | --- | --- |
| 精确命中 | 规范化键索引 | 保留 |
| 粗筛 | SQLite FTS5 | BM25 + dense ANN hybrid retrieval |
| 元数据门 | 已实现 | 增加租户、角色和文档版本关系 |
| 精判 | 保守确定性接口 | 轻量语义等价二分类器 |
| 检索审计 | 已实现 | 增加候选列表、拒绝原因和模型版本 |

## 5. 成本感知的记忆生命周期

TrialCompiler 不允许记忆无限增长。每条 Semantic Element 的保留效用近似为：

```text
U(m)
= a * log(1 + frequency)
 + b * refetch_cost
 + c * latency
 + d * staticity
 + e * authority
 - f * age
 - g * size
```

其中：

- `frequency`：经过完整语义验证后的真实使用次数；
- `refetch_cost`：重新获得证据或专家意见的成本；
- `latency`：重新调用外部服务或人工审核的等待时间；
- `staticity`：知识在未来保持有效的可能性；
- `authority`：监管、企业、项目、文献或模型生成来源；
- `age`：距最近一次有效使用的时间；
- `size`：存储和上下文占用。

监管知识、企业批准规范和专家批准经验受到额外保护。临时模型输出、低频且可低成本重建的内容优先淘汰。只有通过精判的命中才增加频率，粗筛候选不会虚增热度。

## 6. Human-governed Experience Compiler

### 6.1 为什么不直接保存对话

完整对话和 Agent 轨迹包含大量偶然表达、错误尝试和项目特有信息。直接把它们放进长期记忆，会造成经验污染和上下文膨胀。

### 6.2 Decision Capsule

Experience Compiler 将一次审核轨迹压缩为：

```text
Trigger
Conditions
Recommended Action
Rationale
Evidence
Counterexample
Approval Status
Valid Until
```

系统不会记住实例答案“把 Week 12 改为 Week 16”，而会提取程序性经验：

> 当已批准核心事实发生变化时，遍历事实依赖图，定位全部受影响章节，生成保留证据来源的最小修改，并重新运行一致性测试。

### 6.3 经验写回

```text
完整任务轨迹
  -> F Agent 提取候选经验
  -> 合并重复经验
  -> 补充适用条件和反例
  -> 合格人员批准、修改或拒绝
  -> 生成短 Action Card
  -> 后续任务按条件检索
```

未经批准的候选只能用于离线分析。被拒绝、过期或已被新规则替代的经验不能指导真实任务。

### 6.4 可检验假设

应比较三种条件：

1. 无历史记忆；
2. 直接提供原始历史轨迹；
3. 提供经过批准的 Decision Capsule。

主要指标包括人工一次接受率、修复正确率、上下文 token、错误经验引入率和任务完成时间。

## 7. Dependency-guided Incremental Compilation

### 7.1 Clinical Document Graph

文档图包含：

```text
Fact       项目事实
Section    文档章节
Table      表格和时间表
Evidence   原始证据
Rule       法规与企业约束
Issue      审核问题
Decision   人工决策
```

主要关系包括：

```text
uses
depends_on
supported_by
conflicts_with
generated_from
supersedes
```

### 7.2 修改影响传播

当事实 `f` 发生变化时：

```text
ImpactSet(delta f) = Reachable(DocumentGraph, f)
```

系统只重新解析、检索、编制和测试 `ImpactSet` 中的节点，未受影响章节继续使用已验证构建产物。

### 7.3 缓存失效

稳定章节缓存必须在以下情况失效：

- 所依赖 Canonical Fact 变化；
- 引用法规或企业模板版本变化；
- Prompt、模型或文档测试版本变化；
- 人工推翻上一次决定；
- 权限或有效期变化。

### 7.4 可检验假设

相较整篇重新生成，增量编译应当降低：

- 重新生成章节数量；
- 推理 token 与运行时间；
- 未受影响内容被意外改写的比例；
- 关键事实修改遗漏率。

## 8. Evaluator-guided Active Compilation

### 8.1 主动编译循环

```text
C Agent 生成章节或修订方案
  -> D Agent 独立审核
  -> 执行文档单元测试
  -> 返回结构化缺陷
  -> C Agent 根据缺陷、证据和经验重新编译
```

状态更新可以表示为：

```text
x(t+1)
= Repair(
    x(t),
    Defects(x(t)),
    Evidence,
    ApprovedExperience
  )
```

### 8.2 停止与升级条件

工作流在以下任一条件满足时停止：

- 全部强制文档测试通过；
- 达到最大修订轮次；
- 发现缺少关键输入；
- 出现必须由医学、统计、法规或伦理人员判断的问题；
- 证据或权限不足。

系统不得为了完成流程而自动猜测关键临床事实。

### 8.3 与普通多 Agent 的区别

技术重点不是 Agent 数量，而是：

- Agent 通过类型化 State 通信；
- 生成和评价角色分离；
- 评价依据来自事实图、证据和测试；
- 每次返工都有结构化原因；
- 循环轮次有限且可回放；
- 高风险结果必须升级人工。

## 9. TrialDocBench and Replay Harness

每次实验表示为一个完整实验元组：

```text
Experiment
= Benchmark
  x Model
  x Prompt
  x Retrieval Configuration
  x Memory Configuration
  x Rule Set
  x Scorer
  x Runtime Environment
```

Harness 保存：

- 输入文档与版本；
- Canonical Facts；
- Gold Finding 与 Gold Impact Set；
- 检索候选及拒绝原因；
- Agent State 和循环轨迹；
- 模型、Prompt、规则与记忆版本；
- 人工接受、编辑和拒绝结果；
- 时间、token、外部调用和缓存命中。

评测任务分为：

| 层级 | 任务 | 主要指标 |
| --- | --- | --- |
| L1 | 事实提取 | Exact Match、字段 F1、来源定位准确率 |
| L2 | 证据检索 | Recall@K、Admission Precision、错误范围准入率 |
| L3 | 缺陷检测 | 缺陷召回率、精确率、严重度一致性 |
| L4 | 影响传播 | Impact Set Recall、遗漏率、冗余重编译比例 |
| L5 | 修订生成 | 事实保持率、最小修改率、人工接受率 |
| L6 | 经验迁移 | 新项目成功率增益、错误经验引入率、token 节省 |

建议消融实验：

```text
通用 LLM
单 Agent
多 Agent
多 Agent + 普通 RAG
多 Agent + Clinical Semantic Element
多 Agent + CSE + Experience Compiler
完整 TrialCompiler
```

## 10. 原创边界

比赛材料中必须清楚区分已有方法与我们的贡献。

| 已有思想 | 不应声称为原创 | TrialCompiler 的贡献 |
| --- | --- | --- |
| Cortex | Semantic Element、ANN 粗筛、轻量模型精判、LCFU | 加入临床范围、权威、审批、有效期和证据治理 |
| 普通 RAG | embedding 检索和 Top-K 上下文 | 检索前后硬门控、语义等价判定和完整拒绝日志 |
| 多 Agent | 角色拆分和循环协作 | 与事实依赖图、文档测试、人工责任门和可回放 State 结合 |
| Agent Memory | 保存历史和自然语言经验 | 把轨迹编译为经人工批准的程序性 Decision Capsule |
| 软件增量构建 | 依赖图和缓存失效 | 应用于跨章节、跨表格和跨文件的临床文档编制 |
| Agent Benchmark | 轨迹记录和自动评分 | 建立临床文档事实、缺陷、传播、修订和经验迁移任务 |

## 11. 当前完成度

已经实现：

- Clinical Document Graph 的基础事实依赖和冲突检查；
- A-F 类型化 LangGraph 状态机；
- C-D 有限修订与质量门；
- Clinical Semantic Element 的 SQLite 存储；
- FTS5 粗筛、元数据门和精判接口；
- 检索日志与 LCFU 风格淘汰；
- Decision Capsule 候选、批准状态与 Action Card；
- 合成案例、CLI、FastAPI 和自动测试。

尚未完成：

- Word/PDF 结构化解析和原文定位；
- Trial Fact Sheet 人工确认界面；
- 分章节文档编制器；
- dense ANN 与轻量语义精判模型；
- 真实专家构造的 TrialDocBench；
- 飞书租户中的 Aily Workflow；
- 生产级身份、权限、审计存档和电子签核。

## 12. 比赛表达

建议用以下一句话概括技术创新：

> TrialCompiler 通过带治理边界的临床语义记忆、粗到细检索、事实依赖图增量编译和评价器驱动的主动修订，将长篇临床文档生产转化为可计算、可验证、可持续学习的工程过程。

技术展示时优先解释四件事：

1. 为什么语义相似不等于临床知识可复用；
2. 一个事实变化后如何计算完整影响范围；
3. 专家审核轨迹如何变成受控经验，而不是直接污染记忆；
4. 如何通过 TrialDocBench 证明每个模块的实际贡献。
