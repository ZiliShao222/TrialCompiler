from trialcompiler.evidence import select_workflow_evidence, workflow_evidence_digest


def item(**overrides) -> dict:
    payload = {
        "status": "completed",
        "model": "frozen-test-reviewer",
        "result": {"semantic_findings": [], "review_questions": [], "limitations": []},
    }
    result = {
        "evidence_id": "E1",
        "source_id": "S1",
        "project_id": "P1",
        "document_id": "D1",
        "observation_type": "semantic_review",
        "payload": payload,
        "payload_digest": workflow_evidence_digest(payload),
        "status": "approved_for_research",
    }
    result.update(overrides)
    return result


def test_provider_selects_only_scope_matched_digest_verified_observation():
    selected, rejected = select_workflow_evidence(
        [item()], project_id="P1", document_id="D1", consumed_ids=set()
    )
    assert selected is not None
    assert selected.evidence_id == "E1"
    assert rejected == []


def test_provider_rejects_tampering_and_scope_mismatch():
    selected, rejected = select_workflow_evidence(
        [item(payload_digest="sha256:tampered", project_id="OTHER")],
        project_id="P1",
        document_id="D1",
        consumed_ids=set(),
    )
    assert selected is None
    assert rejected[0]["failures"] == [
        "evidence_project_scope_mismatch",
        "evidence_digest_mismatch",
    ]


def test_consumed_observation_is_not_reused():
    selected, rejected = select_workflow_evidence(
        [item()], project_id="P1", document_id="D1", consumed_ids={"E1"}
    )
    assert selected is None
    assert rejected == []
