# Agent uncertainty / explainability reading guide

## Recommended reading order

1. `AUQ-001` establishes why single-turn LLM UQ is insufficient for interactive agents.
2. `AUQ-004` and `AUQ-005` cover a major black-box estimator and how to evaluate heterogeneous scores.
3. `AUQ-003` moves calibration from final answer to trajectory features.
4. `AUQ-007` connects structured uncertainty to information-seeking action.
5. `AUQ-006` supplies the assumptions needed before making coverage guarantees.
6. `XAI-002` defines faithfulness; `XAI-001` shows self-explanations cannot be trusted by default.
7. `XAI-003` shows that locating the responsible agent step remains difficult.
8. `MEDXAI-001/002` constrain how explanation claims should be evaluated with medical users.

## Claims safe to use in the report

- Agent UQ must consider an interactive action-observation trajectory, not only a final answer.
- An information-seeking action can reduce epistemic uncertainty, so the policy and estimator must be evaluated together.
- Semantic entropy is a useful black-box signal for some confabulations, but consistent errors remain possible.
- A score should name its target event; “calibrated probability” additionally requires a calibration set and evaluation.
- Source provenance and execution traces improve auditability but do not by themselves prove explanation faithfulness.
- LLM self-explanations should be tested behaviorally rather than accepted because they are plausible.
- In medical settings, explanation usefulness and risk depend on the user role and decision workflow.

## Claims not supported

- “TrialCompiler currently has calibrated uncertainty.” It does not yet have a labeled calibration/test split.
- “Source disagreement is aleatoric uncertainty.” It is a signal; the kind depends on the data-generating process.
- “Semantic entropy detects hallucinations generally.” It detects a subset and requires repeated sampling/clustering.
- “The audit trace is a causal explanation.” It records events; causal attribution needs intervention assumptions.
- “Counterfactual replay reveals the neural model's mechanism.” It supports behavioral sensitivity only.
- “Conformal guarantees automatically transfer to clinical-document patches.” The coverage event and assumptions must be established on the target distribution.

## Direct mapping to TrialCompiler experiments

- `AUQ-004/005`: compare answer instability, semantic entropy and verifier disagreement using rank-calibration, ECE/Brier where meaningful, and risk-coverage/AURC.
- `AUQ-003`: compare final confidence with weakest-step and trajectory-feature estimators for predicting an invalid patch.
- `AUQ-007`: select the next source using expected information gain minus acquisition cost.
- `XAI-001/003`: remove or replace a cited source, replay the decision, and measure outcome flip/sensitivity rather than judging explanation prose alone.
- `MEDXAI-001/002`: evaluate whether medical, statistical, regulatory and QA reviewers receive the evidence and uncertainty needed for their own decisions.

The canonical metadata is `references/metadata/agent_uncertainty_xai_sources.tsv`. Use its source IDs in notes and reports so that the same title is not cited under multiple names.
