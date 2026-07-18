from trialcompiler.workflows.uncertainty import build_workflow_uncertainty_artifact


def base_state() -> dict:
    return {
        "findings": [
            {
                "finding_id": "F1",
                "evidence_source_ids": ["protocol-v2"],
            }
        ],
        "proposals": [
            {
                "proposal_id": "P1",
                "evidence_source_ids": ["protocol-v2"],
            }
        ],
        "review_coverage": {"deterministic": "completed", "semantic": "completed"},
        "semantic_review": {"status": "completed"},
        "quality": {"accepted": True, "unresolved_finding_ids": []},
        "decision_requests": [],
        "trace": [{"agent": "D", "action": "quality_gate"}],
    }


def test_completed_workflow_submits_candidate_without_claiming_probability():
    artifact = build_workflow_uncertainty_artifact(base_state())
    assert artifact["selected_action"] == "commit_candidate"
    assert artifact["numeric_probability_available"] is False
    assert artifact["calibration_claim_allowed"] is False
    assert artifact["explanation_complete"] is True


def test_decision_debt_forces_human_defer():
    state = base_state()
    state["decision_requests"] = [{"request_id": "D1"}]
    artifact = build_workflow_uncertainty_artifact(state)
    assert artifact["selected_action"] == "defer_to_human"
    assert artifact["estimates_before"][0]["value"] is None


def test_missing_semantic_coverage_requests_more_evidence():
    state = base_state()
    state["semantic_review"] = {"status": "not_run"}
    artifact = build_workflow_uncertainty_artifact(state)
    assert artifact["selected_action"] == "acquire_evidence"
    assert artifact["claim_note"] == "diagnostic_signals_only_no_fitted_calibrator"


def test_allowlisted_acquisition_executes_inside_workflow_artifact():
    state = base_state()
    state["semantic_review"] = {"status": "not_run"}
    state["evidence_acquisition"] = {
        "prior": {"protocol": 0.5, "sap": 0.5},
        "options": [
            {
                "action_id": "fetch-amendment",
                "evidence_target": "signed amendment",
                "observation_probabilities": {"protocol": 0.5, "sap": 0.5},
                "posterior_by_observation": {
                    "protocol": {"protocol": 0.95, "sap": 0.05},
                    "sap": {"protocol": 0.05, "sap": 0.95},
                },
                "acquisition_cost": 0.2,
            }
        ],
        "observations": [
            {
                "action_id": "fetch-amendment",
                "source_id": "amendment-2",
                "source_version": "signed-v2",
                "observation": "protocol",
                "content": "Signed evidence content",
            }
        ],
        "policy": {"commit_threshold": 0.9, "max_steps": 1, "max_cost": 0.5},
    }
    artifact = build_workflow_uncertainty_artifact(state)
    assert artifact["selected_action"] == "deliberate"
    assert artifact["acquisition_loop"]["final_decision"]["action"] == "commit_candidate"
    assert artifact["acquisition_loop"]["steps"][0]["source_id"] == "amendment-2"
    assert artifact["observed_information_gain_bits"] > 0
    assert "cannot bypass" in artifact["governance_note"]


def test_acquisition_cannot_override_qualified_decision_debt():
    state = base_state()
    state["decision_requests"] = [{"request_id": "D1"}]
    state["evidence_acquisition"] = {"prior": {"a": 0.5, "b": 0.5}}
    artifact = build_workflow_uncertainty_artifact(state)
    assert artifact["selected_action"] == "defer_to_human"
    assert "acquisition_loop" not in artifact
