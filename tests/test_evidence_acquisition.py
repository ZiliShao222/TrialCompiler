from trialcompiler.evidence import (
    GovernedEvidenceObservation,
    GovernedEvidenceProvider,
    run_acquisition_loop,
)
from trialcompiler.uncertainty import EvidenceAcquisitionOption, FactBeliefState


def option() -> EvidenceAcquisitionOption:
    return EvidenceAcquisitionOption(
        action_id="fetch-amendment",
        evidence_target="signed amendment",
        observation_probabilities={"protocol": 0.5, "sap": 0.5},
        posterior_by_observation={
            "protocol": FactBeliefState({"protocol": 0.95, "sap": 0.05}),
            "sap": FactBeliefState({"protocol": 0.05, "sap": 0.95}),
        },
        acquisition_cost=0.2,
    )


def observation(label: str = "protocol") -> GovernedEvidenceObservation:
    return GovernedEvidenceObservation(
        action_id="fetch-amendment",
        source_id="amendment-2",
        source_version="signed-2026-07-01",
        observation=label,
        content="The signed amendment establishes the governing endpoint definition.",
    )


def test_allowlisted_evidence_updates_belief_and_commits():
    provider = GovernedEvidenceProvider([observation()])
    result = run_acquisition_loop(
        FactBeliefState({"protocol": 0.5, "sap": 0.5}),
        [option()],
        provider,
        commit_threshold=0.9,
        max_steps=1,
        max_cost=0.5,
    )
    payload = result.to_dict()
    assert payload["final_decision"]["action"] == "commit_candidate"
    assert payload["steps"][0]["source_id"] == "amendment-2"
    assert payload["steps"][0]["content_digest"].startswith("sha256:")
    assert payload["calibration_claim_allowed"] is False


def test_budget_boundary_defers_without_fetching():
    result = run_acquisition_loop(
        FactBeliefState({"protocol": 0.5, "sap": 0.5}),
        [option()],
        GovernedEvidenceProvider([observation()]),
        commit_threshold=0.9,
        max_steps=1,
        max_cost=0.1,
    )
    assert result.status == "deferred_no_positive_affordable_action"
    assert result.steps == []
    assert result.final_decision.action == "defer_to_human"


def test_unknown_observation_blocks_and_defers():
    result = run_acquisition_loop(
        FactBeliefState({"protocol": 0.5, "sap": 0.5}),
        [option()],
        GovernedEvidenceProvider([observation("unmodeled")]),
        commit_threshold=0.9,
        max_steps=1,
        max_cost=0.5,
    )
    assert result.status == "blocked_invalid_observation"
    assert result.failure == "unknown_observation: unmodeled"
    assert result.final_decision.action == "defer_to_human"


def test_provider_rejects_unallowlisted_and_duplicate_actions():
    provider = GovernedEvidenceProvider([observation()])
    try:
        provider.acquire("not-approved")
    except ValueError as exc:
        assert str(exc) == "evidence_action_not_allowlisted"
    else:
        raise AssertionError("unallowlisted action must fail")
    provider.acquire("fetch-amendment")
    try:
        provider.acquire("fetch-amendment")
    except ValueError as exc:
        assert str(exc) == "evidence_action_already_used"
    else:
        raise AssertionError("duplicate acquisition must fail")
