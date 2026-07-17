# TrialDocBench 合成案例包设计

- 版本：v0.1
- 日期：2026-07-17
- 适用范围：AI 先锋未来人才大赛原型评测、答辩展示、后续 benchmark 构建
- 数据边界：只使用公开法规、公开模板、公开产品说明和人工合成文本；不使用真实企业项目文件、真实患者数据或未授权临床试验资料。

## 1. 为什么需要合成案例包

TrialCompiler 要证明的不是“模型能写出一段通顺文字”，而是系统能否管理临床试验方案及其关联文件中的关键设计事实，并在事实变化时发现冲突、定位影响、生成修订建议和保留审计证据。

真实药企方案、Word 批注、会议纪要和历史审核意见通常涉及企业机密，当前阶段不能直接采集。因此我们需要构建一套 **公开来源驱动的合成案例包**：

1. 用公开指南和模板确定文档结构；
2. 用人工设定的 Trial Fact Sheet 作为标准答案；
3. 生成一组相互关联的方案章节、表格和关联文件片段；
4. 人工注入已知缺陷；
5. 用系统和 baseline 模型分别检测、修复和解释；
6. 用可复现指标评估效果。

这套合成案例包既能规避数据合规风险，又能把 TrialCompiler 的核心价值变成可测试任务。

## 2. 一个案例包包含什么

每个案例包建议对应一个虚构但合理的临床研究项目，例如“某药物治疗某适应症的 II 期随机对照试验”。案例包不需要完整数百页文档，但必须覆盖关键事实在多个文档单元之间重复出现的情况。

```text
synthetic_case_001/
├── case_profile.yaml
├── trial_fact_sheet_gold.tsv
├── document_units/
│   ├── protocol_synopsis.md
│   ├── objectives_and_endpoints.md
│   ├── population_criteria.md
│   ├── schedule_of_activities.md
│   ├── statistical_principles.md
│   ├── informed_consent_summary.md
│   └── sap_excerpt.md
├── document_graph_gold.tsv
├── injected_defects.tsv
├── change_requests.tsv
├── expected_impact_matrix.tsv
└── evaluation_notes.md
```

## 3. 核心文件定义

### 3.1 `case_profile.yaml`

记录案例背景和边界：

| 字段 | 含义 |
| --- | --- |
| `case_id` | 稳定案例编号 |
| `therapeutic_area` | 治疗领域，例如 oncology、respiratory、metabolic |
| `trial_phase` | I / II / III / IV |
| `study_design` | 随机、双盲、开放标签、单臂等 |
| `document_scope` | 本案例包含哪些文档单元 |
| `public_source_basis` | 主要参考的公开指南或模板 ID |
| `risk_level` | low / medium / high，用于区分案例复杂度 |

### 3.2 `trial_fact_sheet_gold.tsv`

这是案例包的标准事实表，也是 TrialCompiler 的核心答案层。每一行是一条经人工确认的设计事实。

| 字段 | 含义 |
| --- | --- |
| `fact_id` | 事实编号，例如 `FACT-ENDPOINT-001` |
| `fact_type` | endpoint、timepoint、sample_size、eligibility、visit、dose、analysis_population |
| `current_value` | 当前有效值 |
| `unit_or_format` | Week、days、n、mg、百分比等 |
| `status` | confirmed、candidate、retired |
| `source_unit` | 该事实首次出现的文档单元 |
| `source_location` | 章节、表格或行号 |
| `owner_role` | medical、statistics、regulatory、operation、quality |
| `version` | 事实版本 |
| `scope` | 适用范围 |

### 3.3 `document_units/`

存放短文档片段。每个片段都应该包含若干事实引用，且不同片段之间存在重复和依赖。

建议首批覆盖：

1. 方案摘要；
2. 研究目的与终点；
3. 研究人群与入排标准；
4. 访视流程表；
5. 统计分析原则；
6. 知情同意书摘要；
7. SAP 片段。

这些片段不需要真实药企格式，但要足够像临床文档，使模型必须处理跨章节一致性。

### 3.4 `document_graph_gold.tsv`

记录事实与文档单元之间的依赖关系。

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 边编号 |
| `fact_id` | 对应 Trial Fact Sheet 事实 |
| `document_unit` | 文档单元 |
| `location` | 章节、表格、行号 |
| `dependency_type` | direct_quote、semantic_dependency、derived_value、downstream_instruction |
| `must_update_on_change` | yes / no |
| `rationale` | 为什么该位置受事实影响 |

### 3.5 `injected_defects.tsv`

人工注入缺陷，作为检测任务的 gold label。

| 缺陷类型 | 示例 |
| --- | --- |
| 数值不一致 | 摘要写样本量 120，统计章节写 100 |
| 时间点冲突 | 终点评估时间在正文为 Week 12，访视表为 Week 16 |
| 旧值残留 | 变更后某章节仍保留旧终点时间 |
| 入排标准冲突 | 纳入标准允许某类患者，排除标准又排除同一类患者 |
| 统计定义不一致 | 主要分析集在方案和 SAP 中命名或定义不一致 |
| 执行文件未同步 | 方案修改了访视时间，但 ICF 或操作说明未更新 |
| 来源缺失 | 关键事实没有可追溯来源 |
| 未确认事实误用 | candidate 状态事实被写入正式候选正文 |

### 3.6 `change_requests.tsv`

用于测试变更影响分析。每条记录模拟一次被授权人员提出的设计事实变更。

| 字段 | 含义 |
| --- | --- |
| `change_id` | 变更编号 |
| `fact_id` | 被修改事实 |
| `old_value` | 旧值 |
| `new_value` | 新值 |
| `requester_role` | medical、statistics、regulatory 等 |
| `reason` | 修改原因 |
| `expected_affected_units` | 预期受影响文档单元 |

典型示例：

```text
主要终点评估时间由 Week 12 改为 Week 16。
系统应定位 protocol synopsis、endpoint section、schedule of activities、statistical principles、SAP excerpt 和 ICF summary 中所有直接引用和语义关联位置。
```

### 3.7 `expected_impact_matrix.tsv`

记录系统应该找到的影响范围和候选修订结果，用于评测 impact recall、impact precision 和 stale value removal。

## 4. 任务设计

TrialDocBench 首批任务可以分成六类：

1. **事实抽取**：从文档片段中抽取候选 Trial Fact Sheet；
2. **事实确认门控**：判断 candidate / retired 事实是否被错误使用；
3. **跨文档一致性检测**：发现已注入的数值、时间点、术语和语义冲突；
4. **变更影响分析**：给定一个事实变化，输出受影响文档单元和理由；
5. **候选修订生成**：生成局部红线或修订建议；
6. **经验复用**：判断历史审核意见是否适用于当前案例。

每类任务都应保留 baseline：

- 通用 LLM 直接回答；
- RAG + LLM；
- 单 Agent 审核；
- TrialCompiler 去掉事实门控；
- TrialCompiler 去掉依赖图；
- TrialCompiler 完整版本。

## 5. 指标对应

本文件与 [`../references/metadata/trialdocbench_metric_catalog.tsv`](../references/metadata/trialdocbench_metric_catalog.tsv) 对应。核心指标包括：

1. 关键事实抽取精确率与召回率；
2. 未确认事实误用率；
3. 跨文档冲突召回率与精确率；
4. 变更影响召回率与精确率；
5. 旧值残留清除率；
6. 候选修订接受率；
7. 证据覆盖率；
8. 经验适用性判断准确率；
9. 人工审核时间节省比例。

## 6. 首批构建建议

第一阶段不追求数量极大，而要保证每个案例有清晰 gold label。建议：

1. 先做 5 个高质量案例包，每个案例包 6-8 个文档单元；
2. 每个案例注入 8-12 个缺陷；
3. 每个案例设置 2-3 条变更请求；
4. 覆盖至少 3 个治疗领域和 2 个试验阶段；
5. 每个缺陷必须能追溯到具体事实、文档位置和预期修复方式。

第二阶段再扩展为 30-50 个案例包，用于统计比较和消融实验。

## 7. 队友目前可以贡献什么

医学成员和商业成员不需要写代码，也不需要手工构造 TSV。当前最有价值的贡献是：

1. 收集公开方案模板、公开指南和公开案例说明；
2. 标记哪些章节最容易出现重复事实；
3. 判断哪些事实必须由医学、统计、注册或运营角色确认；
4. 从竞品材料中整理公开宣称的能力边界；
5. 帮助检查合成案例是否像真实临床文档，而不是普通科普文章。

所有清洗、去重、字段标准化、ID 分配、案例包生成和评测脚本都由 AI 成员负责。
