"""Evaluate the real detector on controlled defects seeded into 50 real cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_and_score_public_role_gold import metrics, split_cases
from trialcompiler.documents.graph import ClinicalDocumentGraph
from trialcompiler.models import TrialDocument


def mutated_nct_id(nct_id: str) -> str:
    replacement = str((int(nct_id[-1]) + 1) % 10)
    return nct_id[:-1] + replacement


def trial_document(case: dict[str, Any], observed_nct_id: str, variant: str) -> TrialDocument:
    canonical = case["case_id"]
    source_id = f"SRC-REGISTRY-{canonical}"
    fact_id = f"F-{canonical}-TRIAL-ID"
    if variant == "negative_control":
        text = (
            f"This controlled section belongs to trial {canonical}. "
            f"A related-study citation mentions {mutated_nct_id(canonical)}, but it is not "
            "the current trial identifier."
        )
    else:
        text = f"This controlled section identifies the current trial as {observed_nct_id}."
    return TrialDocument.from_dict(
        {
            "project_id": canonical,
            "document_id": f"SEEDED-{canonical}-{variant}",
            "title": f"Controlled identifier consistency case for {canonical}",
            "document_type": "protocol",
            "jurisdiction": "public_benchmark",
            "therapeutic_area": "registry_consistency",
            "version": "seeded-v1",
            "sources": [
                {
                    "source_id": source_id,
                    "title": f"Frozen ClinicalTrials.gov registry snapshot for {canonical}",
                    "locator": f"registry/{canonical}.json",
                    "authority": "public_registry",
                    "version": case.get("registry_sha256", "unknown"),
                    "access_scope": "public_benchmark",
                }
            ],
            "facts": [
                {
                    "fact_id": fact_id,
                    "name": "canonical ClinicalTrials.gov identifier",
                    "value": canonical,
                    "status": "approved",
                    "source_ids": [source_id],
                    "owner_role": "data_governance",
                    "version": 1,
                }
            ],
            "sections": [
                {
                    "section_id": "S-IDENTIFICATION",
                    "title": "Trial identification",
                    "text": text,
                    "document_type": "protocol",
                    "fact_refs": [fact_id],
                    "source_ids": [source_id],
                }
            ],
        }
    )


def enrollment_document(case: dict[str, Any], variant: str) -> TrialDocument:
    canonical = case["case_id"]
    enrollment = int(case["registry"]["enrollment"]["count"])
    revised = enrollment + max(1, round(enrollment * 0.05))
    observed = enrollment if variant == "seeded_conflict" else revised
    source_id = f"SRC-REGISTRY-{canonical}"
    fact_id = f"F-{canonical}-ENROLLMENT"
    return TrialDocument.from_dict(
        {
            "project_id": canonical,
            "document_id": f"SEEDED-{canonical}-enrollment-{variant}",
            "title": f"Controlled enrollment propagation case for {canonical}",
            "document_type": "protocol",
            "jurisdiction": "public_benchmark",
            "therapeutic_area": "change_propagation",
            "version": "seeded-v1",
            "sources": [
                {
                    "source_id": source_id,
                    "title": f"Frozen ClinicalTrials.gov registry snapshot for {canonical}",
                    "locator": f"registry/{canonical}.json",
                    "authority": "public_registry",
                    "version": case.get("registry_sha256", "unknown"),
                    "access_scope": "public_benchmark",
                }
            ],
            "facts": [
                {
                    "fact_id": fact_id,
                    "name": "target enrollment",
                    "value": revised,
                    "previous_value": enrollment,
                    "unit": "participants",
                    "status": "proposed_change",
                    "source_ids": [source_id],
                    "owner_role": "statistician",
                    "version": 2,
                }
            ],
            "sections": [
                {
                    "section_id": "S-SAMPLE-SIZE",
                    "title": "Sample size",
                    "text": f"The target enrollment is {observed} participants.",
                    "document_type": "protocol",
                    "fact_refs": [fact_id],
                    "source_ids": [source_id],
                }
            ],
        }
    )


def score_identifier_case(case: dict[str, Any], split: str) -> list[dict[str, Any]]:
    canonical = case["case_id"]
    wrong = mutated_nct_id(canonical)
    labels: list[dict[str, Any]] = []
    for variant, expected in (("seeded_conflict", True), ("negative_control", False)):
        observed = wrong if expected else canonical
        document = trial_document(case, observed, variant)
        findings = ClinicalDocumentGraph(document).review()
        matching = [
            finding
            for finding in findings
            if finding.finding_type == "canonical_trial_identifier_conflict"
        ]
        labels.append(
            {
                "label_id": f"{canonical}:{variant}",
                "case_id": canonical,
                "split": split,
                "task": "canonical_trial_identifier_conflict_detection",
                "expected": expected,
                "prediction": bool(matching),
                "predictions": {"trialcompiler_deterministic": bool(matching)},
                "canonical_value": canonical,
                "observed_value": observed,
                "mutation": (
                    {"operator": "last_digit_plus_one_mod_10", "old": canonical, "new": wrong}
                    if expected
                    else None
                ),
                "negative_control_design": (
                    "canonical identifier present; different NCT appears only as "
                    "related-study citation"
                    if not expected
                    else None
                ),
                "source_digest": case.get("registry_sha256"),
                "finding_ids": [finding.finding_id for finding in matching],
                "gold_origin": "controlled_mutation_of_frozen_real_public_case",
            }
        )
    return labels


def score_enrollment_case(case: dict[str, Any], split: str) -> list[dict[str, Any]]:
    canonical = case["case_id"]
    enrollment = int(case["registry"]["enrollment"]["count"])
    revised = enrollment + max(1, round(enrollment * 0.05))
    labels: list[dict[str, Any]] = []
    for variant, expected in (("seeded_conflict", True), ("negative_control", False)):
        document = enrollment_document(case, variant)
        findings = ClinicalDocumentGraph(document).review()
        matching = [
            finding
            for finding in findings
            if finding.finding_type == "proposed_fact_change_not_propagated"
        ]
        labels.append(
            {
                "label_id": f"{canonical}:enrollment:{variant}",
                "case_id": canonical,
                "split": split,
                "task": "enrollment_change_propagation_detection",
                "expected": expected,
                "prediction": bool(matching),
                "predictions": {"trialcompiler_deterministic": bool(matching)},
                "canonical_value": revised,
                "observed_value": enrollment if expected else revised,
                "mutation": (
                    {
                        "operator": "five_percent_minimum_one_increase",
                        "old": enrollment,
                        "new": revised,
                    }
                    if expected
                    else None
                ),
                "negative_control_design": (
                    "revised enrollment correctly propagated to the document section"
                    if not expected
                    else None
                ),
                "source_digest": case.get("registry_sha256"),
                "finding_ids": [finding.finding_id for finding in matching],
                "gold_origin": "controlled_mutation_of_frozen_real_public_case",
            }
        )
    return labels


def build(cases_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    contracts_dir = cases_path.parent / "case_contracts"
    cases = [
        json.loads((contracts_dir / f"{item['nct_id']}.json").read_text(encoding="utf-8"))
        for item in index
    ]
    splits = split_cases([case["case_id"] for case in cases])
    labels: list[dict[str, Any]] = []
    for case in cases:
        split = splits[case["case_id"]]
        labels.extend(score_identifier_case(case, split))
        labels.extend(score_enrollment_case(case, split))
    by_split = {
        split: [label for label in labels if label["split"] == split]
        for split in ("train", "calibration", "test")
    }
    report = {
        "schema": "trialcompiler.seeded_defect_benchmark/v1",
        "tasks": [
            "canonical_trial_identifier_conflict_detection",
            "enrollment_change_propagation_detection",
        ],
        "case_count": 50,
        "label_count": len(labels),
        "positive_count": sum(label["expected"] for label in labels),
        "negative_control_count": sum(not label["expected"] for label in labels),
        "split_case_counts": {
            split: len({label["case_id"] for label in items})
            for split, items in by_split.items()
        },
        "results": {
            split: metrics(items, "trialcompiler_deterministic")
            for split, items in {"all": labels, **by_split}.items()
        },
        "results_by_task": {
            split: {
                task: metrics(
                    [label for label in items if label["task"] == task],
                    "trialcompiler_deterministic",
                )
                for task in (
                    "canonical_trial_identifier_conflict_detection",
                    "enrollment_change_propagation_detection",
                )
            }
            for split, items in {"all": labels, **by_split}.items()
        },
        "claim_boundary": (
            "controlled identifier and enrollment-propagation defects on real public case "
            "contracts; "
            "not naturally occurring clinical-semantic defect accuracy"
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
    labels, report = build(args.corpus / "cases.json")
    gold_dir = args.corpus / "gold"
    gold_dir.mkdir(exist_ok=True)
    (gold_dir / "seeded_defect_labels.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in labels),
        encoding="utf-8",
    )
    (gold_dir / "seeded_defect_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
