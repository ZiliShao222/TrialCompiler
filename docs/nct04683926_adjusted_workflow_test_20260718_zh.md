# NCT04683926 调整后全工作流测试

## 测试边界

- 案例：`NCT04683926 / OMNI-PAIN-103`
- 数据：公开研究文件、人工复核事实表、完全合成变更；无患者级数据
- 模型：真实 `qwen-plus` API
- 运行模式：review-only；系统不能自动批准或覆盖正式文件
- 合成变更：`F015` 最终名义 PK 采样时间由 `32 h` 改为 `36 h`

## 调整内容

1. Qwen 语义发现不再追加在 A-F 工作流之后，而是在 B-agent 中转为统一 finding。
2. C-agent 新增受治理的语义修订调用，只能对现有章节原文生成最小候选红线。
3. D-agent 同时检查确定性修订和语义修订；没有完成语义审查时，`0 finding` 不再等于通过。
4. 长序列事实被拆成原子变化，F015 被识别为 `32 -> 36`，不再要求整串序列匹配。
5. 数值替换受单位约束：`32 hours` 可改为 `36 hours`，但 `32 participants` 必须保持不变。
6. 同一章节出现多个不一致候选红线时，D-agent 会标记 proposal collision 并退回。
7. 模型把数组字段错误返回为字符串时，governor 会转为单元素数组，不再逐字符拆分。
8. 变更理由、变更上下文和影响矩阵均传给语义审查及修订层。

## 基线运行

- Run ID：`run-20260717164705-1bbd7f`
- B-agent：4 条语义 finding
- C-agent：2 条有证据支持的候选红线
- C-agent 拒绝强行修订：2 条，需要统计或临床人员补充判断
- D-agent：`accepted=false`，score `0.50`

这说明系统已不再把“确定性规则未发现问题”误判为整套文档通过。语义层发现会进入同一质量闭环；无法由现有证据安全解决的问题会保持未解决状态。

## F015 合成变更运行

- Run ID：`run-20260717165721-bacba5`
- 影响章节：7 个
- 确定性 findings：7 条
- 语义 findings：3 条
- 候选 repairs：9 条
- D-agent：`accepted=false`，score `0.70`
- 未解决：1 个缺少安全修订的语义问题，以及同章节候选修订冲突

确定性传播正确覆盖：

- Protocol Synopsis
- Protocol Body / Procedures
- Schedule of Procedures
- ICF Participation
- SAP PK Specification
- Synthetic CRF PK field
- ClinicalTrials.gov result summary

关键防误改结果：

```text
Before:
... final 32 hours after each dose. Up to 32 participants may be randomized ...

Candidate redline:
... final 36 hours after each dose. Up to 32 participants may be randomized ...
```

旧实现曾错误地把 `32 participants` 一并改成 `36 participants`；调整后的单位感知替换已经消除该问题。

## 人机交流摘要

```text
Human: 加载公开 NCT04683926 文档包，仅执行 review-only 审查。
A: 锁定项目、文档版本、已批准事实和待复核事实。
B: 合并确定性检查与 Qwen 语义检查，生成统一 findings。
C: 对有明确来源支持的问题生成候选红线；证据不足时保留 unresolved。
D: 检查来源、事实值、非目标内容保护和同章节候选冲突。
E: 生成 findings、红线、限制与质量门报告。
F: 仅在质量门通过且有人类确认基础时生成待审批经验候选。

Human: 提议把 F015 最终采样时间从 32 h 改为 36 h。
System: 找到 7 个直接依赖位置，并将每个旧值位置标记为 revision_candidate。
B: 生成 7 条确定性传播 finding，并合并 3 条语义 finding。
C: 生成 7 条单位感知传播红线和 2 条可治理语义红线。
D: 发现同一章节存在不同修订路径，拒绝自动合并，返回人工复核。
```

## 原始证据

- 工作区：`outputs/nct04683926_adjusted_v2_20260718/`
- 基线控制台输出：`baseline_compile_console.json`
- 最终变更控制台输出：`change_compile_final_console.json`
- 每次 run 均保存：`workflow_state.json`、`agent_trace.jsonl`、`semantic_review.json`、`semantic_repairs.json`、`impact_matrix.json`、`review_report.md`

## 当前结论

本轮调整完成了“发现进入闭环、修订受证据约束、质量门可阻断、数值传播不误伤”的最小可用链路。当前仍保持保守边界：语义上无法由公开资料唯一决定的问题不会被自动解决；候选冲突必须由医学、统计、注册或质量人员确认。
