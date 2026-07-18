from copy import deepcopy

from trialcompiler.assurance import build_assurance_case, materialize_run_summary


def base_state():
    return {
        "findings": [{"finding_id": "F1"}],
        "proposals": [{"proposal_id": "P1", "fact_ids": ["FACT1"], "evidence_source_ids": ["S1"]}],
        "decision_requests": [],
        "quality": {
            "accepted": True,
            "score": 1.0,
            "unresolved_finding_ids": [],
            "machine_repair_complete": True,
        },
        "workflow_status": "ready_for_qualified_approval",
        "verification": {"sandbox_applied": True, "regression_free": True},
    }


def test_coherent_run_is_machine_verified_but_not_released():
    state = base_state()
    case = build_assurance_case(
        state,
        summary=materialize_run_summary(run_id="r", state=state),
        scorer_result={"f1": 0.94, "negative_control_accuracy": 1.0},
    )
    assert case["outcome"] == "machine_verified_for_qualified_approval"
    assert case["release_authorized"] is False
    assert case["failed_check_ids"] == []


def test_stale_summary_is_blocked():
    state = base_state()
    summary = materialize_run_summary(run_id="r", state=state)
    summary["quality"] = {"accepted": False}
    assert (
        "artifact_consistency" in build_assurance_case(state, summary=summary)["failed_check_ids"]
    )


def test_high_f1_cannot_hide_undispositioned_finding():
    state = base_state()
    state["quality"].update({"accepted": False, "unresolved_finding_ids": ["F1"]})
    state["workflow_status"] = "machine_repair_incomplete"
    case = build_assurance_case(
        state,
        summary=materialize_run_summary(run_id="r", state=state),
        scorer_result={"f1": 0.99, "negative_control_accuracy": 1.0},
    )
    assert "unresolved_disposition" in case["failed_check_ids"]


def test_explicit_decision_queue_certifies_safe_block():
    state = base_state()
    state["quality"].update({"accepted": False, "unresolved_finding_ids": ["F1"]})
    state["decision_requests"] = [
        {"request_id": "D1", "finding_ids": ["F1"], "status": "pending_qualified_human_decision"}
    ]
    state["workflow_status"] = "awaiting_qualified_decisions"
    case = build_assurance_case(state, summary=materialize_run_summary(run_id="r", state=state))
    assert case["outcome"] == "safely_blocked_pending_qualified_resolution"


def test_missing_provenance_is_blocked():
    state = deepcopy(base_state())
    state["proposals"][0]["evidence_source_ids"] = []
    assert "proposal_provenance" in build_assurance_case(state)["failed_check_ids"]
