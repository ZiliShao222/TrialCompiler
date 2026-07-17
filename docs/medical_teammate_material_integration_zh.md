# 医学同学资料包整合摘要

## 简短结论

医学同学提交的资料包非常贴合 TrialCompiler 的核心定位。它不是单纯补了若干法规链接，而是从临床试验方案的真实业务流程、关键设计事实、关联文件体系、角色责任、传统变更流程和痛点来源六个方面，强化了我们“临床文档工程化”的论证。

它对当前方案最重要的补强有三点：

1. **把 Trial Fact Sheet 的必要性讲得更真实**：关键设计事实不是文档里的一句话，而是经医学、统计、注册、运营等角色确认后，会传播到 Protocol、Synopsis、SoA、ICF、SAP、CRF/eCRF、IWRS/IRT 等文件和系统的设计决策。
2. **把 Document Graph 的节点补完整**：原本我们主要强调 Protocol/SAP/ICF/Registry，现在医学资料明确把 CRF/eCRF、IWRS/IRT、药物手册、实验室手册、影像手册等执行文件纳入依赖网络。
3. **把变更影响分析的业务价值讲得更强**：资料中以“主要终点评估时间从 Week 12 改为 Week 16”为例，说明单项事实变更会影响方案摘要、终点章节、SoA、SAP、CRF、患者材料、注册材料和数据核查规则。

## 已纳入仓库的整理结果

原始交付物位于：

- `docs/附件_药物临床试验方案设计流程与协同管理痛点分析_排版修订版.docx`
- `docs/医学知识库权威资料包_20260717.zip`
- `docs/医学知识库权威资料包_20260717/`

为了便于后续处理，已规范化整理到：

- `references/inbox/medical_teammate/`
- `references/metadata/medical_teammate_source_index.tsv`
- `references/metadata/medical_teammate_download_status.csv`

当前医学资料包索引共 46 条：

- 已在资料包中存在：27 条；
- 本次补下载成功：13 条；
- 官方站点阻挡自动下载、已保留占位与链接：6 条；
- 本地索引缺失：0 条。

## 对 TrialCompiler 模块的影响

### 1. Trial Fact Sheet

医学资料明确指出，关键设计事实应包含：

- 研究目的与终点；
- 目标样本量与统计假设；
- 研究人群、入组标准、排除标准、分层因素；
- 对照组选择、随机化、盲法；
- 治疗方案、剂量、给药周期、给药方式；
- 访视安排、时间窗、采集项目；
- 安全性评估、停药规则、终止标准；
- 分析集、缺失值处理、敏感性分析；
- 方案修订原因、版本状态和责任角色。

这些内容已经和 `references/metadata/trial_fact_field_dictionary.tsv` 中的字段基本对应。后续可新增/细化：

- `control_group_design`：对照组类型与选择依据；
- `stratification_factors`：随机化分层因素；
- `data_collection_fields`：CRF/eCRF 采集字段；
- `IWRS_IRT_configuration`：随机、分层、药物供应配置；
- `stopping_rules`：停药、暂停、终止标准；
- `protocol_deviation_rules`：方案偏离分类和处理规则。

### 2. Clinical Document Graph

医学资料把关联文件体系分为核心文件、执行文件和监管/质量文件，提示我们的 Document Graph 不应只停留在方案正文层。

应纳入或预留的节点包括：

- Protocol；
- Synopsis；
- SoA；
- ICF；
- SAP；
- CRF/eCRF；
- IWRS/IRT；
- EDC edit checks；
- 药物手册；
- 实验室手册；
- 影像手册；
- 注册/监管提交材料；
- 版本历史和培训材料。

这些节点可以逐步加入 `references/metadata/document_unit_catalog.tsv`。

### 3. Document Unit Tests

医学资料补强了我们对“一致性”的分层：

1. **数值一致**：同一名称、数值、单位和版本在重复引用处一致。
2. **语义一致**：不同表达指向同一设计含义，例如 Week 12、第 84 天、治疗后 12 周。
3. **统计一致**：终点、分析人群、时间点和统计方法互相匹配。
4. **执行一致**：访视表、采集字段、系统配置和现场操作能执行同一事实。

这四层可以直接对应到 `document_unit_test_catalog.tsv`：

- deterministic tests：数字、时间点、样本量、旧值残留；
- hybrid tests：SoA/正文/SAP/ICF 表达对齐；
- semantic tests：终点定义、估计目标、统计原则、角色责任和适用范围；
- execution-facing tests：CRF/eCRF、IRT/IWRS、EDC edit check 与 Protocol 的一致性。

### 4. Change Impact Analysis

医学资料中的 Week 12 -> Week 16 示例应作为 TrialCompiler 的核心演示案例。

建议演示链条：

```text
主要终点评估时间从 Week 12 改为 Week 16
        ↓
建立候选事实新版本
        ↓
定位 Protocol Synopsis / Objectives / SoA / SAP / CRF / ICF / Registry
        ↓
扫描旧值残留：Week 12 / 第 84 天 / 治疗后 12 周
        ↓
生成影响矩阵
        ↓
生成候选修订文本和红线稿
        ↓
医学、统计、注册、运营、质量角色确认
        ↓
形成正式版本和审计记录
```

这一示例比抽象描述更适合比赛展示。

### 5. Experience Reuse

医学资料指出，历史审查意见通常散落在 Word 批注、邮件、会议纪要、问题清单、QC 记录和 CAPA 记录中。它们包含非常有价值的审查经验，但不能直接粗暴复用。

这正好支持我们之前设计的经验记忆层：

- 必须记录来源；
- 必须记录适用范围；
- 必须记录版本和批准状态；
- 必须区分企业通用规则、治疗领域规则、阶段规则、项目专属意见和参考案例；
- 未经确认的历史意见只能作为候选提示，不能成为强规则。

## 对方案文本的建议修改

后续修改比赛文档时，应把重点从“AI 帮忙写方案”改得更明确：

> TrialCompiler 不是一个普通医学写作助手，而是围绕“关键设计事实”建立临床文档工程体系。它将经专业人员确认的研究设计事实传播到方案正文、摘要、访视表、知情同意书、统计分析计划、采集表和执行系统配置中，并通过文档单元测试和变更影响分析减少人工交叉审核中的遗漏。

## 后续动作

1. 将医学资料中的 CRF/eCRF、IWRS/IRT、药物手册、实验室手册等节点补入 Document Unit Catalog。
2. 将 M2 试验设计与统计资料映射到更多 Trial Fact 字段，例如对照组、随机化分层、协变量、富集策略、去中心化元素、方案偏离、贝叶斯设计。
3. 将 M3 AI 治理和方案变更资料用于完善“人工确认”和“AI 不能替代正式判断”的边界。
4. 将 M4 模板与工具用于构造完全合成的 protocol/SAP/ICF/SoA benchmark。
5. 更新比赛三份核心文档，让医学资料中的业务流程和角色责任进入方案叙事。
