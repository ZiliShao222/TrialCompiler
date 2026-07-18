"""Typed, explainable uncertainty records for model-assisted clinical reasoning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class UncertaintyType(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    SOURCE_CONFLICT = "source_conflict"
    SEMANTIC_AMBIGUITY = "semantic_ambiguity"
    MODEL_DISAGREEMENT = "model_disagreement"
    UNKNOWN_IMPACT_SCOPE = "unknown_impact_scope"
    INSUFFICIENT_AUTHORITY = "insufficient_authority"


class UncertaintyAction(StrEnum):
    REPAIR = "repair"
    ACQUIRE_EVIDENCE = "acquire_evidence"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"


@dataclass(slots=True)
class CompetingHypothesis:
    hypothesis_id: str
    statement: str
    supporting_source_ids: list[str] = field(default_factory=list)
    opposing_source_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UncertaintyExplanation:
    uncertainty_id: str
    finding_ids: list[str]
    uncertainty_types: list[UncertaintyType]
    hypotheses: list[CompetingHypothesis]
    affected_section_ids: list[str]
    resolving_observation: str
    counterfactual_test: str
    selected_action: UncertaintyAction
    action_reason: str

    def validate(self) -> list[str]:
        failures: list[str] = []
        if not self.uncertainty_types:
            failures.append("uncertainty_type_required")
        if not self.hypotheses:
            failures.append("competing_hypothesis_required")
        if not any(
            hypothesis.supporting_source_ids or hypothesis.opposing_source_ids
            for hypothesis in self.hypotheses
        ):
            failures.append("hypothesis_evidence_required")
        if not self.resolving_observation.strip():
            failures.append("resolving_observation_required")
        if not self.counterfactual_test.strip():
            failures.append("counterfactual_test_required")
        if not self.action_reason.strip():
            failures.append("action_reason_required")
        return failures

    def to_dict(self) -> dict:
        result = asdict(self)
        result["uncertainty_types"] = [str(value) for value in self.uncertainty_types]
        result["selected_action"] = str(self.selected_action)
        result["explanation_complete"] = not self.validate()
        result["validation_failures"] = self.validate()
        return result
