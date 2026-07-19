import json
from pathlib import Path

from scripts.evaluate_registered_agent_repair_loop import main


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "benchmarks"
    / "trialdocbench"
    / "public_corpus_050"
    / "registered_agent_repair_loop_v1"
)


def test_frozen_registration_agent_outputs_use_strict_patch_fidelity():
    assert main() == 0
    report = json.loads((OUTPUT / "report.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (OUTPUT / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert report["quality_gate_pass_count"] == 75
    assert report["quality_gate_block_count"] == 5
    assert report["repair_success_rate"] == 0.9375
    assert report["negative_control_changed_count"] == 0

    blocked = [
        item
        for item in records
        if item["expected_defect"] and not item["repair_applied"]
    ]
    assert len(blocked) == 5
    assert {item["task"] for item in blocked} == {
        "arm_count",
        "primary_outcome_timeframe",
    }
    assert all(not item["finding_closed"] for item in blocked)
    assert all(
        item["final_unit"] == item["c_repair_proposal"]["before"]
        for item in blocked
    )

