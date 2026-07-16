"""Small, explicit clinical document graph used by the MVP review workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from trialcompiler.models import (
    DocumentSection,
    FactRecord,
    RepairProposal,
    ReviewFinding,
    ReviewStatus,
    Severity,
    TrialDocument,
)

WEEK_PATTERN = re.compile(r"\b(?:week|wk)\s*(\d{1,3})\b", re.IGNORECASE)


@dataclass(slots=True)
class ClinicalDocumentGraph:
    document: TrialDocument
    facts_by_id: dict[str, FactRecord] = field(init=False)
    sections_by_id: dict[str, DocumentSection] = field(init=False)
    fact_to_sections: dict[str, set[str]] = field(init=False)

    def __post_init__(self) -> None:
        self.facts_by_id = {fact.fact_id: fact for fact in self.document.facts}
        self.sections_by_id = {
            section.section_id: section for section in self.document.sections
        }
        self.fact_to_sections = {fact_id: set() for fact_id in self.facts_by_id}
        for section in self.document.sections:
            for fact_id in section.fact_refs:
                self.fact_to_sections.setdefault(fact_id, set()).add(section.section_id)

    def validate_references(self) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        known_sources = {source.source_id for source in self.document.sources}
        for section in self.document.sections:
            for fact_id in section.fact_refs:
                if fact_id not in self.facts_by_id:
                    findings.append(
                        ReviewFinding(
                            finding_id=f"missing-fact-{section.section_id}-{fact_id}",
                            finding_type="missing_fact_reference",
                            severity=Severity.HIGH,
                            section_ids=[section.section_id],
                            message=f"Section references unknown canonical fact {fact_id}.",
                            canonical_fact_id=fact_id,
                        )
                    )
            for source_id in section.source_ids:
                if source_id not in known_sources:
                    findings.append(
                        ReviewFinding(
                            finding_id=f"missing-source-{section.section_id}-{source_id}",
                            finding_type="missing_evidence_reference",
                            severity=Severity.HIGH,
                            section_ids=[section.section_id],
                            message=f"Section references unknown evidence source {source_id}.",
                        )
                    )
        return findings

    def find_week_inconsistencies(self) -> list[ReviewFinding]:
        """Detect contradictions against approved canonical study-week facts."""
        findings: list[ReviewFinding] = []
        for fact in self.document.facts:
            if fact.status is not ReviewStatus.APPROVED:
                continue
            if not isinstance(fact.value, int) or "week" not in fact.name.lower():
                continue
            for section_id in sorted(self.fact_to_sections.get(fact.fact_id, set())):
                section = self.sections_by_id[section_id]
                observed = [int(value) for value in WEEK_PATTERN.findall(section.text)]
                if observed and fact.value not in observed:
                    findings.append(
                        ReviewFinding(
                            finding_id=f"week-conflict-{fact.fact_id}-{section_id}",
                            finding_type="canonical_fact_conflict",
                            severity=Severity.HIGH,
                            section_ids=[section_id],
                            message=(
                                f"{section.title} states week(s) {observed}, while approved "
                                f"fact {fact.fact_id} requires Week {fact.value}."
                            ),
                            canonical_fact_id=fact.fact_id,
                            evidence_source_ids=list(fact.source_ids),
                        )
                    )
        return findings

    def review(self) -> list[ReviewFinding]:
        return self.validate_references() + self.find_week_inconsistencies()

    def impact_set(self, fact_id: str) -> list[str]:
        """Return every section explicitly dependent on a canonical fact."""
        return sorted(self.fact_to_sections.get(fact_id, set()))

    def propose_repairs(self, findings: list[ReviewFinding]) -> list[RepairProposal]:
        proposals: list[RepairProposal] = []
        for finding in findings:
            if finding.finding_type != "canonical_fact_conflict":
                continue
            if not finding.canonical_fact_id:
                continue
            fact = self.facts_by_id[finding.canonical_fact_id]
            for section_id in finding.section_ids:
                section = self.sections_by_id[section_id]
                proposed = WEEK_PATTERN.sub(f"Week {fact.value}", section.text)
                proposals.append(
                    RepairProposal(
                        proposal_id=f"repair-{finding.finding_id}",
                        finding_id=finding.finding_id,
                        section_id=section_id,
                        original_text=section.text,
                        proposed_text=proposed,
                        rationale=(
                            f"Align {section.title} to approved canonical fact "
                            f"{fact.fact_id}; final wording requires qualified review."
                        ),
                        fact_ids=[fact.fact_id],
                        evidence_source_ids=list(fact.source_ids),
                    )
                )
        return proposals
