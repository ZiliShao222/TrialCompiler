"""Operation-level repair composition for auditable document edits."""

from __future__ import annotations

from dataclasses import asdict
from difflib import SequenceMatcher
from typing import Any

from trialcompiler.models import EditOperation


def proposal_to_operations(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a whole-section proposal into minimal edits against its exact base text."""
    original = str(proposal["original_text"])
    proposed = str(proposal["proposed_text"])
    matcher = SequenceMatcher(a=original, b=proposed, autojunk=False)
    operations: list[dict[str, Any]] = []
    for index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes(), start=1):
        if tag == "equal":
            continue
        operation = EditOperation(
            operation_id=f"{proposal['proposal_id']}-op-{index:02d}",
            finding_id=str(proposal["finding_id"]),
            section_id=str(proposal["section_id"]),
            start=i1,
            end=i2,
            replacement=proposed[j1:j2],
            before=original[i1:i2],
            rationale=str(proposal.get("rationale", "")),
            fact_ids=[str(value) for value in proposal.get("fact_ids", [])],
            evidence_source_ids=[
                str(value) for value in proposal.get("evidence_source_ids", [])
            ],
            origin=str(proposal.get("origin", "unknown")),
        )
        operations.append(asdict(operation))
    return operations


def _overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether two base-coordinate edits compete for the same text."""
    ls, le = int(left["start"]), int(left["end"])
    rs, re = int(right["start"]), int(right["end"])
    if ls == le and rs == re:
        return ls == rs
    if ls == le:
        return rs <= ls < re
    if rs == re:
        return ls <= rs < le
    return max(ls, rs) < min(le, re)


def compose_repair_proposals(
    proposals: list[dict[str, Any]],
    *,
    defer_conflict_finding_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge independent edits and return explicit conflict groups for competing edits."""
    deferred = defer_conflict_finding_ids or set()
    by_section: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposals:
        if str(proposal["finding_id"]) in deferred:
            continue
        by_section.setdefault(str(proposal["section_id"]), []).append(proposal)

    composed: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for section_id, section_proposals in by_section.items():
        originals = {str(item["original_text"]) for item in section_proposals}
        if len(originals) != 1:
            conflicts.append(
                {
                    "conflict_id": f"conflict-{section_id}-base",
                    "section_id": section_id,
                    "finding_ids": sorted(
                        {str(item["finding_id"]) for item in section_proposals}
                    ),
                    "reason": "Repair proposals do not share the same base section text.",
                    "operations": [],
                }
            )
            continue
        original = originals.pop()
        operations: list[dict[str, Any]] = []
        for proposal in section_proposals:
            operations.extend(proposal_to_operations(proposal))

        conflicting_indexes: set[int] = set()
        conflict_pairs: list[tuple[int, int]] = []
        for left_index, left in enumerate(operations):
            for right_index in range(left_index + 1, len(operations)):
                right = operations[right_index]
                if not _overlap(left, right):
                    continue
                identical = (
                    left["start"], left["end"], left["replacement"]
                ) == (right["start"], right["end"], right["replacement"])
                if identical:
                    continue
                conflicting_indexes.update({left_index, right_index})
                conflict_pairs.append((left_index, right_index))

        if conflict_pairs:
            conflict_ops = [operations[index] for index in sorted(conflicting_indexes)]
            conflicts.append(
                {
                    "conflict_id": f"conflict-{section_id}-001",
                    "section_id": section_id,
                    "finding_ids": sorted(
                        {str(item["finding_id"]) for item in conflict_ops}
                    ),
                    "reason": "Two evidence-backed edits overlap and propose different text.",
                    "operations": conflict_ops,
                }
            )

        safe_operations = [
            operation
            for index, operation in enumerate(operations)
            if index not in conflicting_indexes
        ]
        unique_operations: dict[tuple[int, int, str], dict[str, Any]] = {}
        for operation in safe_operations:
            key = (
                int(operation["start"]),
                int(operation["end"]),
                str(operation["replacement"]),
            )
            existing = unique_operations.get(key)
            if existing is None:
                unique_operations[key] = operation
            else:
                existing.setdefault("finding_ids", [existing["finding_id"]])
                existing["finding_ids"] = sorted(
                    set(existing["finding_ids"] + [operation["finding_id"]])
                )
        safe_operations = list(unique_operations.values())
        if not safe_operations:
            continue

        proposed_text = original
        for operation in sorted(
            safe_operations, key=lambda item: (int(item["start"]), int(item["end"])), reverse=True
        ):
            start, end = int(operation["start"]), int(operation["end"])
            if proposed_text[start:end] != operation["before"]:
                raise ValueError(
                    f"Edit precondition failed for {operation['operation_id']} in {section_id}"
                )
            proposed_text = proposed_text[:start] + operation["replacement"] + proposed_text[end:]

        finding_ids = sorted(
            {
                str(finding_id)
                for item in safe_operations
                for finding_id in item.get("finding_ids", [item["finding_id"]])
            }
        )
        fact_ids = sorted(
            {str(value) for item in safe_operations for value in item.get("fact_ids", [])}
        )
        source_ids = sorted(
            {
                str(value)
                for item in safe_operations
                for value in item.get("evidence_source_ids", [])
            }
        )
        composed.append(
            {
                "proposal_id": f"composed-{section_id}",
                "finding_id": finding_ids[0],
                "finding_ids": finding_ids,
                "section_id": section_id,
                "original_text": original,
                "proposed_text": proposed_text,
                "rationale": "Merged independent, evidence-traceable edits: "
                + " | ".join(dict.fromkeys(str(item["rationale"]) for item in safe_operations)),
                "fact_ids": fact_ids,
                "evidence_source_ids": source_ids,
                "requires_human_review": True,
                "status": "requires_human_review",
                "origin": "operation_composer",
                "edit_operations": safe_operations,
            }
        )
    return composed, conflicts
