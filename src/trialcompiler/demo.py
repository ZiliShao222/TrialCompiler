"""Reproducible demo setup for the public, synthetic MVP fixture."""

from __future__ import annotations

import json
from pathlib import Path

from trialcompiler.memory.experience import ExperienceRepository
from trialcompiler.models import DecisionCapsule, ReviewStatus, TrialDocument


def load_document(path: str | Path) -> TrialDocument:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TrialDocument.from_dict(payload)


def seed_demo_experience(repository: ExperienceRepository) -> str:
    capsule = DecisionCapsule(
        capsule_id="exp-canonical-fact-propagation-v1",
        title="Propagate approved canonical facts across dependent sections",
        trigger="canonical_fact_conflict",
        conditions={
            "document_type": "protocol",
            "section_type": "any",
            "jurisdiction": "any",
            "therapeutic_area": "any",
        },
        recommendation=(
            "Use the approved fact value to prepare a redline for every dependent section; "
            "preserve the source identifier and require qualified human approval."
        ),
        rationale=(
            "A prior synthetic review showed that changing only one occurrence left the synopsis "
            "and schedule inconsistent."
        ),
        evidence_source_ids=["SRC-DEMO-SOP"],
        status=ReviewStatus.APPROVED,
        authority="human_review",
        approved_by="demo-qualified-reviewer",
    )
    return repository.add_candidate(capsule)
