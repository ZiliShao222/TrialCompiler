# TrialCompiler 资料总账与比赛引用说明

## 1. 资料入口

本项目的资料不再依赖人工浏览文件夹寻找，而统一通过以下总账访问：

- 人工阅读总账：`references/catalog/SOURCE_REGISTER.md`
- 表格筛选总账：`references/catalog/source_register.csv`
- 程序与知识库入口：`references/catalog/sources.jsonl`
- 重复 URL 合并记录：`references/catalog/source_aliases.csv`
- 待人工核查的同内容文件：`references/catalog/duplicate_files_to_review.csv`
- 分类导览：`references/catalog/collections/`

原始文件仍保存在 `references/inbox/` 和 `docs/attachments/`，目录生成过程不会移动、重命名或删除原文件。

## 2. 比赛报告引用规则

每项关键论述至少记录：

1. `source_id`；
2. 资料标题；
3. 发布机构或作者；
4. 年份；
5. 原始 URL；
6. 该资料具体支持的论述；
7. 访问日期；
8. 若使用本地快照，记录仓库相对路径。

推荐在工作稿中使用以下格式：

```text
[source_id] 标题，机构/作者，年份，URL，访问日期：YYYY-MM-DD。
用途：支持“……”这一论述；引用位置为……。
```

最终提交时，可按比赛要求转换为 GB/T 7714、APA 或指定格式，但工作过程中的 `source_id` 应保留在证据表中，便于追溯。

## 3. 证据等级

| 等级 | 含义 | 允许用途 |
| --- | --- | --- |
| A | 监管机构、国际标准组织、正式指南 | 合规规则、强约束、核心事实依据 |
| B | 公共机构模板、注册平台、行业标准 | 文档结构、字段定义、检查规则 |
| C | 同行评议论文、开放研究、技术方法 | 方法设计、技术可行性、研究背景 |
| D | 厂商资料、行业文章、新闻 | 市场背景、竞品观察、需求线索 |
| INTERNAL | 团队附件与内部整理 | 项目过程、团队决策，不作为外部权威证据 |

当同一结论同时存在多个来源时，优先顺序为 `A > B > C > D`。D 级资料中的产品能力和商业数字不得直接写成已经独立验证的事实。

## 4. 结构化分类

| 目录 | 内容 |
| --- | --- |
| `01_regulatory_and_ethics` | 临床研究法规、伦理、GCP、AI 治理与监管要求 |
| `02_templates_and_associated_documents` | 方案、知情同意、统计分析及关联文件模板 |
| `03_data_standards_and_structured_protocols` | CDISC、结构化方案、数据交换和语义标准 |
| `04_ai_methods_and_governance` | 文档 AI、信息抽取、RAG、评估与治理方法 |
| `05_industry_competitors_and_value` | 行业、竞品、成本、价值测算和市场资料 |
| `06_platform_and_integration` | 飞书、接口、部署和系统集成资料 |
| `08_internal_project_materials` | 团队附件、任务表和内部论证材料 |

## 5. 更新方法

新增资料先放入 `references/inbox/`，并在对应来源索引中补充元数据，然后运行：

```powershell
python scripts/build_reference_catalog.py
```

运行后检查 `catalog_summary.json` 中的缺失路径数量必须为 0，并人工处理 `duplicate_files_to_review.csv` 中的记录。知识库只能消费总账中的 canonical 记录，不能直接扫描整个 inbox 后无差别入库。

