# Corrected round-3 controlled defect corpus

本目录为第三轮丰富缺陷集的方向修正版。

- `authoritative_value`：当前案例ClinicalTrials.gov冻结登记中的原始字段值。
- `candidate_value`：缺陷正例中来自另一真实试验同类字段的值；负对照中与权威值相同。
- `mutation_source_case_id`：缺陷值来源的另一真实试验编号。
- `source_digest`：当前案例冻结登记快照的SHA-256摘要。

共50个案例、8类字段、400个缺陷正例和400个未修改负对照。缺陷是受控构造的跨试验同字段错配，不声称为公开登记中自然存在的错误。
