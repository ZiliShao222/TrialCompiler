"""Replay frozen B-node outputs through C repair proposal and D quality gate."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "trialdocbench" / "public_corpus_050"
B_OUTPUT = CORPUS / "round3_qwen_api_v2" / "records_test_160.jsonl"
CONTROLLED = CORPUS / "round3_rich_defects_v2" / "records.jsonl"
OUTPUT = CORPUS / "registered_agent_repair_loop_v1"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return [center - margin, center + margin]


def main() -> int:
    frozen_b = load_jsonl(B_OUTPUT)
    controlled = {item["record_id"]: item for item in load_jsonl(CONTROLLED)}
    records: list[dict] = []

    for b_record in frozen_b:
        base = controlled[b_record["record_id"]]
        output = b_record.get("model_output") or {}
        predicted_defect = bool(output.get("defect_present"))
        replacement = str(output.get("recommended_replacement", "")).strip()
        expected_defect = bool(base["expected"])

        # B Evidence Review: the registration-review agent creates a finding only.
        finding_created = predicted_defect

        # C Repair Proposal: a patch is proposed only for a supported finding.
        proposal_created = finding_created and bool(replacement)
        sandbox_before = {
            "field": base["task"],
            "value": base["candidate_value"],
            "source_digest": base["source_digest"],
            "authoritative_value_digest": base["authoritative_value_digest"],
        }
        sandbox_after = dict(sandbox_before)
        if proposal_created:
            sandbox_after["value"] = replacement

        # D Independent Quality Gate: exact frozen-source fidelity is a hard gate.
        # The patch value must preserve the frozen field representation exactly.
        # Unit-appended strings such as "2 arms" are not accepted for a numeric
        # arm_count field, even if a lenient semantic comparison would normalize them.
        authoritative_match = proposal_created and replacement == str(
            base["authoritative_value"]
        ).strip()
        changed_keys = {
            key for key in sandbox_before if sandbox_before[key] != sandbox_after[key]
        }
        minimal_scope = changed_keys <= {"value"}
        source_trace_preserved = (
            sandbox_before["source_digest"] == sandbox_after["source_digest"]
            and sandbox_before["authoritative_value_digest"]
            == sandbox_after["authoritative_value_digest"]
        )
        gate_passed = bool(authoritative_match and minimal_scope and source_trace_preserved)
        repair_applied = gate_passed
        final_unit = sandbox_after if repair_applied else sandbox_before
        negative_control_preserved = (
            final_unit == sandbox_before if not expected_defect else None
        )

        records.append(
            {
                "record_id": base["record_id"],
                "case_id": base["case_id"],
                "split": base["split"],
                "task": base["task"],
                "expected_defect": expected_defect,
                "b_registration_review_agent": {
                    "finding_created": finding_created,
                    "request_id": b_record.get("request_id"),
                    "reason": output.get("reason"),
                    "recommended_replacement": replacement,
                },
                "c_repair_proposal": {
                    "proposal_created": proposal_created,
                    "before": sandbox_before,
                    "candidate_patch": sandbox_after if proposal_created else None,
                },
                "d_independent_quality_gate": {
                    "authoritative_value_match": authoritative_match,
                    "minimal_scope": minimal_scope,
                    "source_trace_preserved": source_trace_preserved,
                    "gate_passed": gate_passed,
                    "blocked_reason": None if gate_passed or not proposal_created else "replacement_not_exactly_traceable_to_frozen_source",
                },
                "repair_applied": repair_applied,
                "final_unit": final_unit,
                "finding_closed": repair_applied,
                "negative_control_preserved": negative_control_preserved,
            }
        )

    positives = [r for r in records if r["expected_defect"]]
    negatives = [r for r in records if not r["expected_defect"]]
    passed = sum(r["d_independent_quality_gate"]["gate_passed"] for r in positives)
    report = {
        "schema": "trialcompiler.registered_agent_repair_loop/v1",
        "input": "frozen B Evidence Review outputs from the registration-review agent",
        "n": len(records),
        "controlled_defect_count": len(positives),
        "negative_control_count": len(negatives),
        "finding_created_count": sum(r["b_registration_review_agent"]["finding_created"] for r in records),
        "repair_proposal_count": sum(r["c_repair_proposal"]["proposal_created"] for r in records),
        "quality_gate_pass_count": passed,
        "quality_gate_block_count": len(positives) - passed,
        "repair_applied_count": sum(r["repair_applied"] for r in records),
        "finding_closed_count": sum(r["finding_closed"] for r in positives),
        "repair_success_rate": passed / len(positives),
        "repair_success_wilson95": wilson(passed, len(positives)),
        "negative_control_preserved_count": sum(r["negative_control_preserved"] is True for r in negatives),
        "negative_control_changed_count": sum(r["negative_control_preserved"] is False for r in negatives),
        "claim_boundary": "controlled registration-field repair replay; not expert approval or natural clinical-semantic repair validity",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "records.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
