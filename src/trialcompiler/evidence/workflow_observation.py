"""Allow-listed workflow observations for bounded review acquisition loops."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def workflow_evidence_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkflowEvidenceObservation:
    evidence_id: str
    source_id: str
    project_id: str
    document_id: str
    observation_type: str
    payload: dict[str, Any]
    payload_digest: str
    status: str = "approved_for_research"

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> WorkflowEvidenceObservation:
        return cls(
            evidence_id=str(item["evidence_id"]),
            source_id=str(item["source_id"]),
            project_id=str(item["project_id"]),
            document_id=str(item["document_id"]),
            observation_type=str(item["observation_type"]),
            payload=dict(item["payload"]),
            payload_digest=str(item["payload_digest"]),
            status=str(item.get("status", "approved_for_research")),
        )

    def validate_for(self, *, project_id: str, document_id: str) -> list[str]:
        failures: list[str] = []
        if self.status != "approved_for_research":
            failures.append("evidence_not_approved")
        if self.project_id != project_id:
            failures.append("evidence_project_scope_mismatch")
        if self.document_id != document_id:
            failures.append("evidence_document_scope_mismatch")
        if self.observation_type != "semantic_review":
            failures.append("unsupported_observation_type")
        if workflow_evidence_digest(self.payload) != self.payload_digest:
            failures.append("evidence_digest_mismatch")
        if self.payload.get("status") != "completed":
            failures.append("semantic_review_not_completed")
        return failures


def select_workflow_evidence(
    catalog: list[dict[str, Any]],
    *,
    project_id: str,
    document_id: str,
    consumed_ids: set[str],
) -> tuple[WorkflowEvidenceObservation | None, list[dict[str, Any]]]:
    """Select the first stable eligible item and retain rejection diagnostics."""
    rejected: list[dict[str, Any]] = []
    parsed = sorted(
        (WorkflowEvidenceObservation.from_dict(item) for item in catalog),
        key=lambda item: item.evidence_id,
    )
    for item in parsed:
        if item.evidence_id in consumed_ids:
            continue
        failures = item.validate_for(project_id=project_id, document_id=document_id)
        if failures:
            rejected.append({"evidence_id": item.evidence_id, "failures": failures})
            continue
        return item, rejected
    return None, rejected
