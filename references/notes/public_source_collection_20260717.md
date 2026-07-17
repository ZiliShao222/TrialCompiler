# TrialCompiler 公开资料收集记录（2026-07-17）

## 1. 收集边界

本轮资料收集只使用公开、可访问、可核验的网页、PDF、模板、指南、论文和产品资料。当前阶段不采集真实临床项目文件、真实患者数据、企业内部 SOP、内部批注、邮件或会议纪要。

资料用途不是直接生成临床判断，而是为 TrialCompiler 的比赛方案提供三类支撑：

1. 证明临床试验方案及其关联文件存在结构化、标准化、跨文件一致性和变更传播需求。
2. 证明方案修订、终点变更、样本量变更、访视安排变更和入排标准变更会带来真实的多章节、多文件同步问题。
3. 证明现有工具多集中在模板、医学写作、eClinical 平台、eTMF、数据采集或生成式写作，而 TrialCompiler 的差异化在于“事实层 + 文档依赖图 + 文档单元测试 + 变更影响分析 + 人工确认”。

## 2. 当前数量

主索引为 `references/metadata/public_source_index.tsv`。截至本次更新，共收集 169 条公开来源；医学同学提交的补充资料包另有 46 条索引，记录在 `references/metadata/medical_teammate_source_index.tsv`。

| 类别 | 数量 | 主要用途 |
| --- | ---: | --- |
| medical | 23 | ICH、FDA、EMA、SPIRIT、CONSORT、GCP、统计原则、终点与方案修订证据 |
| standards | 17 | TransCelerate、CDISC、NIH、MRCT、DDF/USDM、平台试验模板与结构化内容复用 |
| associated_documents | 26 | SAP、ICF、ClinicalTrials.gov 字段、CSR、Protocol Template、CRF/eCRF、SoA、Clinical Content Reuse 等关联文件 |
| business | 43 | 竞品、替代方案、医学写作自动化、eClinical/eTMF/AI 工具、上游方案优化平台 |
| burden | 15 | 方案写作、修订、复杂度、amendment 和返工成本证据 |
| ai_protocol_authoring | 8 | LLM/RAG/Agent 在 clinical protocol authoring 或 consistency checking 中的公开参考 |
| ai_governance | 5 | 医药 AI 治理、人类监督、透明性、风险与责任边界 |
| china_regulatory | 6 | NMPA/CDE 中文 GCP、方案变更、SAP/统计分析公开资料 |
| feishu | 10 | 飞书 Aily、Workflow、Base、Wiki、自动化和企业协同落地资料 |
| regulatory_constraints | 6 | informed consent、E17、多地区设计、伦理边界等约束资料 |
| schedule_of_activities | 10 | SPIRIT/SoA/participant timeline/访视流程表相关模板和论文 |

本轮后续补充了 20 条竞品/相邻平台/标准基础设施来源，覆盖 HumanTrue、Cori Clinical、Clinials、太美医疗、Veeva AI for Clinical Operations、Evinova Study Document Assistant、IQVIA Protocol Design Optimization、Medidata Protocol Optimization、CDISC DDF/USDM 与 TransCelerate Clinical Content Reuse。它们主要用于支撑 `docs/competitor_analysis_integration_zh.md`、`references/metadata/competitor_capability_matrix.tsv` 与 TrialDocBench 评测设计，避免竞品判断只依赖队友整理的二手描述。

医学资料包索引共 46 条，分为四组：

| 医学资料模块 | 主要用途 |
| --- | --- |
| M1 法规伦理与报告规范 | 约束 TrialCompiler 的人类审核边界、审计要求和合规表述 |
| M2 试验设计与统计 | 支撑 Trial Fact Sheet 字段、统计事实和关键设计事实定义 |
| M3 协议审查与 AI 治理 | 支撑 Agent 输出的可解释、可追踪、人类确认和风险控制 |
| M4 模板与工具 | 支撑 Document Graph 的章节、表格、关联文件和执行系统节点 |

所有索引中的 `local_path` 都有本地文件或占位文件；访问受限的官方来源保留官方链接和占位 HTML，不使用非授权全文。

## 3. 新增结构化资产

本轮不只保存资料，还把资料加工成后续可直接使用的结构化表。

当前 `references/metadata/source_to_module_map.tsv` 已包含 76 条来源到系统模块的映射，覆盖 Trial Fact Sheet、Clinical Document Graph、Document Unit Tests、Change Impact Analysis、Competitor Analysis、Standards Alignment、China Market Fit、Feishu Integration 和 TrialDocBench 等模块。

### 3.1 Trial Fact Sheet 字段字典

文件：`references/metadata/trial_fact_field_dictionary.tsv`

作用：

- 把临床方案中的关键设计事实拆成可管理字段；
- 记录字段类型、数据类型、常见来源、受影响文档单元、风险等级、确认角色和支持来源；
- 支撑后续事实提取、人工确认、版本管理和变更影响分析。

示例字段：

- 主要终点；
- 次要终点；
- 终点评估时间；
- 目标样本量；
- 入组与排除标准；
- 给药方案；
- 访视安排；
- 安全性评估；
- 估计目标；
- 分析人群；
- 主要统计方法；
- 注册终点字段；
- 来源证据位置；
- 审核状态；
- 适用范围。

### 3.2 文档单元目录

文件：`references/metadata/document_unit_catalog.tsv`

作用：

- 把方案正文、SAP、ICF、ClinicalTrials.gov 注册字段、CSR 和 TrialCompiler 生成的审核产物拆成文档单元；
- 标明每个文档单元依赖哪些事实字段；
- 标明常见一致性检查；
- 为 Clinical Document Graph 提供初始节点目录。

典型单元：

- Protocol Synopsis；
- Objectives and Endpoints；
- Eligibility Criteria；
- Schedule of Activities；
- Statistical Analysis；
- SAP Endpoints；
- SAP Analysis Sets；
- ICF Procedures；
- ICF Risks and Benefits；
- Registry Outcomes；
- CSR Protocol Summary；
- Change Impact Matrix；
- Document Unit Test Report。

### 3.3 文档单元测试目录

文件：`references/metadata/document_unit_test_catalog.tsv`

作用：

- 把“文档一致性审核”拆成可实现的测试；
- 区分确定性检查、语义检查和混合检查；
- 为后续 Demo、benchmark 和 MVP 提供 test case 设计基础。

示例测试：

- 主要终点精确一致性；
- 终点评估时间一致性；
- 样本量跨文件一致性；
- 入排标准阈值一致性；
- 治疗组名称一致性；
- 剂量、途径、频率一致性；
- 访视表与正文一致性；
- 不良事件窗口一致性；
- 估计目标与终点、人群连接；
- 旧版本残留扫描；
- 未确认事实阻断；
- 变更影响矩阵完整性。

### 3.4 来源到模块映射

文件：`references/metadata/source_to_module_map.tsv`

作用：

- 说明每个高价值来源服务于哪个 TrialCompiler 模块；
- 防止资料成为“资料堆”，而是变成模块设计、竞品分析、规则抽取和 benchmark 构造的依据。

### 3.5 竞品能力矩阵

文件：`references/metadata/competitor_capability_matrix.tsv`

作用：

- 只基于官方页面或公开论文记录竞品/基线能力；
- 区分行业模板、医学写作 AI、eClinical 平台、eTMF、注册披露、研究原型等不同类型；
- 说明 TrialCompiler 与它们的差异：不是只生成文字，而是围绕确认事实、依赖图、单元测试、变更传播和人工批准构建文档工程闭环。

## 4. 对 TrialCompiler 的直接支撑

### 4.1 结构化方案不是凭空设想

ICH M11、CDISC PRM、TransCelerate、NIH/FDA protocol template 等来源共同说明：临床试验方案已经具有可结构化、可复用、可交换的行业趋势。TrialCompiler 的 Trial Fact Sheet 可以被解释为这一趋势下的比赛级产品化实现。

### 4.2 跨文件一致性是核心痛点

SPIRIT、ClinicalTrials.gov 字段定义、SAP 模板、ICF 模板和 CSR 指南共同说明：同一组关键设计事实会在方案正文、摘要、访视表、SAP、ICF、注册平台和 CSR 中重复出现。TrialCompiler 的文档依赖图正是为这些重复事实建立可追踪连接。

### 4.3 变更影响分析有现实依据

endpoint change、protocol amendment、protocol complexity 和 site performance 相关论文/行业资料说明：方案修订会带来成本、返工、延迟和执行风险。TrialCompiler 的 `Week 12 -> Week 16` 示例不是虚构痛点，而是典型变更传播问题的简化演示。

### 4.4 AI 不能替代专业判断

EMA、FDA、WHO 等 AI 治理资料，以及临床试验 LLM 综述共同支持一个边界：AI 可以做候选事实提取、风险提示、语义一致性检查和候选文本生成，但关键事实确认、医学合理性、统计合理性、注册策略和正式批准必须由授权专业人员完成。

### 4.5 竞品差异要讲清楚

现有产品覆盖医学写作、CSR 自动化、eClinical、eTMF、注册披露、临床数据平台和模板复用。TrialCompiler 的故事不应是“我们也能写方案”，而应是：

> 把临床试验方案及其关联文件转化为可编译、可测试、可追踪、可增量更新的文档工程体系。

## 5. 后续缺口

### 5.1 仍需人工继续补的资料

这些任务适合没有代码基础的队友：

1. 找更多公开 SAP 模板和 SAP 写作指南；
2. 找更多公开 ICF 模板和 ICF 写作/伦理审核指南；
3. 找更多 protocol synopsis、Schedule of Activities、方案摘要模板；
4. 找更多 CDE/NMPA 中文监管公开资料，尤其是方案变更、统计分析计划、数据管理、伦理和安全性；
5. 找更多真实但公开的空白模板，不要找真实患者或企业内部资料；
6. 找更多竞品官网页面，只记录其官方声称能力，不自行夸大。

### 5.2 由 AI 成员处理的工作

这些任务需要由我们来做：

1. 从 PDF/HTML/Word 模板中抽取章节、字段和表格结构；
2. 将来源切成可引用 chunk，形成 `source_id -> text_chunk -> citation`；
3. 将 Trial Fact Sheet 字段和文档单元进一步转成 JSON Schema；
4. 构造完全合成的 protocol conflict benchmark；
5. 把竞品矩阵转化为 proposal 中可展示的对比图；
6. 把文档单元测试目录转化为 MVP 中可运行的规则/LLM checker。

## 6. 比赛叙事价值

这批资料能支撑我们的三层叙事：

1. **行业正在结构化**：ICH M11、CDISC PRM、TransCelerate、NIH/FDA 模板证明临床方案不是普通文章，而是可以结构化和标准化的工程对象。
2. **结构化还不够**：模板和平台不能自动保证跨章节、跨表格、跨文件、跨版本一致。
3. **TrialCompiler 的创新点**：把确认事实、依赖图、文档单元测试、变更影响分析、红线建议、人工审核和经验复用连成闭环。

## 7. 当前注意事项

- `public_source_index.tsv` 是主索引；早期的 `public_source_index.csv` 保留但不作为主索引。
- 本地快照只用于比赛调研和引用整理；正式展示时仍应优先引用官方 URL。
- 访问受限来源不能用非授权全文替代，只能保留 metadata 或官方 landing page。
- 当前资料库不包含真实临床项目、患者数据或企业内部资料。
