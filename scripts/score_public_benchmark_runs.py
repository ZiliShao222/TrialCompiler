"""Score TrialCompiler public-case runs against human-reviewed gold tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _latest_state(workspace: Path) -> tuple[Path, dict[str, Any]]:
    states = sorted(
        workspace.glob("runs/run-*/workflow_state.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not states:
        raise FileNotFoundError(f"No workflow state under {workspace}")
    path = states[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def score_case(gold_path: Path, workspace: Path) -> dict[str, Any]:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    state_path, state = _latest_state(workspace)
    findings = state.get("findings", [])
    positive = [
        test for test in gold["tests"] if test["expected_action"] == "requires_human_review"
    ]
    negative = [
        test
        for test in gold["tests"]
        if test["expected_action"] == "do_not_report_as_conflict"
    ]

    rows = []
    for test in gold["tests"]:
        expected = set(test["expected_section_ids"])
        matches = [
            finding
            for finding in findings
            if expected.intersection(finding.get("section_ids", []))
        ]
        predicted_conflict = bool(matches)
        should_conflict = test["expected_action"] == "requires_human_review"
        rows.append(
            {
                "test_id": test["test_id"],
                "gold_action": test["expected_action"],
                "predicted_conflict": predicted_conflict,
                "correct": predicted_conflict == should_conflict,
                "matching_finding_ids": [item["finding_id"] for item in matches],
            }
        )

    true_positive = sum(
        row["predicted_conflict"]
        for row in rows
        if row["gold_action"] == "requires_human_review"
    )
    false_negative = len(positive) - true_positive
    true_negative = sum(
        not row["predicted_conflict"]
        for row in rows
        if row["gold_action"] == "do_not_report_as_conflict"
    )
    false_positive = len(negative) - true_negative
    return {
        "case_id": gold["case_id"],
        "state_path": str(state_path),
        "positive_recall": true_positive / len(positive) if positive else 1.0,
        "negative_control_accuracy": true_negative / len(negative) if negative else 1.0,
        "true_positive": true_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "tests": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_case(args.gold, args.workspace)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
