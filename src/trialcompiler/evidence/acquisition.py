"""Budgeted, allowlisted evidence acquisition with fail-closed belief updates."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

from trialcompiler.uncertainty import (
    AgentAction,
    BeliefPolicyDecision,
    EvidenceAcquisitionOption,
    FactBeliefState,
    decide_from_belief,
    execute_evidence_acquisition,
    select_evidence_action,
)


@dataclass(frozen=True, slots=True)
class GovernedEvidenceObservation:
    """An observation admitted by source identity, version, and content digest."""

    action_id: str
    source_id: str
    source_version: str
    observation: str
    content: str

    @property
    def content_digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def validate(self) -> list[str]:
        failures: list[str] = []
        if not self.action_id.strip():
            failures.append("action_id_required")
        if not self.source_id.strip():
            failures.append("source_id_required")
        if not self.source_version.strip():
            failures.append("source_version_required")
        if not self.observation.strip():
            failures.append("observation_required")
        if not self.content.strip():
            failures.append("evidence_content_required")
        return failures


class GovernedEvidenceProvider:
    """Deterministic allowlist provider used by a tool adapter or experiment harness."""

    def __init__(self, observations: list[GovernedEvidenceObservation]) -> None:
        failures = [failure for item in observations for failure in item.validate()]
        if failures:
            raise ValueError(", ".join(failures))
        action_ids = [item.action_id for item in observations]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("duplicate_action_id")
        self._observations = {item.action_id: item for item in observations}
        self._used: set[str] = set()

    def available_action_ids(self) -> set[str]:
        return set(self._observations) - self._used

    def acquire(self, action_id: str) -> GovernedEvidenceObservation:
        if action_id not in self._observations:
            raise ValueError("evidence_action_not_allowlisted")
        if action_id in self._used:
            raise ValueError("evidence_action_already_used")
        self._used.add(action_id)
        return self._observations[action_id]


@dataclass(slots=True)
class AcquisitionLoopResult:
    initial_belief: FactBeliefState
    final_belief: FactBeliefState
    final_decision: BeliefPolicyDecision
    steps: list[dict] = field(default_factory=list)
    total_cost: float = 0.0
    status: str = "completed"
    failure: str | None = None

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "final_decision": asdict(self.final_decision),
            "clinical_authority": "none",
            "calibration_claim_allowed": False,
        }


def run_acquisition_loop(
    prior: FactBeliefState,
    options: list[EvidenceAcquisitionOption],
    provider: GovernedEvidenceProvider,
    *,
    commit_threshold: float,
    max_steps: int,
    max_cost: float,
    cost_weight: float = 1.0,
) -> AcquisitionLoopResult:
    """Acquire allowlisted evidence until commit, exhaustion, or a hard budget boundary."""
    if max_steps < 0:
        raise ValueError("max_steps_out_of_range")
    if max_cost < 0:
        raise ValueError("max_cost_out_of_range")
    current = prior
    steps: list[dict] = []
    total_cost = 0.0
    remaining = {option.action_id: option for option in options}

    while len(steps) < max_steps:
        available_ids = provider.available_action_ids() & set(remaining)
        available = [remaining[action_id] for action_id in available_ids]
        decision = decide_from_belief(
            current,
            commit_threshold=commit_threshold,
            evidence_available=bool(available),
        )
        if decision.action is not AgentAction.ACQUIRE_EVIDENCE:
            return AcquisitionLoopResult(prior, current, decision, steps, total_cost)
        affordable = [
            option for option in available if total_cost + option.acquisition_cost <= max_cost
        ]
        selected = select_evidence_action(current, affordable, cost_weight=cost_weight)
        if selected is None:
            deferred = decide_from_belief(
                current, commit_threshold=commit_threshold, evidence_available=False
            )
            return AcquisitionLoopResult(
                prior,
                current,
                deferred,
                steps,
                total_cost,
                status="deferred_no_positive_affordable_action",
            )
        try:
            observation = provider.acquire(selected.action_id)
            step = execute_evidence_acquisition(
                current, selected, observation=observation.observation
            )
        except ValueError as exc:
            deferred = decide_from_belief(
                current, commit_threshold=commit_threshold, evidence_available=False
            )
            return AcquisitionLoopResult(
                prior,
                current,
                deferred,
                steps,
                total_cost,
                status="blocked_invalid_observation",
                failure=str(exc),
            )
        step_payload = step.to_dict()
        step_payload["source_id"] = observation.source_id
        step_payload["source_version"] = observation.source_version
        step_payload["content_digest"] = observation.content_digest
        steps.append(step_payload)
        total_cost += selected.acquisition_cost
        current = step.posterior
        remaining.pop(selected.action_id)

    decision = decide_from_belief(
        current, commit_threshold=commit_threshold, evidence_available=False
    )
    return AcquisitionLoopResult(
        prior,
        current,
        decision,
        steps,
        total_cost,
        status=(
            "step_budget_exhausted"
            if decision.action is AgentAction.DEFER_TO_HUMAN
            else "completed"
        ),
    )
