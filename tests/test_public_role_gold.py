import json
from pathlib import Path

from scripts.build_and_score_public_role_gold import build, split_cases, wilson

CORPUS = Path("benchmarks/trialdocbench/public_corpus_050")


def test_case_split_is_deterministic_grouped_and_30_10_10():
    cases = json.loads((CORPUS / "cases.json").read_text(encoding="utf-8"))["cases"]
    case_ids = [item["nct_id"] for item in cases]
    first = split_cases(case_ids)
    assert first == split_cases(list(reversed(case_ids)))
    assert list(first.values()).count("train") == 30
    assert list(first.values()).count("calibration") == 10
    assert list(first.values()).count("test") == 10


def test_role_gold_has_130_labels_and_no_case_leakage():
    labels, report = build(CORPUS / "corpus_manifest.tsv")
    assert len(labels) == 130
    assert report["case_count"] == 50
    assert report["document_count"] == 65
    assert report["no_case_leakage"] is True
    assert report["split_case_counts"] == {"calibration": 10, "test": 10, "train": 30}
    assert all(item["label_source"].startswith("ClinicalTrials.gov") for item in labels)


def test_report_preserves_role_only_claim_boundary_and_valid_intervals():
    _, report = build(CORPUS / "corpus_manifest.tsv")
    assert "not clinical defect accuracy" in report["claim_boundary"]
    for split in report["results"].values():
        for result in split.values():
            assert 0 <= result["f1"] <= 1
            assert result["accuracy_wilson95"][0] <= result["accuracy"]
            assert result["accuracy"] <= result["accuracy_wilson95"][1]
    assert wilson(0, 0) == [0.0, 0.0]
