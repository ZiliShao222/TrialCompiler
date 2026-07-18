"""Explainably score an NCT04683926 workflow run against its reviewed gold tests.

The scorer deliberately uses case-specific semantic predicates.  A fact id or a
shared word is only an anchor; a match also has to express the relationship the
gold test is about (for example both sides of a numeric or logical conflict).
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPORTING_WORDS = re.compile(
    r"\b(conflict|contradict|inconsisten|mismatch|ambiguit|error|invalid|unresolved)\w*\b",
    re.IGNORECASE,
)
NON_CONFLICT_WORDS = re.compile(
    r"\b(valid|compatible|not (?:a )?conflict|no conflict|distinct|mapping is valid|"
    r"must not be collapsed)\b",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _finding_text(finding: dict[str, Any]) -> str:
    fields = ("finding_type", "message", "title", "summary", "rationale", "explanation")
    return " ".join(_text(finding.get(field)) for field in fields).lower()


def _facts(finding: dict[str, Any]) -> set[str]:
    values = finding.get("fact_ids") or []
    canonical = finding.get("canonical_fact_id")
    return {str(value) for value in values} | ({str(canonical)} if canonical else set())


def _has(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _is_reported_conflict(finding: dict[str, Any]) -> bool:
    text = _finding_text(finding)
    if finding.get("requires_human_review") is False and NON_CONFLICT_WORDS.search(text):
        return False
    return bool(REPORTING_WORDS.search(text)) or finding.get("requires_human_review") is True


def _semantic_checks(test_id: str, finding: dict[str, Any]) -> list[dict[str, Any]]:
    """Return auditable checks; every check must pass for a semantic match."""
    text = _finding_text(finding)
    facts = _facts(finding)
    checks: list[tuple[str, bool, str]]
    if test_id == "TC-SD-001":
        checks = [
            ("fact_anchor", "F018" in facts, "finding references water-restriction fact F018"),
            (
                "both_instructions",
                _has(text, r"no water|prohibit\w* water", r"only water|water (?:is )?allowed"),
                "finding states both 'no water' and 'only water/water allowed' instructions",
            ),
            (
                "logical_relation",
                bool(re.search(r"contradict|inconsisten|conflict", text)),
                "finding identifies the two instructions as contradictory",
            ),
            (
                "human_gate",
                finding.get("requires_human_review") is True,
                "finding requires human review",
            ),
        ]
    elif test_id == "TC-SD-002":
        checks = [
            (
                "fact_anchor",
                {"F005", "F007"}.issubset(facts),
                "finding references design F005 and dose-day F007",
            ),
            (
                "boundary_values",
                _has(
                    text,
                    r">\s*3|greater than 3",
                    r"(?<!>)\b3 days?\b|days?\s*1\s*[,/]\s*4\s*[,/]\s*7\s*[,/]\s*10",
                ),
                "finding states both the >3-day claim and exact three-day boundary",
            ),
            (
                "numeric_relation",
                bool(
                    re.search(
                        r"boundar|inconsisten|conflict|does not satisfy|not greater", text
                    )
                ),
                "finding explains why the numeric claims disagree",
            ),
            (
                "human_gate",
                finding.get("requires_human_review") is True,
                "finding requires human review",
            ),
        ]
    elif test_id == "TC-XD-001":
        checks = [
            ("fact_anchor", "F009" in facts, "finding references duration fact F009"),
            (
                "duration_values",
                _has(text, r"\b11 days?\b", r"(?:about|approximately|~)\s*12 days?|\b12 days?\b"),
                "finding states the 11-day and about-12-day descriptions",
            ),
            (
                "definition_relation",
                bool(
                    re.search(
                        r"definition|counting|confinement|about|participant language", text
                    )
                ),
                "finding treats this as a definition/counting distinction",
            ),
            (
                "not_hard_conflict",
                not bool(re.search(r"unambiguous hard conflict|definitive hard conflict", text)),
                "finding does not overstate an unambiguous hard conflict",
            ),
        ]
    elif test_id == "TC-XD-002":
        checks = [
            ("fact_anchor", "F008" in facts, "finding references screening-window fact F008"),
            (
                "window_values",
                _has(
                    text,
                    r"(?:<=|no more than|up to)\s*30",
                    r"(?:up to|through|inclusive)\s*31|\b31 days?\b",
                ),
                "finding states the protocol 30-day and ICF 31-day boundaries",
            ),
            (
                "boundary_relation",
                bool(
                    re.search(
                        r"inclusive|boundary|participant language|wording|difference", text
                    )
                ),
                "finding explains the inclusive-boundary or participant-language distinction",
            ),
        ]
    elif test_id == "TC-XD-004":
        checks = [
            (
                "population_anchor",
                bool(facts & {"F020", "F021"}),
                "finding references the PP/evaluable population facts",
            ),
            (
                "population_concepts",
                _has(
                    text,
                    r"evaluable|per[- ]protocol|population",
                    r"sap",
                    r"safety(?:-only| only| analysis)",
                ),
                "finding relates population mapping to the SAP safety-only scope",
            ),
            (
                "expert_review",
                bool(
                    re.search(
                        r"statistic|human|review|must not (?:auto[- ]?)?merge|not auto",
                        text,
                    )
                )
                or finding.get("requires_human_review") is True,
                "finding defers mapping/merge to qualified review",
            ),
        ]
    elif test_id == "TC-TR-001":
        required = {
            str(value)
            for value in finding.get("covered_fact_ids", finding.get("fact_ids", []))
        }
        fields = set(finding.get("trace_fields", finding.get("required_fields", [])))
        checks = [
            (
                "all_facts",
                {f"F{i:03d}" for i in range(1, 28)}.issubset(required),
                "trace finding covers F001 through F027",
            ),
            (
                "trace_fields",
                {"source_ids", "source_locator", "status"}.issubset(fields),
                "trace includes source_ids, source_locator, and status",
            ),
            (
                "complete_trace",
                bool(re.search(r"complete.*(?:source|trace)|source.*trace.*complete", text)),
                "finding explicitly asserts complete source traceability",
            ),
        ]
    else:
        return []
    return [{"name": name, "passed": passed, "detail": detail} for name, passed, detail in checks]


def _all_pass(checks: list[dict[str, Any]]) -> bool:
    return bool(checks) and all(check["passed"] for check in checks)


def _negative_checks(test_id: str, finding: dict[str, Any]) -> list[dict[str, Any]]:
    text = _finding_text(finding)
    facts = _facts(finding)
    if test_id == "TC-XD-003":
        checks = [
            ("fact_anchor", bool(facts & {"F022", "F023"}), "finding references a time-axis fact"),
            (
                "dual_axes",
                _has(text, r"continuous|day\s*-?1.*day\s*11", r"period|day\s*1"),
                "finding discusses continuous and period-specific axes",
            ),
            (
                "reported_as_problem",
                _is_reported_conflict(finding),
                "finding reports the valid mapping as a conflict/ambiguity requiring review",
            ),
        ]
    elif test_id == "TC-VS-001":
        checks = [
            (
                "fact_anchor",
                bool(facts & {"F010", "F011", "F012"}),
                "finding references enrollment-state facts",
            ),
            (
                "state_values",
                _has(text, r"planned|maximum", r"target|pk[- ]complete", r"actual|enroll"),
                "finding discusses planned, target, and actual states",
            ),
            (
                "reported_as_problem",
                _is_reported_conflict(finding),
                "finding incorrectly reports distinct states as a conflict",
            ),
        ]
    else:
        return []
    return [{"name": name, "passed": passed, "detail": detail} for name, passed, detail in checks]


def _change_impact_match(
    state: dict[str, Any], summary: dict[str, Any]
) -> tuple[bool, dict[str, Any], set[str]]:
    findings = state.get("findings", [])
    sections = {
        item.get("section_id"): item
        for item in state.get("document", {}).get("sections", [])
    }
    class_aliases = {
        "protocol": {"protocol"},
        "schedule_of_activities": {"schedule_of_activities"},
        "sap": {"statistical_analysis_plan", "sap"},
        "icf": {"informed_consent_form", "icf"},
        "crf": {"crf"},
        "registry_results": {"registry", "registry_results"},
    }
    classes: set[str] = set()
    finding_ids: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for finding in findings:
        text = _finding_text(finding)
        if finding.get("finding_type") != "proposed_fact_change_not_propagated":
            continue
        if "F015" not in _facts(finding) or not _has(text, r"\b32\b", r"\b36\b"):
            continue
        if not re.search(r"propagat|prior value|proposed|change", text):
            continue
        for section_id in finding.get("section_ids", []):
            document_type = str(sections.get(section_id, {}).get("document_type", "")).lower()
            for gold_class, aliases in class_aliases.items():
                if document_type in aliases:
                    classes.add(gold_class)
        finding_ids.add(str(finding.get("finding_id", "<unnamed>")))
        evidence.append(
            {
                "finding_id": finding.get("finding_id"),
                "section_ids": finding.get("section_ids", []),
                "reason": "F015 finding states 32-to-36 change propagation",
            }
        )

    fact = next(
        (
            item
            for item in state.get("document", {}).get("facts", [])
            if item.get("fact_id") == "F015"
        ),
        {},
    )
    proposals = [item for item in state.get("proposals", []) if "F015" in item.get("fact_ids", [])]
    preserved = (
        "32" in str(fact.get("previous_value", ""))
        and "36" in str(fact.get("value", ""))
        and int(fact.get("version", 0)) >= 2
    )
    human_gate = bool(proposals) and all(
        item.get("status") in {"requires_human_review", "proposed_change"}
        for item in proposals
    )
    human_gate = human_gate and summary.get("release_status") != "human_approved_change_applied"
    needed = set(class_aliases)
    checks = [
        {
            "name": "old_new_relation",
            "passed": bool(finding_ids),
            "detail": "one or more F015 findings explicitly relate 32 to 36 hours",
        },
        {
            "name": "affected_classes",
            "passed": needed.issubset(classes),
            "detail": f"covered={sorted(classes)}; required={sorted(needed)}",
        },
        {
            "name": "original_preserved",
            "passed": preserved,
            "detail": "F015 keeps 32-hour previous_value and proposes 36 hours in version 2+",
        },
        {
            "name": "human_approval",
            "passed": human_gate,
            "detail": "F015 proposals remain gated for qualified human approval",
        },
    ]
    return _all_pass(checks), {"checks": checks, "evidence": evidence}, finding_ids


def _governance_match(
    state: dict[str, Any], summary: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    proposals = state.get("proposals", [])
    provenance = bool(proposals) and all(
        item.get("fact_ids") and item.get("evidence_source_ids") for item in proposals
    )
    pending_gate = bool(state.get("decision_requests")) or state.get("workflow_status") in {
        "awaiting_qualified_decisions", "ready_for_qualified_approval"
    }
    release_gate = summary.get("release_status") in {
        "requires_qualified_human_review", "human_rejected_no_change"
    }
    checks = [
        {
            "name": "formal_document_gate",
            "passed": pending_gate and release_gate,
            "detail": "run requires qualified decisions/review before formal release",
        },
        {
            "name": "proposal_provenance",
            "passed": provenance,
            "detail": "every candidate proposal carries fact_ids and evidence_source_ids",
        },
    ]
    evidence = [{
        "source": "workflow_state/run_summary",
        "workflow_status": state.get("workflow_status"),
        "release_status": summary.get("release_status"),
    }]
    return _all_pass(checks), {"checks": checks, "evidence": evidence}


def _load_run(run_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    run_path = run_path.resolve()
    run_dir = run_path.parent if run_path.is_file() else run_path
    state_path = (
        run_path if run_path.name == "workflow_state.json" else run_dir / "workflow_state.json"
    )
    summary_path = run_dir / "run_summary.json"
    if not state_path.is_file():
        raise FileNotFoundError(f"Missing workflow_state.json: {state_path}")
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing run_summary.json: {summary_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return run_dir, state, summary


def _gold_path(benchmark: Path) -> Path:
    benchmark = benchmark.resolve()
    if benchmark.is_file():
        return benchmark
    path = benchmark / "gold" / "gold_tests.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing gold/gold_tests.json: {path}")
    return path


def score_benchmark(benchmark: Path, run: Path) -> dict[str, Any]:
    gold_path = _gold_path(benchmark)
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    run_dir, state, summary = _load_run(run)
    findings = state.get("findings", [])
    consumed: set[str] = set()
    rows: list[dict[str, Any]] = []

    for test in gold.get("tests", []):
        test_id = str(test.get("id", test.get("test_id", "")))
        negative = (
            test.get("must_not_report_as_conflict") is True
            or test.get("expected_action") == "do_not_report_as_conflict"
        )
        if negative:
            violations = []
            for finding in findings:
                checks = _negative_checks(test_id, finding)
                if _all_pass(checks):
                    finding_id = str(finding.get("finding_id", "<unnamed>"))
                    consumed.add(finding_id)
                    violations.append({
                        "finding_id": finding_id,
                        "checks": checks,
                        "message": finding.get("message", ""),
                    })
            rows.append({
                "gold_id": test_id,
                "control_type": "negative_control",
                "expected": "do_not_report_as_conflict",
                "matched": not violations,
                "correct": not violations,
                "violation_detected": bool(violations),
                "matching_finding_ids": [item["finding_id"] for item in violations],
                "evidence": violations
                or [{
                    "reason": "no finding semantically reports this valid distinction as a conflict"
                }],
            })
            continue

        if test_id == "TC-MUT-001":
            matched, detail, ids = _change_impact_match(state, summary)
            if matched:
                consumed.update(ids)
            evidence = detail["evidence"]
            matching_ids = ids if matched else set()
            checks = detail["checks"]
        elif test_id == "TC-QA-001":
            matched, detail = _governance_match(state, summary)
            evidence = detail["evidence"]
            matching_ids = set()
            checks = detail["checks"]
        else:
            candidates = []
            rejected = []
            for finding in findings:
                candidate_checks = _semantic_checks(test_id, finding)
                if _all_pass(candidate_checks):
                    finding_id = str(finding.get("finding_id", "<unnamed>"))
                    consumed.add(finding_id)
                    candidates.append({
                        "finding_id": finding_id,
                        "checks": candidate_checks,
                        "message": finding.get("message", ""),
                    })
                elif any(
                    check["name"].endswith("anchor") and check["passed"]
                    for check in candidate_checks
                ):
                    rejected.append({
                        "finding_id": str(finding.get("finding_id", "<unnamed>")),
                        "decision": "rejected_candidate",
                        "checks": candidate_checks,
                        "message": finding.get("message", ""),
                    })
            matched = bool(candidates)
            evidence = candidates if matched else rejected
            matching_ids = {item["finding_id"] for item in candidates}
            checks = [] if matched else [
                {
                    "name": "semantic_match",
                    "passed": False,
                    "detail": "no finding passed every case-specific semantic condition",
                }
            ]
        rows.append({
            "gold_id": test_id,
            "control_type": "positive",
            "expected": test.get("expected_label", test.get("expected_action")),
            "matched": matched,
            "correct": matched,
            "matching_finding_ids": sorted(matching_ids),
            "evidence": evidence
            or [{"reason": "no finding with the required structured anchor was present"}],
            "checks": checks,
        })

    positives = [row for row in rows if row["control_type"] == "positive"]
    negatives = [row for row in rows if row["control_type"] == "negative_control"]
    tp = sum(row["matched"] for row in positives)
    fn = len(positives) - tp
    negative_fp = sum(row["violation_detected"] for row in negatives)
    ignored_non_conflicts = {
        str(item.get("finding_id", "<unnamed>"))
        for item in findings
        if not _is_reported_conflict(item)
    }
    unmatched = sorted(
        str(item.get("finding_id", "<unnamed>"))
        for item in findings
        if str(item.get("finding_id", "<unnamed>")) not in consumed | ignored_non_conflicts
    )
    fp = negative_fp + len(unmatched)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    tn = len(negatives) - negative_fp
    return {
        "case_id": gold.get("case_id"),
        "gold_version": gold.get("gold_version"),
        "gold_path": str(gold_path),
        "run_path": str(run_dir),
        "workflow_state_path": str(run_dir / "workflow_state.json"),
        "run_summary_path": str(run_dir / "run_summary.json"),
        "metric_basis": {
            "true_positive": "positive gold tests with a complete case-specific semantic match",
            "false_positive": (
                "negative-control violations plus reportable findings not semantically "
                "matched to any positive gold test"
            ),
            "false_negative": "positive gold tests without a complete semantic match",
        },
        "counts": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "negative_control_false_positive": negative_fp,
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "negative_control_accuracy": tn / len(negatives) if negatives else 1.0,
        "unmatched_reportable_findings": unmatched,
        "tests": rows,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark", type=Path, required=True, help="Case directory or gold_tests.json"
    )
    parser.add_argument(
        "--run", type=Path, required=True, help="Run directory or workflow_state.json"
    )
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = score_benchmark(args.benchmark, args.run)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
