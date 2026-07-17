# 公开资料缺口与下一步复核清单

## 当前资料状态

截至 2026-07-17 晚，本仓库已经形成两套资料索引：

1. `references/metadata/public_source_index.tsv`：169 条公开来源。
2. `references/metadata/medical_teammate_source_index.tsv`：医学同学资料包 46 条来源索引。

这些资料已经覆盖：

- 临床试验方案模板与结构化协议；
- ICH、FDA、EMA、NMPA/CDE 等法规与指南；
- SAP、ICF、SoA、CSR、ClinicalTrials.gov 等关联文件；
- AI protocol authoring / RAG / LLM consistency checking；
- 飞书 Aily、Workflow、Base、Wiki 等协作入口资料；
- HumanTrue、Cori Clinical、Clinials、Veeva、太美医疗、Evinova、IQVIA、Medidata 等竞品或相邻产品；
- CDISC DDF/USDM 与 TransCelerate Clinical Content Reuse / DDF 等结构化协议和内容复用方向；
- Trial Fact Sheet 字段字典、Document Graph 文档单元、Document Unit Test 测试目录和 TrialDocBench 指标目录。

## 已经比较稳的结论

### 1. 问题场景足够真实

公开模板、法规和医学同学资料均支持这一判断：临床试验方案不是单个文本文件，而是会驱动 Synopsis、SoA、ICF、SAP、CRF/eCRF、IWRS/IRT、实验室/影像/药物手册和注册材料的核心设计文件。

### 2. 关键事实适合结构化

主要终点、评估时间、样本量、入排标准、对照组、访视安排、统计原则和安全性规则等信息高度重复，适合抽象为 Trial Fact Sheet。

### 3. 变更影响分析适合作为 Demo 主线

`Week 12 -> Week 16` 是清晰、可理解、可构造合成数据的核心案例。它可以展示：

- 事实变更；
- 影响位置定位；
- 旧值残留扫描；
- SoA/SAP/ICF/CRF/eCRF/IWRS 传播；
- 候选红线；
- 审计证据；
- 人工确认。

### 4. 竞品分析需要诚实表述

HumanTrue、Cori Clinical 等公开资料说明，协议结构化、质量检查、来源追踪和修订协同已经有直接竞品。TrialCompiler 的差异不应写成“别人没有跨文档一致性”，而应写成：

- 已确认事实层；
- 文档依赖图；
- 文档单元测试；
- 变更任务闭环；
- 中国药企协作环境适配；
- 规则与历史经验资产化；
- 与 Word/DMS/eTMF/EDC/飞书的开放接口。

## 主要缺口

### 缺口 1：直接竞品公开能力仍需人工逐项核验

自动抓取能保存官网页面，但动态网站中很多内容需要人工打开确认。尤其需要复核：

- HumanTrue 是否公开说明依赖关系、再验证、协议完整性等具体能力；
- Cori REVIEW 页面是否明确说明 cross-document coherence、review synchronization 或类似能力；
- Clinials 是否公开说明 protocol intelligence 的具体输入/输出；
- Evinova Study Document Assistant 是否与协议编制或研究文档一致性直接相关。

输出建议：形成一张“竞品公开能力核验表”。

### 缺口 2：IQVIA 与 Medidata 已补产品页，但仍需人工判断竞争边界

已经补入以下产品级公开来源：

- IQVIA Protocol Design Optimization；
- Medidata Protocol Optimization；
- Medidata Clinical Trial Analytics / Study Feasibility。

下一步不是继续堆链接，而是人工判断它们在竞品图中的位置：它们更偏上游方案设计优化和可行性评估，不应被写成直接临床文档编译器。输出建议：补一列“与 TrialCompiler 的直接竞争程度”和一列“可合作/可集成位置”。

### 缺口 3：CRF/eCRF 与 IWRS/IRT 的公开模板和例子还可以更细

医学资料已经指出 CRF/eCRF 和 IWRS/IRT 很重要，但公开来源中这些执行侧文件的模板和字段例子还可以继续补。

建议搜索方向：

- CRF/eCRF design guideline；
- EDC edit check specification；
- IWRS IRT randomization trial supply configuration；
- protocol to CRF mapping；
- schedule of activities to EDC fields。

输出建议：补充 5-10 条公开资料即可，不需要过度收集。

### 缺口 4：TrialDocBench 已建立 schema 和首个样例，下一步需要扩展与人工复核

目前已经建立：

- `references/metadata/trialdocbench_metric_catalog.tsv`；
- `docs/trialdocbench_synthetic_case_design_zh.md`；
- `references/metadata/trialdocbench_synthetic_case_schema.tsv`。
- `benchmarks/trialdocbench/synthetic_case_001_week12_to_week16/`。

下一步应在首个 `Week 12 -> Week 16` 样例基础上扩展到 3-5 个高质量 synthetic trial package。每个样例包含 Trial Fact Sheet、document units、document graph、injected defects、change requests 和 expected impact matrix。医学同学只需要确认样本逻辑是否符合临床文档常识。

### 缺口 5：飞书落地边界需要确认

需要明确：

- 飞书 Aily 负责自然语言入口和任务编排；
- 飞书多维表格可否承载 Trial Fact Sheet 的人工确认；
- 飞书审批是否适合做人类确认门；
- 正式 Word/DMS/eTMF 文档是否仍作为正式发布路径；
- 哪些能力必须放在后端。

输出建议：形成“飞书可做 / 后端实现 / 暂不做”三列表。

## 未来 24 小时建议

1. 医学同学复核 Trial Fact Sheet 字段和 Document Graph 节点。
2. 商业/竞品同学人工打开直接竞品页面，完成能力核验表。
3. 代码侧扩展 TrialDocBench synthetic package 到 3-5 个样例。
4. 医学同学复核第一个 `Week 12 -> Week 16` 样例的临床文档常识，并标注哪些影响点必须由医学、统计、注册或运营角色人工判断。
5. 产品侧画一张架构图：Feishu Aily -> Trial Fact Sheet -> Clinical Document Graph -> Unit Tests -> Change Impact Matrix -> Human Review Gate -> Experience Library。

## 当前不应做的事

- 不采集真实临床项目文件；
- 不让队员访谈真实企业员工；
- 不处理患者病历；
- 不声明已在健康元内部流程中验证；
- 不声明节省了真实工时；
- 不把竞品没有公开披露的能力写成“竞品没有”；
- 不让 AI 自动决定医学、统计、注册或伦理问题。
