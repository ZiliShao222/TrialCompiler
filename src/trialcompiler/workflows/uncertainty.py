"""Translate a completed review workflow into an auditable uncertainty artifact."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from trialcompiler.evidence import (
    GovernedEvidenceObservation,
    GovernedEvidenceProvider,
    run_acquisition_loop,
)
from trialcompiler.uncertainty import (
    AgentAction,
    AgentUncertaintyDecision,
    EvidenceAcquisitionOption,
    FactBeliefState,
    TraceEvidence,
    UncertaintyEstimate,
    UncertaintyKind,
    UncertaintyLocus,
    UncertaintySignal,
)

TARGET_EVENT = "candidate patch survives independent verification and qualified review"


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _estimate(
    estimate_id: str,
    *,
    step_id: str,
    locus: UncertaintyLocus,
    signal: UncertaintySignal,
    estimator: str,
) -> UncertaintyEstimate:
    return UncertaintyEstimate(
        estimate_id=estimate_id,
        step_id=step_id,
        kind=UncertaintyKind.EPISTEMIC,
        locus=locus,
        signal=signal,
        value=None,
        estimator=estimator,
        target_event=TARGET_EVENT,
    )


def build_workflow_uncertainty_artifact(state: dict[str, Any]) -> dict[str, Any]:
    """Build diagnostic uncertainty without inventing a calibrated probability."""
    findings = state.get("findings", [])
    proposals = state.get("proposals", [])
    quality = state.get("quality", {})
    semantic = state.get("semantic_review", {})
    decision_requests = state.get("decision_requests", [])
    source_ids = sorted(
        {
            str(source_id)
            for item in findings + proposals
            for source_id in item.get("evidence_source_ids", [])
        }
    )
    estimates: list[UncertaintyEstimate] = []
    if semantic.get("status") != "completed":
        estimates.append(
            _estimate(
                "workflow-semantic-coverage",
                step_id="B_evidence",
                locus=UncertaintyLocus.OBSERVATION,
                signal=UncertaintySignal.EVIDENCE_COVERAGE_GAP,
                estimator="semantic_review_completion_diagnostic",
            )
        )
    if decision_requests or quality.get("unresolved_finding_ids"):
        estimates.append(
            _estimate(
                "workflow-decision-debt",
                step_id="D_quality",
                locus=UncertaintyLocus.ACTION,
                signal=UncertaintySignal.EVIDENCE_COVERAGE_GAP,
                estimator="unresolved_decision_debt_diagnostic",
            )
        )
    if any(not item.get("evidence_source_ids") for item in proposals):
        estimates.append(
            _estimate(
                "workflow-provenance-gap",
                step_id="C_repair",
                locus=UncertaintyLocus.OBSERVATION,
                signal=UncertaintySignal.EVIDENCE_COVERAGE_GAP,
                estimator="proposal_provenance_diagnostic",
            )
        )
    if not estimates:
        estimates.append(
            _estimate(
                "workflow-outcome-status",
                step_id="D_quality",
                locus=UncertaintyLocus.TRAJECTORY_OUTCOME,
                signal=UncertaintySignal.VERIFIER_DISAGREEMENT,
                estimator="quality_gate_status_diagnostic",
            )
        )

    if decision_requests:
        action = AgentAction.DEFER_TO_HUMAN
        action_target = "resolve qualified decision requests"
    elif semantic.get("status") != "completed":
        action = AgentAction.ACQUIRE_EVIDENCE
        action_target = "complete governed semantic review or obtain equivalent evidence"
    elif not quality.get("accepted"):
        action = AgentAction.DELIBERATE
        action_target = "repair unresolved findings and repeat independent quality gate"
    else:
        action = AgentAction.COMMIT_CANDIDATE
        action_target = "submit candidate review packet for qualified approval"

    evidence = TraceEvidence(
        step_id="workflow-final",
        source_ids=source_ids,
        observation_digest=_digest(
            {
                "review_coverage": state.get("review_coverage", {}),
                "quality": quality,
                "decision_requests": decision_requests,
                "proposal_ids": [item.get("proposal_id") for item in proposals],
            }
        ),
        supports=action.value,
        contradicts=None,
    )
    influential_source = source_ids[0] if source_ids else "the recorded evidence set"
    decision = AgentUncertaintyDecision(
        decision_id="workflow-final-uncertainty-decision",
        finding_ids=[str(item.get("finding_id")) for item in findings],
        trajectory_id=_digest(state.get("trace", [])),
        estimates_before=estimates,
        selected_action=action,
        action_target=action_target,
        expected_information_gain=None,
        trace_evidence=[evidence],
        counterfactual_intervention=(
            f"Remove or replace {influential_source}, rerun B/C/D with frozen configuration, "
            "and compare finding, action, and patch outcomes."
        ),
    )
    artifact = decision.to_dict()
    artifact["numeric_probability_available"] = False
    artifact["calibration_claim_allowed"] = False
    artifact["claim_note"] = "diagnostic_signals_only_no_fitted_calibrator"
    acquisition = state.get("evidence_acquisition_config")
    if not acquisition and "prior" in state.get("evidence_acquisition", {}):
        acquisition = state["evidence_acquisition"]
    if acquisition and action is AgentAction.ACQUIRE_EVIDENCE:
        prior = FactBeliefState(acquisition["prior"])
        options = [
            EvidenceAcquisitionOption(
                action_id=item["action_id"],
                evidence_target=item["evidence_target"],
                observation_probabilities=item["observation_probabilities"],
                posterior_by_observation={
                    name: FactBeliefState(probabilities)
                    for name, probabilities in item["posterior_by_observation"].items()
                },
                acquisition_cost=float(item.get("acquisition_cost", 0.0)),
            )
            for item in acquisition.get("options", [])
        ]
        provider = GovernedEvidenceProvider(
            [GovernedEvidenceObservation(**item) for item in acquisition.get("observations", [])]
        )
        policy = acquisition.get("policy", {})
        loop = run_acquisition_loop(
            prior,
            options,
            provider,
            commit_threshold=float(policy.get("commit_threshold", 0.9)),
            max_steps=int(policy.get("max_steps", 1)),
            max_cost=float(policy.get("max_cost", 1.0)),
            cost_weight=float(policy.get("cost_weight", 1.0)),
        ).to_dict()
        artifact["acquisition_loop"] = loop
        if loop["steps"] and loop["status"] not in {
            "blocked_invalid_observation",
            "deferred_no_positive_affordable_action",
        }:
            artifact["selected_action"] = AgentAction.DELIBERATE.value
            artifact["action_target"] = (
                "rerun evidence review, repair, and quality gate with acquired evidence"
            )
        else:
            artifact["selected_action"] = AgentAction.DEFER_TO_HUMAN.value
            artifact["action_target"] = "resolve failed or exhausted evidence acquisition"
        artifact["observed_information_gain_bits"] = sum(
            step["observed_information_gain"] for step in loop["steps"]
        )
        artifact["governance_note"] = (
            "Belief threshold cannot bypass B/C/D reverification or qualified review."
        )
    return artifact
