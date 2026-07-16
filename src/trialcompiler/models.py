"""Core data contracts shared by the workflow, memory layer, and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class SourceRef:
    source_id: str
    title: str
    locator: str
    authority: str = "project"
    version: str = "unknown"
    effective_date: str | None = None
    access_scope: str = "project"


@dataclass(slots=True)
class FactRecord:
    fact_id: str
    name: str
    value: Any
    unit: str | None = None
    status: ReviewStatus = ReviewStatus.DRAFT
    source_ids: list[str] = field(default_factory=list)
    owner_role: str = "unassigned"
    version: int = 1
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class DocumentSection:
    section_id: str
    title: str
    text: str
    document_type: str = "protocol"
    fact_refs: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TrialDocument:
    project_id: str
    document_id: str
    title: str
    document_type: str
    jurisdiction: str
    therapeutic_area: str
    facts: list[FactRecord]
    sections: list[DocumentSection]
    sources: list[SourceRef] = field(default_factory=list)
    version: str = "0.1"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TrialDocument:
        return cls(
            project_id=str(payload["project_id"]),
            document_id=str(payload["document_id"]),
            title=str(payload["title"]),
            document_type=str(payload.get("document_type", "protocol")),
            jurisdiction=str(payload.get("jurisdiction", "unspecified")),
            therapeutic_area=str(payload.get("therapeutic_area", "unspecified")),
            facts=[
                FactRecord(
                    **{
                        **item,
                        "status": ReviewStatus(item.get("status", "draft")),
                    }
                )
                for item in payload.get("facts", [])
            ],
            sections=[DocumentSection(**item) for item in payload.get("sections", [])],
            sources=[SourceRef(**item) for item in payload.get("sources", [])],
            version=str(payload.get("version", "0.1")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewFinding:
    finding_id: str
    finding_type: str
    severity: Severity
    section_ids: list[str]
    message: str
    canonical_fact_id: str | None = None
    evidence_source_ids: list[str] = field(default_factory=list)
    requires_human_review: bool = True


@dataclass(slots=True)
class RepairProposal:
    proposal_id: str
    finding_id: str
    section_id: str
    original_text: str
    proposed_text: str
    rationale: str
    fact_ids: list[str] = field(default_factory=list)
    evidence_source_ids: list[str] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.REQUIRES_HUMAN_REVIEW


@dataclass(slots=True)
class QualityDecision:
    accepted: bool
    score: float
    reasons: list[str]
    unresolved_finding_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DecisionCapsule:
    capsule_id: str
    title: str
    trigger: str
    conditions: dict[str, Any]
    recommendation: str
    rationale: str
    evidence_source_ids: list[str]
    status: ReviewStatus = ReviewStatus.DRAFT
    authority: str = "human_review"
    approved_by: str | None = None
    valid_until: str | None = None
    supersedes: str | None = None
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DecisionCapsule:
        return cls(
            **{
                **payload,
                "status": ReviewStatus(payload.get("status", "draft")),
            }
        )


@dataclass(slots=True)
class AgentTraceEvent:
    agent: str
    action: str
    summary: str
    timestamp: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeishuIntakeEnvelope:
    request_id: str
    project_id: str
    actor_id: str
    user_request: str
    task_intent: str
    document_type: str
    locale: str = "zh-CN"
    file_refs: list[str] = field(default_factory=list)
    structured_fields: dict[str, Any] = field(default_factory=dict)
    source: str = "feishu_aily"
    received_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FeishuIntakeEnvelope:
        return cls(**payload)


def to_plain(value: Any) -> Any:
    """Convert dataclasses and enums into JSON-serializable Python values."""
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value
