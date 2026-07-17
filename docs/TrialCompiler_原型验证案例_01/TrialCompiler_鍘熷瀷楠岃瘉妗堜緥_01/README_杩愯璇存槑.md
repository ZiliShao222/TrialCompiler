# TrialCompiler 原型验证案例 01

## 案例目标

本案例用于验证 TrialCompiler 当前 MVP 的完整链路：

1. 飞书 Aily 结构化任务交接；
2. Trial Fact Sheet 中已批准事实的读取；
3. 事实—章节—关联文件依赖追踪；
4. 跨章节/跨文件时间点一致性检查；
5. 最小化候选红线生成；
6. 独立质量门检查；
7. 待人工审核报告与 `draft` 经验候选生成。

案例为**完全合成数据**，不包含真实患者信息，也不用于任何临床、医学、注册或伦理决策。

## 案例设定

虚构项目 `SYNTH-AD-016` 是一项评估虚构研究药物 TC-AD-01 的随机、双盲、安慰剂对照 II 期研究，计划入组 120 名中度特应性皮炎受试者。

医学负责人已批准将主要终点 EASI-75 的评估时间由 Week 12 调整为 Week 16。方案的“研究目的与终点”和知情同意说明已经更新，但方案摘要、访视流程表和 SAP 仍残留 Week 12。

## 文件说明

- `01_feishu_aily_intake.json`：飞书 Aily 向 TrialCompiler 交接的结构化任务。
- `02_trial_document.json`：可直接交给当前 TrialCompiler MVP 的结构化文档。
- `03_expected_result.json`：机器可读的标准答案。
- `04_案例原始资料说明.md`：供演示人员和评委阅读的业务背景。
- `run_case.sh`：macOS/Linux 一键运行脚本。
- `run_case.ps1`：Windows PowerShell 一键运行脚本。

## 一键运行

### macOS / Linux

在终端执行：

```bash
cd "/本案例所在目录"
chmod +x run_case.sh
./run_case.sh "/TrialCompiler仓库绝对路径"
```

例如：

```bash
./run_case.sh "$HOME/TrialCompiler"
```

### Windows PowerShell

```powershell
cd "D:\本案例所在目录"
.\run_case.ps1 -RepoRoot "D:\TrialCompiler"
```

脚本会依次：

1. 验证 Aily 输入合同；
2. 运行带已批准经验卡的合成审阅；
3. 把结果写入本目录下的 `outputs/`。

## 预期结果

成功运行后，命令行摘要应包含：

- `status`: `completed_for_human_review`
- `findings`: `3`
- `proposals`: `3`
- `quality.accepted`: `true`
- `quality.score`: `1.0`
- `experience_cards`: `1`
- `experience_candidate_status`: `draft`

三处应被检出的旧值残留：

1. `S-PROTOCOL-SYNOPSIS`：Week 12 → Week 16；
2. `S-PROTOCOL-SOA`：Week 12 → Week 16；
3. `S-SAP-PRIMARY`：Week 12 → Week 16。

两处不应误报：

1. `S-PROTOCOL-OBJECTIVES` 已为 Week 16；
2. `S-ICF-PROCEDURES` 已为 Week 16。

同时应验证最小化修改：摘要中的 `120 participants` 必须保留，不得被候选红线改写。

## 结果查看

运行完成后重点查看：

- `outputs/review_report.md`：评委演示最直观；
- `outputs/workflow_state.json`：核对 findings、proposals、quality 和 experience candidate；
- `outputs/agent_trace.jsonl`：展示 A–F 各角色审计轨迹；
- `outputs/memory.sqlite3`：演示受控经验记忆。

> 当前质量门仅检查候选修改的事实与证据完整性。“通过”表示可以进入有资格人员审核，不代表正式批准。
