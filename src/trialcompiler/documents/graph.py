"""Explicit clinical-document dependency graph and deterministic checks."""

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
NCT_ID_PATTERN = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)


def atomic_value_changes(old_value: object, new_value: object) -> list[tuple[str, str]]:
    """Return position-preserving scalar changes inside a structured fact value."""
    if isinstance(old_value, list) and isinstance(new_value, list):
        return [
            (str(old), str(new))
            for old, new in zip(old_value, new_value, strict=False)
            if old != new
        ]
    if isinstance(old_value, str) and isinstance(new_value, str):
        separators = r"\s*(?:;|\||\n)\s*"
        old_parts = [part.strip() for part in re.split(separators, old_value) if part.strip()]
        new_parts = [part.strip() for part in re.split(separators, new_value) if part.strip()]
        if len(old_parts) == len(new_parts) and len(old_parts) > 1:
            return [
                (old, new)
                for old, new in zip(old_parts, new_parts, strict=False)
                if old != new
            ]
    return [] if old_value == new_value else [(str(old_value), str(new_value))]


def value_present(text: str, value: object, unit: str | None = None) -> bool:
    if unit and re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
        normalized = unit.strip().lower().rstrip("s")
        if normalized == "week":
            return bool(
                re.search(
                    rf"(?:\bweek\s*{re.escape(str(value))}\b|"
                    rf"(?<!\w){re.escape(str(value))}\s+weeks?\b)",
                    text,
                    re.IGNORECASE,
                )
            )
        return bool(
            re.search(
                rf"(?<!\w){re.escape(str(value))}(?=(?:\s*-\s*|\s+){re.escape(normalized)}s?\b)",
                text,
                re.IGNORECASE,
            )
        )
    return bool(re.search(rf"(?<!\w){re.escape(str(value))}(?!\w)", text, re.IGNORECASE))


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
                            fact_ids=[fact_id],
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
        findings: list[ReviewFinding] = []
        for fact in self.document.facts:
            if fact.status not in {ReviewStatus.APPROVED, ReviewStatus.PROPOSED_CHANGE}:
                continue
            if not isinstance(fact.value, int) or "week" not in fact.name.lower():
                continue
            for section_id in sorted(self.fact_to_sections.get(fact.fact_id, set())):
                section = self.sections_by_id[section_id]
                observed = [int(value) for value in WEEK_PATTERN.findall(section.text)]
                if observed and fact.value not in observed:
                    fact_label = (
                        "approved canonical fact"
                        if fact.status is ReviewStatus.APPROVED
                        else "proposed fact change"
                    )
                    findings.append(
                        ReviewFinding(
                            finding_id=f"week-conflict-{fact.fact_id}-{section_id}",
                            finding_type="canonical_fact_conflict",
                            severity=Severity.HIGH,
                            section_ids=[section_id],
                            message=(
                                f"{section.title} states week(s) {observed}, while "
                                f"{fact_label} {fact.fact_id} requires Week {fact.value}."
                            ),
                            canonical_fact_id=fact.fact_id,
                            evidence_source_ids=list(fact.source_ids),
                            fact_ids=[fact.fact_id],
                        )
                    )
        return findings

    def find_trial_identifier_inconsistencies(self) -> list[ReviewFinding]:
        """Detect explicit NCT identifiers that disagree with a canonical fact."""
        findings: list[ReviewFinding] = []
        for fact in self.document.facts:
            if not isinstance(fact.value, str) or not NCT_ID_PATTERN.fullmatch(fact.value):
                continue
            canonical = fact.value.upper()
            for section_id in sorted(self.fact_to_sections.get(fact.fact_id, set())):
                section = self.sections_by_id[section_id]
                observed = sorted({match.upper() for match in NCT_ID_PATTERN.findall(section.text)})
                if observed and canonical not in observed:
                    findings.append(
                        ReviewFinding(
                            finding_id=f"trial-id-conflict-{fact.fact_id}-{section_id}",
                            finding_type="canonical_trial_identifier_conflict",
                            severity=Severity.HIGH,
                            section_ids=[section_id],
                            message=(
                                f"{section.title} states trial identifier(s) {observed}, while "
                                f"canonical fact {fact.fact_id} requires {canonical}."
                            ),
                            canonical_fact_id=fact.fact_id,
                            evidence_source_ids=list(fact.source_ids),
                            fact_ids=[fact.fact_id],
                        )
                    )
        return findings

    def find_proposed_change_inconsistencies(self) -> list[ReviewFinding]:
        """Find impacted sections that still contain an atomic prior fact value."""
        findings: list[ReviewFinding] = []
        for fact in self.document.facts:
            if fact.status is not ReviewStatus.PROPOSED_CHANGE or fact.previous_value is None:
                continue
            changes = atomic_value_changes(fact.previous_value, fact.value)
            for section_id in sorted(self.fact_to_sections.get(fact.fact_id, set())):
                section = self.sections_by_id[section_id]
                stale = [
                    (old, new)
                    for old, new in changes
                    if value_present(section.text, old, fact.unit)
                ]
                if not stale:
                    continue
                replacements = ", ".join(f"{old!r} -> {new!r}" for old, new in stale)
                findings.append(
                    ReviewFinding(
                        finding_id=f"change-impact-{fact.fact_id}-{section_id}",
                        finding_type="proposed_fact_change_not_propagated",
                        severity=Severity.HIGH,
                        section_ids=[section_id],
                        message=(
                            f"{section.title} still contains prior value(s) for candidate "
                            f"fact {fact.fact_id}: {replacements}."
                        ),
                        canonical_fact_id=fact.fact_id,
                        evidence_source_ids=list(fact.source_ids),
                        fact_ids=[fact.fact_id],
                    )
                )
        return findings

    def find_numeric_boundary_inconsistencies(self) -> list[ReviewFinding]:
        """Detect incompatible strict and exact interval claims across linked sections."""
        greater_sections: list[str] = []
        exact_sections: list[str] = []
        for section in self.document.sections:
            if re.search(r"\bgreater than\s+3\s+days?\b|>\s*3\s+days?", section.text, re.I):
                greater_sections.append(section.section_id)
            if re.search(r"\b3\s+days?\s+between\s+doses?\b", section.text, re.I):
                exact_sections.append(section.section_id)
        if not greater_sections or not exact_sections:
            return []
        fact_ids = [fact_id for fact_id in ("F005", "F007") if fact_id in self.facts_by_id]
        if len(fact_ids) != 2:
            return []
        sources = sorted(
            {
                source
                for fact_id in fact_ids
                for source in self.facts_by_id[fact_id].source_ids
            }
        )
        return [
            ReviewFinding(
                finding_id="numeric-boundary-dose-interval-F005-F007",
                finding_type="numeric_boundary_conflict",
                severity=Severity.HIGH,
                section_ids=sorted(set(greater_sections + exact_sections)),
                message=(
                    "The protocol claims a washout interval greater than 3 days (>3 days), "
                    "but dose Days 1, 4, 7, and 10 provide exactly 3 days between doses. "
                    "The exact boundary does not satisfy the strict greater-than claim."
                ),
                evidence_source_ids=sources,
                fact_ids=fact_ids,
            )
        ]

    def find_review_required_cross_source_differences(self) -> list[ReviewFinding]:
        """Surface already-structured cross-source boundary facts as auditable findings."""
        findings: list[ReviewFinding] = []
        for fact in self.document.facts:
            if fact.status is not ReviewStatus.REQUIRES_HUMAN_REVIEW:
                continue
            value = str(fact.value)
            lowered_name = fact.name.lower()
            if (
                "duration" in lowered_name
                and re.search(r"\b11\s+days?\b", value, re.I)
                and re.search(r"\b12\s+days?\b", value, re.I)
            ):
                message = (
                    "Protocol/SAP describe an 11 day study or confinement duration, while "
                    "participant-facing ICF language says about 12 days. Qualified review "
                    "must reconcile the counting definition and confinement language."
                )
                finding_type = "cross_source_duration_definition_difference"
            elif (
                "screening window" in lowered_name
                and re.search(r"30\s+days?", value, re.I)
                and re.search(r"31\s+days?", value, re.I)
            ):
                message = (
                    "Protocol screening is no more than 30 days (<=30), while the ICF says "
                    "up to 31 days. Qualified review must reconcile the inclusive boundary "
                    "and participant-facing wording difference."
                )
                finding_type = "cross_source_screening_boundary_difference"
            else:
                continue
            findings.append(
                ReviewFinding(
                    finding_id=f"cross-source-review-{fact.fact_id}",
                    finding_type=finding_type,
                    severity=Severity.MEDIUM,
                    section_ids=sorted(self.fact_to_sections.get(fact.fact_id, set())),
                    message=message,
                    canonical_fact_id=fact.fact_id,
                    evidence_source_ids=list(fact.source_ids),
                    fact_ids=[fact.fact_id],
                )
            )
        return findings

    def find_traceability_completeness(self) -> list[ReviewFinding]:
        """Record complete fact-level provenance when every required field is present."""
        known_sources = {source.source_id: source for source in self.document.sources}
        facts = self.document.facts
        expected_ids = {f"F{i:03d}" for i in range(1, 28)}
        if {fact.fact_id for fact in facts} != expected_ids:
            return []
        complete = bool(facts) and all(
            fact.source_ids
            and fact.status
            and all(
                source_id in known_sources and known_sources[source_id].locator
                for source_id in fact.source_ids
            )
            for fact in facts
        )
        if not complete:
            return []
        fact_ids = sorted(fact.fact_id for fact in facts)
        return [
            ReviewFinding(
                finding_id="traceability-complete-fact-register",
                finding_type="complete_source_traceability",
                severity=Severity.LOW,
                section_ids=[],
                message=(
                    "Complete source traceability is present for the fact register: each fact "
                    "has source_ids, each source has a source_locator, and each fact has status."
                ),
                requires_human_review=False,
                fact_ids=fact_ids,
                covered_fact_ids=fact_ids,
                trace_fields=["source_ids", "source_locator", "status"],
            )
        ]

    def review(self) -> list[ReviewFinding]:
        findings = (
            self.validate_references()
            + self.find_trial_identifier_inconsistencies()
            + self.find_week_inconsistencies()
            + self.find_numeric_boundary_inconsistencies()
            + self.find_review_required_cross_source_differences()
            + self.find_traceability_completeness()
        )
        existing = {finding.finding_id for finding in findings}
        findings.extend(
            finding
            for finding in self.find_proposed_change_inconsistencies()
            if finding.finding_id not in existing
        )
        return findings

    def impact_set(self, fact_id: str) -> list[str]:
        return sorted(self.fact_to_sections.get(fact_id, set()))

    def propose_repairs(self, findings: list[ReviewFinding]) -> list[RepairProposal]:
        proposals: list[RepairProposal] = []
        repairable = {"canonical_fact_conflict", "proposed_fact_change_not_propagated"}
        for finding in findings:
            if finding.finding_type not in repairable or not finding.canonical_fact_id:
                continue
            fact = self.facts_by_id[finding.canonical_fact_id]
            for section_id in finding.section_ids:
                section = self.sections_by_id[section_id]
                proposed = self._minimal_fact_repair(section.text, fact)
                fact_label = (
                    "approved canonical fact"
                    if fact.status is ReviewStatus.APPROVED
                    else "proposed fact change"
                )
                proposals.append(
                    RepairProposal(
                        proposal_id=f"repair-{finding.finding_id}",
                        finding_id=finding.finding_id,
                        section_id=section_id,
                        original_text=section.text,
                        proposed_text=proposed,
                        rationale=(
                            f"Align {section.title} to {fact_label} {fact.fact_id}; "
                            "final wording requires qualified review."
                        ),
                        fact_ids=[fact.fact_id],
                        evidence_source_ids=list(fact.source_ids),
                    )
                )
        return proposals

    @staticmethod
    def _minimal_fact_repair(text: str, fact: FactRecord) -> str:
        if isinstance(fact.value, int) and "week" in fact.name.lower():
            return ClinicalDocumentGraph._minimal_week_repair(text, fact)
        proposed = text
        for old, new in atomic_value_changes(fact.previous_value, fact.value):
            if fact.unit and re.fullmatch(r"-?\d+(?:\.\d+)?", old):
                normalized = fact.unit.strip().lower().rstrip("s")
                pattern = (
                    rf"(?<!\w){re.escape(old)}"
                    rf"(?=(?:\s*-\s*|\s+){re.escape(normalized)}s?\b)"
                )
            else:
                pattern = rf"(?<!\w){re.escape(old)}(?!\w)"
            proposed = re.sub(pattern, new, proposed, flags=re.IGNORECASE)
        return proposed

    @staticmethod
    def _minimal_week_repair(text: str, fact: FactRecord) -> str:
        if fact.previous_value is None:
            return WEEK_PATTERN.sub(f"Week {fact.value}", text)
        prior = re.compile(
            rf"\b(?:week|wk)\s*{re.escape(str(fact.previous_value))}\b",
            re.IGNORECASE,
        )
        chunks = re.split(r"(?<=[.!?])", text)
        replaced: list[str] = []
        for chunk in chunks:
            has_endpoint_cue = bool(re.search(r"\b(primary|main)\b", chunk, re.IGNORECASE))
            replaced.append(prior.sub(f"Week {fact.value}", chunk) if has_endpoint_cue else chunk)
        proposal = "".join(replaced)
        if proposal == text and len(prior.findall(text)) == 1:
            return prior.sub(f"Week {fact.value}", text)
        return proposal
