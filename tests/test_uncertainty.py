from trialcompiler.uncertainty import (
    AgentAction,
    AgentUncertaintyDecision,
    CounterfactualReplayResult,
    EvidenceAcquisitionOption,
    FactBeliefState,
    TraceEvidence,
    UncertaintyEstimate,
    UncertaintyKind,
    UncertaintyLocus,
    UncertaintySignal,
    select_evidence_action,
)


def estimate(*, calibrated: bool = False) -> UncertaintyEstimate:
    return UncertaintyEstimate(
        estimate_id="U1",
        step_id="S1",
        kind=UncertaintyKind.EPISTEMIC,
        locus=UncertaintyLocus.ACTION,
        signal=UncertaintySignal.ANSWER_INSTABILITY,
        value=0.42,
        estimator="five-sample semantic clustering",
        target_event="candidate patch survives independent verification",
        calibrated=calibrated,
        calibrator_id="CAL1" if calibrated else None,
        calibration_dataset_id="NCT-public-calibration" if calibrated else None,
    )


def test_trace_grounded_uncertainty_decision_is_operational():
    decision = AgentUncertaintyDecision(
        decision_id="D1",
        finding_ids=["F1"],
        trajectory_id="T1",
        estimates_before=[estimate()],
        selected_action=AgentAction.ACQUIRE_EVIDENCE,
        action_target="signed amendment with effective date",
        expected_information_gain=0.7,
        trace_evidence=[TraceEvidence("S1", ["protocol-v2"], "sha256:abc", "H1")],
        counterfactual_intervention=(
            "Replace the protocol observation with the SAP observation and replay verification."
        ),
    )
    assert decision.validate() == []
    assert decision.to_dict()["explanation_type"] == "trace_grounded_counterfactual"


def test_uncalibrated_score_must_not_claim_calibration():
    item = estimate(calibrated=True)
    item.calibration_dataset_id = None
    assert "calibration_dataset_required" in item.validate()


def test_empty_self_rationale_is_not_an_explanation():
    decision = AgentUncertaintyDecision(
        decision_id="D2",
        finding_ids=["F2"],
        trajectory_id="T2",
        estimates_before=[],
        selected_action=AgentAction.ABSTAIN,
        action_target="",
        expected_information_gain=None,
        trace_evidence=[],
        counterfactual_intervention="",
    )
    assert decision.validate() == [
        "pre_action_estimate_required",
        "trace_evidence_required",
        "counterfactual_intervention_required",
    ]


def test_information_gain_selects_the_evidence_that_best_resolves_fact_belief():
    prior = FactBeliefState({"protocol_governs": 0.5, "sap_governs": 0.5})
    signed_amendment = EvidenceAcquisitionOption(
        action_id="signed-amendment",
        evidence_target="signed amendment",
        observation_probabilities={"protocol": 0.5, "sap": 0.5},
        posterior_by_observation={
            "protocol": FactBeliefState({"protocol_governs": 0.95, "sap_governs": 0.05}),
            "sap": FactBeliefState({"protocol_governs": 0.05, "sap_governs": 0.95}),
        },
        acquisition_cost=0.1,
    )
    duplicate_copy = EvidenceAcquisitionOption(
        action_id="duplicate-copy",
        evidence_target="duplicate unsigned protocol",
        observation_probabilities={"same": 1.0},
        posterior_by_observation={"same": prior},
        acquisition_cost=0.1,
    )
    assert select_evidence_action(prior, [duplicate_copy, signed_amendment]) == signed_amendment


def test_counterfactual_replay_does_not_overclaim_mechanistic_causality():
    replay = CounterfactualReplayResult(
        source_id="SAP-v1",
        original_outcome="defer",
        removal_outcome="patch",
        replacement_outcome="no_finding",
    )
    payload = replay.to_dict()
    assert payload["necessary_for_outcome"] is True
    assert payload["claim_scope"] == "behavioral_counterfactual_not_mechanistic_causality"
