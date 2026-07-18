"""TrialDocBench runners, metrics, baselines, and ablations."""

from trialcompiler.evaluation.ablation import (
    AblationRecord,
    ExperimentArm,
    ablation_dataset_digest,
    evaluate_ablation,
    validate_ablation_records,
)
from trialcompiler.evaluation.uncertainty import (
    OutcomePrediction,
    area_under_risk_coverage,
    brier_score,
    evaluate_counterfactual_replays,
    evaluate_predictions,
    expected_calibration_error,
    pairwise_rank_accuracy,
    risk_coverage_curve,
)

__all__ = [
    "AblationRecord",
    "ExperimentArm",
    "ablation_dataset_digest",
    "OutcomePrediction",
    "area_under_risk_coverage",
    "brier_score",
    "evaluate_counterfactual_replays",
    "evaluate_predictions",
    "expected_calibration_error",
    "pairwise_rank_accuracy",
    "risk_coverage_curve",
    "evaluate_ablation",
    "validate_ablation_records",
]
