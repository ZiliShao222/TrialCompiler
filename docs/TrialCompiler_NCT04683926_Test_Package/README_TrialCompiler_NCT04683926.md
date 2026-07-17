# TrialCompiler 原型测试案例包

## 1. 主案例

本案例选用 **ClinicalTrials.gov NCT04683926 / OMNI-PAIN-103**：一项在健康志愿者中评价 desmetramadol 剂量比例性和食物效应的 Phase 1、随机、开放、四治疗四周期四序列交叉研究。

该案例适合作为 TrialCompiler 的首个端到端验证对象，原因包括：Protocol、独立 SAP、IRB 批准 ICF 和结果记录均公开；核心事实高度结构化；同时存在自然形成的单文档与跨文档差异，可以测试事实抽取、来源追溯、冲突识别、双时间轴映射、变更影响分析和人工确认门。

## 2. 推荐执行顺序

第一轮只导入 Protocol，验证标题层级、Synopsis、入排标准、给药序列、PK 采样时间、Schedule of Procedures 和统计章节的解析。目标输出为 Trial Fact Sheet、来源证据表和单文档缺陷清单。

第二轮加入 SAP、ICF、ClinicalTrials.gov 注册记录和结果记录，验证计划事实、实际结果事实、受试者语言和统计分析定义之间的跨文档关系。重点检查 11 天与约 12 天、筛选 30 天与最多 31 天、Protocol 连续日模型与 CRF period/day 模型、evaluable 与 PP 人群术语映射。

第三轮导入完全合成的变更请求，将最终 PK 采样时间从 32 h 改为 36 h。系统应定位 Protocol Synopsis、研究流程、SoA、SAP、ICF、合成 CRF 和结果 time frame，并生成影响矩阵、候选红线和重检任务。该变更不代表真实试验修订。

## 3. 包内文件

- `TrialCompiler_NCT04683926_Test_Package.xlsx`：候选比较、来源清单、Trial Fact Sheet、依赖图、测试用例、合成 CRF 字段映射和评价表。
- `source_manifest.csv`：公开资料的正式 URL、版本和用途。
- `download_public_sources.py`：在可联网环境中下载公开 Protocol、SAP 和 ICF。
- `ground_truth_tests.json`：机器可读的测试金标准。
- `Synthetic_Amendment_PK32h_to_36h.md`：完全合成的变更请求。

## 4. 关键自然测试点

### 单文档

Protocol Synopsis 对给药前后 1 小时的饮水要求写为 “No water allowed”，正文流程写为仅允许水或饮食限制为 water only。系统应将其识别为操作指令冲突，并阻断该事实进入已确认状态。

Protocol 对处理间隔同时出现 `>3 days` 和 `3 days`，给药日为 Day 1、4、7、10。该项适合测试数值边界、自然语言和结构化日程的联合判断。

### 跨文档

Protocol 和 SAP 表述受试者在研究中 11 天，ICF 表述住院约 12 天；Protocol 筛选窗口为不超过 30 天，ICF 表述最多 31 天。系统应提供证据并交由临床运营和伦理角色判断，不宜自动选值。

SAP 明确说明 Protocol 使用连续日序列，而 CRF 使用四个独立 period、每次给药记录为该 period 的 Day 1。系统需要建立可解释映射，不应将其简单归类为错误。

Protocol 使用 evaluable population 进行剂量比例性和食物效应分析，SAP 的主要描述人群为 Safety 和 PP。系统应建立定义矩阵并标记待统计确认。

## 5. 数据与合规边界

本包只使用公开研究级资料和完全合成测试资产，不包含患者级数据。公开文件中的个人联系方式不应进入原型的结构化事实层。任何候选冲突、医学判断、统计定义或伦理表述均需授权人员确认后才能成为有效事实。
