import pytest

from trialcompiler.evaluation import (
    OutcomePrediction,
    evaluate_counterfactual_replays,
    evaluate_predictions,
    risk_coverage_curve,
)
from trialcompiler.uncertainty import CounterfactualReplayResult


def predictions(split: str = "test") -> list[OutcomePrediction]:
    return [
        OutcomePrediction("p1", 0.9, True, split),
        OutcomePrediction("p2", 0.8, True, split),
        OutcomePrediction("p3", 0.4, False, split),
        OutcomePrediction("p4", 0.1, False, split),
    ]


def test_uncertainty_report_contains_calibration_ranking_and_selective_risk():
    report = evaluate_predictions(predictions(), bins=2)
    assert report["n"] == 4
    assert report["brier"] == pytest.approx(0.055)
    assert report["ece"] == pytest.approx(0.2)
    assert report["pairwise_rank_accuracy"] == 1.0
    assert report["calibration_claim_allowed"] is True
    curve = risk_coverage_curve(predictions())
    assert curve[0] == {"coverage": 0.25, "risk": 0.0}
    assert curve[-1] == {"coverage": 1.0, "risk": 0.5}


def test_mixed_split_report_refuses_calibration_claim():
    records = predictions("calibration") + [OutcomePrediction("test", 0.7, True, "test")]
    report = evaluate_predictions(records)
    assert report["calibration_claim_allowed"] is False
    assert report["claim_note"] == "mixed_or_non_test_split"


def test_counterfactual_metrics_keep_behavioral_scope():
    report = evaluate_counterfactual_replays(
        [
            CounterfactualReplayResult("s1", "defer", "patch", "no_finding"),
            CounterfactualReplayResult("s2", "defer", "defer", "defer"),
        ]
    )
    assert report["necessity_flip_rate"] == 0.5
    assert report["contrastive_sensitivity"] == 0.5
    assert report["claim_scope"] == "behavioral_counterfactual_not_mechanistic_causality"


def test_invalid_probability_fails_closed():
    with pytest.raises(ValueError, match="probability_out_of_range"):
        evaluate_predictions([OutcomePrediction("bad", 1.2, True, "test")])
