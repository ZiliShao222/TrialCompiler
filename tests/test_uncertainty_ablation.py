import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from trialcompiler.evaluation import (
    AblationRecord,
    ExperimentArm,
    ablation_dataset_digest,
    evaluate_ablation,
    validate_ablation_records,
)


def matrix(split: str = "test") -> list[AblationRecord]:
    records: list[AblationRecord] = []
    for arm in ExperimentArm:
        is_active = arm in {
            ExperimentArm.ACTIVE_ACQUISITION,
            ExperimentArm.ACTIVE_WITH_FAITHFULNESS,
        }
        can_defer = arm in {
            ExperimentArm.PASSIVE_UQ,
            ExperimentArm.ACTIVE_ACQUISITION,
            ExperimentArm.ACTIVE_WITH_FAITHFULNESS,
        }
        has_faithfulness = arm is ExperimentArm.ACTIVE_WITH_FAITHFULNESS
        records.extend(
            [
                AblationRecord(
                    "case-good",
                    arm,
                    split,
                    True,
                    "commit_candidate",
                    probability=0.9,
                    acquisition_count=int(is_active),
                    evidence_cost=0.2 if is_active else 0.0,
                    necessity_flip=True if has_faithfulness else None,
                    contrastive_effect=True if has_faithfulness else None,
                ),
                AblationRecord(
                    "case-risk",
                    arm,
                    split,
                    False,
                    "defer_to_human" if can_defer else "commit_candidate",
                    probability=0.2,
                    acquisition_count=int(is_active),
                    evidence_cost=0.2 if is_active else 0.0,
                    necessity_flip=False if has_faithfulness else None,
                    contrastive_effect=True if has_faithfulness else None,
                ),
            ]
        )
    return records


def test_six_arm_matrix_reports_safety_cost_and_faithfulness_without_overclaim():
    report = evaluate_ablation(matrix(), minimum_cases=30)
    assert report["complete_six_arm_matrix"] is True
    assert report["paired_cases"] == 2
    assert report["result_claim_allowed"] is False
    active = report["arms"][str(ExperimentArm.ACTIVE_WITH_FAITHFULNESS)]
    assert active["error_auto_commit_rate"] == 0.0
    assert active["mean_evidence_cost"] == 0.2
    assert active["necessity_flip_rate"] == 0.5
    assert active["contrastive_sensitivity"] == 1.0


def test_complete_held_out_matrix_can_be_claimed_only_above_prespecified_minimum():
    report = evaluate_ablation(matrix(), minimum_cases=2)
    assert report["result_claim_allowed"] is True
    assert report["claim_note"] == "held_out_complete_ablation"


def test_case_leakage_across_splits_is_rejected():
    records = matrix()
    changed = records[0]
    records[0] = AblationRecord(
        "case-good",
        changed.arm,
        "calibration",
        changed.patch_valid,
        changed.selected_action,
        changed.probability,
    )
    with pytest.raises(ValueError, match="case_leaks_across_splits"):
        validate_ablation_records(records)


def test_unpaired_arms_are_rejected():
    records = matrix()
    records.pop()
    with pytest.raises(ValueError, match="unpaired_arm_case_sets"):
        validate_ablation_records(records)


def test_dataset_digest_is_order_stable_and_content_sensitive():
    records = matrix()
    assert ablation_dataset_digest(records) == ablation_dataset_digest(list(reversed(records)))
    changed = list(records)
    first = changed[0]
    changed[0] = AblationRecord(
        first.case_id,
        first.arm,
        first.split,
        not first.patch_valid,
        first.selected_action,
        first.probability,
    )
    assert ablation_dataset_digest(records) != ablation_dataset_digest(changed)


def test_ablation_cli_verifies_frozen_digest(tmp_path: Path):
    records = matrix()
    input_path = tmp_path / "ablation.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps(
            {
                "experiment_id": "test-ablation",
                "dataset_digest": ablation_dataset_digest(records),
                "records": [asdict(item) for item in records],
            }
        ),
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "evaluate_uncertainty_ablation.py"),
            str(input_path),
            "--output",
            str(output_path),
            "--minimum-cases",
            "2",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["result_claim_allowed"] is True
    assert report["dataset_digest"] == ablation_dataset_digest(records)
