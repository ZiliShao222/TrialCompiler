# TrialCompiler CLI 原型使用指南

## 1. 原型定位

当前 CLI 是 TrialCompiler 的产品内核验证版本。它把一次临床试验方案修订表示为可追踪的对象链：

```text
项目工作区
  -> 有来源和状态的 Trial Fact Sheet
  -> 事实变更请求
  -> 文档依赖与影响矩阵
  -> A-F 审阅编译
  -> 确定性检查 + Qwen 语义复核
  -> 红线建议与质量门
  -> 专业人员批准或拒绝
  -> 新文档版本与追加式审计日志
```

当前版本仅用于合成数据和比赛演示，不可用于真实临床生产，也不允许 AI 自动批准医学、统计、注册或质量决策。

## 2. 环境

```powershell
cd D:\TrialCompiler
$env:PYTHONPATH = "src"
$py = "D:\miniconda\envs\iGEM\python.exe"
```

Qwen 语义审阅使用服务端环境变量，不把密钥写入仓库：

```powershell
$env:DASHSCOPE_API_KEY = "<local secret>"
```

缺少该变量时，`--llm auto` 会继续执行确定性编译，并明确记录语义审阅未运行；`--llm on` 会直接报错，避免误以为已经调用模型。

## 3. 推荐的完整命令流程

### 3.1 创建持久工作区

```powershell
& $py -m trialcompiler init `
  --workspace outputs/workspaces/tc_demo `
  --document data/fixtures/synthetic_protocol_conflict.json `
  --actor demo-owner
```

工作区包含当前文档、变更请求、每次编译产物、审批记录和 `audit.jsonl`。命令重新启动后状态不会丢失。

### 3.2 查看项目和事实表

```powershell
& $py -m trialcompiler status --workspace outputs/workspaces/tc_demo
& $py -m trialcompiler facts --workspace outputs/workspaces/tc_demo
```

候选事实必须有来源，才能由授权人员确认：

```powershell
& $py -m trialcompiler fact-decision `
  --workspace outputs/workspaces/tc_demo `
  --fact-id FACT-ID `
  --decision confirm `
  --reviewer medical-reviewer `
  --note "Source and scope checked"
```

### 3.3 发起事实变更

```powershell
& $py -m trialcompiler change `
  --workspace outputs/workspaces/tc_demo `
  --fact-id F-PRIMARY-ENDPOINT-WEEK `
  --value 20 `
  --reason "Synthetic amendment demonstration" `
  --actor medical-lead
```

系统返回唯一 `change_id`。该步骤只是创建候选变更，不修改当前批准版本。

### 3.4 查看影响并编译

```powershell
& $py -m trialcompiler impact `
  --workspace outputs/workspaces/tc_demo `
  --change-id <change_id>

& $py -m trialcompiler compile `
  --workspace outputs/workspaces/tc_demo `
  --change-id <change_id> `
  --actor demo-reviewer `
  --seed-demo-experience `
  --llm on `
  --llm-model qwen-plus
```

`--change-id` 可以省略；此时 CLI 会自动选择最新一项尚未被人工批准或拒绝的候选变更。
如果不存在未决变更，才会对当前正式文档执行基线审查。

编译会生成：

- `workflow_state.json`：完整结构化状态；
- `review_report.md`：面向审核人员的审阅包；
- `agent_trace.jsonl`：A-F agent 协作轨迹；
- `impact_matrix.json`：受影响章节及当前值观察；
- `semantic_review.json`：经 ID 白名单和越界推测过滤后的 Qwen 语义审查；
- `run_summary.json`：运行、质量门和发布状态摘要。

Qwen 输出只是语义风险提示，不会覆盖确定性检查或人工决策。模型输出中的未知
section/fact/source ID 会被移除，对未提供文件的存在性猜测也不会进入有效审查结果。

### 3.5 人工批准或拒绝

```powershell
& $py -m trialcompiler decide `
  --workspace outputs/workspaces/tc_demo `
  --change-id <change_id> `
  --decision approve `
  --reviewer qualified-reviewer `
  --note "Synthetic demonstration approval"
```

只有质量门通过且专业人员明确批准后，候选值和对应红线才会写入新的文档版本。拒绝不会修改文档。

### 3.6 查看变更和审计

```powershell
& $py -m trialcompiler changes --workspace outputs/workspaces/tc_demo
& $py -m trialcompiler audit --workspace outputs/workspaces/tc_demo --limit 30
```

## 4. 面向非程序人员的引导模式

```powershell
& $py -m trialcompiler workspace `
  --workspace outputs/workspaces/tc_demo `
  --llm auto
```

引导模式只包装上述原子命令，不维护另一套隐藏状态。因此同一项目既可以交互操作，也可以在自动化脚本或后续飞书入口中调用。

## 5. 当前能力边界

- 输入仍是结构化合成文档 JSON；Word/PDF 的候选事实提取将在后续入口层实现。
- 确定性检查目前覆盖来源引用和终点评估周冲突；复杂表格语义由 Qwen 给出候选风险，并交给人工判断。
- 当前审批是比赛原型中的显式身份字符串，不等同于企业电子签名、RBAC 或计算机化系统验证。
- 当前不会处理患者病历筛查、真实受试者数据或临床数据清洗。
