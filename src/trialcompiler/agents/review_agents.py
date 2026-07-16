"""Role-separated nodes for the review-only TrialCompiler MVP."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from trialcompiler.documents import ClinicalDocumentGraph
from trialcompiler.memory.experience import ExperienceRepository
from trialcompiler.models import (
    AgentTraceEvent,
    QualityDecision,
    ReviewStatus,
    TrialDocument,
)


def trace(agent: str, action: str, summary: str, **metadata: Any) -> AgentTraceEvent:
    return AgentTraceEvent(agent=agent, action=action, summary=summary, metadata=metadata)


class ReviewAgents:
    """Agent roles share typed state, never hidden conversational context."""

    def __init__(self, experience_repository: ExperienceRepository) -> None:
        self.experience_repository = experience_repository

    def context_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        document = TrialDocument.from_dict(state["document"])
        unresolved = [
            fact.fact_id for fact in document.facts if fact.status is not ReviewStatus.APPROVED
        ]
        context_lock = {
            "project_id": document.project_id,
            "document_id": document.document_id,
            "document_type": document.document_type,
            "jurisdiction": document.jurisdiction,
            "therapeutic_area": document.therapeutic_area,
            "approved_fact_ids": [
                fact.fact_id for fact in document.facts if fact.status is ReviewStatus.APPROVED
            ],
            "unapproved_fact_ids": unresolved,
            "release_blocked": True,
        }
        return {
            "context_lock": context_lock,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "A",
                        "context_lock",
                        "Canonical context locked.",
                        unresolved=unresolved,
                    )
                )
            ],
        }

    def evidence_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        document = TrialDocument.from_dict(state["document"])
        graph = ClinicalDocumentGraph(document)
        findings = graph.review()
        query_text = " ".join(sorted({finding.finding_type for finding in findings})) or (
            f"review {document.document_type} consistency"
        )
        hits = self.experience_repository.recall(
            query_text,
            document_type=document.document_type,
            section_type="any",
            jurisdiction=document.jurisdiction,
            therapeutic_area=document.therapeutic_area,
        )
        cards = self.experience_repository.compile_action_cards(hits)
        return {
            "findings": [asdict(item) for item in findings],
            "experience_cards": cards,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "B",
                        "evidence_and_experience",
                        f"Detected {len(findings)} finding(s) and admitted "
                        f"{len(cards)} experience card(s).",
                    )
                )
            ],
        }

    def repair_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        from trialcompiler.models import ReviewFinding, Severity

        document = TrialDocument.from_dict(state["document"])
        graph = ClinicalDocumentGraph(document)
        findings = [
            ReviewFinding(
                **{
                    **item,
                    "severity": Severity(item["severity"]),
                }
            )
            for item in state.get("findings", [])
        ]
        proposals = graph.propose_repairs(findings)
        cards = state.get("experience_cards", [])
        card_ids = [card["capsule_id"] for card in cards]
        proposal_payloads = []
        for proposal in proposals:
            payload = asdict(proposal)
            payload["applied_experience_ids"] = card_ids
            payload["status"] = proposal.status.value
            proposal_payloads.append(payload)
        round_index = int(state.get("round_index", 0)) + 1
        return {
            "proposals": proposal_payloads,
            "round_index": round_index,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "C",
                        "repair_proposal",
                        f"Prepared {len(proposals)} traceable repair proposal(s), "
                        f"round {round_index}.",
                        experience_cards=card_ids,
                    )
                )
            ],
        }

    def quality_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        document = TrialDocument.from_dict(state["document"])
        graph = ClinicalDocumentGraph(document)
        proposals = state.get("proposals", [])
        reasons: list[str] = []
        unresolved: list[str] = []
        for finding in state.get("findings", []):
            matching = [p for p in proposals if p["finding_id"] == finding["finding_id"]]
            if not matching:
                unresolved.append(finding["finding_id"])
                reasons.append(f"No repair proposal for {finding['finding_id']}.")
                continue
            for proposal in matching:
                if not proposal.get("evidence_source_ids"):
                    unresolved.append(finding["finding_id"])
                    reasons.append(f"Repair {proposal['proposal_id']} lacks evidence provenance.")
                fact_id = finding.get("canonical_fact_id")
                if fact_id and fact_id in graph.facts_by_id:
                    expected = str(graph.facts_by_id[fact_id].value)
                    if expected not in proposal["proposed_text"]:
                        unresolved.append(finding["finding_id"])
                        reasons.append(
                            f"Repair {proposal['proposal_id']} does not contain "
                            f"canonical value {expected}."
                        )
        unresolved = sorted(set(unresolved))
        accepted = not unresolved
        score = max(0.0, 1.0 - len(unresolved) / max(1, len(state.get("findings", []))))
        decision = QualityDecision(
            accepted=accepted,
            score=score,
            reasons=reasons or ["All proposed changes preserve fact and evidence provenance."],
            unresolved_finding_ids=unresolved,
        )
        return {
            "quality": asdict(decision),
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "D",
                        "quality_gate",
                        f"Quality gate {'passed' if accepted else 'returned'} "
                        f"at score {score:.2f}.",
                    )
                )
            ],
        }

    def reporter_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        document = TrialDocument.from_dict(state["document"])
        lines = [
            f"# TrialCompiler review report: {document.title}",
            "",
            "> Status: requires qualified human review; "
            "no proposal has been applied automatically.",
            "",
            "## Context lock",
            "",
            f"- Project: `{document.project_id}`",
            f"- Document: `{document.document_id}` version `{document.version}`",
            f"- Jurisdiction: `{document.jurisdiction}`",
            f"- Therapeutic area: `{document.therapeutic_area}`",
            "",
            "## Findings",
            "",
        ]
        for finding in state.get("findings", []):
            lines.append(
                f"- **{finding['severity']} / {finding['finding_type']}**: {finding['message']}"
            )
        lines += ["", "## Proposed redlines", ""]
        for proposal in state.get("proposals", []):
            lines.extend(
                [
                    f"### {proposal['section_id']}",
                    "",
                    f"- Before: {proposal['original_text']}",
                    f"- Proposed: {proposal['proposed_text']}",
                    f"- Rationale: {proposal['rationale']}",
                    f"- Evidence: {', '.join(proposal['evidence_source_ids']) or 'MISSING'}",
                    "",
                ]
            )
        quality = state.get("quality", {})
        lines += [
            "## Independent quality gate",
            "",
            f"- Accepted for human review: `{quality.get('accepted', False)}`",
            f"- Score: `{quality.get('score', 0.0):.2f}`",
            "- This gate checks proposal integrity; it is not medical or regulatory approval.",
            "",
        ]
        report = "\n".join(lines)
        return {
            "report_markdown": report,
            "trace": state.get("trace", [])
            + [asdict(trace("E", "report", "Generated review packet and redline summary."))],
        }

    def experience_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        candidate = None
        findings = state.get("findings", [])
        proposals = state.get("proposals", [])
        quality_payload = state.get("quality", {})
        if findings and proposals and quality_payload.get("accepted"):
            quality = QualityDecision(**quality_payload)
            document = TrialDocument.from_dict(state["document"])
            candidate = self.experience_repository.candidate_from_review(
                project_id=document.project_id,
                finding_type=findings[0]["finding_type"],
                quality=quality,
                recommendation=proposals[0]["rationale"],
                evidence_source_ids=proposals[0]["evidence_source_ids"],
                conditions={
                    "document_type": document.document_type,
                    "section_type": "any",
                    "jurisdiction": document.jurisdiction,
                    "therapeutic_area": document.therapeutic_area,
                },
            )
            self.experience_repository.add_candidate(candidate)
        return {
            "experience_candidate": asdict(candidate) if candidate else None,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "F",
                        "experience_candidate",
                        "Created an unapproved experience candidate."
                        if candidate
                        else "No reusable experience candidate created.",
                    )
                )
            ],
        }
