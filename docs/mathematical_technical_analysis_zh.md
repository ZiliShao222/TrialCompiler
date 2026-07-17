# TrialCompiler 数学技术分析：全局目标对齐与局部文档编译

- 项目名称：TrialCompiler
- 文档性质：技术原理、算法设计与评测框架
- 版本：v1.0
- 日期：2026-07-17
- 当前验证边界：公开资料桌面研究与完全合成数据评测

> 本文从数学角度统一描述 TrialCompiler。它既讨论事实抽取、检索、依赖图、缺陷检测和修复等局部技术，也讨论系统是否持续服务于临床文档正确性、可追溯性、专业责任和审核效率等全局目标。本文中的部分目标函数属于后续训练与评测设计，不代表当前 MVP 已经训练了对应模型。

## 1. 核心问题

TrialCompiler 面对的不是普通文本生成问题，而是一个**具有来源、版本、依赖、权限和人工审批约束的序列决策问题**。

设初始资料和文档状态为 (X_0)，系统经过事实提取、知识检索、候选编制、缺陷检查、修复和人工审核后形成状态序列：

$$
\tau=(X_0,X_1,\ldots,X_T).
$$

第 (t) 步的操作为 (a_t)，状态转移为：

$$
X_{t+1}=\mathcal{T}(X_t,a_t,\Gamma,M_t,H_t),
$$

其中：

- (Gamma)：项目级全局目标与边界；
- (M_t)：规则、证据和受控经验记忆；
- (H_t)：人工确认、拒绝、修改和审批状态；
- (mathcal{T})：文档编译与审核状态转移函数。

普通生成系统主要优化：

$$
\operatorname{Quality}_{local}(x),
$$

例如语言是否流畅、段落是否完整。TrialCompiler 真正关心的是：

$$
R_{\Gamma}(X_t)=R(X_t\mid \Gamma),
$$

即当前文档状态是否仍然服从已批准的研究事实、规则、权限和专业责任边界。局部文本可以变得更漂亮，但如果它引入了未经确认的终点、遗漏了受影响章节或掩盖了不确定性，那么全局状态反而变差。

## 2. 数学对象与符号

## 2.1 来源资料

设授权来源集合为：

$$
\mathcal{S}=\{s_1,s_2,\ldots,s_{N_S}\}.
$$

每个来源对象表示为：

$$
s_i=(c_i,p_i,v_i,a_i,o_i),
$$

其中 (c_i) 为内容，(p_i) 为可定位位置，(v_i) 为版本，(a_i) 为权威属性，(o_i) 为访问权限。

## 2.2 项目事实

候选或有效事实集合为：

$$
\mathcal{F}_t=\{f_1,\ldots,f_{N_F}\}.
$$

单条事实写为：

$$
f_i=(k_i,v_i,\sigma_i,e_i,\omega_i,\rho_i),
$$

其中：

- (k_i)：规范化事实键，如“主要终点评估时间”；
- (v_i)：事实值，如 `Week 16`；
- (sigma_i)：`candidate/confirmed/effective/superseded` 状态；
- (e_i\subseteq\mathcal{S})：来源证据；
- (omega_i)：版本与适用范围；
- (
ho_i)：提出人、审核人和责任角色。

## 2.3 规则与经验

规则约束集合记为 (mathcal{R})，经人工批准的经验集合记为 (mathcal{M})。二者与项目事实分开：

$$
\mathcal{K}=\mathcal{F}\;\dot\cup\;\mathcal{R}\;\dot\cup\;\mathcal{M},
$$

其中 (dot\cup) 表示类型不混淆的并集。语义相似不能使规则变成项目事实，也不能使历史经验直接成为当前项目决定。

## 2.4 文档单元与依赖图

将方案章节、表格、单元格和关联文件切分为文档单元：

$$
\mathcal{U}=\{u_1,u_2,\ldots,u_{N_U}\}.
$$

Clinical Document Graph 定义为有向多关系图：

$$
\mathcal{G}_t=(\mathcal{V}_t,\mathcal{E}_t,\mathcal{L}),
$$

其中节点集合包含 Fact、Rule、Section、Table、Document、Issue、Revision 和 Human Decision，
(mathcal{L}) 为 `MENTIONED_IN`、`AFFECTS`、`CONSTRAINED_BY`、`CONFLICTS_WITH`、`SUPERSEDES` 等关系类型。

事实与文档单元之间可用依赖矩阵表示：

$$
A_{ij}=
\begin{cases}
1,&u_j\text{ 依赖或引用 }f_i,\\
0,&\text{否则}.
\end{cases}
$$

## 2.5 问题、修订与人工决定

检测到的问题集合记为 (mathcal{I}_t)，候选修订集合记为 (mathcal{Y}_t)，人工决定集合记为 (mathcal{H}_t)。单个人工决定可表示为：

$$
h=(\text{actor},\text{role},\text{decision},\text{reason},\text{time},\text{version}).
$$

## 3. 全局目标 (Gamma)

## 3.1 全局目标不是一句提示词

TrialCompiler 的全局目标由质量目标、硬约束、适用范围和责任结构共同组成：

$$
\Gamma=(q^*,\mathcal{C}_{hard},\Omega,\mathcal{P}),
$$

其中：

- (q^*)：期望质量向量或最低阈值；
- (mathcal{C}_{hard})：不可被其他得分抵消的硬约束；
- (Omega)：治疗领域、试验阶段、地区、文档类型和项目范围；
- (mathcal{P})：角色、权限和审批关系。

定义当前质量向量：

$$
q_t=
\begin{bmatrix}
q_{fact}\\
q_{consistency}\\
q_{traceability}\\
q_{coverage}\\
q_{minimality}\\
q_{rule}\\
q_{calibration}\\
q_{human\_control}\\
q_{efficiency}
\end{bmatrix}_t.
$$

这些分量分别表示事实正确性、跨文档一致性、来源可追溯性、影响范围覆盖、修改最小性、规则满足度、不确定性校准、人工控制完整性和工作效率。

## 3.2 硬约束

典型硬约束包括：

1. 只有 `effective` 且经授权人员确认的项目事实才能驱动正式候选编制；
2. 关键主张必须有可定位来源；
3. 不得调用过期、越权或范围不匹配的知识；
4. 不得绕过人工审批发布正式临床文件；
5. 同一范围内不能同时存在相互冲突的有效事实版本；
6. 高不确定性、高风险或证据不足时必须升级人工；
7. 未授权资料不得进入模型上下文或输出；
8. 当前比赛原型不得处理真实患者数据和企业内部项目文件。

设第 (j) 个硬约束违反量为 (c_j(X_t)ge 0)。可行状态集合为：

$$
\mathcal{X}_{feasible}=\{X:c_j(X)=0,\ \forall j\in\mathcal{C}_{hard}\}.
$$

## 3.3 为什么不能只用加权总分

如果简单定义：

$$
R=0.6\times\text{语言质量}+0.4\times\text{事实正确性},
$$

那么语言质量的提高可能抵消一个严重事实错误。临床文档场景不允许“写得更好”补偿“事实错误或越权”。因此，TrialCompiler 采用分层或词典序目标：

$$
\max_{\pi}\operatorname{Lex}
\left(
-C_{hard},
-R_{critical},
Q_{global},
-C_{human},
-C_{compute}
\right).
$$

优化优先级为：

```text
先满足硬约束
→ 再降低严重风险
→ 再提高整体质量
→ 再减少人工成本
→ 最后优化计算成本和文风
```

权重分数可以用于离线评测和模型训练，但不能替代运行时硬门控。

## 4. 全局对齐分数

在满足硬约束的前提下，可定义离线评测用的全局对齐指数：

$$
\operatorname{GAI}_{\Gamma}(X)
=\mathbf{1}[X\in\mathcal{X}_{feasible}]
\cdot
\exp\left(
\sum_{i=1}^{d}w_i\log(\epsilon+q_i)
-\rho^{\top}r
\right),
$$

其中：

- (q_i\in[0,1]) 为各质量分量；
- (w_i\ge0,\sum_iw_i=1)；
- (r) 为幻觉、越权、过期知识、隐私和漏改等风险向量；
- (
ho) 为风险权重；
- (epsilon) 防止数值为零时对数无定义。

使用几何聚合而不是简单算术平均，可以降低“一个维度极差但被其他维度平均掉”的情况；任何硬约束被违反时，指标直接为零。

## 5. 目标条件化轨迹偏离

## 5.1 局部优化偏离

设系统某轮修改使文风和完整性提高，但引入了未经确认的事实。此时可能出现：

$$
Q_{local}(X_{t+1})>Q_{local}(X_t),
$$

但：

$$
R_{\Gamma}(X_{t+1})<R_{\Gamma}(X_t).
$$

这就是 TrialCompiler 中的 trajectory drift。

## 5.2 全局残差方向

设目标质量为 (q^*)，当前尚未满足的目标残差为：

$$
d_t=(q^*-q_t)_+.
$$

一次动作带来的质量变化为：

$$
\Delta q_t=q_{t+1}-q_t.
$$

动作是否沿着真正需要改善的方向前进，可由方向一致度衡量：

$$
P_t=
\frac{\langle \Delta q_t,d_t\rangle}
{\|\Delta q_t\|_2\|d_t\|_2+\epsilon}.
$$

当 (P_t<0) 时，修改总体上远离尚未满足的全局目标；当 (P_t>0) 时，修改在缩小目标残差。

## 5.3 偏离损失

综合分数退化、方向偏离和硬约束违反，可定义：

$$
\mathcal{L}_{drift}
=\sum_{t=0}^{T-1}
\left[
\alpha\,[R_{\Gamma}(X_t)-R_{\Gamma}(X_{t+1})]_+
+\beta\,[-P_t]_+
+\sum_j\kappa_jc_j(X_{t+1})
\right].
$$

其中 ([z]_+=\max(0,z))。第一项惩罚全局分数下降，第二项惩罚向错误方向修改，第三项惩罚约束违反。

## 6. 全局风险分解

系统风险可拆成：

$$
R_{risk}
=\lambda_hR_{hallucination}
+\lambda_uR_{unauthorized}
+\lambda_vR_{version}
+\lambda_sR_{scope}
+\lambda_pR_{privacy}
+\lambda_mR_{missed\_impact}
+\lambda_oR_{overpropagation}.
$$

其中：

- (R_{hallucination})：无来源或来源不支持的内容；
- (R_{unauthorized})：AI 越过专业人员作出正式决定；
- (R_{version})：使用失效或被替代版本；
- (R_{scope})：跨治疗领域、阶段、地区或文档类型误用；
- (R_{privacy})：访问控制或敏感信息边界违反；
- (R_{missed\_impact})：事实变更后漏掉受影响位置；
- (R_{overpropagation})：修改了无关内容并增加审核负担。

不同风险的成本不相同。对于严重漏改、越权和隐私问题，应设置远高于普通文风问题的代价。

## 7. 系统状态与受约束决策过程

将第 (t) 步状态定义为：

$$
S_t=(\mathcal{F}_t,\mathcal{R}_t,\mathcal{M}_t,\mathcal{G}_t,
\mathcal{U}_t,\mathcal{I}_t,\mathcal{Y}_t,\mathcal{H}_t,\Gamma).
$$

动作空间包括：

$$
\mathcal{A}=\{
extract,confirm,retrieve,admit,generate,test,repair,
report,escalate,approve,reject,compile\_memory
\}.
$$

由于真实临床语义、规则适用性和专业判断不能由模型完全观测，该问题可以视为带人工观测的受约束 POMDP。Agent 策略为：

$$
\pi_{\theta}(a_t\mid S_t,\Gamma).
$$

全局目标是：

$$
\max_{\pi_\theta}
\mathbb{E}_{\tau\sim\pi_\theta}
\left[
\sum_{t=0}^{T}\gamma^t
\left(R_{\Gamma}(S_t,a_t)-\eta C(a_t)\right)
\right]
$$

满足：

$$
\mathbb{E}[c_j(S_t,a_t)]\le\varepsilon_j,
\quad\forall j.
$$

对越权、未授权访问等约束，$\varepsilon_j=0$；对可容忍的低严重度错误，可在离线训练中设置小的风险预算，但运行时仍由质量门决定是否升级人工。

## 8. A-F Agent 状态机

TrialCompiler 的 Agent 协作可写成：

```text
A：锁定上下文、范围和硬边界
→ B：检索事实、规则、证据和受控经验
→ C：生成或修复最小候选文本
→ D：独立测试与质量判断
    ├─ 可自动修复：返回 C
    ├─ 证据或专业判断不足：升级人工
    └─ 通过：进入 E
→ E：生成红线稿、影响矩阵、证据表与审核报告
→ 人工接受、修改或拒绝
→ F：从已完成人工审核的轨迹中提炼候选经验
→ 再次人工批准后进入长期知识层
```

令 (z_t\in\{A,B,C,D,E,F,HUMAN,DONE\}) 表示控制状态，则：

$$
z_{t+1}=\delta(z_t,o_t,b_t,n_t),
$$

其中 (o_t) 是模块输出，(b_t) 是边界检查结果，(n_t) 是当前返工次数。若 (n_t\ge N_{max})、证据覆盖不足或高严重度问题未消除，则必须转入 `HUMAN`，不能无限自循环。

## 9. 全局动作调度：优先修复什么

系统不应按固定顺序机械调用所有模块，而应选择最能降低全局剩余风险的下一步动作。定义动作 (a) 的预期净价值：

$$
\operatorname{VOA}(a\mid S_t)
=\frac{
\mathbb{E}[\mathcal{L}_{global}(S_t)-\mathcal{L}_{global}(S_{t+1})\mid a]
}{C(a)+\epsilon}
-\xi\operatorname{Risk}(a).
$$

下一动作可选为：

$$
a_t^*=\arg\max_{a\in\mathcal{A}_{feasible}}
\operatorname{VOA}(a\mid S_t).
$$

例如，当来源证据覆盖率很低时，继续润色文本的全局价值很小，系统应优先检索或请求人工补充证据；当所有事实已经确认但存在多个旧值残留时，应优先运行影响分析和一致性测试。

## 10. 局部目标一：候选事实提取与确认

## 10.1 多任务事实提取

对来源文本中的候选事实 (f_i)，模型需要同时预测：

- 事实跨度 (y_i^{span})；
- 事实类型 (y_i^{type})；
- 规范化值 (y_i^{value})；
- 来源位置 (y_i^{source})；
- 适用范围 (y_i^{scope})；
- 置信度 (p_i)。

可定义多任务损失：

$$
\mathcal{L}_{extract}
=\lambda_{span}\mathcal{L}_{span}
+\lambda_{type}\mathcal{L}_{type}
+\lambda_{value}\mathcal{L}_{value}
+\lambda_{source}\mathcal{L}_{source}
+\lambda_{scope}\mathcal{L}_{scope}
+\lambda_{cal}\mathcal{L}_{calibration}.
$$

其中：

- 文本跨度和类型可使用交叉熵；
- 数值事实可使用 Huber Loss，降低异常值对训练的影响；
- 枚举事实可使用分类交叉熵；
- 来源位置可使用 span matching 或 ranking loss；
- 置信度可使用 Brier Score 或 ECE 校准。

数值事实需要先完成单位归一化。若原始表达为 (v_i^{raw})，单位变换为 (g_i)，则：

$$
\tilde v_i=g_i(v_i^{raw}).
$$

例如 `12 weeks`、`84 days` 在规范化后应具有同一值，而不是被误判为冲突。

## 10.2 事实证据覆盖

设关键事实集合为 (mathcal{F}_{critical})，事实 (f_i) 是否具有可定位证据记为 (e_i\in\{0,1\})，则：

$$
Q_{fact\_evidence}
=\frac{\sum_{f_i\in\mathcal{F}_{critical}}w_i e_i}
{\sum_{f_i\in\mathcal{F}_{critical}}w_i}.
$$

主要终点、样本量和入排标准等事实的 (w_i) 应高于普通描述性字段。

## 10.3 人工状态门

模型置信度高并不等于事实已生效。运行时有效事实必须满足：

$$
\operatorname{Effective}(f_i)
=\mathbf{1}[sigma_i=effective]
\cdot\mathbf{1}[e_i\neq\varnothing]
\cdot\mathbf{1}[\operatorname{ApprovedByQualifiedRole}(f_i)].
$$

这个状态门是离散治理约束，不应被神经网络概率替代。

## 11. 局部目标二：知识召回与准入

## 11.1 粗召回损失

对查询 (q)、正样本知识 (m^+) 和负样本 (m^-)，可使用 InfoNCE 学习语义召回：

$$
\mathcal{L}_{retrieve}
=-\log
\frac{\exp(\operatorname{sim}(q,m^+)/\tau)}
{\exp(\operatorname{sim}(q,m^+)/\tau)
+\sum_{m^-}\exp(\operatorname{sim}(q,m^-)/\tau)}.
$$

负样本不能只随机抽取，应重点加入“主题相同但地区、版本、阶段或权限不匹配”的 hard negatives，因为这些才是临床知识检索中最危险的错误。

## 11.2 准入精判损失

设 (y_m=1) 表示候选知识可用于当前任务，(p_m) 为精判器输出。由于错误准入通常比错误拒绝风险更高，可使用成本敏感损失：

$$
\mathcal{L}_{admit}
=-\sum_m
\left[
c_{FN}y_m\log p_m
+c_{FP}(1-y_m)\log(1-p_m)
\right],
$$

其中对高风险知识设置 (c_{FP}>c_{FN})。

运行时最终准入不是单一概率阈值，而是：

$$
\operatorname{Admit}(m,q)
=\mathbf{1}[p_m\ge\tau_m]
\prod_{k}\mathbf{1}[g_k(m,q)=1],
$$

其中 (g_k) 分别检查范围、版本、审批、权限和来源状态。

## 11.3 检索风险指标

除 Recall@K、MRR 和 nDCG 外，必须报告：

$$
\operatorname{FalseAdmissionRate}
=\frac{\#\text{不适用但被准入的知识}}
{\#\text{所有不适用候选}},
$$

以及：

$$
\operatorname{UnsupportedUseRate}
=\frac{\#\text{进入输出但无有效证据的知识}}
{\#\text{输出使用的知识}}.
$$

对于 TrialCompiler，降低错误准入率通常比单纯提高召回率更重要。

## 12. 局部目标三：文档依赖图学习

## 12.1 关系预测

对任意两个节点 (v_i,v_j)，模型预测关系类型 (ell\in\mathcal{L})：

$$
p_{ij}^{(\ell)}
=\operatorname{softmax}_{\ell}
\left(g_{\theta}(h_i,h_j,h_i\odot h_j)\right).
$$

关系分类损失为：

$$
\mathcal{L}_{edge}
=-\sum_{(i,j)}\sum_{\ell}
w_{\ell}y_{ij}^{(\ell)}\log p_{ij}^{(\ell)}.
$$

`AFFECTS`、`CONFLICTS_WITH` 等关键关系可设置较高权重。图中允许存在不同语义的回路，因此不应机械施加 DAG 约束；需要约束的是版本替代关系不能形成逻辑循环。

## 12.2 版本关系一致性

若 `SUPERSEDES(f_i,f_j)` 表示 (f_i) 替代 (f_j)，则该子图应满足反自反和无环：

$$
\neg\operatorname{SUPERSEDES}(f_i,f_i),
$$

$$
\operatorname{Cycle}(\mathcal{G}_{supersedes})=0.
$$

若同一事实键和适用范围存在多个有效版本，则定义版本冲突损失：

$$
\mathcal{L}_{version}
=\sum_k
\left[\max\left(0,
\sum_{f_i:k_i=k}\mathbf{1}[\sigma_i=effective]-1
\right)\right].
$$

## 12.3 图质量指标

图模块不应只报告边分类 F1，还应报告：

- 关键依赖边召回率；
- 错误跨文件连接率；
- 来源到事实再到章节的路径完整率；
- 版本替代冲突数；
- 影响分析的端到端召回率。

## 13. 局部目标四：跨章节一致性检查

## 13.1 事实值与有效事实的偏差

设事实 (f_i) 的有效值为 (v_i^*)，其在文档单元 (u_j) 中的规范化表达为 (hat v_{ij})。事实偏差为：

$$
D_{ij}=d(\hat v_{ij},v_i^*).
$$

距离函数需要适配不同事实类型：

$$
d(a,b)
=\lambda_{num}\min\left(1,\frac{|a-b|}{s+\epsilon}\right)
+\lambda_{cat}\mathbf{1}[a\neq b]
+\lambda_{sem}(1-P_{equiv}(a,b)).
$$

数值时间点使用归一化数值距离，枚举字段使用精确匹配，复杂定义使用语义等价概率。

事实一致性损失为：

$$
\mathcal{L}_{fact\_cons}
=\frac{1}{|\mathcal{E}_{mention}|}
\sum_{(i,j)\in\mathcal{E}_{mention}}
w_iD_{ij}.
$$

## 13.2 文档内部成对一致性

即使有效事实尚未确认，也可以检测同一候选事实在多处表达是否相互冲突。令 (mathcal{U}(f_i)) 为引用该事实的单元集合，则：

$$
\mathcal{L}_{pair\_cons}
=\sum_i
\frac{1}{\binom{|\mathcal{U}(f_i)|}{2}}
\sum_{j<k}d(\hat v_{ij},\hat v_{ik}).
$$

最终一致性损失为：

$$
\mathcal{L}_{consistency}
=\alpha\mathcal{L}_{fact\_cons}
+\beta\mathcal{L}_{pair\_cons}
+\gamma\mathcal{L}_{terminology}
+\delta\mathcal{L}_{reference}.
$$

## 13.3 风险加权缺陷分数

不同缺陷不能等价计数。设问题 (i) 的严重度为 (s_i)、置信度为 (p_i)、影响节点数为 (n_i)，则：

$$
\operatorname{RiskScore}(i)
=s_i\cdot p_i\cdot\log(1+n_i).
$$

主要终点冲突应排在普通缩写不一致之前，即使后者数量更多。

## 14. 局部目标五：变更影响分析

## 14.1 影响节点预测

对事实变更 (Delta f)，设真实受影响节点标签为 (y_j\in\{0,1\})，模型预测为 (p_j)。可使用成本敏感二元损失：

$$
\mathcal{L}_{impact}
=-\sum_j
\left[
c_{miss}y_j\log p_j
+c_{extra}(1-y_j)\log(1-p_j)
\right].
$$

临床文档中漏改通常风险更大，因此一般设置 (c_{miss}>c_{extra})，但过度传播会显著增加人工审核成本，也不能忽略。

## 14.2 漏改与过度传播

设真实影响集合为 (I^*)，系统预测为 (hat I)：

$$
L_{miss}
=\frac{|I^*\setminus\hat I|}{|I^*|+\epsilon},
$$

$$
L_{over}
=\frac{|\hat I\setminus I^*|}{|\mathcal{U}\setminus I^*|+\epsilon}.
$$

传播损失为：

$$
\mathcal{L}_{propagation}
=\lambda_{miss}L_{miss}+\lambda_{over}L_{over}.
$$

## 14.3 变更传播的约束优化

影响分析可以被表述为最小覆盖问题：

$$
\min_{I\subseteq\mathcal{U}}|I|
$$

满足：

$$
\operatorname{AllRequiredDependenciesCovered}(I,\Delta f)=1.
$$

该目标对应“找到所有必须修改的位置，同时不扩大到无关内容”。

## 15. 局部目标六：候选修订生成

## 15.1 最小修订原则

设原文档为 (Y)，候选修订为 (Y')，目标是修复全部高风险问题并尽量少改无关内容：

$$
\min_{Y'}
\lambda_{edit}D_{edit}(Y,Y')
+\lambda_{preserve}D_{unaffected}(Y,Y')
$$

满足：

$$
\operatorname{Tests}(Y',\mathcal{F}_{effective},\mathcal{R})=pass.
$$

## 15.2 修订损失

可进一步写为：

$$
\mathcal{L}_{repair}
=\lambda_1\mathcal{L}_{remaining\_defect}
+\lambda_2\mathcal{L}_{fact\_violation}
+\lambda_3\mathcal{L}_{unsupported}
+\lambda_4\mathcal{L}_{unaffected\_change}
+\lambda_5\mathcal{L}_{edit\_size}
+\lambda_6\mathcal{L}_{style}.
$$

其中前五项的优先级应高于文风。特别是：

$$
\mathcal{L}_{unaffected\_change}
=\frac{1}{|\bar I|}
\sum_{u_j\notin I^*}
d_{semantic}(u_j,u_j'),
$$

用于惩罚对未受事实变更影响内容的语义改写。

## 15.3 事实保持率与无关改动率

$$
\operatorname{FactPreservation}
=1-\frac{\#\text{修订后被破坏的原有正确事实}}
{\#\text{原有正确事实}},
$$

$$
\operatorname{UnrelatedChangeRate}
=\frac{\#\text{发生语义变化的无关单元}}
{\#\text{无关单元}}.
$$

一个高质量修订不仅要消除目标缺陷，也要保持其他正确内容不变。

## 16. 局部目标七：独立质量评审与报告

## 16.1 D Agent 的成本敏感判定

设缺陷类别为 (c\in\mathcal{C})，D Agent 输出概率 (p(c\mid Y'))，则：

$$
\mathcal{L}_{judge}
=-\sum_i\sum_c w_c y_{ic}\log p_{ic}.
$$

高严重度漏判权重 (w_c) 应显著更高。除了分类准确率，还需优化校准：

$$
\operatorname{Brier}
=\frac{1}{N}\sum_i(p_i-y_i)^2.
$$

## 16.2 质量门

令：

- (n_{critical})：未解决严重问题数；
- (q_{evidence})：证据覆盖率；
- (q_{tests})：必需测试通过率；
- (u)：总体不确定性。

自动进入报告阶段的必要条件为：

$$
\operatorname{GatePass}
=\mathbf{1}[n_{critical}=0]
\mathbf{1}[q_{evidence}\ge\tau_e]
\mathbf{1}[q_{tests}=1]
\mathbf{1}[u\le\tau_u].
$$

需要再次强调：`GatePass=1` 只表示系统内部质量门通过，不等于医学、统计、注册或质量批准。

## 16.3 E Agent 的报告完整性

设必须交付的报告要素集合为 (mathcal{Z})，实际输出覆盖为 (hat{\mathcal{Z}})，则：

$$
Q_{report\_coverage}
=\frac{|\mathcal{Z}\cap\hat{\mathcal{Z}}|}{|\mathcal{Z}|}.
$$

报告还需满足每项问题、建议和修订都能追溯到事实、规则或来源：

$$
Q_{report\_trace}
=\frac{\#\text{带有效证据链的关键报告项}}
{\#\text{全部关键报告项}}.
$$

## 17. 局部目标八：经验编译与记忆生命周期

## 17.1 候选经验质量

F Agent 从审核轨迹 (	au_h) 中提取 Decision Capsule (m)。一个可复用经验需要同时满足：

$$
m=(trigger,conditions,action,rationale,evidence,counterexample,status,expiry).
$$

候选经验损失可写为：

$$
\mathcal{L}_{capsule}
=\lambda_{miss}\mathcal{L}_{field\_missing}
+\lambda_{scope}\mathcal{L}_{scope\_overgeneralization}
+\lambda_{faith}\mathcal{L}_{trajectory\_unfaithful}
+\lambda_{privacy}\mathcal{L}_{sensitive\_retention}
+\lambda_{dup}\mathcal{L}_{duplicate}.
$$

其中最关键的是防止把项目特有决定泛化为企业通用规则。

## 17.2 经验写入门

经验进入长期知识层的条件为：

$$
\operatorname{Store}(m)
=\mathbf{1}[approved]
\mathbf{1}[scope\ defined]
\mathbf{1}[evidence\ linked]
\mathbf{1}[privacy\ cleared]
\mathbf{1}[not\ superseded].
$$

模型生成的草稿经验只能进入离线候选区，不能直接指导后续正式任务。

## 17.3 记忆效用

设记忆 (m) 的保留效用为：

$$
U(m)
=a\log(1+f_m)
+bC_{refetch}(m)
+cL_{refetch}(m)
+dS_{static}(m)
+eA_{authority}(m)
-g\operatorname{Age}(m)
-h\operatorname{Size}(m).
$$

其中 (f_m) 只计算通过完整准入验证后的真实使用次数。可以将保留问题写成容量约束优化：

$$
\max_{z_m\in\{0,1\}}
\sum_m z_mU(m),
\quad
\text{s.t.}\quad
\sum_m z_m\operatorname{Size}(m)\le B.
$$

在实际系统中，法规、企业批准规则和专家批准经验还应获得保护优先级，不能只按访问频率淘汰。

## 18. 局部目标与全局目标的耦合

## 18.1 为什么局部损失不能独立最小化

假设只优化召回损失 (mathcal{L}_{retrieve})，系统可能通过放宽召回范围提高 Recall，却使错误地区和过期知识进入上下文；只优化修订流畅度，可能增加无关改写；只优化影响召回，可能把所有章节都标为受影响。

因此，每个局部模块 (m) 都会对全局质量向量产生影响：

$$
\Delta q\approx J_m\Delta z_m,
$$

其中 (z_m) 为模块输出，(J_m=\partial q/\partial z_m) 描述局部输出对事实正确性、覆盖率、最小性和审核成本等全局维度的影响。

## 18.2 统一训练目标

设所有局部损失集合为：

$$
\mathcal{L}_{local}
=\lambda_f\mathcal{L}_{extract}
+\lambda_r\mathcal{L}_{retrieve}
+\lambda_a\mathcal{L}_{admit}
+\lambda_g\mathcal{L}_{edge}
+\lambda_c\mathcal{L}_{consistency}
+\lambda_i\mathcal{L}_{impact}
+\lambda_p\mathcal{L}_{propagation}
+\lambda_y\mathcal{L}_{repair}
+\lambda_j\mathcal{L}_{judge}
+\lambda_m\mathcal{L}_{capsule}.
$$

加入全局偏离、成本和约束后：

$$
\mathcal{L}_{total}
=\mathcal{L}_{local}
+\lambda_d\mathcal{L}_{drift}
+\eta C_{human}
+\zeta C_{compute}
+\sum_j\mu_j[c_j-\varepsilon_j]_+.
$$

若使用拉格朗日对偶更新约束权重：

$$
\mu_j\leftarrow
\left[\mu_j+\eta_{\mu}(c_j-\varepsilon_j)\right]_+.
$$

当某类风险持续超过预算时，其惩罚权重自动上升。但对零容忍约束，运行时仍需使用硬门，而不能只依赖训练惩罚。

## 18.3 多目标与 Pareto 前沿

效率、影响召回和最小修改之间可能存在冲突，因此不应只报告一个总分。设目标向量：

$$
J(\theta)=
\left(
-R_{critical},
Q_{fact},
Q_{consistency},
Q_{impact},
Q_{minimality},
Q_{trace},
-C_{human}
\right).
$$

模型 A 只有在所有维度不差于模型 B、且至少一个维度更好时，才 Pareto 支配 B。比赛展示可以给出 Pareto 前沿，说明系统不是用更多人工审核换取表面准确率，也不是用大范围重写换取影响召回。

## 18.4 分层优化比统一端到端模型更适合当前阶段

当前缺少真实临床项目训练数据，因此不适合把所有目标直接端到端训练为一个黑箱模型。更合理的路径是：

1. 将确定性约束编码为规则和状态门；
2. 将语义任务拆成可独立评测的分类、匹配和生成模块；
3. 用合成数据验证接口与全局协作；
4. 未来在获得授权数据后，逐步训练准入、语义一致性和质量评审模块；
5. 始终保留人工确认与模块级可替换性。

## 19. 人工反馈与可训练评分函数

## 19.1 三类人工信号

系统可以收集：

1. `accept`：接受候选事实、问题或修订；
2. `edit`：人工修改候选结果；
3. `reject`：拒绝并给出原因。

`edit` 通常比简单接受包含更多信息，因为它提供了模型输出与专业答案之间的差异。

## 19.2 成对偏好学习

给定同一状态 (S,Gamma) 下的两个候选修订 (y^+) 和 (y^-)，若专业人员偏好 (y^+)，可使用 Bradley-Terry 模型：

$$
P(y^+\succ y^-\mid S,\Gamma)
=\sigma\left(r_{\phi}(S,y^+,\Gamma)-r_{\phi}(S,y^-,\Gamma)\right).
$$

偏好损失为：

$$
\mathcal{L}_{pref}
=-\log P(y^+\succ y^-\mid S,\Gamma).
$$

评分函数必须以 (Gamma) 和事实状态为条件，否则模型可能只学会偏好更长、更流畅的文本。

## 19.3 角色加权与分歧

医学、统计、注册和质量人员对不同问题的专业权重不同。对标注 (l_{ir})，可引入角色可靠度 (alpha_r)：

$$
\mathcal{L}_{human}
=\sum_{i,r}\alpha_r\mathcal{L}(\hat y_i,l_{ir}).
$$

但 (alpha_r) 不应被简单理解为个人排名，而应由问题类型和职责决定。若不同专业角色意见冲突，系统应保留分歧并进入联合确认，不应通过平均投票掩盖真实治理问题。

## 19.4 从反馈到经验，而不是直接记答案

人工反馈首先更新当前项目状态，再由 F Agent 提炼候选 Decision Capsule。只有经过第二次批准后才进入长期记忆。这相当于：

$$
\text{Human Decision}
\not\Rightarrow
\text{Global Rule},
$$

而是：

$$
\text{Human Decision}
\Rightarrow
\text{Candidate Capsule}
\Rightarrow
\text{Scoped Approval}
\Rightarrow
\text{Reusable Experience}.
$$

## 20. 不确定性、校准与人工升级

## 20.1 预期风险决策

设自动执行动作的错误概率为 (p_{err})，错误成本为 (C_{err})，人工审核成本为 (C_{review})。当：

$$
p_{err}C_{err}>C_{review},
$$

系统应选择人工升级。对主要终点、样本量、关键入排标准等高风险事实，即使 (p_{err}) 较低，(C_{err}) 也可能足够高而触发审核。

## 20.2 综合升级函数

$$
\operatorname{Escalate}(S)
=\mathbf{1}[
p_{err}C_{err}>C_{review}
\lor q_{evidence}<\tau_e
\lor u>\tau_u
\lor n_{critical}>0
\lor conflict_{role}=1
].
$$

## 20.3 校准指标

模型置信度必须与真实正确率匹配。可使用：

- Brier Score；
- Expected Calibration Error；
- 可靠性图；
- 分严重度和事实类型的校准曲线；
- 必要时使用 conformal prediction 输出候选集合而不是单一答案。

高准确率但严重过度自信的模型不适合承担质量门角色。

## 21. TrialDocBench 数学评测体系

## 21.1 分层任务

| 层级 | 评测任务 | 核心指标 |
| --- | --- | --- |
| L1 | 候选事实抽取与来源定位 | Span F1、Value Accuracy、Evidence Accuracy、ECE |
| L2 | 知识召回与准入 | Recall@K、MRR、False Admission Rate |
| L3 | 文档依赖图 | Edge Macro F1、关键边召回、路径完整率 |
| L4 | 跨章节缺陷检测 | Precision、Recall、Macro F1、严重缺陷召回 |
| L5 | 变更影响分析 | Impact Recall、Impact Precision、漏改率、过度传播率 |
| L6 | 候选修订 | 修复率、事实保持率、无关改动率、人工接受率 |
| L7 | 经验复用 | 正确复用率、错误经验引入率、上下文成本 |
| L8 | 全局轨迹 | GAI、Drift Rate、人工时间、审计完整率 |

## 21.2 风险加权错误率

普通错误率不能区分主要终点冲突和轻微格式问题。定义：

$$
\operatorname{WeightedError}
=\frac{\sum_i c_i\mathbf{1}[\hat y_i\neq y_i]}
{\sum_i c_i},
$$

其中 (c_i) 为缺陷严重度与影响范围决定的成本。

## 21.3 全局轨迹偏离率

$$
\operatorname{DriftRate}
=\frac{1}{T}
\sum_{t=0}^{T-1}
\mathbf{1}[R_{\Gamma}(X_{t+1})<R_{\Gamma}(X_t)].
$$

还可以报告平均退化幅度：

$$
\operatorname{MeanDriftMagnitude}
=\frac{1}{T}
\sum_t[R_{\Gamma}(X_t)-R_{\Gamma}(X_{t+1})]_+.
$$

## 21.4 人工审核效率

真实环境中最有意义的效率指标为：

$$
\operatorname{NetTimeSaved}
=T_{baseline}-T_{system}-T_{review},
$$

其中 (T_{system}) 是系统运行等待时间，(T_{review}) 是审核 AI 结果所需时间。不能只报告生成速度，而忽略核查错误输出所增加的成本。

## 21.5 数据划分

当前合成数据不能简单按段落随机划分，否则同一模板和同一事实的近重复内容会同时进入训练集和测试集。应按以下维度分组切分：

- 文档模板；
- 事实类型；
- 缺陷组合；
- 变更类型；
- 治疗领域背景；
- 规则来源；
- 难度级别。

测试集必须包含未见过的缺陷组合和表达方式，才能评估系统是否真正理解依赖关系。

## 21.6 基线与消融

至少比较：

1. 通用大模型直接回答；
2. 长上下文提示；
3. 普通 RAG；
4. 单 Agent；
5. 多 Agent 但无 Trial Fact Sheet；
6. 完整系统去掉元数据硬门控；
7. 完整系统去掉文档依赖图；
8. 完整系统去掉独立 D Agent；
9. 完整系统去掉 Experience Compiler；
10. 完整 TrialCompiler。

对主要指标使用 bootstrap 置信区间。若数据规模允许，可用配对检验比较同一案例在不同系统下的表现，减少案例难度差异带来的噪声。

## 22. `Week 12 → Week 16` 数学算例

## 22.1 初始状态

设有效事实：

$$
f^*: \text{主要终点评估时间}=\text{Week 16}.
$$

五个文档单元为：

| 单元 | 内容 | 是否真实受影响 |
| --- | --- | --- |
| (u_1) 方案摘要 | Week 12 | 是 |
| (u_2) 终点章节 | Week 16 | 是，但值已正确 |
| (u_3) 访视流程表 | Week 12 | 是 |
| (u_4) 统计原则 | Week 12 | 是 |
| (u_5) 随访安全说明 | 与主要终点评估时间无关 | 否 |

真实影响集合：

$$
I^*=\{u_1,u_2,u_3,u_4\}.
$$

## 22.2 初始一致性损失

若对时间点使用零一距离，则：

$$
\mathcal{L}_{fact\_cons}
=\frac{1+0+1+1}{4}=0.75.
$$

这表明四个引用位置中有三个与有效事实冲突。

## 22.3 影响预测

假设系统预测：

$$
\hat I=\{u_1,u_2,u_3,u_4,u_5\}.
$$

则：

$$
\operatorname{ImpactRecall}=\frac{4}{4}=1,
$$

$$
\operatorname{ImpactPrecision}=\frac{4}{5}=0.8.
$$

系统没有漏改，但存在对 (u_5) 的过度传播风险。质量门应要求 C Agent 只修改 (u_1,u_3,u_4)，保留已经正确的 (u_2) 和无关的 (u_5)。

## 22.4 最小修订

理想候选修订满足：

$$
u_1,u_3,u_4:\text{Week 12}\rightarrow\text{Week 16},
$$

$$
u_2'=u_2,\quad u_5'=u_5.
$$

修订后：

$$
\mathcal{L}_{fact\_cons}'=0,
$$

$$
\operatorname{FactPreservation}=1,
$$

$$
\operatorname{UnrelatedChangeRate}=0.
$$

## 22.5 局部变好但全局偏离的反例

假设模型在修订时重写了 (u_5)，让语言更流畅，但加入了未经确认的新随访安排。此时文风得分可能提高，但：

- 无关改动率上升；
- 出现未经支持事实；
- 人工审核范围扩大；
- 全局可追溯性和最小性下降。

因此：

$$
Q_{style}(X_{t+1})>Q_{style}(X_t),
$$

但：

$$
R_{\Gamma}(X_{t+1})<R_{\Gamma}(X_t),
$$

偏离损失会阻止系统把这种修订判定为“整体更好”。

## 23. 当前 MVP 与数学框架的映射

| 数学模块 | 当前 MVP 状态 | 后续可训练方向 |
| --- | --- | --- |
| 事实状态门 | 已有结构化事实与人工确认思路 | 完善角色与版本审批 |
| 确定性一致性检查 | 可实现并优先使用 | 扩展单位、表格和引用规则 |
| 语义一致性 | 主要依赖 LLM 接口 | 训练或校准专门判别器 |
| 知识粗召回 | 可使用 FTS/BM25 | 增加 dense ANN 混合召回 |
| 元数据门控 | 架构已定义 | 完善地区、阶段、租户和权限 |
| 语义准入精判 | 可由 LLM 结构化判断 | 构建 hard-negative 数据训练分类器 |
| 文档依赖图 | 已定义数据模型 | 自动关系抽取与人工校正界面 |
| 影响分析 | 规则和图遍历原型 | 学习间接影响概率并校准 |
| C-D 有限返工 | 工作流设计已具备 | 优化返工策略与停止条件 |
| Experience Compiler | 具备 Decision Capsule 设计 | 专家批准、冲突和失效治理 |
| TrialDocBench | 可用合成案例启动 | 扩展公开基准与未来授权验证 |
| 全局对齐调度 | 本文给出数学定义 | 建立可解释的动作价值估计器 |

这一区分非常重要：数学框架既描述当前可实现的规则化 MVP，也描述未来有数据后可以训练的模块，不能把目标设计误写成已经验证完成的结果。

## 24. 对项目创新的全局解释

从局部看，TrialCompiler 包含事实抽取、RAG、图关系、缺陷检测、文本修复和多 Agent；这些单项技术大多已有成熟研究。

从全局看，项目真正解决的是：

$$
\text{如何让多个局部 AI 模块在多轮修订中持续服从同一个受治理的临床文档目标？}
$$

其回答不是单一模型，而是：

$$
\boxed{
\text{Global Goal}
+\text{Hard Governance Gates}
+\text{Local Verifiable Losses}
+\text{Dependency-aware State Transition}
+\text{Human Feedback}
+\text{Replayable Evaluation}
}
$$

这使 TrialCompiler 与普通“AI 帮我写方案”形成根本差别：普通工具优化一次输出，TrialCompiler 优化一条有边界、可回退、可审计、可积累的文档演化轨迹。

## 25. 一句话总结

> TrialCompiler 可以被形式化为一个全局目标条件化的受约束序列决策系统：全局层用硬约束、风险优先级和 trajectory drift 保证系统不因局部文本优化而偏离事实、证据和专业责任；局部层用可独立训练和评测的损失函数优化事实、检索、图依赖、缺陷、影响、修订、评审和经验；人工确认则作为事实生效、风险处置和长期记忆写入的最终状态门。
