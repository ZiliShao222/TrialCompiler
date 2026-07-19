"""Round-3 benchmark: diverse controlled stale-fact defects on 50 real public cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.build_and_score_public_role_gold import metrics, split_cases, wilson
from scripts.evaluate_simulated_human_repair_loop import (
    apply_approved_proposals,
    document_digest,
    trace_payload,
)
from trialcompiler.documents.graph import (
    ClinicalDocumentGraph,
    atomic_value_changes,
    stale_value_present,
    value_present,
)
from trialcompiler.models import TrialDocument


TASKS = (
    "enrollment",
    "official_title",
    "overall_status",
    "study_type",
    "primary_outcome_measure",
    "primary_outcome_timeframe",
    "condition",
    "arm_count",
)


def digest_text(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest().upper()


def registry_values(registry: dict[str, Any]) -> dict[str, object]:
    protocol = registry["protocolSection"]
    identification = protocol["identificationModule"]
    status = protocol["statusModule"]
    design = protocol["designModule"]
    conditions = protocol["conditionsModule"]
    outcomes = protocol["outcomesModule"]["primaryOutcomes"]
    arms = protocol.get("armsInterventionsModule", {}).get("armGroups", [])
    first_outcome = outcomes[0]
    return {
        "enrollment": int(design["enrollmentInfo"]["count"]),
        "official_title": identification.get("officialTitle") or identification["briefTitle"],
        "overall_status": status["overallStatus"],
        "study_type": design["studyType"],
        "primary_outcome_measure": first_outcome["measure"],
        "primary_outcome_timeframe": first_outcome["timeFrame"],
        "condition": conditions["conditions"][0],
        "arm_count": len(arms),
    }


def mutate(task: str, old: object) -> object:
    if isinstance(old, int):
        return old + max(1, round(max(old, 1) * 0.05))
    value = str(old)
    if task == "overall_status":
        return "RECRUITING" if value != "RECRUITING" else "COMPLETED"
    if task == "study_type":
        return "OBSERVATIONAL" if value != "OBSERVATIONAL" else "INTERVENTIONAL"
    if task == "primary_outcome_timeframe":
        return f"{value} plus 1 day"
    return f"{value} [revised]"


def controlled_document(
    case_id: str,
    source_digest: str,
    task: str,
    old: object,
    new: object,
    propagated: bool,
) -> TrialDocument:
    fact_id = f"F-{case_id}-{task.upper().replace('_', '-')}"
    source_id = f"SRC-REGISTRY-{case_id}"
    observed = new if propagated else old
    unit = "participants" if task == "enrollment" else "arms" if task == "arm_count" else None
    text = f"The controlled document field value is {observed}"
    if unit:
        text += f" {unit}"
    text += "."
    return TrialDocument.from_dict(
        {
            "project_id": case_id,
            "document_id": f"ROUND3-{case_id}-{task}-{'control' if propagated else 'defect'}",
            "title": f"Round-3 controlled {task} propagation case",
            "document_type": "protocol",
            "jurisdiction": "public_benchmark",
            "therapeutic_area": "controlled_rich_mutation",
            "version": "round3-v1",
            "sources": [
                {
                    "source_id": source_id,
                    "title": f"Frozen ClinicalTrials.gov registry snapshot for {case_id}",
                    "locator": f"registry/{case_id}.json",
                    "authority": "public_registry",
                    "version": source_digest,
                    "access_scope": "public_benchmark",
                }
            ],
            "facts": [
                {
                    "fact_id": fact_id,
                    "name": task.replace("_", " "),
                    "value": new,
                    "previous_value": old,
                    "unit": unit,
                    "status": "proposed_change",
                    "source_ids": [source_id],
                    "owner_role": "data_governance",
                    "version": 2,
                }
            ],
            "sections": [
                {
                    "section_id": "S-CONTROLLED-FIELD",
                    "title": f"Controlled {task.replace('_', ' ')} field",
                    "text": text,
                    "document_type": "protocol",
                    "fact_refs": [fact_id],
                    "source_ids": [source_id],
                }
            ],
        }
    )


def evaluate(corpus: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry_paths = sorted((corpus / "registry").glob("NCT*.json"))
    splits = split_cases([path.stem for path in registry_paths])
    records: list[dict[str, Any]] = []
    for path in registry_paths:
        case_id = path.stem
        raw = path.read_bytes()
        source_digest = hashlib.sha256(raw).hexdigest().upper()
        values = registry_values(json.loads(raw))
        for task in TASKS:
            old = values[task]
            new = mutate(task, old)
            for propagated, expected in ((False, True), (True, False)):
                document = controlled_document(case_id, source_digest, task, old, new, propagated)
                before_digest = document_digest(document)
                before_findings = ClinicalDocumentGraph(document).review()
                findings = [
                    item for item in before_findings
                    if item.finding_type == "proposed_fact_change_not_propagated"
                ]
                prediction = bool(findings)
                decision = "approve_repair" if expected else "reject_repair"
                proposals = ClinicalDocumentGraph(document).propose_repairs(findings) if expected else []
                patched = apply_approved_proposals(
                    document, {item.section_id: item.proposed_text for item in proposals}
                ) if proposals else document
                after_findings = ClinicalDocumentGraph(patched).review()
                remaining = [
                    item for item in after_findings
                    if item.finding_type == "proposed_fact_change_not_propagated"
                ]
                changed = [
                    before.section_id
                    for before, after in zip(document.sections, patched.sections, strict=True)
                    if before.text != after.text
                ]
                semantic_ok = None
                if proposals:
                    section = patched.sections[0]
                    semantic_ok = value_present(section.text, new, document.facts[0].unit) and all(
                        not stale_value_present(section.text, stale, current, document.facts[0].unit)
                        for stale, current in atomic_value_changes(old, new)
                    )
                introduced = sorted(
                    {item.finding_id for item in after_findings}
                    - {item.finding_id for item in before_findings}
                )
                records.append(
                    {
                        "record_id": f"{case_id}:{task}:{'defect' if expected else 'negative_control'}",
                        "case_id": case_id,
                        "split": splits[case_id],
                        "task": task,
                        "expected": expected,
                        "prediction": prediction,
                        "predictions": {"trialcompiler_round3": prediction},
                        "old_value": old,
                        "new_value": new,
                        "mutation_operator": "controlled_stale_value_after_approved_fact_change" if expected else None,
                        "negative_control_design": "same fact change correctly propagated" if not expected else None,
                        "source_digest": source_digest,
                        "old_value_digest": digest_text(old),
                        "new_value_digest": digest_text(new),
                        "simulated_decision": decision,
                        "repair_available": bool(proposals),
                        "repair_applied": bool(proposals),
                        "repair_closed": bool(findings) and not remaining,
                        "semantic_patch_correct": semantic_ok,
                        "minimal_scope_patch": changed == ["S-CONTROLLED-FIELD"] if proposals else None,
                        "source_trace_preserved": trace_payload(document) == trace_payload(patched),
                        "negative_control_preserved": (before_digest == document_digest(patched)) if not expected else None,
                        "introduced_finding_ids": introduced,
                        "claim_boundary": "controlled mutation on a frozen public baseline; not a naturally occurring defect",
                    }
                )
    positives = [item for item in records if item["expected"]]
    negatives = [item for item in records if not item["expected"]]
    repaired = [item for item in positives if item["repair_applied"]]
    report = {
        "schema": "trialcompiler.round3_rich_seeded_defects/v1",
        "case_count": len(registry_paths),
        "task_count": len(TASKS),
        "tasks": list(TASKS),
        "scenario_count": len(records),
        "positive_count": len(positives),
        "negative_control_count": len(negatives),
        "results": {
            split: metrics(
                [item for item in records if split == "all" or item["split"] == split],
                "trialcompiler_round3",
            )
            for split in ("all", "train", "calibration", "test")
        },
        "results_by_task": {
            task: metrics(
                [item for item in records if item["task"] == task],
                "trialcompiler_round3",
            )
            for task in TASKS
        },
        "repair": {
            "approved_count": len(positives),
            "repair_available_count": len(repaired),
            "repair_closed_count": sum(item["repair_closed"] for item in repaired),
            "repair_success_rate": sum(item["repair_closed"] for item in repaired) / len(repaired),
            "repair_success_wilson95": wilson(sum(item["repair_closed"] for item in repaired), len(repaired)),
            "semantic_patch_correct_count": sum(item["semantic_patch_correct"] is True for item in repaired),
            "minimal_scope_patch_count": sum(item["minimal_scope_patch"] is True for item in repaired),
            "source_trace_preserved_count": sum(item["source_trace_preserved"] for item in repaired),
            "introduced_finding_count": sum(len(item["introduced_finding_ids"]) for item in repaired),
            "negative_control_changed_count": sum(not item["negative_control_preserved"] for item in negatives),
        },
        "claim_boundary": "eight controlled propagation-defect families on 50 frozen public registry baselines",
    }
    return records, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("benchmarks/trialdocbench/public_corpus_050"))
    args = parser.parse_args()
    records, report = evaluate(args.corpus)
    output = args.corpus / "round3_rich_defects"
    output.mkdir(exist_ok=True)
    (output / "records.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
