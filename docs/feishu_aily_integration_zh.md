# 飞书 Aily 前置工作流设计

- 目标：明确使用一项飞书 AI 能力，并把它放在 TrialCompiler 主工作流之前
- 选择：飞书智能伙伴创建平台 Aily 的 Workflow 模式，使用“自然语言提问与字段抽取”节点

## 1. 为什么放在前置层

TrialCompiler 后端需要结构化任务：项目、文档、任务意图、文件引用、操作者和审阅范围。用户在飞书中的真实输入往往只是一句“帮我看看这个方案的终点有没有前后不一致”。若后端直接猜测，会把模糊输入带入高风险文档流程。

Aily 负责：

1. 在飞书对话中理解自然语言任务；
2. 从历史上下文和当前回答中抽取字段；
3. 对缺失字段发起多轮澄清；
4. 生成固定 JSON；
5. 通过 HTTP 节点调用 TrialCompiler。

TrialCompiler 负责证据、文档图、Agent 循环、审计和人工审批。两者边界清楚，比赛中的飞书 AI 功能也不是一个装饰按钮。

## 2. Aily Workflow 节点

```text
开始：接收用户消息与附件
  -> AI 提问/字段抽取：识别 task_intent、project_id、document_type、scope
  -> 条件判断：字段是否完整
       -> 否：自然语言澄清
       -> 是：继续
  -> 结构化数据节点：组装 FeishuIntakeEnvelope
  -> HTTP 节点：POST /api/v1/intake/feishu
  -> 条件判断：是否已有 file_refs
       -> 否：提示上传或选择飞书文档
       -> 是：POST /api/v1/review
  -> 输出：返回审阅任务状态和人工审核入口
```

## 3. Aily 需要抽取的字段

| 字段 | 是否必填 | 获取方式 |
| --- | --- | --- |
| `request_id` | 是 | Workflow 生成 |
| `project_id` | 是 | 上下文、选项或追问 |
| `actor_id` | 是 | 飞书身份上下文 |
| `user_request` | 是 | 原始消息保留 |
| `task_intent` | 是 | AI 分类为 review / compile / propagate / explain |
| `document_type` | 是 | AI 抽取，无法确定时追问 |
| `file_refs` | 条件必填 | 消息附件或用户选择的飞书文档 |
| `requested_scope` | 否 | 章节、表格或全篇 |
| `locale` | 否 | 默认 `zh-CN` |

## 4. 本地与服务器接口

仓库已实现：

- `POST /api/v1/intake/feishu`：验证和规范化 Aily 输出；
- `POST /api/v1/review`：启动 review-only 工作流；
- `data/fixtures/feishu_aily_intake.json`：对接样例；
- `schemas/feishu_aily_intake.schema.json`：结构合同。

本地验证：

```powershell
$env:PYTHONPATH = "src"
python -m trialcompiler feishu-intake --payload data/fixtures/feishu_aily_intake.json
```

## 5. Aily 配置步骤

1. 在 Aily 新建 Workflow 模式应用。
2. 在开始节点声明 `project_id`、`document_type`、`task_intent` 和 `file_refs`。
3. 增加自然语言提问节点，开启从用户回答中智能识别并提取指定字段。
4. 设置缺失字段分支，只追问必要信息；已在历史对话中出现的字段不重复询问。
5. 使用结构化数据节点生成和 Schema 一致的 JSON。
6. 使用 HTTP 节点调用 TrialCompiler 的 HTTPS 地址。
7. 将 `request_id` 和后端返回的任务状态写入飞书消息。
8. 真实上线前配置应用权限、服务端鉴权、签名校验、访问控制和数据保留策略。

## 6. 比赛演示脚本

用户在飞书输入：

> 我把方案终点时间从 12 周改成 16 周了，帮我检查有没有漏改。

Aily 自动识别“变更传播/一致性审阅”，若用户没有选择项目或文件，只追问这两项。字段完整后调用 TrialCompiler。后端返回受影响章节、红线建议、来源和 D Agent 质量门结果。用户在飞书中批准或拒绝，F Agent 再生成待批准的经验胶囊。

演示应同时显示：

- Aily 对模糊请求的结构化与澄清；
- TrialCompiler 对跨章节依赖的定位；
- 人工审批前不自动覆盖原文；
- 接受/拒绝结果可成为下一次审阅的受控经验。

## 7. 当前边界

代码已完成 Aily 入口合同和 API，但仓库不保存飞书 App ID、App Secret 或真实文档权限。Aily 控制台中的 Workflow 仍需在比赛团队飞书租户中人工创建和授权；这不是可以用公开代码替代的步骤。
