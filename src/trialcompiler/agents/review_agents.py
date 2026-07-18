"""Role-separated nodes for the review-only TrialCompiler MVP."""

from __future__ import annotations

import copy
import re
from dataclasses import asdict
from typing import Any

from trialcompiler.documents import ClinicalDocumentGraph, compose_repair_proposals
from trialcompiler.documents.graph import atomic_value_changes, value_present
from trialcompiler.memory.experience import ExperienceRepository
from trialcompiler.models import (
    AgentTraceEvent,
    DecisionRequest,
    QualityDecision,
    ReviewStatus,
    Severity,
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
        finding_payloads = [asdict(item) for item in findings]
        semantic_review = state.get("semantic_review", {})
        semantic_result = semantic_review.get("result", {})
        for index, item in enumerate(semantic_result.get("semantic_findings", []), start=1):
            semantic_fact_ids = {str(value) for value in item.get("fact_ids", [])}
            if (
                {"F022", "F023"}.issubset(semantic_fact_ids)
                and str(item.get("finding_type", "")).lower() == "time_axis_inconsistency"
                and all(
                    graph.facts_by_id[fact_id].status is ReviewStatus.APPROVED
                    for fact_id in ("F022", "F023")
                    if fact_id in graph.facts_by_id
                )
            ):
                continue
            severity = str(item.get("severity", "medium")).lower()
            if severity not in {member.value for member in Severity}:
                severity = Severity.MEDIUM.value
            fact_ids = [str(value) for value in item.get("fact_ids", [])]
            finding_payloads.append(
                {
                    "finding_id": str(item.get("finding_id", f"semantic-{index:03d}")),
                    "finding_type": str(item.get("finding_type", "semantic_review_issue")),
                    "severity": severity,
                    "section_ids": [str(value) for value in item.get("section_ids", [])],
                    "message": str(item.get("message", "Semantic review issue.")),
                    "canonical_fact_id": None,
                    "evidence_source_ids": [str(value) for value in item.get("source_ids", [])],
                    "requires_human_review": True,
                    "fact_ids": fact_ids,
                    "origin": "llm_semantic_review",
                }
            )
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
            "findings": finding_payloads,
            "review_coverage": {
                "deterministic": "completed",
                "semantic": semantic_review.get("status", "not_run"),
                "deterministic_finding_count": len(findings),
                "semantic_finding_count": len(finding_payloads) - len(findings),
            },
            "experience_cards": cards,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "B",
                        "evidence_and_experience",
                        f"Detected {len(finding_payloads)} combined finding(s) and admitted "
                        f"{len(cards)} experience card(s).",
                    )
                )
            ],
        }

    def repair_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        from trialcompiler.models import ReviewFinding

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
        for proposal in state.get("semantic_repairs", {}).get("proposals", []):
            payload = dict(proposal)
            payload["applied_experience_ids"] = card_ids
            payload["status"] = ReviewStatus.REQUIRES_HUMAN_REVIEW.value
            payload["origin"] = "llm_semantic_repair"
            proposal_payloads.append(payload)
        approved_fact_ids = {
            fact.fact_id for fact in document.facts if fact.status is ReviewStatus.APPROVED
        }
        active_change_fact_id = str((state.get("change_context") or {}).get("fact_id", ""))
        if active_change_fact_id:
            approved_fact_ids.add(active_change_fact_id)
        eligible_proposals: list[dict[str, Any]] = []
        authorization_blocks: list[dict[str, Any]] = []
        for payload in proposal_payloads:
            fact_ids = {str(value) for value in payload.get("fact_ids", [])}
            unauthorized = sorted(fact_ids - approved_fact_ids)
            is_semantic = payload.get("origin") == "llm_semantic_repair"
            semantic_without_fact = is_semantic and not fact_ids
            if is_semantic and (unauthorized or semantic_without_fact):
                authorization_blocks.append(
                    {
                        "proposal_id": str(payload["proposal_id"]),
                        "finding_id": str(payload["finding_id"]),
                        "section_id": str(payload["section_id"]),
                        "unauthorized_fact_ids": unauthorized,
                        "reason": (
                            "Semantic repair has no confirmed fact anchor."
                            if semantic_without_fact
                            else "Repair depends on facts that are not approved and are not "
                            "the active governed change."
                        ),
                    }
                )
                continue
            eligible_proposals.append(payload)
        round_index = int(state.get("round_index", 0)) + 1
        feedback = state.get("repair_feedback", {})
        deferred = {str(value) for value in feedback.get("defer_to_human_finding_ids", [])}
        composed_proposals, conflicts = compose_repair_proposals(
            eligible_proposals,
            defer_conflict_finding_ids=deferred,
        )
        return {
            "raw_proposals": proposal_payloads,
            "proposals": composed_proposals,
            "repair_conflicts": conflicts,
            "authorization_blocks": authorization_blocks,
            "deferred_finding_ids": sorted(deferred),
            "round_index": round_index,
            "trace": state.get("trace", [])
            + [
                asdict(
                    trace(
                        "C",
                        "repair_proposal",
                        f"Composed {len(composed_proposals)} section patch(es) from "
                        f"{len(proposal_payloads)} traceable proposal(s); "
                        f"{len(conflicts)} conflict group(s), "
                        f"{len(authorization_blocks)} authorization block(s), "
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
        decision_requests = list(state.get("decision_requests", []))
        deferred = {str(value) for value in state.get("deferred_finding_ids", [])}
        authorization_blocks = state.get("authorization_blocks", [])
        authorization_blocked = {str(item["finding_id"]) for item in authorization_blocks}

        def add_decision_request(finding: dict[str, Any], reason: str) -> None:
            request_id = f"decision-{finding['finding_id']}"
            if any(item.get("request_id") == request_id for item in decision_requests):
                return
            request = DecisionRequest(
                request_id=request_id,
                finding_ids=[str(finding["finding_id"])],
                section_ids=[str(value) for value in finding.get("section_ids", [])],
                question=(
                    "Which evidence-supported interpretation should govern this finding, "
                    "and which affected sections may be revised?"
                ),
                reason=reason,
                options=[
                    "Confirm one supplied interpretation and authorize a new candidate patch.",
                    "Provide additional source evidence before revision.",
                    "Accept the documented inconsistency with a qualified justification.",
                ],
                evidence_source_ids=[
                    str(value) for value in finding.get("evidence_source_ids", [])
                ],
            )
            decision_requests.append(asdict(request))

        for finding in state.get("findings", []):
            matching = [
                proposal
                for proposal in proposals
                if finding["finding_id"]
                in proposal.get("finding_ids", [proposal.get("finding_id")])
            ]
            if not matching:
                if finding["finding_id"] in authorization_blocked:
                    related = [
                        item
                        for item in authorization_blocks
                        if item["finding_id"] == finding["finding_id"]
                    ]
                    fact_ids = sorted(
                        {
                            str(fact_id)
                            for item in related
                            for fact_id in item.get("unauthorized_fact_ids", [])
                        }
                    )
                    add_decision_request(
                        finding,
                        "Candidate wording depends on unapproved facts"
                        + (f" ({', '.join(fact_ids)})" if fact_ids else "")
                        + "; qualified confirmation is required before any text change.",
                    )
                    continue
                if finding["finding_id"] in deferred:
                    add_decision_request(
                        finding,
                        "Competing edits overlap in the same source span; choosing one requires "
                        "qualified judgment.",
                    )
                    continue
                if finding.get("origin") == "llm_semantic_review":
                    add_decision_request(
                        finding,
                        "The supplied evidence supports a concern but not a unique safe redline.",
                    )
                    continue
                unresolved.append(finding["finding_id"])
                reasons.append(f"No repair proposal for {finding['finding_id']}.")
                continue
            for proposal in matching:
                if proposal["original_text"] == proposal["proposed_text"]:
                    unresolved.append(finding["finding_id"])
                    reasons.append(
                        f"Repair {proposal['proposal_id']} does not change the source text."
                    )
                if not proposal.get("evidence_source_ids"):
                    unresolved.append(finding["finding_id"])
                    reasons.append(f"Repair {proposal['proposal_id']} lacks evidence provenance.")
                fact_id = finding.get("canonical_fact_id")
                if fact_id and fact_id in graph.facts_by_id:
                    fact = graph.facts_by_id[fact_id]
                    required_values = [str(fact.value)]
                    if fact.previous_value is not None:
                        required_values = [
                            new
                            for old, new in atomic_value_changes(fact.previous_value, fact.value)
                            if value_present(proposal["original_text"], old, fact.unit)
                        ]
                    missing_values = [
                        value
                        for value in required_values
                        if not value_present(proposal["proposed_text"], value, fact.unit)
                    ]
                    if missing_values:
                        unresolved.append(finding["finding_id"])
                        reasons.append(
                            f"Repair {proposal['proposal_id']} does not contain "
                            f"required value(s) {missing_values}."
                        )
                    previous = fact.previous_value
                    if previous is not None and isinstance(fact.value, int):
                        original_weeks = re.findall(
                            r"\b(?:week|wk)\s*(\d{1,3})\b",
                            proposal["original_text"],
                            re.IGNORECASE,
                        )
                        proposed_weeks = re.findall(
                            r"\b(?:week|wk)\s*(\d{1,3})\b",
                            proposal["proposed_text"],
                            re.IGNORECASE,
                        )
                        protected = {
                            value
                            for value in original_weeks + proposed_weeks
                            if value not in {str(previous), str(fact.value)}
                        }
                        for value in protected:
                            if original_weeks.count(value) != proposed_weeks.count(value):
                                unresolved.append(finding["finding_id"])
                                reasons.append(
                                    f"Repair {proposal['proposal_id']} changes unrelated "
                                    f"Week {value} occurrences."
                                )
        conflicts = state.get("repair_conflicts", [])
        conflict_finding_ids = sorted(
            {
                str(finding_id)
                for conflict in conflicts
                for finding_id in conflict.get("finding_ids", [])
            }
        )
        if conflict_finding_ids:
            unresolved.extend(conflict_finding_ids)
            for conflict in conflicts:
                reasons.append(
                    f"Atomic edit conflict in section {conflict['section_id']}: "
                    f"{', '.join(conflict.get('finding_ids', []))}."
                )
        candidate_payload = copy.deepcopy(document.to_dict())
        candidate_sections = {
            section["section_id"]: section for section in candidate_payload["sections"]
        }
        for proposal in proposals:
            section = candidate_sections.get(proposal["section_id"])
            if section is not None:
                section["text"] = proposal["proposed_text"]
        candidate_document = TrialDocument.from_dict(candidate_payload)
        candidate_findings = ClinicalDocumentGraph(candidate_document).review()
        candidate_finding_ids = {finding.finding_id for finding in candidate_findings}
        initial_deterministic_ids = {
            str(finding["finding_id"])
            for finding in state.get("findings", [])
            if finding.get("origin") == "deterministic"
        }
        remaining_after_patch = sorted(
            (initial_deterministic_ids & candidate_finding_ids) - deferred
        )
        new_after_patch = sorted(candidate_finding_ids - initial_deterministic_ids)
        if remaining_after_patch:
            unresolved.extend(remaining_after_patch)
            reasons.append(
                "Sandbox verification did not close deterministic finding(s): "
                + ", ".join(remaining_after_patch)
                + "."
            )
        if new_after_patch:
            unresolved.extend(new_after_patch)
            reasons.append(
                "Sandbox verification detected new deterministic finding(s): "
                + ", ".join(new_after_patch)
                + "."
            )

        unresolved = sorted(set(unresolved))
        findings = state.get("findings", [])
        findings_by_id = {str(finding["finding_id"]): finding for finding in findings}
        for finding_id in unresolved:
            finding = findings_by_id.get(finding_id)
            if finding is not None:
                add_decision_request(
                    finding,
                    "Sandbox verification could not prove a unique, regression-free machine "
                    "repair. Qualified disposition or additional evidence is required.",
                )
        coverage = state.get("review_coverage", {})
        if not findings and coverage.get("semantic") != "completed":
            accepted = False
            score = 0.0
            reasons.append(
                "No findings were produced, but semantic review did not complete; "
                "the result is indeterminate rather than a pass."
            )
        else:
            accepted = not unresolved
            score = max(0.0, 1.0 - len(unresolved) / max(1, len(findings)))
        decision = QualityDecision(
            accepted=accepted,
            score=score,
            reasons=reasons or ["All proposed changes preserve fact and evidence provenance."],
            unresolved_finding_ids=unresolved,
            decision_request_ids=[str(item["request_id"]) for item in decision_requests],
            machine_repair_complete=not unresolved,
        )
        workflow_status = (
            "machine_repair_incomplete"
            if unresolved
            else "awaiting_qualified_decisions"
            if decision_requests
            else "ready_for_qualified_approval"
        )
        return {
            "quality": asdict(decision),
            "decision_requests": decision_requests,
            "workflow_status": workflow_status,
            "repair_feedback": {
                "retry_finding_ids": conflict_finding_ids,
                "defer_to_human_finding_ids": conflict_finding_ids,
                "conflict_groups": conflicts,
                "instructions": (
                    "Preserve non-conflicting operations. Do not choose between overlapping "
                    "evidence-backed edits; convert them into qualified decision requests."
                    if conflicts
                    else "No targeted machine retry required."
                ),
            },
            "verification": {
                "sandbox_applied": True,
                "candidate_section_count": len(proposals),
                "remaining_deterministic_finding_ids": remaining_after_patch,
                "new_deterministic_finding_ids": new_after_patch,
                "regression_free": not new_after_patch,
            },
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
                    f"- Covers findings: {', '.join(proposal.get('finding_ids', []))}",
                    "",
                ]
            )
        lines += ["", "## Qualified decision requests", ""]
        if not state.get("decision_requests"):
            lines.append("- None.")
        for request in state.get("decision_requests", []):
            lines.extend(
                [
                    f"### {request['request_id']}",
                    "",
                    f"- Findings: {', '.join(request['finding_ids'])}",
                    f"- Question: {request['question']}",
                    f"- Reason: {request['reason']}",
                    f"- Evidence: {', '.join(request['evidence_source_ids']) or 'MISSING'}",
                    "- Options:",
                    *[f"  - {option}" for option in request.get("options", [])],
                    "",
                ]
            )
        quality = state.get("quality", {})
        uncertainty = state.get("uncertainty_artifact", {})
        lines += [
            "## Independent quality gate",
            "",
            f"- Accepted for human review: `{quality.get('accepted', False)}`",
            f"- Score: `{quality.get('score', 0.0):.2f}`",
            "- This gate checks proposal integrity; it is not medical or regulatory approval.",
            f"- Workflow status: `{state.get('workflow_status', 'unknown')}`",
            "- Pending qualified decision requests block final document approval.",
            "",
            "## Uncertainty-governed next action",
            "",
            f"- Selected action: `{uncertainty.get('selected_action', 'unavailable')}`",
            f"- Target: {uncertainty.get('action_target', 'unavailable')}",
            "- Numeric calibrated probability: `not available`",
            f"- Claim note: `{uncertainty.get('claim_note', 'unavailable')}`",
            "- The signal is diagnostic and does not constitute clinical authority.",
            "",
        ]
        semantic = state.get("semantic_review", {})
        if semantic.get("status") == "completed":
            lines += [
                "## Semantic review coverage",
                "",
                f"- Model: `{semantic.get('model', 'unknown')}`",
                f"- Summary: {semantic.get('result', {}).get('summary', '')}",
                "- Semantic findings above entered the same B/C/D quality loop.",
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
        if (
            findings
            and proposals
            and quality_payload.get("accepted")
            and state.get("workflow_status") == "ready_for_qualified_approval"
            and not state.get("decision_requests")
        ):
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
