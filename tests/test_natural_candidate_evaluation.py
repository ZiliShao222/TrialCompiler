import json
from pathlib import Path

from scripts.evaluate_natural_defect_candidates import evaluate


def load_items():
    path = Path(
        "benchmarks/trialdocbench/public_corpus_050/adjudication/diverse_review_set.jsonl"
    )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_pre_gold_evaluation_freezes_predictions_without_accuracy_claim():
    predictions, report = evaluate(load_items())
    assert len(predictions) == 197
    assert report["candidate_count"] == 197
    assert report["accuracy_metrics_available"] is False
    assert report["auto_confirmed_defect_count"] == 0
    assert report["qualified_review_count"] == 197
    assert report["source_locator_completeness"] == 1.0
    assert len(report["prediction_digest"]) == 64
    assert all(item["prediction_frozen_before_gold"] for item in predictions)


def test_related_study_nct_is_not_auto_promoted_to_current_trial_conflict():
    item = next(
        item
        for item in load_items()
        if item["category"] == "trial_identifier_scope"
        and "study" in item["excerpt"].lower()
    )
    predictions, _ = evaluate([item])
    assert predictions[0]["auto_confirmed_defect"] is False
    assert predictions[0]["requires_qualified_review"] is True
