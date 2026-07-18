import json

import pytest

from trialcompiler.reviewers import (
    ReviewerRole,
    SimulatedReviewCommittee,
    SimulatedReviewer,
    review_pending_requests,
    run_simulated_review,
    write_audit_json,
)

REQUEST = {
    "request_id": "C002-T001",
    "finding_ids": ["finding-identifier"],
    "section_ids": ["PROT-COVER", "REG-ID"],
    "question": "Is the identifier conflict supported?",
    "reason": "Two source documents disagree.",
    "evidence_source_ids": ["SRC-PROT", "SRC-REG"],
    "status": "pending_qualified_human_decision",
}
GOLD = {
    "tests": [
        {
            "test_id": "C002-T001",
            "expected_action": "do_not_report_as_conflict",
            "expected_section_ids": ["PROT-COVER", "REG-ID"],
            "evidence": [
                {"source_id": "SRC-PROT", "locator": "page 1"},
                {"source_id": "SRC-REG", "locator": "nctId"},
            ],
        }
    ]
}
EVIDENCE = [
    {"source_id": "SRC-PROT", "locator": "page 1", "excerpt": "NCT03233983"},
    {"source_id": "SRC-REG", "locator": "nctId", "excerpt": "NCT03232983"},
]
POLICY = {
    "simulation_only": True,
    "minimum_evidence_count": 2,
    "action_mapping": {"do_not_report_as_conflict": "accept"},
}


def test_all_roles_emit_required_simulation_fields() -> None:
    for role in ReviewerRole:
        result = SimulatedReviewer(role).review(
            REQUEST, evidence=EVIDENCE, gold=GOLD, evaluator_policy=POLICY
        )
        assert result.decision == "accept"
        assert result.rationale
        assert len(result.cited_evidence) == 2
        assert 0 <= result.confidence <= 1
        assert result.role == role.value
        assert result.simulation_only is True
        assert result.real_approval is False
        assert result.authority == "benchmark_simulation"


def test_insufficient_evidence_can_never_accept() -> None:
    result = SimulatedReviewer("medical").review(
        REQUEST, evidence=EVIDENCE[:1], gold=GOLD, evaluator_policy=POLICY
    )
    assert result.decision == "request_evidence"
    assert result.missing_evidence_source_ids == ["SRC-REG"]


def test_accept_requires_explicit_policy_mapping() -> None:
    result = SimulatedReviewer("medical").review(
        REQUEST,
        evidence=EVIDENCE,
        gold=GOLD,
        evaluator_policy={"simulation_only": True, "minimum_evidence_count": 2},
    )
    assert result.decision == "request_evidence"


def test_policy_must_explicitly_mark_simulation_only() -> None:
    with pytest.raises(ValueError, match="simulation_only=true"):
        SimulatedReviewer("quality").review(
            REQUEST, evidence=EVIDENCE, gold=GOLD, evaluator_policy={}
        )


def test_committee_is_conservative_and_preserves_role_votes() -> None:
    policy = {
        **POLICY,
        "roles": {"statistical": {"allowed_decisions": ["request_evidence"]}},
    }
    result = SimulatedReviewCommittee().review(
        REQUEST, evidence=EVIDENCE, gold=GOLD, evaluator_policy=policy
    )
    assert result["decision"] == "request_evidence"
    assert result["simulation_only"] is True
    assert {vote["role"] for vote in result["votes"]} == set(ReviewerRole)


def test_pending_filter_and_audit_never_touch_real_approvals(tmp_path) -> None:
    resolved = {**REQUEST, "request_id": "old", "status": "resolved_accepted"}
    decisions = review_pending_requests(
        [resolved, REQUEST], evidence=EVIDENCE, gold=GOLD, evaluator_policy=POLICY
    )
    assert [item["request_id"] for item in decisions] == ["C002-T001"]

    audit_path = write_audit_json(tmp_path / "simulated_audit.json", decisions)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["audit_type"] == "benchmark_simulated_reviewer"
    assert audit["simulation_only"] is True
    assert audit["decisions"][0]["real_approval"] is False
    with pytest.raises(ValueError, match="approvals"):
        write_audit_json(tmp_path / "approvals" / "fake.json", decisions)


def test_file_runner_reads_inputs_and_retains_committee_audit(tmp_path) -> None:
    inputs = {
        "requests.json": [REQUEST],
        "evidence.json": {"evidence": EVIDENCE},
        "gold.json": GOLD,
        "policy.json": POLICY,
    }
    for name, payload in inputs.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    decisions = run_simulated_review(
        decision_requests_path=tmp_path / "requests.json",
        evidence_path=tmp_path / "evidence.json",
        gold_path=tmp_path / "gold.json",
        evaluator_policy_path=tmp_path / "policy.json",
        audit_path=tmp_path / "simulation-audit.json",
    )
    assert decisions[0]["decision"] == "accept"
    assert (tmp_path / "simulation-audit.json").is_file()
