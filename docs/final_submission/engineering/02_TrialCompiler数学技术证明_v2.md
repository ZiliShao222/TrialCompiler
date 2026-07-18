# TrialCompiler 数学技术证明（v2）

## 0. 文档定位

本文给出 TrialCompiler 当前原型的形式化描述、关键正确性命题与可复现实验对应。与旧版数学分析相比，本版做三项修正：

1. 严格区分当前代码已经实现的性质与未来可能训练的目标函数；
2. 将抽象公式落实到 Trial Fact Sheet、Clinical Document Graph、确定性规则、质量门和 benchmark scorer；
3. 使用 NCT04683926 与 Metformin-PAD 的实际运行结果验证推导，不把语言模型自评分视为证明。

本文证明的是工程控制性质：在明确假设下，系统能够保持来源、状态和变更传播的可审计性，能够阻断一组已编码的严重矛盾。本文不证明生成内容具有普适临床正确性，也不证明系统可以替代合格专业人员。

## 1. 形式化对象

### 1.1 来源、事实与文档单元

设授权来源集合为

$$
\mathcal{S}=\{s_1,\ldots,s_m\},
$$

每个来源表示为

$$
s_i=(id_i,locator_i,version_i,authority_i,scope_i).
$$

设事实集合为

$$
\mathcal{F}=\{f_1,\ldots,f_n\},
$$

其中

$$
f_i=(id_i,key_i,value_i,status_i,source_i,owner_i,version_i,previous_i).
$$

`status` 属于有限状态集合：

$$
\Sigma=\{draft,proposed\_change,requires\_human\_review,approved,rejected,superseded\}.
$$

文档单元集合为

$$
\mathcal{U}=\{u_1,\ldots,u_k\},
$$

一个文档单元可以是 Protocol 章节、SoA 表格、SAP 规则、ICF 表述、CRF 字段或注册记录。

### 1.2 依赖矩阵与文档图

定义事实到文档单元的依赖矩阵

$$
A\in\{0,1\}^{n\times k},\qquad
A_{ij}=1 \iff u_j\text{ 引用或依赖 }f_i.
$$

Clinical Document Graph 可写为

$$
G=(V,E),\qquad V=\mathcal{S}\cup\mathcal{F}\cup\mathcal{U}\cup\mathcal{I}\cup\mathcal{R}\cup\mathcal{H},
$$

其中 $\mathcal{I}$ 为 findings，$\mathcal{R}$ 为 repair proposals，$\mathcal{H}$ 为人工决定。边至少包括：

$$
source\rightarrow fact,\quad fact\rightarrow unit,\quad finding\rightarrow fact,\quad repair\rightarrow finding.
$$

对事实 $f_i$，其影响集合为

$$
Impact(f_i)=\{u_j\in\mathcal{U}:A_{ij}=1\}.
$$

这一定义直接对应代码中的 `fact_to_sections` 与 `impact_set`。

## 2. 三个系统不变量

### 不变量 I：来源可追溯性

对任何进入正式审核状态的事实 $f_i$，必须满足

$$
source_i\neq\varnothing
$$

且

$$
\forall s\in source_i,\quad s\in\mathcal{S}\land locator(s)\neq\varnothing.
$$

这意味着事实不能只有模型生成的文字而没有可定位来源。

### 不变量 II：状态不可由置信度替代

设模型对事实正确性的置信度为 $p_i$。事实可驱动正式修改的必要条件不是 $p_i>\tau$，而是

$$
Effective(f_i)=
\mathbf{1}[status_i=approved]
\cdot\mathbf{1}[source_i\neq\varnothing]
\cdot\mathbf{1}[QualifiedOwner(owner_i)].
$$

即使 $p_i=0.99$，只要未被合格角色批准，$Effective(f_i)=0$。

### 不变量 III：硬门禁不可由软分数抵消

设语言模型质量分为 $Q_{LLM}\in[0,100]$，确定性阻断 finding 数为 $B\ge0$。系统的释放函数定义为

$$
Release(X)=\mathbf{1}[B(X)=0]\cdot\mathbf{1}[HumanGate(X)=1].
$$

因此：

$$
B(X)>0\Longrightarrow Release(X)=0,
$$

与 $Q_{LLM}$ 的数值无关。

**命题 1（非补偿性）**：不存在任何有限的语言质量增量 $\Delta Q$ 能使一个含阻断 finding 的状态自动释放。

**证明**：若 $B(X)>0$，则第一指示函数为 0，故 $Release(X)=0$。$Q_{LLM}$ 不出现在释放函数的乘积项中，因此任意 $\Delta Q$ 均不改变结果。证毕。

该命题对应 Phase 2 中 `blocked_machine_gate` 对 LLM judge 的强制覆盖。

## 3. 变更传播的正确性

### 3.1 候选变更

设事实 $f$ 从旧值 $v_0$ 变为候选值 $v_1$：

$$
\Delta f=(f,v_0\rightarrow v_1).
$$

系统不直接删除 $v_0$，而是保存

$$
previous(f)=v_0,\quad value(f)=v_1,\quad status(f)=proposed\_change.
$$

对每个 $u\in Impact(f)$，定义旧值残留谓词：

$$
Stale(u,f)=\mathbf{1}[Contains(u,v_0)].
$$

系统生成 finding 集合

$$
F_{stale}(f)=\{u\in Impact(f):Stale(u,f)=1\}.
$$

### 3.2 完备性命题

**假设 A1**：依赖矩阵 $A$ 完整，即所有真实依赖单元均被登记。

**假设 A2**：`Contains` 对待检测的原子旧值无漏检。

**命题 2（旧值残留检查的完备性）**：在 A1、A2 下，所有依赖于 $f$ 且仍包含 $v_0$ 的单元都会进入 $F_{stale}(f)$。

**证明**：任取真实依赖且包含旧值的单元 $u_j$。由 A1，$A_{fj}=1$，故 $u_j\in Impact(f)$；由 A2，$Stale(u_j,f)=1$。根据集合定义，$u_j\in F_{stale}(f)$。证毕。

### 3.3 健全性命题

**假设 A3**：`Contains(u,v_0)=1` 仅当 $v_0$ 在 $u$ 中代表该事实，而非无关同值。

**命题 3（旧值残留检查的健全性）**：在 A1、A3 下，$F_{stale}(f)$ 中不存在与 $f$ 无关的单元。

**证明**：任取 $u\in F_{stale}(f)$。集合定义要求 $u\in Impact(f)$ 且 `Contains` 为真。前者说明存在依赖，A3 排除同值但不同语义的情况，因此 $u$ 是真实残留位置。证毕。

实际系统不能保证 A1 和 A3 对所有自由文本恒成立，因此 benchmark 同时报告 Impact Recall 与负对照准确率，而不是宣称规则绝对正确。

## 4. 最小修订与原子补丁

设原文档为 $Y$，目标 finding 集合为 $I$，候选文档为 $Y'$。理想修订满足：

$$
\min_{Y'} D_{edit}(Y,Y')
$$

约束为

$$
Unresolved(Y',I)=0,
$$

$$
NewRegression(Y',Y)=0,
$$

$$
Traceable(Y')=1.
$$

系统把每个修订表示为原子操作

$$
o=(section,start,end,before,after,fact\_ids,source\_ids).
$$

若两个操作 $o_a,o_b$ 的区间不重叠，则可交换：

$$
[start_a,end_a)\cap[start_b,end_b)=\varnothing
\Longrightarrow o_a\circ o_b=o_b\circ o_a.
$$

**命题 4（非重叠补丁可合并）**：若所有原子操作区间两两不重叠，且每个操作的 `before` 与原文一致，则按位置有序应用不会互相覆盖。

**证明说明**：不相交区间修改不同字符集合；从高偏移到低偏移应用可避免前一操作改变后一操作的坐标，因此所有替换均保留。若区间重叠，则交换律不成立，系统不自动选择，而生成 `DecisionRequest`。

这解释了为何 TrialCompiler 采用最小红线和冲突合并，而不是让多个 Agent 顺序重写整章。

## 5. 数值边界检查

### 5.1 严格不等式与实际日程

在 NCT04683926 案例中，一处文本声明给药间隔

$$
\Delta d>3\text{ days},
$$

而给药日为

$$
D=(1,4,7,10).
$$

相邻差分为

$$
\nabla D=(4-1,7-4,10-7)=(3,3,3).
$$

因此

$$
\min(\nabla D)=3\not>3.
$$

**命题 5**：给药日 1、4、7、10 与“greater than 3 days”不能同时为真。

该问题不依赖语言模型推理，可由确定性规则稳定发现。这里必须区分 $>3$ 与 $\ge3$，否则会出现边界漏检。

### 5.2 合法双时间轴负对照

Protocol 使用连续时间轴

$$
T_P=\{-1,1,4,7,10,11\},
$$

CRF/SAP 使用 period-specific 表示，每个 Period 内给药日记为 Day 1。设映射

$$
\phi(period_i,day\ 1)=D_i,
$$

其中 $D_i\in\{1,4,7,10\}$。只要 $\phi$ 被明确记录且两个时间轴事实均获批准，两种表示是坐标变换而非矛盾。

因此系统使用负对照约束：

$$
Approved(F022)\land Approved(F023)\land MappingExists
\Longrightarrow Conflict=0.
$$

该约束使 NCT 案例的双时间轴误报被消除。

## 6. 样本量可复现性证明

### 6.1 正态近似

对等比例双臂连续型结局，设两组均值差为 $\delta$，共同标准差为 $\sigma$，双侧显著性水平为 $\alpha$，目标 power 为 $1-\beta$。每组可评价样本量近似为

$$
n_{arm}=2\times((z_{1-\alpha/2}+z_{1-\beta})\sigma/\delta)^2.
$$

若脱落率为 $r$，总随机样本量为

$$
n_{total}=ceil(2n_{arm}/(1-r)).
$$

### 6.2 Metformin-PAD 代入计算

冻结产物给出：

$$
\delta=20\text{ m},\quad \sigma=65\text{ m},\quad \alpha=0.05,
$$

$$
1-\beta=0.85,\quad r=0.15.
$$

查标准正态分布：

$$
z_{0.975}\approx1.960,\qquad z_{0.85}\approx1.036.
$$

于是

$$
n_{arm}\approx2\times(((1.960+1.036)\times65)/20)^2\approx189.6,
$$

$$
n_{total}\approx ceil((2\times189.6)/0.85)\approx447.
$$

因此生成文本中的 $n=220$ 无法由其自身给出的参数复现。

若仍使用 $n=220$，近似 achieved power 为

$$
Power\approx\Phi(\delta\sqrt{n(1-r)/(4\sigma^2)}-z_{1-\alpha/2})\approx0.557.
$$

**命题 6**：在上述简化双臂正态近似假设下，$n=220$ 不足以达到 85% power。

该证明只用于检查“文本中的数字能否相互复现”。若专业统计方案采用 MMRM、协变量调整或模拟得到其他样本量，必须提供可执行假设和输出，系统不能用此近似公式替代正式统计设计。

## 7. Estimand 与分析集的一致性

设 estimand 的目标人群为所有随机化受试者：

$$
P_E=\{x:x\text{ 被随机化}\}.
$$

若 FAS 要求至少用药一次且至少有一次基线后测量：

$$
P_{FAS}=\{x:x\text{ 随机化}\land dose(x)\ge1\land postbaseline(x)\ge1\}.
$$

显然

$$
P_{FAS}\subseteq P_E.
$$

只要存在随机化后未用药或无基线后测量的受试者，便有

$$
P_{FAS}\subsetneq P_E.
$$

**命题 7**：若 estimand 声称针对所有随机化受试者，而实现它的分析集排除部分随机化受试者，则分析集不能完整实现该 estimand 人群定义。

系统因此触发 `DET-STAT-002`，但不会自动决定应修改 estimand 还是 FAS；该选择属于合格统计人员的责任。

## 8. 终末事件不是普通 MAR 缺失

令 $Y_t$ 为时间 $t$ 的功能结局，$D_t=1$ 表示受试者在 $t$ 前死亡。死亡后 $Y_t$ 不是“虽然存在但未观测”的普通随机变量，而可能在临床定义上不存在。若直接设

$$
Y_t\mid D_t=1\sim MAR
$$

并执行普通多重插补，就隐含假设死亡后的功能结局可由存活者观测分布合理生成，这通常缺乏临床可解释性。

因此系统采用保守规则：文本同时出现 death、MAR 和 multiple imputation 时触发 `DET-STAT-004`，要求明确 composite、while-on-treatment、hypothetical 或其他适当 intercurrent-event 策略及敏感性分析。

这是一条风险检测规则，不是对所有 estimand 策略的数学裁决。

## 9. Benchmark 评分与改进证明

### 9.1 基本指标

设 TP、FP、FN、TN 分别为真阳性、假阳性、假阴性和真阴性：

$$
Precision=TP/(TP+FP),\qquad Recall=TP/(TP+FN),
$$

$$
F1=2PR/(P+R).
$$

NCT04683926 初始评分：

$$
TP=4,\quad FP=2,\quad FN=4,\quad TN=1,
$$

故

$$
Precision=4/6=0.6667,
$$

$$
Recall=4/8=0.5000,
$$

$$
F1=0.5714.
$$

加入数值边界、跨来源时长/筛选窗口、来源链完整性及合法时间轴负控后：

$$
TP=8,\quad FP=1,\quad FN=0,\quad TN=2,
$$

因此

$$
Precision=8/9=0.8889,
$$

$$
Recall=8/8=1.0000,
$$

$$
F1=(2\times0.8889\times1)/(0.8889+1)=0.9412.
$$

### 9.2 改进幅度

绝对 F1 增量为

$$
\Delta F1=0.9412-0.5714=0.3698.
$$

相对增幅约为

$$
0.3698/0.5714\approx64.7\%.
$$

同时负对照准确率从 0.5 提升到 1.0，说明提升并非简单通过“报告更多问题”换取 Recall，而是同时消除了已知时间轴误报。

不过该 benchmark 只有 10 个 gold tests。样本规模过小，不应报告窄置信区间或将结果外推到其他治疗领域。正确结论是：在同一冻结案例和同一 scorer 下，新增规则修复了全部已知 FN，并消除了已知负控误报。

## 10. 整改闭环的终止条件

设阻断 finding 集为 $B_t$，每条 finding 对应一个整改工单 $w_i$，其退出条件谓词为 $Exit(w_i)$。系统允许进入独立质量审核的条件为

$$
Ready_t=
\mathbf{1}[B_t=\varnothing]
\prod_i\mathbf{1}[Exit(w_i)=1].
$$

整改序列为

$$
qualified\ decision
\rightarrow fact\ update
\rightarrow propagation
\rightarrow revalidation
\rightarrow independent\ review.
$$

高风险工单设置

$$
AutomaticApply(w_i)=0,
$$

因此系统可以自动生成整改要求和重检结果，但不能自动批准样本量、estimand 或监管路径。

若每轮至少关闭一个 finding，且不产生新 finding，则 $|B_t|$ 严格递减，最多经过 $|B_0|$ 轮达到空集；若产生新 finding、证据不足或专业意见冲突，则系统转入人工决策而不是无限自循环。

## 11. 当前证明覆盖与未证明事项

### 11.1 当前可由代码与测试支持

- 类型化来源、事实、章节、finding、repair 和 decision request；
- 事实到章节的显式依赖与影响集合；
- NCT 标识符、Week、严格数值边界和旧值残留等确定性检查；
- 原子补丁合并和重叠冲突升级；
- Phase 1/Phase 2/Evaluator-only 可见性隔离与 checkpoint digest；
- 样本量、合成监管权威化、estimand/FAS、多重性和终末事件门禁；
- 独立 gold scorer 与负对照；
- 当前 65 项自动化测试通过。

### 11.2 尚不能证明

- 对任意临床文档均能完整抽取所有事实；
- 对任意跨文件语义冲突均有高 Recall 与高 Precision；
- 当前规则覆盖所有统计或监管风险；
- 语言模型判断具有稳定跨领域校准；
- 系统能够替代医学、统计、注册或质量人员；
- 小规模公开/合成 benchmark 的结果可以代表生产性能。

## 12. 结论

TrialCompiler 当前最可靠的数学描述不是“一个自动写 Protocol 的生成模型”，而是一个带硬约束的文档状态转换系统：

$$
X_{t+1}=T(X_t,a_t;G,S,H),
$$

其中 $G$ 是显式文档依赖图，$S$ 是带来源和状态的事实集合，$H$ 是人工治理状态。系统优先保持三个不变量：来源可追溯、状态不可由模型置信度替代、硬门禁不可由软分数抵消。

在依赖登记和原子匹配正确的假设下，旧值传播检查具有可证明的完备性与健全性；在不重叠区间假设下，原子补丁可以安全合并；样本量、严格时间边界和集合包含关系可以通过确定性计算复核；独立 benchmark 证明新增规则在 NCT04683926 小型测试集上将 F1 从 0.5714 提升到 0.9412，并同时提高负对照准确率。

因此，本项目的技术贡献不在于宣称 AI 已经获得临床专业正确性，而在于把模型输出置于一个可表示、可检查、可阻断、可回放并最终由专业人员批准的工程体系中。
