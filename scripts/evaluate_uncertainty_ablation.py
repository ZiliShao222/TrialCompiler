"""Evaluate a frozen, paired uncertainty-agent ablation record set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trialcompiler.evaluation import (
    AblationRecord,
    ExperimentArm,
    ablation_dataset_digest,
    evaluate_ablation,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--reference-arm",
        choices=list(ExperimentArm),
        default=ExperimentArm.FIXED_RAG,
    )
    parser.add_argument("--minimum-cases", type=int, default=30)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    records = [AblationRecord.from_dict(item) for item in payload.get("records", [])]
    declared_digest = payload.get("dataset_digest")
    observed_digest = ablation_dataset_digest(records)
    if not declared_digest:
        raise ValueError("dataset_digest_required")
    if declared_digest != observed_digest:
        raise ValueError("dataset_digest_mismatch")
    report = evaluate_ablation(
        records,
        reference_arm=ExperimentArm(args.reference_arm),
        minimum_cases=args.minimum_cases,
    )
    report["experiment_id"] = payload.get("experiment_id", "unspecified")
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
