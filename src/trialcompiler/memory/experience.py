"""Human-governed experience compilation and reuse."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from trialcompiler.memory.semantic_store import (
    RetrievalHit,
    RetrievalQuery,
    SemanticElement,
    SemanticElementStore,
    stable_id,
)
from trialcompiler.models import DecisionCapsule, QualityDecision, ReviewStatus


class ExperienceRepository:
    """Store and retrieve decision capsules without treating drafts as policy."""

    NAMESPACE = "approved_experience"

    def __init__(self, store: SemanticElementStore) -> None:
        self.store = store

    def add_candidate(self, capsule: DecisionCapsule) -> str:
        if capsule.status is ReviewStatus.APPROVED and not capsule.approved_by:
            raise ValueError("approved capsules require approved_by")
        element = self._to_element(capsule)
        self.store.upsert(element)
        return element.element_id

    def approve(self, capsule: DecisionCapsule, reviewer: str) -> str:
        capsule.status = ReviewStatus.APPROVED
        capsule.approved_by = reviewer
        return self.add_candidate(capsule)

    def recall(
        self,
        query_text: str,
        *,
        document_type: str,
        section_type: str,
        jurisdiction: str,
        therapeutic_area: str,
        top_k: int = 4,
    ) -> list[RetrievalHit]:
        return self.store.retrieve(
            RetrievalQuery(
                text=query_text,
                namespace=self.NAMESPACE,
                element_types=["decision_capsule"],
                document_type=document_type,
                section_type=section_type,
                jurisdiction=jurisdiction,
                therapeutic_area=therapeutic_area,
                approval_statuses=[ReviewStatus.APPROVED.value],
                top_k=top_k,
            )
        )

    @staticmethod
    def compile_action_cards(hits: list[RetrievalHit]) -> list[dict[str, Any]]:
        """Expose only the minimum actionable capsule fields to downstream agents."""
        cards: list[dict[str, Any]] = []
        for hit in hits:
            value = hit.element.value
            cards.append(
                {
                    "capsule_id": value["capsule_id"],
                    "trigger": value["trigger"],
                    "conditions": value["conditions"],
                    "recommendation": value["recommendation"],
                    "rationale": value["rationale"],
                    "evidence_source_ids": value["evidence_source_ids"],
                    "retrieval_score": round(hit.fine_score, 4),
                }
            )
        return cards

    @staticmethod
    def candidate_from_review(
        *,
        project_id: str,
        finding_type: str,
        quality: QualityDecision,
        recommendation: str,
        evidence_source_ids: list[str],
        conditions: dict[str, Any],
    ) -> DecisionCapsule:
        """Create a draft only; a qualified human must approve it separately."""
        return DecisionCapsule(
            capsule_id=stable_id(project_id, finding_type, recommendation),
            title=f"Candidate response to {finding_type}",
            trigger=finding_type,
            conditions=conditions,
            recommendation=recommendation,
            rationale=(
                "Derived from a completed review cycle with quality score "
                f"{quality.score:.2f}. It is not reusable until human approval."
            ),
            evidence_source_ids=evidence_source_ids,
            status=ReviewStatus.DRAFT,
        )

    @staticmethod
    def _to_element(capsule: DecisionCapsule) -> SemanticElement:
        conditions = capsule.conditions
        semantic_key = " ".join(
            part
            for part in (
                capsule.trigger,
                capsule.title,
                str(conditions.get("section_type", "")),
                str(conditions.get("document_type", "")),
                capsule.recommendation,
            )
            if part
        )
        return SemanticElement(
            element_id=capsule.capsule_id,
            namespace=ExperienceRepository.NAMESPACE,
            semantic_key=semantic_key,
            value=asdict(capsule),
            element_type="decision_capsule",
            document_type=str(conditions.get("document_type", "any")),
            section_type=str(conditions.get("section_type", "any")),
            jurisdiction=str(conditions.get("jurisdiction", "any")),
            therapeutic_area=str(conditions.get("therapeutic_area", "any")),
            authority=capsule.authority,
            approval_status=capsule.status.value,
            valid_until=capsule.valid_until,
            source_ids=list(capsule.evidence_source_ids),
            tags=[capsule.trigger, capsule.title],
            staticity=7.0 if capsule.valid_until else 5.0,
            fetch_cost=0.2,
            latency_ms=120.0,
        )
