from pathlib import Path

from scripts.evaluate_simulated_human_repair_loop import evaluate

CORPUS = Path("benchmarks/trialdocbench/public_corpus_050")


def test_simulated_human_loop_repairs_only_approved_supported_changes():
    records, report = evaluate(CORPUS)
    assert len(records) == 200
    assert report["simulated_approved_count"] == 100
    assert report["simulated_rejected_count"] == 100
    assert report["repair_applied_count"] == 50
    assert report["repair_closed_count"] == 50
    assert report["semantically_correct_patch_count"] == 50
    assert report["minimal_scope_patch_count"] == 50
    assert report["source_trace_preserved_count"] == 50
    assert report["new_finding_after_patch_count"] == 0
    assert report["repair_success_rate"] == 1.0
    assert report["manual_edit_required_count"] == 50
    assert report["negative_control_changed_count"] == 0
    assert report["unexpected_change_count"] == 0


def test_held_out_repair_loop_closes_supported_patches_and_preserves_controls():
    _, report = evaluate(CORPUS)
    test = report["held_out_test"]
    assert test["scenario_count"] == 40
    assert test["repair_applied_count"] == 10
    assert test["repair_closed_count"] == 10
    assert test["semantically_correct_patch_count"] == 10
    assert test["minimal_scope_patch_count"] == 10
    assert test["negative_control_changed_count"] == 0
