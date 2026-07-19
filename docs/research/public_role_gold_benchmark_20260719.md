# TrialCompiler 50 例公开文档角色金标签与基线结果

## 1. 本轮标注解决了什么

本轮首先完成可由公开权威来源直接判定的金标签任务：识别每份公开 PDF 是否承担
Protocol 角色、是否承担 SAP 角色。标签不是由待评测模型生成，也不是从文件名反推，
而是来自 ClinicalTrials.gov `largeDocs` 中由记录提交方给出的 `hasProtocol` 与 `hasSap`
元数据。65 份文档对两个角色各形成一个二元判断，共 130 个标签。

该标签属于“官方元数据金标签”，可以用于文档准入、路由、取证与检索评测。它不等于
医学、统计或监管专家对临床缺陷的人工裁决，因此不能把本任务的准确率写成 TrialCompiler
发现临床问题的总体准确率。

## 2. 冻结切分与防泄漏

50 个 NCT 案例通过 NCT ID 的 SHA-256 顺序进行确定性分组：30 个 train、10 个
calibration、10 个 held-out test。同一 NCT 下的 Protocol、SAP 或合并文档只能进入同一
split，不允许同一研究跨 split。最终 test 包含 10 个案例、14 份文档、28 个二元标签。

## 3. 比较的透明基线

`text` 基线只读取 PDF 正文中的角色语义词。Protocol 信号包括 protocol、clinical study
和 study plan；SAP 信号包括 statistical analysis plan、statistical analysis、analysis
plan 和 statistical methods。

`filename` 基线只识别官方上传文件名中的 `Prot`/`Protocol` 与 `SAP` 标记。

`hybrid_or` 在任一信号为真时预测相应角色。该组合追求召回率，但正文中讨论另一类文档
时容易产生假阳性。

## 4. Held-out test 结果

正文语义基线在 28 个 test 标签上得到 TP=19、FP=4、FN=1、TN=4；Precision=82.61%，
Recall=95.00%，F1=88.37%，Accuracy=82.14%。Accuracy 的 Wilson 95% 区间为
64.41%–92.12%。分角色看，Protocol F1=90.91%，SAP F1=85.71%。

文件名基线在本次 test 上得到 TP=20、FP=0、FN=0、TN=8；Precision、Recall、F1 和
Accuracy 均为 100%。由于 test 只有 28 个二元标签，其 Accuracy Wilson 95% 区间仍为
87.94%–100%，不能把点估计解释为未来数据必然 100%。该结果主要说明 ClinicalTrials.gov
本批官方上传文档具有高度规范的命名约定，而不是复杂语义模型已经解决角色识别。

混合 OR 基线得到 TP=20、FP=4、FN=0、TN=4；Precision=83.33%，Recall=100%，
F1=90.91%，Accuracy=85.71%，Accuracy Wilson 95% 区间为 68.51%–94.30%。它消除了
正文基线的一个漏报，但保留了四个正文假阳性，说明简单扩大语义触发词会提高召回并损害
精度。

## 5. 目前可以与不可以声称的结论

可以声称：TrialCompiler 已在 50 个真实公开案例上建立 130 个官方元数据角色标签；冻结
的 held-out test 上，正文语义基线 F1 为 88.37%，规范文件名基线 F1 为 100%，混合基线
F1 为 90.91%。结果揭示角色分类中“正文召回—误报”和“命名规范先验”的具体差异。

不能声称：TrialCompiler 在 50 个试验中的临床缺陷检测成功率达到 100%。缺陷检测标签仍
需要医学、统计、注册和质量人员对具体事实冲突、允许差异、负对照和 patch validity 进行
独立裁决。当前 NCT04683926 的 F1=94.12% 仍是单个已审阅案例的结果，不能与角色识别
任务混为一个总体成功率。

## 6. 复现

```powershell
python scripts/build_and_score_public_role_gold.py
python -m pytest tests/test_public_role_gold.py -q
```

标签文件：`benchmarks/trialdocbench/public_corpus_050/gold/document_role_labels.jsonl`。
完整结果：`benchmarks/trialdocbench/public_corpus_050/gold/role_baseline_results.json`。
