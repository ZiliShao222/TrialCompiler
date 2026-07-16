# 仓库结构与边界

本仓库参考 `global_alignment_agent` 已验证的配置、提示词、schema、源码和应用分层，同时针对临床长文档与 benchmark 工作增加独立的知识资产、参考文献、数据生命周期和评测目录。

## 目录职责

| 目录 | 职责 | 不应存放 |
| --- | --- | --- |
| `apps/` | API 与前端应用 | Agent 核心业务逻辑 |
| `benchmarks/` | TrialDocBench 任务规范、数据卡与评分协议 | 大体积原始数据 |
| `config/` | 可提交的默认配置与示例 | API Key、口令和私有地址 |
| `data/` | 数据生命周期说明与可公开 fixture | 真实患者身份信息 |
| `docs/` | 产品、架构、实验和决策文档 | 运行时输出 |
| `knowledge/` | 监管、企业、项目和经验知识资产 | 检索实现代码 |
| `outputs/` | 本地运行结果 | 需要长期维护的源文件 |
| `prompts/` | Agent、系统和记忆契约 | Python 业务逻辑 |
| `references/` | 文献和官方来源索引 | 未授权论文全文 |
| `schemas/` | Trial Fact Sheet、Issue、Decision Capsule 等契约 | 具体项目数据 |
| `scripts/` | 可重复执行的维护脚本 | 只执行一次的临时试验 |
| `src/trialcompiler/` | Agent、工作流、文档图、知识和评测代码 | 私有材料与密钥 |
| `tests/` | 单元、集成、工作流和 benchmark 测试 | 生产数据副本 |

## 知识分层

```text
knowledge/
├── regulatory/   ICH、NMPA、FDA 等外部规范及其元数据
├── enterprise/   经授权的企业 SOP、模板和术语表
├── project/      当前试验的受控事实与决策材料
└── experience/   经人工确认的 Decision Capsules
```

知识内容与实现代码必须分开。`knowledge/` 保存可审计资产；`src/trialcompiler/knowledge/` 负责解析、索引、检索、权限和引用。

## 数据规则

- 默认不提交真实患者数据、个人身份信息或企业私有材料。
- 原始、处理中和生成后的数据分别放入 `data/raw/`、`data/interim/` 与 `data/processed/`，这些目录默认被 Git 忽略。
- 小型、脱敏、可公开的测试样本放入 `data/fixtures/`。
- 每个 benchmark 版本必须有数据卡、来源说明、许可状态和划分策略。
- 训练集、验证集和测试集必须按试验项目划分，避免同一项目的章节跨集合泄漏。

## 提示词规则

- 提示词不得直接写入 Python 模块。
- 每个 Agent 使用独立文件，并声明输入、输出、允许行为、禁止行为和失败升级条件。
- Prompt 变更应当能够与 benchmark 结果对应，避免无法解释的行为漂移。

\n