"""Freeze pre-adjudication TrialCompiler decisions for real PDF candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

RELATED_STUDY = re.compile(
    r"\b(?:related|previous|prior|extension|extended access|from the .+ study|"
    r"CATALYST|LARIAT|citation|reference|background)\b",
    re.IGNORECASE,
)


def decide(item: dict[str, Any]) -> dict[str, Any]:
    category = item["category"]
    excerpt = item["excerpt"]
    if category == "trial_identifier_scope" and RELATED_STUDY.search(excerpt):
        disposition = "likely_out_of_scope_reference"
        next_action = "verify_current_trial_identity_and_related_study_scope"
        risk = "medium"
    elif category == "trial_identifier_scope":
        disposition = "potential_conflict_needs_scope_review"
        next_action = "retrieve_identification_section_and_registry_snapshot"
        risk = "high"
    elif category == "enrollment_scope_or_state_difference":
        disposition = "scope_or_state_ambiguous"
        next_action = "align_planned_actual_population_and_version"
        risk = "high"
    elif category in {
        "analysis_population",
        "estimand_intercurrent_event",
        "missing_data",
        "multiplicity",
    }:
        disposition = "statistical_semantics_requires_adjudication"
        next_action = "retrieve_protocol_sap_context_and_route_to_statistician"
        risk = "high"
    else:
        disposition = "medical_statistical_context_required"
        next_action = "retrieve_cross_document_context_and_route_to_qualified_review"
        risk = "high"
    return {
        "candidate_id": item["candidate_id"],
        "candidate_digest": item["candidate_digest"],
        "case_id": item["case_id"],
        "category": category,
        "source_locator": {"filename": item["filename"], "page": item["page"]},
        "disposition": disposition,
        "next_action": next_action,
        "risk": risk,
        "auto_confirmed_defect": False,
        "requires_qualified_review": True,
        "prediction_frozen_before_gold": True,
        "explanation": (
            "A real evidence signal was found, but one excerpt cannot establish matched scope, "
            "version, population, and semantic relation. Preserve as a candidate and acquire "
            "the comparison source before defect commitment."
        ),
    }


def evaluate(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions = [decide(item) for item in items]
    dispositions = Counter(item["disposition"] for item in predictions)
    categories = Counter(item["category"] for item in predictions)
    complete_locators = sum(
        bool(item["source_locator"]["filename"] and item["source_locator"]["page"] > 0)
        for item in predictions
    )
    digest = hashlib.sha256(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in predictions
        ).encode("utf-8")
    ).hexdigest().upper()
    report = {
        "schema": "trialcompiler.natural_candidate_pre_gold_evaluation/v1",
        "candidate_count": len(predictions),
        "case_count": len({item["case_id"] for item in predictions}),
        "category_counts": dict(sorted(categories.items())),
        "disposition_counts": dict(sorted(dispositions.items())),
        "auto_confirmed_defect_count": sum(
            item["auto_confirmed_defect"] for item in predictions
        ),
        "qualified_review_count": sum(
            item["requires_qualified_review"] for item in predictions
        ),
        "source_locator_complete_count": complete_locators,
        "source_locator_completeness": complete_locators / len(predictions),
        "prediction_digest": digest,
        "prediction_freeze": "before_natural_gold_adjudication",
        "accuracy_metrics_available": False,
        "unavailable_metrics": ["precision", "recall", "f1", "accuracy"],
        "claim_boundary": (
            "coverage, routing, and pre-gold decision behavior only; no correctness claim"
        ),
    }
    return predictions, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "benchmarks/trialdocbench/public_corpus_050/adjudication/diverse_review_set.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050/results"),
    )
    args = parser.parse_args()
    items = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    predictions, report = evaluate(items)
    args.output_dir.mkdir(exist_ok=True)
    (args.output_dir / "natural_candidate_predictions_pre_gold.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in predictions
        ),
        encoding="utf-8",
    )
    (args.output_dir / "natural_candidate_evaluation_pre_gold.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
