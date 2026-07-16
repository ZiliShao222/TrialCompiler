# Memory and agent research index

Only primary papers, official project pages, official repositories, and official product documentation should be promoted into design evidence.

| Topic | Source | Use in TrialCompiler |
| --- | --- | --- |
| Semantic cache | [Cortex, NSDI 2026](https://www.usenix.org/system/files/nsdi26-ruan-cortex.pdf) | Semantic Elements, two-stage retrieval, cache metadata, LCFU-inspired lifecycle |
| Long-term memory | [Mem0](https://arxiv.org/abs/2504.19413) | Salient extraction, consolidation, retrieval, graph extension, efficiency evaluation |
| Agentic memory | [A-MEM](https://arxiv.org/abs/2502.12110) | Atomic structured notes and dynamic memory links |
| Workflow reuse | [Agent Workflow Memory](https://arxiv.org/abs/2409.07429) | Induce and selectively replay reusable procedures |
| Experience learning | [ExpeL](https://arxiv.org/abs/2308.10144) | Extract natural-language insights from success and failure without fine-tuning |
| Verbal feedback | [Reflexion](https://arxiv.org/abs/2303.11366) | Store task feedback as episodic reflection, with TrialCompiler adding human approval |
| Feishu AI workflow | [Aily feature overview](https://www.feishu.cn/content/ap8ie3h2) | Structured workflow nodes, clarification, and typed outputs |
| Feishu question node | [Aily question node](https://www.feishu.cn/content/v9fw8kv2) | Natural-language clarification and field extraction |
| Feishu server integration | [Aily session API](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/aily-v1/aily_session/create) | Production conversation/run integration boundary |

## Implementation rule

Research ideas are adopted only when they solve a measured failure mode. The MVP therefore implements the storage contract, gating, lifecycle metadata, and reproducible tests before adding a vector database or training a new model.
