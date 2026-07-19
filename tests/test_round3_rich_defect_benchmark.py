from pathlib import Path

from scripts.run_round3_rich_defect_benchmark import TASKS, evaluate
from scripts.run_round3_qwen_blind_benchmark import replacement_matches
from trialcompiler.documents.graph import stale_value_present


CORPUS = Path("benchmarks/trialdocbench/public_corpus_050")


def test_qwen_numeric_replacement_scoring_accepts_correct_units():
    record = {"task": "arm_count", "authoritative_value": 10, "expected": True}
    assert replacement_matches(record, "10")
    assert replacement_matches(record, "10 arms")
    assert not replacement_matches(record, "2 arms")


def test_old_string_inside_complete_new_value_is_not_stale():
    assert not stale_value_present(
        "Primary outcome is Overall survival [revised].",
        "Overall survival",
        "Overall survival [revised]",
    )
    assert stale_value_present(
        "Old section: Overall survival. New section: Overall survival [revised].",
        "Overall survival",
        "Overall survival [revised]",
    )


def test_round3_has_balanced_diverse_grouped_cases_and_complete_repairs():
    records, report = evaluate(CORPUS)
    assert len(TASKS) == 8
    assert len(records) == 800
    assert report["positive_count"] == 400
    assert report["negative_control_count"] == 400
    assert report["results"]["all"]["f1"] == 1.0
    assert report["results"]["test"]["f1"] == 1.0
    assert report["repair"]["repair_success_rate"] == 1.0
    assert report["repair"]["negative_control_changed_count"] == 0
    assert report["repair"]["introduced_finding_count"] == 0
    assert report["schema"].endswith("/v2")
    positives = [item for item in records if item["expected"]]
    assert all(item["candidate_value"] != item["authoritative_value"] for item in positives)
    assert all(item["mutation_operator"] == "cross_trial_same_field_transplant" for item in positives)
    assert all("[revised]" not in str(item["candidate_value"]) for item in positives)
    for case_id in {item["case_id"] for item in records}:
        case_records = [item for item in records if item["case_id"] == case_id]
        assert len(case_records) == 16
        assert len({item["split"] for item in case_records}) == 1
        assert {item["task"] for item in case_records} == set(TASKS)
