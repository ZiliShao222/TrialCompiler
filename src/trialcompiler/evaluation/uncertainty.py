"""Evaluation primitives for uncertainty and explanation experiments.

These metrics evaluate recorded predictions. They do not turn heuristic scores into
calibrated probabilities; calibration claims still require an independent split.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from trialcompiler.uncertainty import CounterfactualReplayResult


@dataclass(frozen=True, slots=True)
class OutcomePrediction:
    prediction_id: str
    probability: float
    outcome: bool
    split: str
    trajectory_id: str | None = None

    def validate(self) -> list[str]:
        failures: list[str] = []
        if not 0.0 <= self.probability <= 1.0:
            failures.append("probability_out_of_range")
        if not self.split.strip():
            failures.append("split_required")
        return failures


def _validated(records: list[OutcomePrediction]) -> None:
    if not records:
        raise ValueError("prediction_records_required")
    failures = [failure for record in records for failure in record.validate()]
    if failures:
        raise ValueError(", ".join(failures))


def brier_score(records: list[OutcomePrediction]) -> float:
    _validated(records)
    return sum((item.probability - float(item.outcome)) ** 2 for item in records) / len(
        records
    )


def expected_calibration_error(
    records: list[OutcomePrediction], *, bins: int = 10
) -> float:
    _validated(records)
    if bins < 1:
        raise ValueError("bins_must_be_positive")
    buckets: list[list[OutcomePrediction]] = [[] for _ in range(bins)]
    for item in records:
        index = min(int(item.probability * bins), bins - 1)
        buckets[index].append(item)
    return sum(
        len(bucket)
        / len(records)
        * abs(
            sum(item.probability for item in bucket) / len(bucket)
            - sum(item.outcome for item in bucket) / len(bucket)
        )
        for bucket in buckets
        if bucket
    )


def risk_coverage_curve(records: list[OutcomePrediction]) -> list[dict[str, float]]:
    """Return prefix risk when retaining predictions from most to least confident."""
    _validated(records)
    ranked = sorted(records, key=lambda item: (-item.probability, item.prediction_id))
    errors = 0
    curve: list[dict[str, float]] = []
    for index, item in enumerate(ranked, start=1):
        errors += int(not item.outcome)
        curve.append({"coverage": index / len(ranked), "risk": errors / index})
    return curve


def area_under_risk_coverage(records: list[OutcomePrediction]) -> float:
    """Discrete AURC: mean selective risk over all attainable coverage levels."""
    curve = risk_coverage_curve(records)
    return sum(point["risk"] for point in curve) / len(curve)


def pairwise_rank_accuracy(records: list[OutcomePrediction]) -> float | None:
    """Probability that a positive receives a higher score than a negative.

    Ties receive half credit. This is a discrimination/ranking measure, not a
    probability-calibration guarantee.
    """
    _validated(records)
    positives = [item for item in records if item.outcome]
    negatives = [item for item in records if not item.outcome]
    if not positives or not negatives:
        return None
    credit = 0.0
    for positive in positives:
        for negative in negatives:
            credit += float(positive.probability > negative.probability)
            credit += 0.5 * float(positive.probability == negative.probability)
    return credit / (len(positives) * len(negatives))


def evaluate_predictions(
    records: list[OutcomePrediction], *, bins: int = 10
) -> dict[str, object]:
    _validated(records)
    splits = sorted({item.split for item in records})
    return {
        "n": len(records),
        "splits": splits,
        "brier": brier_score(records),
        "ece": expected_calibration_error(records, bins=bins),
        "aurc": area_under_risk_coverage(records),
        "pairwise_rank_accuracy": pairwise_rank_accuracy(records),
        "calibration_claim_allowed": len(splits) == 1 and splits[0] == "test",
        "claim_note": (
            "metrics_on_held_out_test_only" if splits == ["test"] else "mixed_or_non_test_split"
        ),
    }


def evaluate_counterfactual_replays(
    records: list[CounterfactualReplayResult],
) -> dict[str, object]:
    if not records:
        raise ValueError("counterfactual_replays_required")
    necessity = sum(item.necessary_for_outcome for item in records) / len(records)
    contrastive = [item for item in records if item.replacement_outcome is not None]
    return {
        "n": len(records),
        "necessity_flip_rate": necessity,
        "replacement_n": len(contrastive),
        "contrastive_sensitivity": (
            sum(item.contrastive_effect_observed for item in contrastive) / len(contrastive)
            if contrastive
            else None
        ),
        "claim_scope": "behavioral_counterfactual_not_mechanistic_causality",
        "records": [asdict(item) for item in records],
    }
