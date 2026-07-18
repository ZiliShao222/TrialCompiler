"""Constrained, benchmark-only simulation of qualified reviewer decisions.

This module deliberately has no dependency on ``ProjectWorkspace``.  A simulated
decision is an evaluator artifact and can never resolve a workflow request or
create a real approval.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ReviewerRole(StrEnum):
    MEDICAL = "medical"
    STATISTICAL = "statistical"
    REGISTRATION = "registration"
    QUALITY = "quality"


class SimulatedOutcome(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    REQUEST_EVIDENCE = "request_evidence"


PENDING_STATUSES = {"pending", "pending_qualified_human_decision"}
DEFAULT_ACTION_MAP = {
    "reject": SimulatedOutcome.REJECT,
    "rejected": SimulatedOutcome.REJECT,
    "deny": SimulatedOutcome.REJECT,
    "unsupported": SimulatedOutcome.REJECT,
    "must_reject": SimulatedOutcome.REJECT,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return [str(item) for item in value]
    return [str(value)]


def _plain_mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError("Expected a mapping or dataclass")


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    source_id: str
    locator: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class SimulatedDecision:
    request_id: str
    decision: str
    rationale: str
    cited_evidence: list[dict[str, str]]
    confidence: float
    role: str
    simulation_only: bool = True
    authority: str = "benchmark_simulation"
    real_approval: bool = False
    decision_id: str = field(default_factory=lambda: f"sim-{uuid.uuid4().hex[:12]}")
    reviewed_at: str = field(default_factory=_now)
    missing_evidence_source_ids: list[str] = field(default_factory=list)
    gold_test_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _evidence_index(
    evidence: Sequence[Mapping[str, Any] | Any],
) -> dict[str, EvidenceCitation]:
    indexed: dict[str, EvidenceCitation] = {}
    for raw in evidence:
        item = _plain_mapping(raw)
        source_id = str(item.get("source_id", "")).strip()
        locator = str(item.get("locator", item.get("path", ""))).strip()
        excerpt = str(
            item.get("excerpt", item.get("content", item.get("text", item.get("value", ""))))
        ).strip()
        available = item.get("available", True) is not False
        if source_id and locator and excerpt and available:
            indexed[source_id] = EvidenceCitation(source_id, locator, excerpt)
    return indexed


def _gold_tests(gold: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(gold, Mapping):
        tests = gold.get("tests", gold.get("decisions", []))
    else:
        tests = gold
    return [dict(item) for item in tests if isinstance(item, Mapping)]


def _matching_gold(
    request: Mapping[str, Any], tests: Sequence[dict[str, Any]]
) -> dict[str, Any] | None:
    request_ids = {
        str(request.get("request_id", "")),
        *(_strings(request.get("finding_ids"))),
    }
    exact = [
        item
        for item in tests
        if str(item.get("test_id", item.get("request_id", ""))) in request_ids
    ]
    if len(exact) == 1:
        return exact[0]
    section_ids = set(_strings(request.get("section_ids")))
    if section_ids:
        scored = [
            (len(section_ids.intersection(_strings(item.get("expected_section_ids")))), item)
            for item in tests
        ]
        best = max((score for score, _ in scored), default=0)
        candidates = [item for score, item in scored if score == best and score > 0]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _policy_for_role(policy: Mapping[str, Any], role: ReviewerRole) -> dict[str, Any]:
    merged = dict(policy)
    role_rules = policy.get("roles", policy.get("role_policies", {}))
    if isinstance(role_rules, Mapping) and isinstance(role_rules.get(role.value), Mapping):
        merged.update(role_rules[role.value])
    return merged


def _mapped_outcome(action: str, policy: Mapping[str, Any]) -> SimulatedOutcome:
    configured = policy.get("action_mapping", {})
    if not isinstance(configured, Mapping):
        configured = {}
    raw = configured.get(action, DEFAULT_ACTION_MAP.get(action, "request_evidence"))
    try:
        return SimulatedOutcome(str(raw))
    except ValueError:
        return SimulatedOutcome.REQUEST_EVIDENCE


class SimulatedReviewer:
    """Evaluate pending requests without exercising real approval authority."""

    def __init__(self, role: ReviewerRole | str) -> None:
        self.role = ReviewerRole(role)

    def review(
        self,
        request: Mapping[str, Any] | Any,
        *,
        evidence: Sequence[Mapping[str, Any] | Any],
        gold: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        evaluator_policy: Mapping[str, Any],
    ) -> SimulatedDecision:
        request_data = _plain_mapping(request)
        request_id = str(request_data.get("request_id", "")).strip()
        if not request_id:
            raise ValueError("DecisionRequest requires request_id")
        if str(request_data.get("status", "")) not in PENDING_STATUSES:
            raise ValueError(f"DecisionRequest {request_id} is not pending")
        if evaluator_policy.get("simulation_only") is not True:
            raise ValueError("Evaluator policy must explicitly set simulation_only=true")

        role_policy = _policy_for_role(evaluator_policy, self.role)
        match = _matching_gold(request_data, _gold_tests(gold))
        evidence_by_id = _evidence_index(evidence)
        required = set(_strings(request_data.get("evidence_source_ids")))
        if match:
            required.update(
                str(item.get("source_id", ""))
                for item in match.get("evidence", [])
                if isinstance(item, Mapping) and item.get("source_id")
            )
        required.update(_strings(role_policy.get("required_evidence_source_ids")))
        minimum = max(1, int(role_policy.get("minimum_evidence_count", 1)))
        missing = sorted(source_id for source_id in required if source_id not in evidence_by_id)
        citations = [
            asdict(evidence_by_id[source_id])
            for source_id in sorted(required)
            if source_id in evidence_by_id
        ]
        if not required:
            missing = ["unspecified_source_evidence"]
        insufficient = bool(missing) or len(citations) < minimum

        if not match:
            outcome = SimulatedOutcome.REQUEST_EVIDENCE
            rationale = "No unique gold/evaluator rule matches this pending request."
            confidence = 0.2
        elif insufficient:
            outcome = SimulatedOutcome.REQUEST_EVIDENCE
            rationale = "Required source evidence is missing or not substantively citable."
            confidence = 0.98
        else:
            action = str(match.get("expected_action", match.get("decision", ""))).strip()
            outcome = _mapped_outcome(action, role_policy)
            rationale = (
                f"Evaluator policy maps gold action '{action}' to '{outcome.value}' "
                f"for the {self.role.value} simulation role."
            )
            confidence = float(role_policy.get("confidence", 0.9))

        allowed = set(
            _strings(
                role_policy.get("allowed_decisions", [item.value for item in SimulatedOutcome])
            )
        )
        if outcome.value not in allowed:
            outcome = SimulatedOutcome.REQUEST_EVIDENCE
            rationale = "The evaluator policy does not authorize the simulated outcome."
            confidence = min(confidence, 0.75)
        confidence = min(1.0, max(0.0, confidence))
        return SimulatedDecision(
            request_id=request_id,
            decision=outcome.value,
            rationale=rationale,
            cited_evidence=citations,
            confidence=confidence,
            role=self.role.value,
            missing_evidence_source_ids=missing,
            gold_test_id=(str(match.get("test_id")) if match and match.get("test_id") else None),
        )


class SimulatedReviewCommittee:
    """Conservatively aggregate all four independent simulated reviewer roles."""

    def __init__(self, roles: Sequence[ReviewerRole | str] | None = None) -> None:
        selected = roles or list(ReviewerRole)
        self.reviewers = [SimulatedReviewer(role) for role in selected]
        if not self.reviewers:
            raise ValueError("A committee requires at least one reviewer role")

    def review(
        self,
        request: Mapping[str, Any] | Any,
        *,
        evidence: Sequence[Mapping[str, Any] | Any],
        gold: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        evaluator_policy: Mapping[str, Any],
    ) -> dict[str, Any]:
        votes = [
            reviewer.review(
                request,
                evidence=evidence,
                gold=gold,
                evaluator_policy=evaluator_policy,
            )
            for reviewer in self.reviewers
        ]
        outcomes = {vote.decision for vote in votes}
        if SimulatedOutcome.REJECT.value in outcomes:
            decision = SimulatedOutcome.REJECT.value
            rationale = "Committee rejects because at least one constrained role rejected."
        elif outcomes == {SimulatedOutcome.ACCEPT.value}:
            decision = SimulatedOutcome.ACCEPT.value
            rationale = "All constrained reviewer roles accepted with citable evidence."
        else:
            decision = SimulatedOutcome.REQUEST_EVIDENCE.value
            rationale = "Committee cannot accept without unanimous evidence-supported acceptance."
        cited = {
            (item["source_id"], item["locator"], item["excerpt"]): item
            for vote in votes
            for item in vote.cited_evidence
        }
        return {
            "request_id": votes[0].request_id,
            "decision": decision,
            "rationale": rationale,
            "cited_evidence": list(cited.values()),
            "confidence": min(vote.confidence for vote in votes),
            "role": "committee",
            "simulation_only": True,
            "authority": "benchmark_simulation",
            "real_approval": False,
            "decision_id": f"sim-committee-{uuid.uuid4().hex[:12]}",
            "reviewed_at": _now(),
            "votes": [vote.to_dict() for vote in votes],
        }


def review_pending_requests(
    requests: Sequence[Mapping[str, Any] | Any],
    *,
    evidence: Sequence[Mapping[str, Any] | Any],
    gold: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    evaluator_policy: Mapping[str, Any],
    committee: SimulatedReviewCommittee | None = None,
) -> list[dict[str, Any]]:
    """Review only pending requests; resolved requests are never reconsidered."""
    panel = committee or SimulatedReviewCommittee()
    return [
        panel.review(
            request,
            evidence=evidence,
            gold=gold,
            evaluator_policy=evaluator_policy,
        )
        for request in requests
        if str(_plain_mapping(request).get("status", "")) in PENDING_STATUSES
    ]


def write_audit_json(
    path: str | Path,
    decisions: Sequence[Mapping[str, Any] | SimulatedDecision],
) -> Path:
    """Atomically retain simulation output outside any real approval directory."""
    target = Path(path)
    if "approvals" in {part.casefold() for part in target.parts}:
        raise ValueError("Simulation audit must not be written to a real approvals directory")
    plain_decisions = [
        item.to_dict() if isinstance(item, SimulatedDecision) else dict(item) for item in decisions
    ]
    required_fields = {
        "decision",
        "rationale",
        "cited_evidence",
        "confidence",
        "role",
        "simulation_only",
    }
    for item in plain_decisions:
        missing_fields = sorted(required_fields.difference(item))
        if missing_fields:
            raise ValueError(
                "Simulation audit decision is missing fields: " + ", ".join(missing_fields)
            )
        if item["simulation_only"] is not True or item.get("real_approval", False) is not False:
            raise ValueError("Simulation audit cannot contain a real approval")
        if item["decision"] not in {outcome.value for outcome in SimulatedOutcome}:
            raise ValueError(f"Invalid simulated decision: {item['decision']}")
    payload = {
        "audit_type": "benchmark_simulated_reviewer",
        "simulation_only": True,
        "created_at": _now(),
        "decisions": plain_decisions,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_simulated_review(
    *,
    decision_requests_path: str | Path,
    evidence_path: str | Path,
    gold_path: str | Path,
    evaluator_policy_path: str | Path,
    audit_path: str | Path,
    committee: SimulatedReviewCommittee | None = None,
) -> list[dict[str, Any]]:
    """Run the complete file-based benchmark simulation and retain its audit."""
    requests_payload = load_json(decision_requests_path)
    evidence_payload = load_json(evidence_path)
    requests = (
        requests_payload.get("decision_requests", [])
        if isinstance(requests_payload, Mapping)
        else requests_payload
    )
    evidence = (
        evidence_payload.get("evidence", evidence_payload.get("sources", []))
        if isinstance(evidence_payload, Mapping)
        else evidence_payload
    )
    if not isinstance(requests, list) or not isinstance(evidence, list):
        raise ValueError("Decision requests and evidence JSON must contain arrays")
    decisions = review_pending_requests(
        requests,
        evidence=evidence,
        gold=load_json(gold_path),
        evaluator_policy=load_json(evaluator_policy_path),
        committee=committee,
    )
    write_audit_json(audit_path, decisions)
    return decisions
