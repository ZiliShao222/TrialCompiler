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
