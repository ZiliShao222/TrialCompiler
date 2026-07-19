"""Test find -> simulated approval -> sandbox repair -> revalidation across 50 cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.build_and_score_public_role_gold import split_cases, wilson
from scripts.build_and_score_seeded_defect_gold import (
    enrollment_document,
    mutated_nct_id,
    trial_document,
)
from trialcompiler.documents.graph import (
    ClinicalDocumentGraph,
    atomic_value_changes,
    value_present,
)
from trialcompiler.models import TrialDocument


def document_digest(document: TrialDocument) -> str:
    payload = json.dumps(
        document.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def apply_approved_proposals(
    document: TrialDocument, proposal_by_section: dict[str, str]
) -> TrialDocument:
    payload = document.to_dict()
    for section in payload["sections"]:
        if section["section_id"] in proposal_by_section:
            section["text"] = proposal_by_section[section["section_id"]]
    return TrialDocument.from_dict(payload)


def trace_payload(document: TrialDocument) -> dict[str, Any]:
    """Return provenance-bearing fields that a text-only repair must preserve."""
    return {
        "facts": [
            {
                "fact_id": fact.fact_id,
                "source_ids": fact.source_ids,
                "status": fact.status,
                "value": fact.value,
                "previous_value": fact.previous_value,
            }
            for fact in document.facts
        ],
        "sources": document.sources,
        "section_links": [
            {
                "section_id": section.section_id,
                "fact_refs": section.fact_refs,
                "source_ids": section.source_ids,
            }
            for section in document.sections
        ],
    }


def evaluate_case(case: dict[str, Any], split: str) -> list[dict[str, Any]]:
    case_id = case["case_id"]
    scenarios = [
        (
            "identifier_conflict",
            True,
            trial_document(case, mutated_nct_id(case_id), "seeded_conflict"),
            "canonical_trial_identifier_conflict",
        ),
        (
            "identifier_negative_control",
            False,
            trial_document(case, case_id, "negative_control"),
            "canonical_trial_identifier_conflict",
        ),
        (
            "enrollment_stale_value",
            True,
            enrollment_document(case, "seeded_conflict"),
            "proposed_fact_change_not_propagated",
        ),
        (
            "enrollment_negative_control",
            False,
            enrollment_document(case, "negative_control"),
            "proposed_fact_change_not_propagated",
        ),
    ]
    records: list[dict[str, Any]] = []
    for scenario, gold_defect, document, expected_type in scenarios:
        before_digest = document_digest(document)
        graph = ClinicalDocumentGraph(document)
        before_review = graph.review()
        findings = [item for item in before_review if item.finding_type == expected_type]
        simulated_decision = "approve_repair" if gold_defect else "reject_repair"
        proposals = (
            graph.propose_repairs(findings)
            if simulated_decision == "approve_repair"
            else []
        )
        repair_available = bool(proposals)
        if proposals:
            patched = apply_approved_proposals(
                document, {item.section_id: item.proposed_text for item in proposals}
            )
        else:
            patched = document
        after_digest = document_digest(patched)
        after_review = ClinicalDocumentGraph(patched).review()
        remaining = [item for item in after_review if item.finding_type == expected_type]
        changed_section_ids = sorted(
            before.section_id
            for before, after in zip(document.sections, patched.sections, strict=True)
            if before.text != after.text
        )
        proposal_section_ids = sorted({item.section_id for item in proposals})
        semantic_checks: list[bool] = []
        for proposal in proposals:
            section = next(
                item for item in patched.sections if item.section_id == proposal.section_id
            )
            fact = next(item for item in patched.facts if item.fact_id in proposal.fact_ids)
            changes = atomic_value_changes(fact.previous_value, fact.value)
            semantic_checks.append(
                value_present(section.text, fact.value, fact.unit)
                and all(not value_present(section.text, old, fact.unit) for old, _ in changes)
            )
        introduced_finding_ids = sorted(
            {item.finding_id for item in after_review}
            - {item.finding_id for item in before_review}
        )
        expected_change = gold_defect and repair_available
        records.append(
            {
                "case_id": case_id,
                "split": split,
                "scenario": scenario,
                "gold_defect": gold_defect,
                "finding_detected": bool(findings),
                "simulated_human_role": (
                    "statistician" if scenario.startswith("enrollment") else "data_governance"
                ),
                "simulated_decision": simulated_decision,
                "repair_available": repair_available,
                "repair_applied": bool(proposals),
                "expected_document_change": expected_change,
                "document_changed": before_digest != after_digest,
                "finding_closed_after_patch": bool(findings) and not remaining,
                "semantic_patch_correct": all(semantic_checks) if proposals else None,
                "minimal_scope_patch": (
                    changed_section_ids == proposal_section_ids if proposals else None
                ),
                "source_trace_preserved": trace_payload(document) == trace_payload(patched),
                "changed_section_ids": changed_section_ids,
                "introduced_finding_ids": introduced_finding_ids,
                "new_finding_count": len(introduced_finding_ids),
                "regression_free_for_target_check": not remaining,
                "before_digest": before_digest,
                "after_digest": after_digest,
                "proposal_count": len(proposals),
                "remaining_finding_ids": [item.finding_id for item in remaining],
                "outcome": (
                    "patched_and_revalidated"
                    if proposals and not remaining
                    else "approved_but_manual_edit_required"
                    if gold_defect and not repair_available
                    else "rejected_and_preserved"
                ),
                "claim_boundary": "simulated human decision, not real expert authorization",
            }
        )
    return records


def evaluate(corpus: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((corpus / "case_contracts").glob("NCT*.json"))
    ]
    splits = split_cases([case["case_id"] for case in cases])
    records = [
        record
        for case in cases
        for record in evaluate_case(case, splits[case["case_id"]])
    ]
    test = [record for record in records if record["split"] == "test"]
    applied = [record for record in records if record["repair_applied"]]
    test_applied = [record for record in test if record["repair_applied"]]
    negatives = [record for record in records if not record["gold_defect"]]
    report = {
        "schema": "trialcompiler.simulated_human_repair_loop/v1",
        "case_count": 50,
        "scenario_count": len(records),
        "simulated_approved_count": sum(record["gold_defect"] for record in records),
        "simulated_rejected_count": len(negatives),
        "auto_repair_available_count": sum(record["repair_available"] for record in records),
        "manual_edit_required_count": sum(
            record["outcome"] == "approved_but_manual_edit_required" for record in records
        ),
        "repair_applied_count": len(applied),
        "repair_closed_count": sum(record["finding_closed_after_patch"] for record in applied),
        "semantically_correct_patch_count": sum(
            record["semantic_patch_correct"] is True for record in applied
        ),
        "minimal_scope_patch_count": sum(
            record["minimal_scope_patch"] is True for record in applied
        ),
        "source_trace_preserved_count": sum(
            record["source_trace_preserved"] for record in applied
        ),
        "new_finding_after_patch_count": sum(
            record["new_finding_count"] for record in applied
        ),
        "repair_success_rate": sum(
            record["finding_closed_after_patch"] for record in applied
        )
        / len(applied),
        "repair_success_wilson95": wilson(
            sum(record["finding_closed_after_patch"] for record in applied), len(applied)
        ),
        "negative_control_changed_count": sum(
            record["document_changed"] for record in negatives
        ),
        "unexpected_change_count": sum(
            record["document_changed"] != record["expected_document_change"]
            for record in records
        ),
        "held_out_test": {
            "scenario_count": len(test),
            "repair_applied_count": len(test_applied),
            "repair_closed_count": sum(
                record["finding_closed_after_patch"] for record in test_applied
            ),
            "semantically_correct_patch_count": sum(
                record["semantic_patch_correct"] is True for record in test_applied
            ),
            "minimal_scope_patch_count": sum(
                record["minimal_scope_patch"] is True for record in test_applied
            ),
            "negative_control_changed_count": sum(
                record["document_changed"] for record in test if not record["gold_defect"]
            ),
        },
        "claim_boundary": (
            "simulated qualified decisions on controlled defects; validates repair mechanics, "
            "not real expert authorization or natural clinical-semantic patch validity"
        ),
    }
    return records, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    args = parser.parse_args()
    records, report = evaluate(args.corpus)
    output = args.corpus / "results"
    output.mkdir(exist_ok=True)
    (output / "simulated_human_repair_records.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    (output / "simulated_human_repair_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
