"""Select a diverse, case-balanced real-evidence adjudication set."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCOPE_WORDS = re.compile(
    r"\b(?:planned|actual|randomized|screened|enrolled|treated|evaluable|per protocol|"
    r"intent.to.treat|primary|secondary|related|previous|extension|follow-up|citation)\b",
    re.IGNORECASE,
)


def quality_score(item: dict[str, Any]) -> tuple[int, int, str]:
    text = item["excerpt"]
    replacement_noise = text.count("�") + text.count("鈥") + text.count("︹")
    context = len(SCOPE_WORDS.findall(text))
    return (context * 10 - replacement_noise * 3, len(text), item["candidate_id"])


def select(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[(item["case_id"], item["category"])].append(item)
    selected: list[dict[str, Any]] = []
    for _, items in sorted(grouped.items()):
        chosen = max(items, key=quality_score)
        chosen = {
            **chosen,
            "candidate_digest": hashlib.sha256(
                json.dumps(chosen, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest().upper(),
            "adjudication": {
                "label": None,
                "severity": None,
                "scope_relation": None,
                "rationale": None,
                "adjudicator_role": None,
                "second_review": None,
            },
        }
        selected.append(chosen)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/public_adjudication/natural_defect_candidates.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/trialdocbench/public_corpus_050/adjudication/diverse_review_set.jsonl"
        ),
    )
    args = parser.parse_args()
    candidates = [
        json.loads(line)
        for line in args.candidates.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = select(candidates)
    args.output.parent.mkdir(exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in selected),
        encoding="utf-8",
    )
    counts = Counter(item["category"] for item in selected)
    report = {
        "schema": "trialcompiler.natural_defect_adjudication_set/v1",
        "source_candidate_count": len(candidates),
        "selected_count": len(selected),
        "case_count": len({item["case_id"] for item in selected}),
        "category_counts": dict(sorted(counts.items())),
        "selection": "highest context-quality candidate per case and category",
        "gold_count": 0,
        "required_labels": [
            "confirmed_defect",
            "legitimate_difference",
            "insufficient_evidence",
            "out_of_scope_reference",
        ],
        "claim_boundary": "balanced real-evidence adjudication queue; not gold before review",
    }
    (args.output.parent / "adjudication_set_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
