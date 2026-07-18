"""Trajectory-level uncertainty and trace-grounded explanations for agents.

The module deliberately separates uncertainty *kind* and *locus* from observed
diagnostic signals. Evidence conflict is a signal; it is not itself a canonical
uncertainty kind. Numeric probabilities are marked calibrated only when a named
calibrator and evaluation set are supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from math import log2


class UncertaintyKind(StrEnum):
    EPISTEMIC = "epistemic"
    ALEATORIC = "aleatoric"


class UncertaintyLocus(StrEnum):
    OBSERVATION = "observation"
    BELIEF_STATE = "belief_state"
    ACTION = "action"
    TRAJECTORY_OUTCOME = "trajectory_outcome"


class UncertaintySignal(StrEnum):
    SEMANTIC_ENTROPY = "semantic_entropy"
    ANSWER_INSTABILITY = "answer_instability"
    SOURCE_DISAGREEMENT = "source_disagreement"
    VERIFIER_DISAGREEMENT = "verifier_disagreement"
    EVIDENCE_COVERAGE_GAP = "evidence_coverage_gap"
    OUT_OF_DISTRIBUTION = "out_of_distribution"


class AgentAction(StrEnum):
    COMMIT_CANDIDATE = "commit_candidate"
    ACQUIRE_EVIDENCE = "acquire_evidence"
    DELIBERATE = "deliberate"
    ABSTAIN = "abstain"
    DEFER_TO_HUMAN = "defer_to_human"


@dataclass(slots=True)
class UncertaintyEstimate:
    """One estimate at a specific point in an agent trajectory."""

    estimate_id: str
    step_id: str
    kind: UncertaintyKind
    locus: UncertaintyLocus
    signal: UncertaintySignal
    value: float | None
    estimator: str
    target_event: str
    calibrated: bool = False
    calibrator_id: str | None = None
    calibration_dataset_id: str | None = None

    def validate(self) -> list[str]:
        failures: list[str] = []
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            failures.append("estimate_out_of_range")
        if self.calibrated and not self.calibrator_id:
            failures.append("calibrator_id_required")
        if self.calibrated and not self.calibration_dataset_id:
            failures.append("calibration_dataset_required")
        if not self.target_event.strip():
            failures.append("target_event_required")
        return failures


@dataclass(slots=True)
class TraceEvidence:
    """Replayable evidence for an explanation, not a free-form model rationale."""

    step_id: str
    source_ids: list[str]
    observation_digest: str
    supports: str
    contradicts: str | None = None


@dataclass(slots=True)
class AgentUncertaintyDecision:
    decision_id: str
    finding_ids: list[str]
    trajectory_id: str
    estimates_before: list[UncertaintyEstimate]
    selected_action: AgentAction
    action_target: str
    expected_information_gain: float | None
    trace_evidence: list[TraceEvidence]
    counterfactual_intervention: str
    estimates_after: list[UncertaintyEstimate] = field(default_factory=list)
    observed_uncertainty_reduction: float | None = None

    def validate(self) -> list[str]:
        failures = [
            failure
            for estimate in self.estimates_before + self.estimates_after
            for failure in estimate.validate()
        ]
        if not self.estimates_before:
            failures.append("pre_action_estimate_required")
        if not self.trace_evidence:
            failures.append("trace_evidence_required")
        if not self.counterfactual_intervention.strip():
            failures.append("counterfactual_intervention_required")
        if (
            self.expected_information_gain is not None
            and not 0 <= self.expected_information_gain <= 1
        ):
            failures.append("expected_information_gain_out_of_range")
        if (
            self.observed_uncertainty_reduction is not None
            and not -1 <= self.observed_uncertainty_reduction <= 1
        ):
            failures.append("observed_reduction_out_of_range")
        return failures

    def to_dict(self) -> dict:
        result = asdict(self)
        result["selected_action"] = str(self.selected_action)
        result["explanation_type"] = "trace_grounded_counterfactual"
        result["explanation_complete"] = not self.validate()
        result["validation_failures"] = self.validate()
        result["clinical_authority"] = "none"
        return result


@dataclass(slots=True)
class FactBeliefState:
    """A finite belief over mutually exclusive canonical-fact hypotheses."""

    hypothesis_probabilities: dict[str, float]

    def validate(self) -> list[str]:
        if not self.hypothesis_probabilities:
            return ["hypothesis_distribution_required"]
        if any(value < 0 or value > 1 for value in self.hypothesis_probabilities.values()):
            return ["hypothesis_probability_out_of_range"]
        if abs(sum(self.hypothesis_probabilities.values()) - 1.0) > 1e-6:
            return ["hypothesis_distribution_not_normalized"]
        return []

    def entropy(self) -> float:
        failures = self.validate()
        if failures:
            raise ValueError(", ".join(failures))
        return -sum(p * log2(p) for p in self.hypothesis_probabilities.values() if p > 0)


@dataclass(slots=True)
class EvidenceAcquisitionOption:
    """Possible observation outcomes and their posterior fact beliefs."""

    action_id: str
    evidence_target: str
    observation_probabilities: dict[str, float]
    posterior_by_observation: dict[str, FactBeliefState]
    acquisition_cost: float = 0.0

    def expected_information_gain(self, prior: FactBeliefState) -> float:
        if abs(sum(self.observation_probabilities.values()) - 1.0) > 1e-6:
            raise ValueError("observation_distribution_not_normalized")
        if set(self.observation_probabilities) != set(self.posterior_by_observation):
            raise ValueError("observation_posterior_mismatch")
        expected_posterior_entropy = sum(
            probability * self.posterior_by_observation[name].entropy()
            for name, probability in self.observation_probabilities.items()
        )
        return prior.entropy() - expected_posterior_entropy

    def utility(self, prior: FactBeliefState, cost_weight: float) -> float:
        return self.expected_information_gain(prior) - cost_weight * self.acquisition_cost

    def posterior_for(self, observation: str) -> FactBeliefState:
        """Return the declared posterior for an actually observed outcome."""
        if observation not in self.posterior_by_observation:
            raise ValueError(f"unknown_observation: {observation}")
        posterior = self.posterior_by_observation[observation]
        failures = posterior.validate()
        if failures:
            raise ValueError(", ".join(failures))
        return posterior


def select_evidence_action(
    prior: FactBeliefState,
    options: list[EvidenceAcquisitionOption],
    *,
    cost_weight: float = 1.0,
) -> EvidenceAcquisitionOption | None:
    """Select positive net-information acquisition; otherwise abstain from searching."""
    if not options:
        return None
    ranked = sorted(
        options,
        key=lambda option: (-option.utility(prior, cost_weight), option.action_id),
    )
    return ranked[0] if ranked[0].utility(prior, cost_weight) > 0 else None


@dataclass(slots=True)
class EvidenceAcquisitionStep:
    """One auditable belief update produced by an evidence observation."""

    action_id: str
    evidence_target: str
    observation: str
    prior: FactBeliefState
    posterior: FactBeliefState
    expected_information_gain: float
    observed_information_gain: float
    acquisition_cost: float

    def to_dict(self) -> dict:
        return asdict(self)


def execute_evidence_acquisition(
    prior: FactBeliefState,
    option: EvidenceAcquisitionOption,
    *,
    observation: str,
) -> EvidenceAcquisitionStep:
    """Apply an observation model and record expected versus realized entropy change.

    The observation is supplied by a tool or experiment harness. This function never
    invents a probability or observation from an LLM response.
    """
    prior_failures = prior.validate()
    if prior_failures:
        raise ValueError(", ".join(prior_failures))
    posterior = option.posterior_for(observation)
    return EvidenceAcquisitionStep(
        action_id=option.action_id,
        evidence_target=option.evidence_target,
        observation=observation,
        prior=prior,
        posterior=posterior,
        expected_information_gain=option.expected_information_gain(prior),
        observed_information_gain=prior.entropy() - posterior.entropy(),
        acquisition_cost=option.acquisition_cost,
    )


@dataclass(slots=True)
class BeliefPolicyDecision:
    """Explicit stopping policy over a canonical-fact belief state."""

    action: AgentAction
    leading_hypothesis: str
    leading_probability: float
    reason: str


def decide_from_belief(
    belief: FactBeliefState,
    *,
    commit_threshold: float,
    evidence_available: bool,
) -> BeliefPolicyDecision:
    """Commit only above threshold; otherwise acquire evidence or defer."""
    failures = belief.validate()
    if failures:
        raise ValueError(", ".join(failures))
    if not 0.5 <= commit_threshold <= 1.0:
        raise ValueError("commit_threshold_out_of_range")
    leading_hypothesis, leading_probability = max(
        belief.hypothesis_probabilities.items(), key=lambda item: (item[1], item[0])
    )
    if leading_probability >= commit_threshold:
        action = AgentAction.COMMIT_CANDIDATE
        reason = "belief_exceeds_commit_threshold"
    elif evidence_available:
        action = AgentAction.ACQUIRE_EVIDENCE
        reason = "belief_below_threshold_and_evidence_available"
    else:
        action = AgentAction.DEFER_TO_HUMAN
        reason = "belief_below_threshold_and_no_evidence_available"
    return BeliefPolicyDecision(action, leading_hypothesis, leading_probability, reason)


@dataclass(slots=True)
class CounterfactualReplayResult:
    """Behavioral faithfulness evidence for a claimed influential source."""

    source_id: str
    original_outcome: str
    removal_outcome: str
    replacement_outcome: str | None = None

    @property
    def necessary_for_outcome(self) -> bool:
        return self.original_outcome != self.removal_outcome

    @property
    def contrastive_effect_observed(self) -> bool:
        return self.replacement_outcome is not None and (
            self.replacement_outcome != self.original_outcome
        )

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "necessary_for_outcome": self.necessary_for_outcome,
            "contrastive_effect_observed": self.contrastive_effect_observed,
            "claim_scope": "behavioral_counterfactual_not_mechanistic_causality",
        }
