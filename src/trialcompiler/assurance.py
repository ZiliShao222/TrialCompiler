"""Machine-verifiable assurance cases for clinical document compilation runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def materialize_run_summary(
    *,
    run_id: str,
    state: dict[str, Any],
    change_id: str | None = None,
    created_at: str | None = None,
    artifacts: dict[str, str] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild every state-derived summary field, preventing partial-update drift."""
    review = state.get("semantic_review", {})
    repairs = state.get("semantic_repairs", {})
    requests = state.get("decision_requests", [])
    pending = [r for r in requests if r.get("status") != "resolved_accepted"]
    result = dict(existing or {})
    result.update(
        {
            "run_id": run_id,
            "change_id": change_id,
            "quality": state.get("quality", {}),
            "finding_count": len(state.get("findings", [])),
            "proposal_count": len(state.get("proposals", [])),
            "decision_request_count": len(requests),
            "pending_decision_request_count": len(pending),
            "workflow_status": state.get("workflow_status", "unknown"),
            "verification": state.get("verification", {}),
            "uncertainty": {
                "selected_action": state.get("uncertainty_artifact", {}).get(
                    "selected_action"
                ),
                "calibration_claim_allowed": state.get("uncertainty_artifact", {}).get(
                    "calibration_claim_allowed", False
                ),
                "claim_note": state.get("uncertainty_artifact", {}).get("claim_note"),
            },
            "semantic_review": {
                "status": review.get("status", "not_run"),
                "model": review.get("model"),
                "finding_count": len(review.get("result", {}).get("semantic_findings", [])),
                "review_question_count": len(review.get("result", {}).get("review_questions", [])),
                "governance_warning_count": len(review.get("governance_warnings", [])),
            },
            "semantic_repairs": {
                "status": repairs.get("status", "not_run"),
                "model": repairs.get("model"),
                "proposal_count": len(repairs.get("proposals", [])),
                "governance_warning_count": len(repairs.get("governance_warnings", [])),
            },
        }
    )
    if created_at is not None:
        result["created_at"] = created_at
    if artifacts is not None:
        result["artifacts"] = artifacts
    result.setdefault("human_decision", "pending")
    result.setdefault("release_status", "requires_qualified_human_review")
    return result


def build_assurance_case(
    state: dict[str, Any],
    *,
    summary: dict[str, Any] | None = None,
    scorer_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Certify machine readiness or a safe explicit block; never clinical approval."""
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str, evidence: Any = None) -> None:
        item = {"check_id": name, "passed": bool(passed), "detail": detail}
        if evidence is not None:
            item["evidence"] = evidence
        checks.append(item)

    quality = state.get("quality", {})
    requests = state.get("decision_requests", [])
    pending = [r for r in requests if r.get("status") != "resolved_accepted"]
    if summary is not None:
        expected = materialize_run_summary(
            run_id=str(summary.get("run_id", "unknown")),
            change_id=summary.get("change_id"),
            state=state,
            existing=summary,
        )
        keys = (
            "quality",
            "finding_count",
            "proposal_count",
            "decision_request_count",
            "pending_decision_request_count",
            "workflow_status",
            "verification",
            "uncertainty",
        )
        mismatch = [k for k in keys if summary.get(k) != expected.get(k)]
        add("artifact_consistency", not mismatch, "State and summary must agree.", mismatch)
    else:
        add("artifact_consistency", True, "No duplicate summary supplied.")
    bad_provenance = [
        str(p.get("proposal_id", "unknown"))
        for p in state.get("proposals", [])
        if not p.get("fact_ids") or not p.get("evidence_source_ids")
    ]
    add(
        "proposal_provenance",
        not bad_provenance,
        "Every patch must name facts and evidence sources.",
        bad_provenance,
    )
    unresolved = {str(x) for x in quality.get("unresolved_finding_ids", [])}
    dispositioned = {str(x) for r in requests for x in r.get("finding_ids", [])}
    missing = sorted(unresolved - dispositioned)
    add(
        "unresolved_disposition",
        not missing,
        "Every unresolved finding must enter a qualified decision queue.",
        missing,
    )
    verification = state.get("verification", {})
    sandbox_ok = bool(verification.get("sandbox_applied")) and bool(
        verification.get("regression_free")
    )
    add(
        "sandbox_regression",
        sandbox_ok,
        "Sandbox verification must report no new finding.",
        verification,
    )
    release = summary.get("release_status") if summary else None
    allowed = {
        None,
        "requires_qualified_human_review",
        "human_approved_change_applied",
        "human_rejected_no_change",
    }
    add(
        "qualified_release_gate",
        release in allowed,
        "Only a qualified human can authorize release.",
        release,
    )
    neg = (scorer_result or {}).get("negative_control_accuracy")
    add(
        "negative_control_protection",
        scorer_result is None or neg == 1.0,
        "Declared negative controls must all be protected.",
        neg,
    )
    add(
        "metric_gate_separation",
        True,
        "Detection metrics cannot override workflow gates.",
        {"f1": (scorer_result or {}).get("f1"), "quality_accepted": quality.get("accepted")},
    )
    uncertainty = state.get("uncertainty_artifact", {})
    uncertainty_ok = bool(uncertainty) and not uncertainty.get(
        "calibration_claim_allowed", False
    )
    add(
        "uncertainty_claim_governance",
        uncertainty_ok,
        "Every new run must record a next action without claiming unfitted calibration.",
        {
            "selected_action": uncertainty.get("selected_action"),
            "claim_note": uncertainty.get("claim_note"),
        },
    )
    bindings = {"workflow_state": _digest(state)}
    if summary is not None:
        bindings["run_summary"] = _digest(summary)
    add("rollback_identity", True, "Digests bind the proof to exact artifacts.", bindings)
    failed = [c["check_id"] for c in checks if not c["passed"]]
    outcome = (
        "blocked_missing_assurance"
        if failed
        else "machine_verified_for_qualified_approval"
        if quality.get("accepted") and not pending
        else "safely_blocked_pending_qualified_resolution"
    )
    return {
        "schema": "trialcompiler.assurance/v1",
        "case_id": _digest({"state": state, "summary": summary, "score": scorer_result}),
        "outcome": outcome,
        "release_authorized": False,
        "failed_check_ids": failed,
        "checks": checks,
        "artifact_bindings": bindings,
        "interpretation": "This proof never constitutes clinical approval.",
    }
