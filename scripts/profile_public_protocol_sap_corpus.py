"""Create a deterministic coverage profile for the frozen public corpus."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def summarize(values: list[int]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p90": ordered[min(len(ordered) - 1, int(0.9 * (len(ordered) - 1)))],
        "max": ordered[-1],
        "total": sum(ordered),
    }


def profile(corpus: Path) -> dict[str, Any]:
    contracts = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((corpus / "case_contracts").glob("NCT*.json"))
    ]
    study_types: Counter[str] = Counter()
    phases: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    document_layouts: Counter[str] = Counter()
    action_costs: list[int] = []
    missing = Counter()
    for case in contracts:
        registry = case["registry"]
        study_types[registry.get("study_type") or "MISSING"] += 1
        statuses[registry.get("overall_status") or "MISSING"] += 1
        for phase in registry.get("phases") or ["MISSING"]:
            phases[phase] += 1
        documents = case["documents"]
        document_layouts["combined" if len(documents) == 1 else "separate"] += 1
        action_costs.extend(action["cost_unit"] for action in case["available_actions"])
        if not registry.get("enrollment"):
            missing["enrollment"] += 1
        if not registry.get("primary_outcomes"):
            missing["primary_outcomes"] += 1
    if not contracts or not action_costs:
        raise ValueError("corpus contains no case contracts or actions")
    return {
        "schema": "trialcompiler.public_corpus_profile/v1",
        "case_count": len(contracts),
        "study_types": dict(sorted(study_types.items())),
        "phases": dict(sorted(phases.items())),
        "overall_statuses": dict(sorted(statuses.items())),
        "document_layouts": dict(sorted(document_layouts.items())),
        "action_page_cost": summarize(action_costs),
        "missing_registry_fields": dict(sorted(missing.items())),
        "interpretation": {
            "usable_for": [
                "source-integrity regression",
                "document acquisition cost stratification",
                "future blinded annotation",
            ],
            "not_yet_usable_for": [
                "model accuracy claims",
                "six-arm effect-size claims",
            ],
            "reason": "case-level gold annotations have not yet been independently created",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    args = parser.parse_args()
    result = profile(args.corpus)
    target = args.corpus / "corpus_profile.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
