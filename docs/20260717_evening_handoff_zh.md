# 2026-07-17 晚间交接清单

## 1. 当前已经完成

### 1.1 医学资料归档

- 已接收医学同学提交的资料包和 Word 附件。
- 已建立医学资料索引：
  - `references/metadata/medical_teammate_source_index.tsv`
  - `references/metadata/medical_teammate_download_status.csv`
- 已将医学资料映射到 TrialCompiler 系统模块：
  - `docs/medical_source_to_system_mapping_zh.md`
  - `docs/medical_teammate_material_integration_zh.md`

### 1.2 公开资料库

- 当前公开来源索引：169 条。
- 医学资料包索引：46 条。
- 已补充 IQVIA、Medidata、CDISC DDF/USDM、TransCelerate Clinical Content Reuse / DDF 等来源。
- 当前资料边界仍是公开来源，不使用真实企业项目文件、真实患者数据或未授权资料。

### 1.3 竞品分析整合

- 已新增：
  - `docs/competitor_analysis_integration_zh.md`
  - `references/notes/competitor_public_evidence_notes_20260717.md`
  - `references/metadata/competitor_capability_matrix.tsv`
- 核心口径已收敛：
  - 不再说竞品没有协议结构化、来源追踪或跨文件一致性；
  - TrialCompiler 的差异点是确认事实层、临床文档依赖图、文档单元测试、变更影响闭环、中国药企协作适配、专家经验治理和可复现 benchmark。

### 1.4 TrialDocBench 初步建立

- 已建立指标目录：
  - `references/metadata/trialdocbench_metric_catalog.tsv`
- 已建立合成案例包设计说明：
  - `docs/trialdocbench_synthetic_case_design_zh.md`
- 已建立机器可读 schema：
  - `references/metadata/trialdocbench_synthetic_case_schema.tsv`
- 已建立第一个最小 synthetic case：
  - `benchmarks/trialdocbench/synthetic_case_001_week12_to_week16/`

第一个 case 覆盖：

- Trial Fact Sheet gold；
- 文档片段；
- 文档依赖图；
- 注入缺陷；
- `Week 12 -> Week 16` 变更请求；
- expected impact matrix；
- evaluation notes。

## 2. 明天优先任务

### 2.1 医学同学

请医学同学只做人工复核，不需要写代码：

1. 复核 `Trial Fact Sheet` 字段是否符合临床试验方案常识；
2. 复核 `Week 12 -> Week 16` synthetic case 是否像真实临床文档；
3. 标注哪些影响点必须由医学、统计、注册或运营角色人工判断；
4. 检查当前“文档单元测试”四层分类是否合理：
   - 数字一致性；
   - 语义一致性；
   - 统计一致性；
   - 执行一致性。

### 2.2 商业/竞品同学

请商业同学做人工打开网页核验：

1. HumanTrue、Cori Clinical、Clinials 是否真的公开声明 protocol structure、revision impact、cross-document coherence 或 source traceability；
2. IQVIA 和 Medidata 是否应放在上游方案设计优化，而不是直接文档编译；
3. Veeva、太美医疗是否应作为受控文档/临床运营平台，而不是直接替代；
4. 输出一张“竞品公开能力核验表”，不要写竞品没有公开披露的能力。

### 2.3 代码/AI 侧

下一步由 AI 侧完成：

1. 把 `Week 12 -> Week 16` synthetic case 接入现有 MVP workflow；
2. 输出系统检测到的缺陷、影响矩阵和候选红线；
3. 与 baseline 对比：
   - 通用 LLM 直接审阅；
   - RAG + LLM；
   - 单 Agent 审核；
   - TrialCompiler 去掉事实门控；
   - TrialCompiler 去掉依赖图；
   - TrialCompiler 完整版本。
4. 扩展到 3-5 个 synthetic cases；
5. 准备一张答辩图：
   - Public Sources；
   - Trial Fact Sheet；
   - Clinical Document Graph；
   - Document Unit Tests；
   - Change Impact Matrix；
   - Human Review Gate；
   - Experience Library。

## 3. 当前不应做

- 不要采集真实患者病历；
- 不要采集真实企业内部方案、SOP、邮件或批注；
- 不要声称已经在健康元真实流程中验证；
- 不要声称节省了真实工时；
- 不要把 AI 输出当成医学、统计、注册或伦理决策；
- 不要把竞品未公开披露的信息写成确定事实。

## 4. 当前可用于答辩的一句话

TrialCompiler 不是一个简单的临床方案写作助手，而是把临床试验方案及其关联文件转化为可编译、可测试、可追踪、可增量更新的文档工程体系：用经人工确认的 Trial Fact Sheet 管理关键设计事实，用 Clinical Document Graph 追踪事实在章节、表格和关联文件中的依赖，用 Document Unit Tests 发现跨文件冲突，用 Change Impact Matrix 支撑安全修订，并把专家审核经验沉淀为可治理、可复用的组织知识。
