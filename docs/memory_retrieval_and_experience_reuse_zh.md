# TrialCompiler 记忆检索与经验复用技术设计

- 版本：v0.1
- 日期：2026-07-17
- 状态：MVP 已实现，向量 ANN 与模型语义判别器待替换

## 1. 目标

TrialCompiler 的记忆层不是“把所有历史文本塞进提示词”，而是解决两个不同问题：

1. 在大量监管材料、企业规范、项目事实与历史审阅中，低延迟地找到可能相关的少量候选。
2. 在候选中严格判断哪一条在当前文档类型、地区、治疗领域、章节、版本和权限下可以安全复用。

临床文档场景中，语义相似不等于可复用。例如，同样讨论“主要终点评估时间”的两条经验，可能分别适用于不同适应证、不同版本或不同地区。错误命中比缓存未命中更危险。因此系统选择“高召回粗筛 + 高精度复核 + 权限与有效期门控”，而不是单阶段 Top-K RAG。

## 2. 从参考研究中吸收的设计

### 2.1 Cortex：Semantic Element 与两阶段 Seri

Cortex 将可复用交互表示为 Semantic Element：语义键是规范化查询或工具输入，值是已获取的响应，并记录 staticity、frequency、cost、size、latency 等元数据。其 Seri 检索先由 ANN 提供高召回候选，再由轻量语义模型判断新旧请求是否真正等价。

TrialCompiler 采用同一原则，但增加临床治理字段：

- `document_type`
- `section_type`
- `jurisdiction`
- `therapeutic_area`
- `authority`
- `approval_status`
- `valid_from / valid_until`
- `source_ids`
- `access_scope`

这些字段不是排序装饰，而是候选进入模型上下文之前的硬门。

### 2.2 Mem0：提取、整合与持久化

Mem0 的启发是：长期记忆应提取高价值内容并持久化，而不是反复携带完整历史。TrialCompiler 因此把完整审阅轨迹与可复用经验分开：轨迹长期保存用于审计；只有经过压缩、结构化和人工批准的 Decision Capsule 才能进入经验检索空间。

### 2.3 A-MEM：原子笔记与动态关联

A-MEM 使用带上下文、关键词、标签和链接的原子记忆。TrialCompiler 的 Decision Capsule 同样保持原子性，并通过触发条件、章节、文档类型、来源和适用范围建立链接。后续版本可以把当前 SQLite 表扩展为事实、缺陷、决策、证据之间的图，而不改变上层接口。

### 2.4 Agent Workflow Memory：复用流程而非只复用答案

AWM 从历史任务中归纳可复用工作流。TrialCompiler 不只保存“应改成 Week 16”这样的实例答案，而保存“当已批准核心事实改变时，遍历依赖图、生成跨章节红线、保留来源并请求签核”的处理程序。这样经验可以迁移到不同数值和不同文档。

### 2.5 ExpeL 与 Reflexion：从反馈中学习，但不自动升级权限

ExpeL 将成功与失败经验提炼成自然语言知识，Reflexion 将反馈写入情景记忆。TrialCompiler 保留这种“无需微调即可从反馈学习”的优点，但加了一道治理边界：F Agent 只能生成候选经验，不能把自己的反思直接提升为批准规则。

## 3. 三段式查询

```text
精确规范键命中
      |
      v
粗筛索引（MVP: SQLite FTS5；后续: hybrid ANN + BM25）
      |
      v
元数据门（权限、版本、有效期、范围、批准状态）
      |
      v
语义等价判别（MVP: 保守本地判别；后续: 小模型二分类器）
      |
      v
已验证 hit / miss + 审计事件
```

### 3.1 粗筛

MVP 使用 SQLite FTS5 和规范键索引，避免为了演示引入独立向量服务。接口已经抽象为 `RetrievalQuery`，可在不改 Agent 的前提下替换为：

- BM25 + dense embedding 混合检索；
- HNSW / FAISS / Qdrant；
- 基于文档结构的分层索引；
- 查询分解后的并行检索。

粗筛目标是高召回，不直接构成缓存命中。

### 3.2 元数据门

系统在语义判别前拒绝以下候选：

- 未经人工批准的经验；
- 已过期或有效期无效的规则；
- 文档类型不匹配；
- 章节类型不匹配；
- 地区或治疗领域不匹配；
- 权限范围不允许当前任务访问。

该门可以减少错误记忆进入模型后造成的指令漂移和越权引用。

### 3.3 精细语义判别

精细判别回答的是“这个缓存值是否可以直接回答当前请求”，而不是“两个文本是否讨论相同主题”。输出必须是：

```json
{
  "admitted": false,
  "confidence": 0.87,
  "reasons": ["same topic but different jurisdiction"]
}
```

MVP 的确定性判别便于离线测试；正式实验应比较：

1. 单阶段 BM25；
2. 单阶段向量 Top-K；
3. Hybrid retrieval；
4. Hybrid + 元数据门；
5. Hybrid + 元数据门 + 小模型语义判别。

## 4. 缓存生命周期

每次候选判定都会写 `retrieval_events`。只有通过完整链路的候选才增加 frequency。清理策略采用 LCFU 思路，综合：

- 访问频率；
- 最后访问时间；
- 重新获取成本；
- 外部调用延迟；
- 内容大小；
- 稳定性；
- 来源权威度与批准状态。

高权威且已批准的监管或企业知识受到额外保护。模型临时输出、低频且可低成本重建的内容优先淘汰。

## 5. 快速利用经验知识

### 5.1 Decision Capsule

```json
{
  "trigger": "canonical_fact_conflict",
  "conditions": {
    "document_type": "protocol",
    "section_type": "any",
    "jurisdiction": "CN"
  },
  "recommendation": "遍历依赖章节并生成带来源的最小红线",
  "rationale": "只改一处会保留跨章节矛盾",
  "evidence_source_ids": ["source-id"],
  "status": "approved",
  "valid_until": null
}
```

它比整段历史对话更快、更稳，也更容易撤销和版本化。

### 5.2 Action Card

B Agent 在一个任务开始时只检索一次经验，并把命中的 Decision Capsule 编译成短 Action Card。C 和 D 共享同一组卡片，不重复查询，也不加载无关历史。卡片只包含触发条件、建议、理由、证据和命中分数。

### 5.3 写回流程

```text
Agent 完成一次修订
  -> D Agent 通过质量门
  -> 专家接受/拒绝/改写
  -> F Agent 生成候选胶囊
  -> 专家补充适用条件与有效期
  -> 批准后进入经验索引
  -> 后续可撤销、过期或被新版替代
```

未经人工确认的候选只可用于离线分析，不能指导后续真实审阅。

## 6. 当前实现

- `src/trialcompiler/memory/semantic_store.py`：Semantic Element、FTS5 粗筛、元数据门、精细判别接口、命中日志和 LCFU 清理。
- `src/trialcompiler/memory/experience.py`：Decision Capsule 的候选、批准、检索和 Action Card 编译。
- `prompts/memory/semantic_fine_judge.md`：未来模型判别器契约。
- `tests/test_memory.py`：批准状态、过期时间和清理策略测试。

## 7. 下一轮研究指标

| 指标 | 含义 |
| --- | --- |
| Candidate Recall@K | 正确经验是否进入粗筛候选 |
| Admission Precision | 通过精细门的经验中真正可复用的比例 |
| Wrong-scope Admission Rate | 地区、版本或章节不匹配仍被接纳的比例 |
| p50 / p95 Retrieval Latency | 检索延迟 |
| Context Tokens Saved | 相对完整历史提示减少的 token |
| External Fetches Avoided | 有效缓存减少的外部调用数 |
| Human Acceptance Delta | 使用经验后修订建议的一次接受率变化 |
| Memory-induced Error Rate | 使用记忆后新引入错误的比例 |

只有同时改善准确性、延迟和人工接受率，才能说明经验层真正有效。
