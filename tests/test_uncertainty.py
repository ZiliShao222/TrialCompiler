from trialcompiler.uncertainty import (
    CompetingHypothesis,
    UncertaintyAction,
    UncertaintyExplanation,
    UncertaintyType,
)


def test_uncertainty_explanation_requires_operational_evidence():
    explanation = UncertaintyExplanation(
        uncertainty_id="U1",
        finding_ids=["F1"],
        uncertainty_types=[UncertaintyType.SOURCE_CONFLICT],
        hypotheses=[CompetingHypothesis("H1", "Protocol governs", ["protocol-v2"], ["sap-v1"])],
        affected_section_ids=["eligibility"],
        resolving_observation="Obtain the signed amendment and effective date.",
        counterfactual_test=(
            "If SAP is authoritative, the proposed protocol patch must be rejected."
        ),
        selected_action=UncertaintyAction.ACQUIRE_EVIDENCE,
        action_reason="Authority cannot be inferred from recency alone.",
    )
    assert explanation.validate() == []
    assert explanation.to_dict()["explanation_complete"] is True


def test_confidence_free_explanation_rejects_empty_rationale():
    explanation = UncertaintyExplanation(
        uncertainty_id="U2",
        finding_ids=["F2"],
        uncertainty_types=[],
        hypotheses=[],
        affected_section_ids=[],
        resolving_observation="",
        counterfactual_test="",
        selected_action=UncertaintyAction.ABSTAIN,
        action_reason="",
    )
    assert len(explanation.validate()) == 6
