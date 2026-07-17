# TrialCompiler 语义修订收敛技术报告

## 1. 本次解决的问题

早期原型能够发现临床试验方案中的确定性不一致，也能调用大模型发现语义风险，但修订阶段存在三个关键缺口：

1. 确定性修订与语义修订可能同时改写同一章节，整段文本比较会把互不冲突的修改误判为冲突。
2. 大模型指出问题后，如果现有证据不足以支持唯一改法，系统仍可能尝试生成看似合理但未经授权的文本。
3. D-agent 只能给出通过或失败，不能把冲突位置和返工范围结构化地反馈给 C-agent，循环容易重复相同提案。

本次将修订单元从“整段替换”下沉为“带来源的最小编辑操作”，并建立了可收敛的诊断、修订、合并、沙箱验证和人工决策闭环。

## 2. 技术路线

```text
B-agent findings
        ↓
C-agent raw repair proposals
        ↓
proposal → minimal edit operations
        ↓
按 section 分组并进行区间冲突分析
        ↓
非重叠操作自动合并
相同操作去重并合并 finding provenance
重叠且结果不同的操作形成 conflict group
        ↓
D-agent 在候选文档沙箱中应用补丁
        ↓
重新运行确定性检查
        ↓
无回归且机器可修复项关闭
        ↓
证据不足或存在歧义的项目转为 DecisionRequest
        ↓
E-agent 输出红线、证据、影响范围和专业决策包
```

## 3. 操作级修订表示

每个编辑操作记录：

```json
{
  "operation_id": "repair-change-impact-F015-op-02",
  "finding_ids": ["change-impact-F015", "semantic-004"],
  "section_id": "PROT-BODY-PROCEDURES",
  "start": 278,
  "end": 279,
  "before": "2",
  "replacement": "6",
  "fact_ids": ["F015"],
  "evidence_source_ids": ["SRC-PROT"],
  "origin": "deterministic"
}
```

`start` 和 `end` 使用原始章节文本坐标。合并器从后向前应用操作，避免前序替换改变后续坐标。两个操作只有在原始区间重叠且替换结果不同的情况下才构成真实冲突。

## 4. 冲突与收敛规则

### 4.1 可以自动合并

- 同一章节、不同文本区间的修改；
- 同一区间、相同替换内容的重复建议；
- 确定性规则与语义审查对同一事实变更给出一致结果。

### 4.2 不允许自动裁决

- 同一区间被建议替换为不同内容；
- 现有来源只证明“存在矛盾”，但不能证明哪一种表述正确；
- 修改涉及医学合理性、统计解释、注册策略或受试者执行要求。
- 候选修订引用的事实仍处于 `requires_human_review`，或没有任何已确认事实锚点。

这些情况不会通过增加循环次数强行解决，而是生成 `DecisionRequest`，记录问题、受影响章节、证据、可选处置和状态。

系统设置独立的“事实授权门”。确定性传播可处理当前受治理的变更请求；大模型语义修订则只能引用已批准事实或本次活动变更事实。来源文件能够证明“原文这样写”，并不等同于授权系统选择其中一种冲突表述。

### 4.3 D-agent 定向返工

D-agent 返回结构化的 `repair_feedback`：

- `retry_finding_ids`：需要再次处理的 finding；
- `defer_to_human_finding_ids`：证据不足、必须转人工的 finding；
- `conflict_groups`：冲突操作、章节和来源；
- `instructions`：C-agent 下一轮只能修改的范围。

C-agent 保留已通过的非冲突补丁，只移除冲突补丁并生成专业决策请求，避免整份候选稿重新生成。

## 5. 外部验证器

D-agent 不以大模型的自我评价作为最终依据。合并后的候选章节先写入内存沙箱，再重新运行 `ClinicalDocumentGraph.review()`：

- `remaining_deterministic_finding_ids` 检查原问题是否仍存在；
- `new_deterministic_finding_ids` 检查修订是否制造新问题；
- `regression_free` 只有在没有新确定性错误时才为真。

因此，质量分数表示机器修订包的完整性，而不是医学或法规批准。

## 6. 人工治理锁

机器能够完成的修订与专业判断被明确分离：

- `machine_repair_complete=true`：所有可由现有规则和证据验证的修订已经闭合；
- `workflow_status=awaiting_qualified_decisions`：仍有专业决策请求；
- `workflow_status=ready_for_qualified_approval`：机器修订完成且所有决策请求已处理。

只要存在未解决的 `DecisionRequest`，`decide approve` 就会拒绝写回正式文档。审核者必须记录非空理由，选择接受已记录差异，或要求补充证据并重新编译；操作写入追加式审计日志。

## 7. NCT04683926 公开案例验证

验证使用公开的 NCT04683926 / OMNI-PAIN-103 案例和完全合成的 `32 h → 36 h` 变更，不包含患者级数据。

真实 `qwen-plus` 回归结果：

- 语义审查与语义修订均为 `completed`，未使用 fallback；
- 最终回归产生 13 个原始修订，并被合成为 7 个章节级补丁；
- 同章节真实冲突数为 0；
- 沙箱复检无残余确定性 finding；
- 沙箱复检无新增确定性 finding；
- `32 participants` 保持不变，未出现错误的 `36 participants`；
- 终末 PK 采样时间在受影响位置由 `32 hours` 更新为 `36 hours`；
- 最终回归中 3 个证据不足的语义问题被转换为专业决策请求，而非自动改写。

由于模型输出具有随机性，连续真实回归中原始建议数量和专业决策请求数量会发生变化，但安全不变量保持一致。最终 run 为 `run-20260717180303-10544e`：7 个合成补丁、0 个冲突、0 个残余确定性 finding、0 个新增回归、3 个专业决策请求。

此外，将上一轮真实 API 曾生成的“依据待审核 F018 统一饮水规则”建议原样回放到新门控：系统识别出 2 个未授权候选，阻止 F018 进入任何最终补丁，并把问题保留为专业决策请求。回放证据保存于 `outputs/nct04683926_adjusted_v2_20260718/validation/authorization_gate_replay/`。

## 8. 测试覆盖

新增测试覆盖：

- 同章节非重叠编辑可组合；
- 重叠且不同的编辑不会静默合并；
- 语义歧义会转换为 DecisionRequest；
- C/D 循环只返工冲突 finding；
- 沙箱复检可检测残余问题和新回归；
- 未处理的 DecisionRequest 阻止正式批准；
- 合格审核决定被单独落盘并进入审计日志。
- 待审核事实不能作为语义自动修订的授权依据；
- 未解决歧义不会生成可复用经验候选。

当前完整回归：`37 passed`。唯一警告来自 Starlette TestClient 的上游弃用提示，不影响本次修订逻辑。

## 9. 方法依据

- [Self-Refine](https://arxiv.org/abs/2303.17651)：生成、反馈、迭代修订的循环结构；
- [Reflexion](https://arxiv.org/abs/2303.11366)：将失败反馈转化为下一轮行动条件，而非无条件重复；
- JSON Patch / 操作级补丁思想：以最小操作表达修改，使冲突检测和审计可计算；
- Human-in-the-loop：当证据不能唯一确定文本时，以显式决策请求终止机器循环。

本实现没有直接复制通用 agent 的自由文本循环，而是将其约束为临床文档工程中的可验证状态转移。
