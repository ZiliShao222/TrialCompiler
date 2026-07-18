"""Repair stale duplicate run artifacts and explicitly queue unresolved findings."""

import argparse
import json
from pathlib import Path

from trialcompiler.assurance import materialize_run_summary

parser = argparse.ArgumentParser()
parser.add_argument("run_dir", type=Path)
args = parser.parse_args()
state_path = args.run_dir / "workflow_state.json"
summary_path = args.run_dir / "run_summary.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
summary = json.loads(summary_path.read_text(encoding="utf-8"))
requests = state.setdefault("decision_requests", [])
existing = {str(x) for r in requests for x in r.get("finding_ids", [])}
findings = {str(f["finding_id"]): f for f in state.get("findings", [])}
for finding_id in state.get("quality", {}).get("unresolved_finding_ids", []):
    if str(finding_id) in existing:
        continue
    finding = findings.get(str(finding_id), {})
    requests.append(
        {
            "request_id": f"decision-{finding_id}",
            "finding_ids": [str(finding_id)],
            "section_ids": [str(x) for x in finding.get("section_ids", [])],
            "question": "Which qualified disposition should govern this unresolved finding?",
            "reason": (
                "Machine verification could not prove a unique regression-free repair; "
                "additional evidence, an authorized patch, or documented acceptance is required."
            ),
            "options": [
                "Authorize an evidence-supported patch and recompile.",
                "Provide additional evidence before revision.",
                "Accept the documented inconsistency with qualified justification.",
            ],
            "evidence_source_ids": [str(x) for x in finding.get("evidence_source_ids", [])],
            "status": "pending_qualified_human_decision",
        }
    )
state["quality"]["decision_request_ids"] = [str(r["request_id"]) for r in requests]
if requests:
    state["workflow_status"] = "awaiting_qualified_decisions"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(args.run_dir / "decision_requests.json").write_text(
    json.dumps(requests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
summary = materialize_run_summary(
    run_id=str(summary.get("run_id", args.run_dir.name)),
    change_id=summary.get("change_id"),
    state=state,
    existing=summary,
)
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(
    json.dumps(
        {"decision_request_count": len(requests), "workflow_status": state["workflow_status"]}
    )
)
