"""Persistent project workspace for the TrialCompiler command-line product."""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trialcompiler.assurance import materialize_run_summary
from trialcompiler.documents import ClinicalDocumentGraph
from trialcompiler.documents.graph import atomic_value_changes, value_present
from trialcompiler.models import ReviewStatus, TrialDocument, to_plain


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_plain(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_plain(payload), ensure_ascii=False) + "\n")


@dataclass(slots=True)
class ChangeRequest:
    change_id: str
    fact_id: str
    old_value: Any
    proposed_value: Any
    reason: str
    requested_by: str
    status: str = "draft"
    created_at: str = field(default_factory=_now)
    compiled_run_id: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None


class ProjectWorkspace:
    """Store one synthetic or authorized project as inspectable files."""

    MANIFEST = "project.json"
    DOCUMENT = "document.json"
    AUDIT = "audit.jsonl"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def manifest_path(self) -> Path:
        return self.root / self.MANIFEST

    @property
    def document_path(self) -> Path:
        return self.root / self.DOCUMENT

    @property
    def audit_path(self) -> Path:
        return self.root / self.AUDIT

    def initialize(self, document: TrialDocument, *, actor: str, replace: bool = False) -> None:
        if self.manifest_path.exists() and not replace:
            raise FileExistsError(f"Workspace already exists: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("changes", "runs", "approvals"):
            (self.root / name).mkdir(exist_ok=True)
        _write_json(
            self.manifest_path,
            {
                "workspace_version": 1,
                "project_id": document.project_id,
                "title": document.title,
                "document_id": document.document_id,
                "release_mode": "review_only",
                "created_at": _now(),
                "updated_at": _now(),
            },
        )
        _write_json(self.document_path, document.to_dict())
        self.audit(
            actor=actor,
            action="workspace_initialized",
            object_type="document",
            object_id=document.document_id,
            detail={"source": str(self.document_path), "version": document.version},
        )

    def require(self) -> None:
        if not self.manifest_path.exists() or not self.document_path.exists():
            raise FileNotFoundError(
                f"Not a TrialCompiler workspace: {self.root}. Run `trialcompiler init` first."
            )

    def load_document(self) -> TrialDocument:
        self.require()
        return TrialDocument.from_dict(json.loads(self.document_path.read_text(encoding="utf-8")))

    def save_document(self, document: TrialDocument) -> None:
        _write_json(self.document_path, document.to_dict())
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["updated_at"] = _now()
        _write_json(self.manifest_path, manifest)

    def audit(
        self,
        *,
        actor: str,
        action: str,
        object_type: str,
        object_id: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        _append_jsonl(
            self.audit_path,
            {
                "event_id": f"evt-{uuid.uuid4().hex[:12]}",
                "timestamp": _now(),
                "actor": actor,
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "detail": detail or {},
            },
        )

    def status(self) -> dict[str, Any]:
        document = self.load_document()
        changes = self.list_changes()
        fact_counts: dict[str, int] = {}
        for fact in document.facts:
            fact_counts[fact.status.value] = fact_counts.get(fact.status.value, 0) + 1
        return {
            "project_id": document.project_id,
            "title": document.title,
            "document_id": document.document_id,
            "document_version": document.version,
            "facts": fact_counts,
            "sections": len(document.sections),
            "sources": len(document.sources),
            "open_changes": sum(item.status not in {"approved", "rejected"} for item in changes),
            "release_mode": "review_only",
        }

    def create_change(
        self,
        *,
        fact_id: str,
        proposed_value: Any,
        reason: str,
        requested_by: str,
    ) -> ChangeRequest:
        document = self.load_document()
        facts = {fact.fact_id: fact for fact in document.facts}
        if fact_id not in facts:
            raise KeyError(f"Unknown fact: {fact_id}")
        change = ChangeRequest(
            change_id=f"chg-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            fact_id=fact_id,
            old_value=facts[fact_id].value,
            proposed_value=proposed_value,
            reason=reason,
            requested_by=requested_by,
        )
        _write_json(self.root / "changes" / f"{change.change_id}.json", asdict(change))
        self.audit(
            actor=requested_by,
            action="change_requested",
            object_type="fact",
            object_id=fact_id,
            detail={
                "change_id": change.change_id,
                "old_value": change.old_value,
                "proposed_value": proposed_value,
                "reason": reason,
            },
        )
        return change

    def decide_fact(
        self,
        *,
        fact_id: str,
        decision: str,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        if decision not in {"confirm", "reject"}:
            raise ValueError("decision must be confirm or reject")
        document = self.load_document()
        facts = {fact.fact_id: fact for fact in document.facts}
        if fact_id not in facts:
            raise KeyError(f"Unknown fact: {fact_id}")
        fact = facts[fact_id]
        previous_status = fact.status.value
        if decision == "confirm":
            if not fact.source_ids:
                raise ValueError("A fact cannot be confirmed without a source reference")
            fact.status = ReviewStatus.APPROVED
        else:
            fact.status = ReviewStatus.REJECTED
        fact.updated_at = _now()
        self.save_document(document)
        record = {
            "fact_id": fact_id,
            "decision": decision,
            "reviewer": reviewer,
            "timestamp": fact.updated_at,
            "previous_status": previous_status,
            "new_status": fact.status.value,
            "note": note,
        }
        self.audit(
            actor=reviewer,
            action=f"fact_{fact.status.value}",
            object_type="fact",
            object_id=fact_id,
            detail=record,
        )
        return record

    def list_changes(self) -> list[ChangeRequest]:
        self.require()
        paths = sorted((self.root / "changes").glob("*.json"))
        return [self.load_change(path.stem) for path in paths]

    def latest_actionable_change(self) -> ChangeRequest | None:
        """Return the newest change that has not received a final human decision."""
        actionable = [
            change
            for change in self.list_changes()
            if change.status not in {"approved", "rejected"}
        ]
        return actionable[-1] if actionable else None

    def load_change(self, change_id: str) -> ChangeRequest:
        path = self.root / "changes" / f"{change_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Unknown change request: {change_id}")
        return ChangeRequest(**json.loads(path.read_text(encoding="utf-8")))

    def save_change(self, change: ChangeRequest) -> None:
        _write_json(self.root / "changes" / f"{change.change_id}.json", asdict(change))

    def candidate_document(self, change: ChangeRequest) -> TrialDocument:
        payload = copy.deepcopy(self.load_document().to_dict())
        matched = False
        for fact in payload["facts"]:
            if fact["fact_id"] == change.fact_id:
                fact["previous_value"] = change.old_value
                fact["value"] = change.proposed_value
                fact["status"] = ReviewStatus.PROPOSED_CHANGE.value
                fact["version"] = int(fact.get("version", 1)) + 1
                fact["updated_at"] = _now()
                matched = True
        if not matched:
            raise KeyError(f"Unknown fact: {change.fact_id}")
        return TrialDocument.from_dict(payload)

    def impact_matrix(self, change: ChangeRequest) -> list[dict[str, Any]]:
        document = self.load_document()
        graph = ClinicalDocumentGraph(document)
        fact = graph.facts_by_id[change.fact_id]
        rows: list[dict[str, Any]] = []
        for section_id in graph.impact_set(change.fact_id):
            section = graph.sections_by_id[section_id]
            observed_values = self._observed_values(section.text, change, unit=fact.unit)
            changes = atomic_value_changes(change.old_value, change.proposed_value)
            aligned = bool(changes) and all(
                not value_present(section.text, old, fact.unit)
                and value_present(section.text, new, fact.unit)
                for old, new in changes
            )
            rows.append(
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "document_type": section.document_type,
                    "impact_type": "direct_fact_dependency",
                    "old_value_present": any(
                        value_present(section.text, old, fact.unit) for old, _ in changes
                    ),
                    "proposed_value_present": any(
                        value_present(section.text, new, fact.unit) for _, new in changes
                    ),
                    "observed_values": observed_values,
                    "alignment": "already_aligned" if aligned else "revision_candidate",
                    "review_status": "requires_human_review",
                }
            )
        return rows

    @staticmethod
    def _observed_values(text: str, change: ChangeRequest, *, unit: str | None = None) -> list[str]:
        if "week" in text.lower():
            values = re.findall(r"\b(?:week|wk)\s*(\d{1,3})\b", text, re.IGNORECASE)
            if values:
                return values
        observed: list[str] = []
        for old, new in atomic_value_changes(change.old_value, change.proposed_value):
            for value in (old, new):
                if value_present(text, value, unit) and value not in observed:
                    observed.append(value)
        return observed

    @staticmethod
    def _value_present(text: str, value: Any) -> bool:
        if isinstance(value, list):
            return any(value_present(text, item) for item in value)
        if isinstance(value, str) and re.search(r"[;|\n]", value):
            parts = [part.strip() for part in re.split(r"\s*(?:;|\||\n)\s*", value)]
            return any(value_present(text, part) for part in parts if part)
        return value_present(text, value)

    def write_run_artifacts(
        self,
        *,
        run_id: str,
        change: ChangeRequest | None,
        state: dict[str, Any],
        workflow_paths: dict[str, str],
        impact: list[dict[str, Any]],
    ) -> Path:
        run_dir = self.root / "runs" / run_id
        _write_json(run_dir / "impact_matrix.json", impact)
        semantic_review = state.get("semantic_review", {})
        _write_json(run_dir / "semantic_review.json", semantic_review)
        semantic_repairs = state.get("semantic_repairs", {})
        _write_json(run_dir / "semantic_repairs.json", semantic_repairs)
        _write_json(run_dir / "decision_requests.json", state.get("decision_requests", []))
        _write_json(
            run_dir / "run_summary.json",
            materialize_run_summary(
                run_id=run_id,
                change_id=change.change_id if change else None,
                created_at=_now(),
                state=state,
                artifacts=workflow_paths,
            ),
        )
        return run_dir

    def decide_change(
        self,
        *,
        change_id: str,
        decision: str,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        change = self.load_change(change_id)
        if change.status in {"approved", "rejected"}:
            raise ValueError(f"Change {change_id} is already {change.status}")
        change.status = "approved" if decision == "approve" else "rejected"
        change.reviewed_by = reviewer
        change.reviewed_at = _now()
        change.review_note = note

        applied_sections: list[str] = []
        if decision == "approve":
            if not change.compiled_run_id:
                raise ValueError("Compile the change before approval")
            run_dir = self.root / "runs" / change.compiled_run_id
            state = json.loads((run_dir / "workflow_state.json").read_text(encoding="utf-8"))
            quality = state.get("quality", {})
            if not quality.get("accepted"):
                raise ValueError("Quality gate did not accept this change for human review")
            pending_requests = [
                request
                for request in state.get("decision_requests", [])
                if request.get("status") != "resolved_accepted"
            ]
            if pending_requests:
                request_ids = ", ".join(
                    str(request.get("request_id", "unknown")) for request in pending_requests
                )
                raise ValueError(
                    "Qualified decision requests must be resolved before approval: " + request_ids
                )
            document = self.load_document()
            facts = {fact.fact_id: fact for fact in document.facts}
            fact = facts[change.fact_id]
            previous = fact.value
            fact.value = change.proposed_value
            fact.version += 1
            fact.updated_at = _now()
            fact.status = ReviewStatus.APPROVED
            sections = {section.section_id: section for section in document.sections}
            for proposal in state.get("proposals", []):
                section = sections.get(proposal["section_id"])
                if section and proposal.get("fact_ids") == [change.fact_id]:
                    section.text = proposal["proposed_text"]
                    applied_sections.append(section.section_id)
            document.version = self._next_version(document.version)
            self.save_document(document)
            detail = {
                "change_id": change_id,
                "old_value": previous,
                "new_value": change.proposed_value,
                "applied_sections": applied_sections,
                "document_version": document.version,
                "note": note,
            }
        else:
            detail = {"change_id": change_id, "note": note}

        self.save_change(change)
        if change.compiled_run_id:
            summary_path = self.root / "runs" / change.compiled_run_id / "run_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                summary.update(
                    {
                        "human_decision": decision,
                        "reviewer": reviewer,
                        "reviewed_at": change.reviewed_at,
                        "review_note": note,
                        "release_status": (
                            "human_approved_change_applied"
                            if decision == "approve"
                            else "human_rejected_no_change"
                        ),
                    }
                )
                _write_json(summary_path, summary)
        approval = {
            "change_id": change_id,
            "decision": decision,
            "reviewer": reviewer,
            "timestamp": change.reviewed_at,
            "note": note,
            "applied_sections": applied_sections,
        }
        _write_json(self.root / "approvals" / f"{change_id}.json", approval)
        self.audit(
            actor=reviewer,
            action=f"change_{change.status}",
            object_type="change_request",
            object_id=change_id,
            detail=detail,
        )
        return approval

    def resolve_decision_request(
        self,
        *,
        change_id: str,
        request_id: str,
        decision: str,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        """Record a qualified decision without silently inventing a document edit."""
        if decision not in {"accept_documented", "require_recompile"}:
            raise ValueError("decision must be accept_documented or require_recompile")
        if not note.strip():
            raise ValueError("A qualified decision requires a non-empty justification")
        change = self.load_change(change_id)
        if not change.compiled_run_id:
            raise ValueError("Compile the change before resolving decision requests")
        run_dir = self.root / "runs" / change.compiled_run_id
        state_path = run_dir / "workflow_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        requests = state.get("decision_requests", [])
        request = next(
            (item for item in requests if item.get("request_id") == request_id),
            None,
        )
        if request is None:
            raise KeyError(f"Unknown decision request: {request_id}")
        request.update(
            {
                "status": (
                    "resolved_accepted" if decision == "accept_documented" else "requires_recompile"
                ),
                "decision": decision,
                "reviewer": reviewer,
                "reviewed_at": _now(),
                "review_note": note,
            }
        )
        pending = [item for item in requests if item.get("status") != "resolved_accepted"]
        state["workflow_status"] = (
            "ready_for_qualified_approval" if not pending else "awaiting_qualified_decisions"
        )
        _write_json(state_path, state)
        _write_json(run_dir / "decision_requests.json", requests)
        summary_path = run_dir / "run_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary = materialize_run_summary(
                run_id=str(summary.get("run_id", change.compiled_run_id)),
                change_id=summary.get("change_id", change_id),
                state=state,
                existing=summary,
            )
            _write_json(summary_path, summary)
        record = {
            "change_id": change_id,
            "request_id": request_id,
            "decision": decision,
            "reviewer": reviewer,
            "reviewed_at": request["reviewed_at"],
            "note": note,
            "workflow_status": state["workflow_status"],
        }
        self.audit(
            actor=reviewer,
            action="decision_request_resolved",
            object_type="decision_request",
            object_id=request_id,
            detail=record,
        )
        return record

    @staticmethod
    def _next_version(version: str) -> str:
        try:
            major, minor = version.split(".", maxsplit=1)
            return f"{major}.{int(minor) + 1}"
        except (AttributeError, ValueError):
            return f"{version}.1"
