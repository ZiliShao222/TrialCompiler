"""Freeze official document-role labels and score transparent baselines."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def split_cases(case_ids: list[str]) -> dict[str, str]:
    ordered = sorted(
        set(case_ids), key=lambda value: hashlib.sha256(value.encode()).hexdigest()
    )
    if len(ordered) != 50:
        raise ValueError(f"expected 50 unique cases, found {len(ordered)}")
    return {
        case_id: "train" if index < 30 else "calibration" if index < 40 else "test"
        for index, case_id in enumerate(ordered)
    }


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2))
    margin /= denominator
    lower = 0.0 if successes == 0 else max(0.0, center - margin)
    upper = 1.0 if successes == total else min(1.0, center + margin)
    return [lower, upper]


def prediction(row: dict[str, str], role: str, baseline: str) -> bool:
    pattern = (
        r"(^|[_-])prot(?:ocol)?([_.-]|$)"
        if role == "protocol"
        else r"(^|[_-])sap([_.-]|$)"
    )
    filename_signal = bool(re.search(pattern, row["filename"].lower()))
    text_signal = row[f"{role}_text_signal"] == "True"
    if baseline == "text":
        return text_signal
    if baseline == "filename":
        return filename_signal
    if baseline == "hybrid_or":
        return filename_signal or text_signal
    raise ValueError(f"unknown baseline: {baseline}")


def metrics(labels: list[dict[str, Any]], baseline: str) -> dict[str, Any]:
    true_positive = false_positive = false_negative = true_negative = 0
    for label in labels:
        predicted = label["predictions"][baseline]
        expected = label["expected"]
        if expected and predicted:
            true_positive += 1
        elif not expected and predicted:
            false_positive += 1
        elif expected and not predicted:
            false_negative += 1
        else:
            true_negative += 1
    total = len(labels)
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (true_positive + true_negative) / total
    return {
        "n": total,
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "tn": true_negative,
        "precision": precision,
        "precision_wilson95": wilson(true_positive, precision_denominator),
        "recall": recall,
        "recall_wilson95": wilson(true_positive, recall_denominator),
        "f1": f1,
        "accuracy": accuracy,
        "accuracy_wilson95": wilson(true_positive + true_negative, total),
    }


def build(manifest: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    splits = split_cases([row["nct_id"] for row in rows])
    labels: list[dict[str, Any]] = []
    for row in rows:
        official_roles = set(row["roles"].split(";"))
        for role in ("protocol", "sap"):
            labels.append(
                {
                    "label_id": f"{row['nct_id']}:{row['filename']}:{role}",
                    "case_id": row["nct_id"],
                    "document_sha256": row["sha256"],
                    "filename": row["filename"],
                    "role": role,
                    "expected": role in official_roles,
                    "split": splits[row["nct_id"]],
                    "label_source": "ClinicalTrials.gov largeDocs hasProtocol/hasSap",
                    "predictions": {
                        baseline: prediction(row, role, baseline)
                        for baseline in ("text", "filename", "hybrid_or")
                    },
                }
            )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label in labels:
        grouped[label["split"]].append(label)
    report = {
        "schema": "trialcompiler.public_role_benchmark/v1",
        "task": "official_protocol_sap_document_role_classification",
        "case_count": 50,
        "document_count": len(rows),
        "label_count": len(labels),
        "split_case_counts": {
            split: len({item["case_id"] for item in items})
            for split, items in sorted(grouped.items())
        },
        "no_case_leakage": all(
            len({item["split"] for item in labels if item["case_id"] == case_id}) == 1
            for case_id in splits
        ),
        "results": {
            split: {
                baseline: metrics(items, baseline)
                for baseline in ("text", "filename", "hybrid_or")
            }
            for split, items in {"all": labels, **dict(grouped)}.items()
        },
        "results_by_role": {
            split: {
                role: {
                    baseline: metrics(
                        [item for item in items if item["role"] == role], baseline
                    )
                    for baseline in ("text", "filename", "hybrid_or")
                }
                for role in ("protocol", "sap")
            }
            for split, items in {"all": labels, **dict(grouped)}.items()
        },
        "claim_boundary": (
            "document-role classification against official metadata; not clinical defect accuracy"
        ),
    }
    return labels, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    args = parser.parse_args()
    labels, report = build(args.corpus / "corpus_manifest.tsv")
    gold_dir = args.corpus / "gold"
    gold_dir.mkdir(exist_ok=True)
    (gold_dir / "document_role_labels.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in labels),
        encoding="utf-8",
    )
    (gold_dir / "role_baseline_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
