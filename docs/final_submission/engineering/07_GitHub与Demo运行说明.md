# TrialCompiler GitHub 与 Demo 运行说明

项目的一句话定位：**把 AI 的跨文档不确定性推理编译成可解释、可机器核验的临床变更证明。** 图、规则、状态机和审计是安全底座；AI 研究对象是竞争假设、主动取证、不确定性校准及可解释拒答。

携证证明命令：

```powershell
$env:PYTHONPATH='src'
python scripts/build_assurance_case.py --state <run>/workflow_state.json --summary <run>/run_summary.json --score <score.json> --output <assurance.json>
```

证明中的 `release_authorized=false` 是固定安全设计，机器结论不能代替医学、统计、注册或质量批准。

## 1. GitHub 提交入口

项目仓库：

```text
https://github.com/ZiliShao222/TrialCompiler
```

建议在比赛提交系统中将链接名称填写为：

> TrialCompiler：基于证据、文档依赖图、多智能体质量门与人工审批的临床试验文档编译系统

仓库根目录提供以下评审入口：

- `README.md`：产品定位、能力、快速运行和安全边界；
- `ARCHITECTURE.md`：系统分层、依赖方向、受控数据流与代码映射；
- `.github/workflows/ci.yml`：GitHub Actions 自动验证；
- `src/trialcompiler/`：核心实现；
- `tests/`：自动化测试；
- `benchmarks/trialdocbench/`：公开和合成 benchmark；
- `prompts/`：A-F 专业角色、G 不确定性治理与 H 受控取证所使用的生成/审核契约；
- `schemas/`：机器可读数据契约；
- `docs/final_submission/engineering/`：工科提交材料。

关键在线页面：

```text
仓库首页
https://github.com/ZiliShao222/TrialCompiler

系统架构
https://github.com/ZiliShao222/TrialCompiler/blob/main/ARCHITECTURE.md

GitHub Actions
https://github.com/ZiliShao222/TrialCompiler/actions

工科提交材料
https://github.com/ZiliShao222/TrialCompiler/tree/main/docs/final_submission/engineering

NCT04683926 公开案例
https://github.com/ZiliShao222/TrialCompiler/tree/main/benchmarks/trialdocbench/public_case_001_nct04683926
```

## 2. 环境要求

- Python 3.11 或更高版本；
- Windows PowerShell、PowerShell 7、macOS Terminal 或 Linux shell；
- 运行确定性测试不需要 API Key；
- 只有模型辅助审核和方案生成需要兼容模型服务的 API Key；
- 不应使用真实患者数据、受保护健康信息或未授权申办方材料。

## 3. 安装

以下命令以 Windows PowerShell 为例：

```powershell
git clone https://github.com/ZiliShao222/TrialCompiler.git
cd TrialCompiler

python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

macOS 或 Linux 激活环境时使用：

```bash
source .venv/bin/activate
```

安装成功后检查 CLI：

```powershell
python -m trialcompiler --help
```

## 4. 最快验收路径

### 4.1 运行静态检查和自动化测试

```powershell
python -m ruff check src tests
python -m pytest -q
```

当前提交基线的本地验证结果为：

```text
Ruff: All checks passed
Pytest: 121 passed
```

GitHub Actions 会在推送到 `main` 和 Pull Request 时执行同样的检查。若未来新增测试，以 GitHub Actions 对相应提交的结果为准，不应把“121”视为永久固定数量。

### 4.2 启动 API

```powershell
python -m uvicorn apps.api.app:app --host 127.0.0.1 --port 8810
```

浏览器打开：

```text
http://127.0.0.1:8810/docs
```

主要接口：

- `GET /health`：运行状态和 review-only 发布模式；
- `POST /api/v1/intake/feishu`：验证飞书 Aily 交接载荷；
- `POST /api/v1/review`：运行受治理文档审核；
- `POST /api/v1/memory/search`：检索已准入且范围匹配的经验元素。

### 4.3 运行 CLI 引导演示

```powershell
python -m trialcompiler workspace `
  --workspace outputs/workspaces/guided-demo
```

所有生成运行和本地数据库默认写入 `outputs/`。该目录默认不进入 Git 版本控制。

## 5. NCT04683926 公开案例复现

### 5.1 校验公开 benchmark 包

```powershell
python -m pytest tests/test_trialdocbench_public_case.py -q
```

该步骤检查公开来源、27 条 Trial Fact Sheet、gold tests、合成变更隔离和来源定位，不调用外部模型。

### 5.2 构建运行 fixture

```powershell
python scripts/build_nct04683926_runtime_fixture.py
```

### 5.3 复评分冻结运行

若本地已经按照复现说明生成冻结运行目录，可执行：

```powershell
python scripts/score_nct04683926_benchmark.py `
  --benchmark benchmarks/trialdocbench/public_case_001_nct04683926 `
  --run outputs/nct04683926_rule_breakthrough_20260718/run-deterministic-v2 `
  --output outputs/nct04683926_rule_breakthrough_20260718/run-deterministic-v2_score.json
```

当前提交的冻结评分证据为：

```text
TP = 8
FP = 1
FN = 0
TN = 2
Precision = 0.8889
Recall = 1.0000
F1 = 0.9412
Negative-control accuracy = 1.0000
```

这些结果仅适用于 NCT04683926 当前 gold/scorer 版本，不能外推为模型总体临床准确率。

## 6. 模型辅助模式

模型辅助审核使用环境变量提供密钥。不要把密钥写入命令历史、提交文件或运行报告。

```powershell
$env:DASHSCOPE_API_KEY = "<LOCAL_SECRET>"
```

也可以通过位于仓库外或受 `.gitignore` 保护的本地环境文件提供密钥。仓库中的 `.env.example` 只给出变量名，不包含真实凭据。

模型输出始终是候选意见。未解决的医学、统计、注册和质量问题必须转换为 Decision Request 或阻断 finding，不得因为模型给出高分而自动发布。

## 7. 受控方案生成案例

Metformin-PAD 案例采用严格可见性隔离：

1. Phase 1 只读取 Phase 1 可见资料；
2. Phase 2 在冻结 Phase 1 的基础上增加 Phase 2 资料；
3. evaluator-only 文件只在生成结果冻结后交给盲评器；
4. 确定性机器门禁不能被 LLM Judge 高分覆盖；
5. 阻断 finding 被编译成带责任角色和退出条件的整改工单。

测试包属于合成/历史重建的研究验证材料，不是申办方正式方案，不包含患者级数据，也不构成医学、统计、注册或质量批准。

## 8. 输出与审计

典型运行目录包含：

```text
outputs/<workspace-or-run>/
├── workflow_state.json
├── agent_trace.jsonl
├── semantic_review.json
├── semantic_repairs.json
├── decision_requests.json
├── impact_matrix.json
├── review_report.md
└── run_summary.json
```

不同命令的产物可能略有不同。正式复现实验应额外记录：

- Git commit；
- Python 和依赖版本；
- 模型名称与服务模式；
- Prompt 哈希；
- 输入文件哈希；
- 运行时间；
- scorer 和 gold 版本。

## 9. 演示时建议说明的边界

可以说明：

> TrialCompiler 已形成可运行的临床文档工程研究原型，能够进行事实治理、跨文档依赖分析、候选最小红线、独立复检、人工决策门、经验准入和可复现 benchmark 评分。

不应说明：

- 系统能够自动批准临床方案；
- 系统能够替代医学、统计、注册或质量人员；
- 单个公开案例的 F1 可以代表生产总体准确率；
- Metformin-PAD 合成/历史重建材料代表真实监管认可；
- 当前原型已经完成生产环境安全与合规验证。

## 10. 提交检查

在提交 GitHub 链接或演示前执行：

```powershell
git status --short
git rev-parse HEAD
python -m ruff check src tests
python -m pytest -q
```

确认 GitHub `main` 已包含目标 commit，GitHub Actions 对该提交完成验证，并使用 `docs/final_submission_20260719_verified.zip` 作为线下附件包。

## 11. 50 例真实公开语料复现

仓库新增入口：

```text
https://github.com/ZiliShao222/TrialCompiler/tree/main/benchmarks/trialdocbench/public_corpus_050
```

本地执行：

```powershell
python scripts/build_public_protocol_sap_corpus.py --limit 50 --workers 8
python scripts/profile_public_protocol_sap_corpus.py
python -m pytest tests/test_public_corpus_050.py tests/test_public_corpus_builder.py tests/test_public_corpus_profile.py -q
```

构建器需要网络访问 ClinicalTrials.gov；仓库保存冻结注册快照、官方文档 URL、SHA-256
与 case contract，不提交约 150 MB 的本地 PDF 下载缓存。冻结语料包含 50 个案例和 65
份验证文档；`gold_status=not_annotated` 是强制声明边界，不能把完整性测试解释为模型准确率。
