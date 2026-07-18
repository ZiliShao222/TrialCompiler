# Agent 不确定性与可解释性：TrialCompiler 文献审计与研究定义

> 状态：研究定义稿，不是已完成实验报告。检索与复核日期：2026-07-18。

## 1. 先纠正四个概念混用

1. 来源冲突、证据缺失和权限不足是任务中的诊断信号或治理状态，不等同于标准 UQ 类别。
2. 模型自报 confidence、多次采样一致性、semantic entropy、verifier disagreement 和校准概率是不同量，不能互换。
3. provenance 说明用了哪些来源，observability 说明执行了哪些步骤，二者不自动构成 faithful explanation。
4. 自然语言 rationale 或 CoT 具有 plausibility 不代表它忠实反映了模型实际决策依据。

## 2. Agent UQ 的对象

单轮 LLM UQ 通常研究给定输入后输出答案的不确定性；Agent UQ 研究连续 action、observation 与 environment state 构成的轨迹。Agent 可以通过工具、澄清和外部来源获得新信息，因此不确定性既会传播，也可能被动作条件化地约减。现有综述指出四个特有难点：估计器选择、异构实体的不确定性、交互过程中的动态传播/约减，以及缺少细粒度 benchmark。

本项目采用两个正交维度描述估计对象：

- kind：epistemic（原则上可通过信息或推理约减）与 aleatoric（来自环境或观察过程的不可约随机性）；
- locus：observation、belief state、next action、trajectory outcome。

每个数值估计还必须声明 target event，例如“候选 patch 通过独立验证”，而不是脱离事件写一个 confidence。只有在独立 calibration dataset 上验证过的输出才标记 calibrated。

## 3. 可用估计信号及限制

- token likelihood/NLL：成本低，但自由文本长度与措辞会混入信号。
- verbalized confidence：黑盒模型易用，但常过度自信；不能天然视为校准概率。
- answer instability/self-consistency：多次采样的最终答案变化是标签无关信号，但稳定错误无法被发现。
- semantic entropy：在语义等价类而不是字符串上测量分散，可检测部分 confabulation；需要多次采样与语义聚类，同样不能发现一致性错误。
- source/verifier disagreement：适合当前任务，但需要处理多个 verifier 的相关错误，不能把多数票直接当概率。
- learned trajectory calibrator：可利用早期不确定性、跨步梯度和稳定性，但需要有标签轨迹，存在分布漂移问题。
- conformal methods：可提供特定假设下的 coverage/risk 控制，但必须声明 calibration population、exchangeability 条件、nonconformity score 和覆盖事件。

评估不能只报 accuracy。至少需要 Brier、ECE 或 rank-calibration 检验数值/排序质量，并用 risk–coverage curve 与 AURC 检验拒答后保留样本的风险。长轨迹还要报告 end-state、average 与 weakest-link 等不同聚合方式，避免平均值掩盖一个致命步骤。

## 4. 从被动估计到 Agent 行动

Agentic 的关键不是展示 uncertainty，而是让它选择动作。相关研究包括增加推理预算、澄清、工具选择、拒答、转交和 prediction set。Structured Uncertainty guided Clarification 将工具参数的不确定性与 EVPI 结合选择澄清问题；Agent UQ 文献强调信息获取造成的条件不确定性下降；selective prediction 研究 accuracy–coverage 权衡；conformal factuality 通过逐步降低回答具体性扩大不确定集。

TrialCompiler 对应的潜在状态不是患者诊断，而是“当前文档集合中应当生效的规范事实”。Protocol、SAP、ICF、注册记录和人工确认都是带版本、权威和噪声的 observation。动作空间为：获取指定来源、请求专业确认、增加语义采样/验证预算、提出候选 patch、拒答、转交人工。

最小研究算法是有限 hypothesis belief 上的 expected information gain：

`EIG(a) = H(B_t) - E_o[H(B_{t+1} | a,o)]`

选择 `EIG(a) - lambda * cost(a)` 为正且最大的证据动作。该公式只在明确给出 observation model/posterior 的实验案例上使用，不能用 LLM 随口生成的数字冒充概率模型。

## 5. 可解释性与忠实性

需要分开评价：

- provenance：事实、finding、patch 与来源是否可追溯；
- transparency/observability：是否完整记录实际 action、tool result 和 state transition；
- plausibility：人是否觉得解释合理；
- faithfulness：解释是否准确描述真正影响系统行为的因素；
- causal/mechanistic explanation：是否有资格声称内部或结构因果关系。

现有研究表明 LLM self-explanation 的忠实性随模型、任务与解释形式变化，不能默认信任。多 Agent 失败归因 benchmark 也显示，模型很难准确定位导致失败的具体步骤。对黑盒 TrialCompiler，当前可实现的是 behavioral counterfactual faithfulness：移除被声称必要的证据、替换为对立证据，然后以固定配置重放 finding/action/patch 决策。

建议报告：

- necessity flip rate：移除“必要证据”后结果是否改变；
- contrastive sensitivity：替换为对立证据后是否转向预期竞争假设；
- sufficiency/comprehensiveness：保留/移除解释证据时性能变化；
- replay variance：随机重放下干预效应的均值与区间；
- unsupported-rationale rate：解释中不存在于实际 trace/source 的主张比例。

这些只能支持行为层反事实结论。没有结构因果模型和受控干预设计时，不写“证明了模型内部因果机制”。

## 6. 医疗场景给出的额外约束

医疗 XAI 文献警告，流畅的 post-hoc explanation 可能扩大系统行为与可正当化主张之间的 epistemic gap。临床用户还需要任务、角色和工作流匹配的解释；单纯增加解释可能制造 automation bias。近期医疗 LLM UQ benchmark 也观察到 accuracy、calibration 和 discrimination 并不总同步，不同医学问题类型差异明显。

TrialCompiler 处理的是临床研究文档，而不是患者诊断，因此不能挪用“诊断准确率”包装成果。专业终点应该是：冲突 finding 正确率、选择性 patch 风险、专业升级召回率、每次正确闭合的证据成本、负对照保护，以及解释干预能否预测系统行为。

## 7. 最适合 TrialCompiler 的研究问题

**RQ1：** 与固定 RAG 和被动 UQ 相比，不确定性驱动的证据获取能否在相同证据成本下提高跨文档事实调和准确率？

**RQ2：** action/trajectory-level UQ 是否比 final-answer confidence 更好地预测错误 patch，从而改善 risk–coverage？

**RQ3：** evidence-removal/replacement replay 能否识别“来源可追溯但解释不忠实”的 patch？

**RQ4：** 携证门禁能否在保持 finding recall 的同时，把错误自动提交率控制为零或预设上限？

## 8. 实验矩阵

- A：deterministic rules only；
- B：single-shot LLM；
- C：fixed RAG + LLM；
- D：fixed RAG + passive UQ/abstention；
- E：uncertainty-guided evidence acquisition；
- F：E + counterfactual explanation gate。

数据应包含原始一致案例、人工验证矛盾、合成单事实扰动、跨来源权威冲突、缺失来源、过期来源和负对照。划分 calibration/test，避免使用 test gold 调阈值。除 finding 指标外，报告 Brier/ECE/rank-calibration、AURC、取证次数与成本、信息增益、错误提交率、defer recall，以及解释 flip/sensitivity 指标。

## 9. 当前实现审计

已具备：来源绑定、文档图、确定性 finding、负对照、候选 patch 沙箱、决策请求、完整 trace、携证阻断与重放基础。

尚未具备：真实多采样 UQ、独立 calibration set、trajectory calibrator、可验证 observation model、主动取证闭环、干预重放统计、解释 faithfulness benchmark。

因此当前代码只能提供研究接口和 deterministic reference implementation，不能宣称已经完成 UQ/XAI 实验。`simulated reviewer confidence` 是规则分数，必须从 calibration 结果中排除。

## 10. 主要文献

本综述的可复用文献库位于 `references/inbox/agent_uncertainty_xai/`。正文与后续报告优先使用 `AUQ-*`、`XAI-*`、`MEDXAI-*` 稳定编号；题录、主链接、本地状态与适用边界见 `references/metadata/agent_uncertainty_xai_sources.tsv`，正式参考文献可直接导入 `references/metadata/agent_uncertainty_xai.bib`。本地 PDF 的 SHA-256 与解析页数记录在 `references/metadata/agent_uncertainty_xai_checksums.tsv`。这些论文用于支持研究问题和实验方法，不替代法规、指南或项目自身的验证证据。

- Oh et al. (2026), *Uncertainty Quantification in LLM Agents: Foundations, Emerging Challenges, and Opportunities*, arXiv:2602.05073.
- Zhang et al. (2026), *Agentic Uncertainty Quantification*, arXiv:2601.15703.
- Zhang et al. (2026), *Agentic Confidence Calibration*, ICML 2026.
- Farquhar et al. (2024), *Detecting hallucinations in large language models using semantic entropy*, Nature 630.
- Huang et al. (2024), *Uncertainty in Language Models: Assessment through Rank-Calibration*, EMNLP 2024.
- Mohri and Hashimoto (2024), *Language Models with Conformal Factuality Guarantees*, ICML 2024.
- Suri et al. (2025/2026), *Structured Uncertainty guided Clarification for LLM Agents*, arXiv:2511.08798.
- Madsen et al. (2024), *Are self-explanations from Large Language Models faithful?*, Findings of ACL 2024.
- Lyu et al. (2024), *Towards Faithful Model Explanation in NLP*, Computational Linguistics 50(2).
- Zhang et al. (2025), *Which Agent Causes Task Failures and When?*, arXiv:2505.00212.
- Chen et al. (2022), *Explainable medical imaging AI needs human-centered design*, npj Digital Medicine.
- Afolabi et al. (2026), *Faithful or Just Plausible? Evaluating the Faithfulness of Closed-Source LLMs in Medical Reasoning*, ML4H 2026.
