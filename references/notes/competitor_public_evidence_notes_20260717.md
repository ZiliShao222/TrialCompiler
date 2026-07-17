# 竞品公开证据笔记（2026-07-17）

## 目的

本笔记用于把 `docs/附件_竞品分析.docx` 中的竞品判断与本地公开来源索引连接起来。它不是最终商业尽调，也不代表已经完成全部人工核验；用途是为比赛材料提供可追溯的公开来源入口，并标出需要谨慎表述的地方。

## 已补充到公开来源索引的竞品来源

新增来源 ID：`COMP-001` 至 `COMP-010`，均已写入：

- `references/metadata/public_source_index.tsv`
- `references/metadata/public_source_download_status.csv`
- `references/metadata/source_to_module_map.tsv`

本轮新增后，公开来源主索引共 159 条，其中 business 类 40 条。

## 竞品证据摘要

### HumanTrue

本地来源：

- `COMP-001`：HumanTrue clinical trials quality copilot

可支持的判断：

- HumanTrue 可作为直接协议智能平台类竞品。
- 它的公开页面标题和页面文本围绕 protocol integrity、quality copilot、protocol productivity 等概念展开。
- 因此，在比赛材料中可以谨慎表述为：HumanTrue 已经公开强调协议质量、完整性和协议可操作化方向，说明“协议结构化/质量检查”不是 TrialCompiler 独有命题。

谨慎边界：

- 不应在未逐项核验前声称 HumanTrue 已实现或未实现某个具体功能。
- 我们的差异应表述为“拟在中国药企协作、已确认事实层、企业规则治理和任务闭环上形成差异”，而不是“竞品没有这些能力”。

### Cori Clinical

本地来源：

- `COMP-002`：Cori Clinical AI workspace for clinical trial documents
- `COMP-003`：Cori Clinical ASSIST Word-centered authoring
- `COMP-004`：Cori Clinical REVIEW cross-document coherence（自动下载受阻，保留占位与链接）

可支持的判断：

- Cori Clinical 可作为临床文档 AI 工作台类直接竞品。
- 其公开页面标题显示其定位于 clinical-grade AI 与 study startup/clinical trial documents。
- ASSIST 页面支持我们关注 Word-centered authoring 的产品边界讨论。

谨慎边界：

- `COMP-004` 自动下载失败，需要人工打开官方链接核验后再引用 REVIEW 相关细节。
- 比赛材料中应强调：TrialCompiler 不应试图替代 Word 或正式文档系统，而应把飞书作为任务协作入口，把 Word/DMS/eTMF 作为正式审阅和发布环境。

### Clinials

本地来源：

- `COMP-005`：Clinials protocol intelligence platform
- `COMP-006`：Clinials about protocol intelligence

可支持的判断：

- Clinials 可作为 protocol intelligence / structured authoring 方向竞品。
- 其公开标题强调把 protocol complexity 转化为 clarity。
- 这支持我们把 Clinials 归入“协议生成、结构化摘要、协议信息提取和利益相关者协作”相关竞品。

谨慎边界：

- 不应将其描述为只做初稿生成；更安全的表述是“公开定位更偏 protocol intelligence 和清晰化，TrialCompiler 需要通过事实确认、变更影响和审计责任说明差异”。

### 太美医疗

本地来源：

- `COMP-007`：Taimei Wiz-iCTA document management agent
- `COMP-008`：Taimei ICH M11 and AI platform article

可支持的判断：

- 太美医疗是本土临床运营和文档管理场景中的重要相邻竞品或合作生态。
- Wiz-iCTA 页面可支持“临床试验文档/TMF 智能管理、海量重复性文档管理工作”的本土场景判断。
- ICH M11 与 AI 平台文章可支持“中国临床研发正在关注结构化协议、AI Agent、iCTA、eCRF 和临床数据/文档工作流”的行业背景。

谨慎边界：

- 不应把太美医疗描述为单一 protocol compiler 竞品。
- 更准确的定位是：它代表本土临床运营和文档管理平台，TrialCompiler 应作为事实与变更治理层与此类平台互补。

### Veeva

本地来源：

- `COMP-009`：Veeva AI for Clinical Operations

可支持的判断：

- Veeva 属于临床运营和受控文档平台类相邻竞品/生态平台。
- 竞品分析中的“TrialCompiler 不应替代 Veeva，而应作为语义治理层与之接口”是合理方向。

谨慎边界：

- 不应声称 Veeva 不具备 AI 或文档质量检查能力。
- 应强调产品边界：Veeva 等平台承担受控文档、权限、审批和企业系统底座，TrialCompiler 聚焦事实层、依赖图、文档单元测试和变更影响分析。

### Evinova

本地来源：

- `COMP-010`：Evinova Study Document Assistant

可支持的判断：

- Evinova 可作为 Study Document Assistant 类相邻竞品。
- 它支持“临床研究文档助手”是一个已经存在的产品类别，因此 TrialCompiler 必须说明自己不是泛化写作助手，而是事实与变更治理系统。

## 对后续比赛材料的写法建议

推荐表述：

> 公开竞品已经覆盖协议结构化、文档生成、质量检查、修订协同和受控文档管理等能力，因此 TrialCompiler 不把“使用大模型写文档”作为核心创新，而把重点放在已确认事实层、跨文件依赖图、文档单元测试、变更任务闭环、组织经验治理和中国药企协作环境适配。

避免表述：

> 竞品都做不到跨文件一致性。

原因：HumanTrue、Cori Clinical 等公开资料已经显示该方向存在直接竞品，过度宣称会削弱可信度。

## 待人工复核

1. 人工打开 `COMP-004` 对应官方页面，确认 Cori REVIEW 是否公开说明 cross-document coherence 或 review synchronization。
2. 补充 IQVIA Protocol Design Optimization 的具体官方页面，避免只用公司总页。
3. 补充 Medidata Protocol Optimization 的具体官方页面，避免只用平台总页。
4. 若后续正式提交，需要把每个竞品的公开声明逐项核验，形成可引用的表格版本。
