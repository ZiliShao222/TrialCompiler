import json
import tempfile
import unittest
from pathlib import Path

from trialcompiler.demo import load_document, seed_demo_experience
from trialcompiler.documents import ClinicalDocumentGraph
from trialcompiler.memory import SemanticElementStore
from trialcompiler.project import ProjectWorkspace
from trialcompiler.workflows import ReviewWorkflow

ROOT = Path(__file__).resolve().parents[1]


class ProjectWorkspaceTests(unittest.TestCase):
    def test_sequence_change_detects_and_repairs_atomic_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = ProjectWorkspace(Path(temp) / "workspace")
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            fact = document.facts[0]
            fact.fact_id = "F-PK-SEQUENCE"
            fact.name = "PK sampling sequence"
            fact.value = "0 hours; 12 hours; 32 hours"
            fact.unit = "hours"
            document.sections[0].fact_refs = [fact.fact_id]
            document.sections[0].text = (
                "Up to 32 participants may enroll. "
                "PK samples are collected at 0, 12, and 32 hours."
            )
            for section in document.sections[1:]:
                section.fact_refs = []
            workspace.initialize(document, actor="tester")
            change = workspace.create_change(
                fact_id=fact.fact_id,
                proposed_value="0 hours; 12 hours; 36 hours",
                reason="Synthetic terminal PK update",
                requested_by="tester",
            )
            impact = workspace.impact_matrix(change)
            self.assertEqual(["32 hours"], impact[0]["observed_values"])
            graph = ClinicalDocumentGraph(workspace.candidate_document(change))
            findings = graph.review()
            proposals = graph.propose_repairs(findings)
            self.assertEqual(1, len(proposals))
            self.assertIn("36 hours", proposals[0].proposed_text)
            self.assertIn("32 participants", proposals[0].proposed_text)
            self.assertNotIn("32 hours", proposals[0].proposed_text)

    def test_latest_actionable_change_skips_final_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = ProjectWorkspace(Path(temp_dir) / "workspace")
            workspace.initialize(
                load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json"),
                actor="tester",
            )
            first = workspace.create_change(
                fact_id="F-PRIMARY-ENDPOINT-WEEK",
                proposed_value=20,
                reason="first",
                requested_by="tester",
            )
            first.status = "rejected"
            workspace.save_change(first)
            second = workspace.create_change(
                fact_id="F-PRIMARY-ENDPOINT-WEEK",
                proposed_value=24,
                reason="second",
                requested_by="tester",
            )

            self.assertEqual(workspace.latest_actionable_change().change_id, second.change_id)

    def test_change_compile_approve_updates_every_impacted_section_and_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            workspace = ProjectWorkspace(root)
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            for section in document.sections:
                section.text = section.text.replace("Week 12", "Week 16")
            workspace.initialize(document, actor="tester")

            change = workspace.create_change(
                fact_id="F-PRIMARY-ENDPOINT-WEEK",
                proposed_value=20,
                reason="Synthetic amendment test",
                requested_by="medical-lead",
            )
            self.assertEqual(3, len(workspace.impact_matrix(change)))

            candidate = workspace.candidate_document(change)
            store = SemanticElementStore(root / "memory.sqlite3")
            try:
                workflow = ReviewWorkflow(store)
                seed_demo_experience(workflow.experience_repository)
                state = workflow.run(candidate)
                run_id = "run-test"
                run_dir = root / "runs" / run_id
                paths = workflow.save_run(state, run_dir)
                workspace.write_run_artifacts(
                    run_id=run_id,
                    change=change,
                    state=state,
                    workflow_paths=paths,
                    impact=workspace.impact_matrix(change),
                )
                change.status = "compiled"
                change.compiled_run_id = run_id
                workspace.save_change(change)

                approval = workspace.decide_change(
                    change_id=change.change_id,
                    decision="approve",
                    reviewer="qualified-reviewer",
                    note="Synthetic approval only",
                )
            finally:
                store.close()
            self.assertEqual("approve", approval["decision"])
            updated = workspace.load_document()
            changed_fact = next(f for f in updated.facts if f.fact_id == change.fact_id)
            self.assertEqual(20, changed_fact.value)
            self.assertTrue(all("Week 20" in section.text for section in updated.sections))
            run_summary = json.loads(
                (root / "runs" / "run-test" / "run_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("approve", run_summary["human_decision"])
            self.assertEqual(
                "human_approved_change_applied", run_summary["release_status"]
            )
            lines = workspace.audit_path.read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in lines]
            self.assertEqual(
                ["workspace_initialized", "change_requested", "change_approved"],
                [event["action"] for event in events],
            )

    def test_reject_keeps_document_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = ProjectWorkspace(Path(temp) / "workspace")
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            workspace.initialize(document, actor="tester")
            change = workspace.create_change(
                fact_id="F-SAMPLE-SIZE",
                proposed_value=150,
                reason="Synthetic option",
                requested_by="statistician",
            )
            workspace.decide_change(
                change_id=change.change_id,
                decision="reject",
                reviewer="qualified-reviewer",
                note="Not supported",
            )
            updated = workspace.load_document()
            changed_fact = next(f for f in updated.facts if f.fact_id == change.fact_id)
            self.assertEqual(120, changed_fact.value)

    def test_pending_decision_request_blocks_approval_until_qualified_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            workspace = ProjectWorkspace(root)
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            for section in document.sections:
                section.text = section.text.replace("Week 12", "Week 16")
            workspace.initialize(document, actor="tester")
            change = workspace.create_change(
                fact_id="F-PRIMARY-ENDPOINT-WEEK",
                proposed_value=20,
                reason="Synthetic governed decision test",
                requested_by="medical-lead",
            )
            candidate = workspace.candidate_document(change)
            store = SemanticElementStore(root / "memory.sqlite3")
            try:
                workflow = ReviewWorkflow(store)
                state = workflow.run(candidate)
                state["decision_requests"] = [
                    {
                        "request_id": "decision-test",
                        "finding_ids": ["semantic-test"],
                        "section_ids": [candidate.sections[0].section_id],
                        "question": "Which interpretation is authorized?",
                        "reason": "Evidence does not determine a unique redline.",
                        "options": ["Accept documented inconsistency"],
                        "evidence_source_ids": [candidate.sources[0].source_id],
                        "status": "pending_qualified_human_decision",
                    }
                ]
                state["workflow_status"] = "awaiting_qualified_decisions"
                state["quality"]["decision_request_ids"] = ["decision-test"]
                run_id = "run-decision-test"
                paths = workflow.save_run(state, root / "runs" / run_id)
                workspace.write_run_artifacts(
                    run_id=run_id,
                    change=change,
                    state=state,
                    workflow_paths=paths,
                    impact=workspace.impact_matrix(change),
                )
                change.status = "compiled"
                change.compiled_run_id = run_id
                workspace.save_change(change)
            finally:
                store.close()

            with self.assertRaisesRegex(ValueError, "decision-test"):
                workspace.decide_change(
                    change_id=change.change_id,
                    decision="approve",
                    reviewer="qualified-reviewer",
                    note="Premature approval",
                )

            workspace.resolve_decision_request(
                change_id=change.change_id,
                request_id="decision-test",
                decision="accept_documented",
                reviewer="qualified-reviewer",
                note="Source discrepancy is accepted and documented for this synthetic test.",
            )
            approval = workspace.decide_change(
                change_id=change.change_id,
                decision="approve",
                reviewer="qualified-reviewer",
                note="All qualified requests resolved",
            )
            self.assertEqual("approve", approval["decision"])
            resolved = json.loads(
                (root / "runs" / run_id / "decision_requests.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("resolved_accepted", resolved[0]["status"])

    def test_candidate_fact_can_be_confirmed_with_a_source(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = ProjectWorkspace(Path(temp) / "workspace")
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            document.facts[0].status = "draft"
            workspace.initialize(document, actor="tester")
            decision = workspace.decide_fact(
                fact_id=document.facts[0].fact_id,
                decision="confirm",
                reviewer="medical-reviewer",
                note="Source checked in synthetic fixture",
            )
            self.assertEqual("approved", decision["new_status"])


if __name__ == "__main__":
    unittest.main()
