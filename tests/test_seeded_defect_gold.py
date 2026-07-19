from pathlib import Path

from scripts.build_and_score_seeded_defect_gold import build, mutated_nct_id

CORPUS = Path("benchmarks/trialdocbench/public_corpus_050")


def test_mutation_is_valid_and_different_nct_identifier():
    observed = mutated_nct_id("NCT01921517")
    assert observed == "NCT01921518"
    assert len(observed) == 11


def test_seeded_defect_gold_has_balanced_200_labels_and_grouped_splits():
    labels, report = build(CORPUS / "cases.json")
    assert len(labels) == 200
    assert report["positive_count"] == 100
    assert report["negative_control_count"] == 100
    assert report["split_case_counts"] == {"train": 30, "calibration": 10, "test": 10}
    for case_id in {label["case_id"] for label in labels}:
        case_labels = [label for label in labels if label["case_id"] == case_id]
        assert len(case_labels) == 4
        assert len({label["split"] for label in case_labels}) == 1
        assert {label["expected"] for label in case_labels} == {True, False}
        assert len({label["task"] for label in case_labels}) == 2


def test_trialcompiler_detector_scores_expected_controls_without_leakage():
    labels, report = build(CORPUS / "cases.json")
    assert all(label["prediction"] == label["expected"] for label in labels)
    test = report["results"]["test"]
    assert test["tp"] == 20
    assert test["fp"] == 0
    assert test["fn"] == 0
    assert test["tn"] == 20
    assert test["f1"] == 1.0
    assert "not naturally occurring" in report["claim_boundary"]
