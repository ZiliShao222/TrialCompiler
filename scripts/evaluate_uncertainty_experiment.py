"""Evaluate held-out uncertainty predictions and counterfactual replays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trialcompiler.evaluation import (
    OutcomePrediction,
    evaluate_counterfactual_replays,
    evaluate_predictions,
)
from trialcompiler.uncertainty import CounterfactualReplayResult


def evaluate(payload: dict, *, bins: int) -> dict:
    predictions = [OutcomePrediction(**item) for item in payload.get("predictions", [])]
    replays = [CounterfactualReplayResult(**item) for item in payload.get("replays", [])]
    return {
        "experiment_id": payload.get("experiment_id", "unspecified"),
        "uncertainty": evaluate_predictions(predictions, bins=bins),
        "faithfulness": evaluate_counterfactual_replays(replays),
        "limitations": [
            "Calibration claims require an untouched held-out test split.",
            "Counterfactual metrics establish behavioral sensitivity, not model mechanism.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bins", type=int, default=10)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = evaluate(payload, bins=args.bins)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
