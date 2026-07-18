import tempfile
import unittest
from pathlib import Path

from trialcompiler.demo import load_document, seed_demo_experience
from trialcompiler.memory import SemanticElementStore
from trialcompiler.models import ReviewStatus
from trialcompiler.workflows import ReviewWorkflow

ROOT = Path(__file__).resolve().parents[1]


class ReviewWorkflowTests(unittest.TestCase):
    def test_semantic_repair_cannot_use_unapproved_fact_as_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SemanticElementStore(Path(temp) / "memory.sqlite3")
            try:
                workflow = ReviewWorkflow(store)
                document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
                fact = document.facts[0]
                fact.status = ReviewStatus.REQUIRES_HUMAN_REVIEW
                section = document.sections[0]
                semantic_review = {
                    "status": "completed",
                    "model": "test-model",
                    "result": {
                        "summary": "Unapproved interpretation was proposed.",
                        "semantic_findings": [
                            {
                                "finding_type": "unapproved_fact_interpretation",
                                "severity": "high",
                                "section_ids": [section.section_id],
                                "message": "Candidate wording depends on a pending fact.",
                                "fact_ids": [fact.fact_id],
                                "source_ids": list(fact.source_ids),
                                "requires_human_review": True,
                            }
                        ],
                        "review_questions": [],
                        "limitations": [],
                    },
                }
                semantic_repairs = {
                    "status": "completed",
                    "model": "test-model",
                    "proposals": [
                        {
                            "proposal_id": "semantic-unapproved-fact",
                            "finding_id": "semantic-001",
                            "section_id": section.section_id,
                            "original_text": section.text,
                            "proposed_text": section.text + " Pending interpretation chosen.",
                            "rationale": "Must not be authorized by a pending fact.",
                            "fact_ids": [fact.fact_id],
                            "evidence_source_ids": list(fact.source_ids),
                        }
                    ],
                }
                state = workflow.run(
                    document,
                    semantic_review=semantic_review,
                    semantic_repairs=semantic_repairs,
                )
                self.assertEqual(1, len(state["authorization_blocks"]))
                self.assertEqual(
                    [fact.fact_id],
                    state["authorization_blocks"][0]["unauthorized_fact_ids"],
                )
                self.assertFalse(
                    any(
                        "semantic-001" in proposal.get("finding_ids", [])
                        for proposal in state["proposals"]
                    )
                )
                request = next(
                    item
                    for item in state["decision_requests"]
                    if "semantic-001" in item["finding_ids"]
                )
                self.assertIn("unapproved facts", request["reason"])
            finally:
                store.close()

    def test_semantic_findings_enter_shared_quality_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SemanticElementStore(Path(temp) / "memory.sqlite3")
            try:
                workflow = ReviewWorkflow(store)
                document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
                semantic_review = {
                    "status": "completed",
                    "model": "test-model",
                    "result": {
                        "summary": "One additional semantic issue.",
                        "semantic_findings": [
                            {
                                "finding_type": "ambiguous_definition",
                                "severity": "medium",
                                "section_ids": ["S-OBJECTIVES"],
                                "message": "The analysis population needs review.",
                                "fact_ids": [],
                                "source_ids": [],
                                "requires_human_review": True,
                            }
                        ],
                        "review_questions": [],
                        "limitations": [],
                    },
                }
                state = workflow.run(document, semantic_review=semantic_review)
                self.assertTrue(
                    any(item["origin"] == "llm_semantic_review" for item in state["findings"])
                )
                self.assertTrue(state["quality"]["accepted"])
                self.assertTrue(state["quality"]["machine_repair_complete"])
                self.assertNotIn("semantic-001", state["quality"]["unresolved_finding_ids"])
                self.assertEqual(
                    ["decision-semantic-001"], state["quality"]["decision_request_ids"]
                )
                self.assertIn("semantic-001", state["decision_requests"][0]["finding_ids"])
                self.assertEqual("awaiting_qualified_decisions", state["workflow_status"])
                self.assertIsNone(state["experience_candidate"])
            finally:
                store.close()

    def test_end_to_end_review_is_traceable_and_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SemanticElementStore(Path(temp) / "memory.sqlite3")
            workflow = ReviewWorkflow(store)
            seed_demo_experience(workflow.experience_repository)
            document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
            state = workflow.run(document)
            self.assertEqual(2, len(state["findings"]))
            self.assertEqual(2, len(state["proposals"]))
            self.assertEqual(1, len(state["experience_cards"]))
            self.assertTrue(state["quality"]["accepted"])
            self.assertEqual("draft", state["experience_candidate"]["status"])
            self.assertEqual(
                ["A", "B", "C", "D", "G", "E", "F"],
                [e["agent"] for e in state["trace"]],
            )
            self.assertIn("requires qualified human review", state["report_markdown"])
            self.assertEqual(
                "acquire_evidence", state["uncertainty_artifact"]["selected_action"]
            )
            self.assertFalse(
                state["uncertainty_artifact"]["calibration_claim_allowed"]
            )
            run_paths = workflow.save_run(state, Path(temp) / "run")
            uncertainty_path = Path(run_paths["uncertainty"])
            self.assertTrue(uncertainty_path.exists())
            self.assertIn(
                '"numeric_probability_available": false',
                uncertainty_path.read_text(encoding="utf-8"),
            )
            self.assertIn("Uncertainty-governed next action", state["report_markdown"])
            store.close()

    def test_overlapping_repairs_converge_to_explicit_decision_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SemanticElementStore(Path(temp) / "memory.sqlite3")
            try:
                workflow = ReviewWorkflow(store)
                document = load_document(ROOT / "data/fixtures/synthetic_protocol_conflict.json")
                original = document.sections[0].text
                semantic_review = {
                    "status": "completed",
                    "model": "test-model",
                    "result": {
                        "summary": "Competing endpoint interpretation.",
                        "semantic_findings": [
                            {
                                "finding_type": "endpoint_interpretation",
                                "severity": "high",
                                "section_ids": ["S-SYNOPSIS"],
                                "message": "A reviewer proposed Week 18.",
                                "fact_ids": ["F-PRIMARY-ENDPOINT-WEEK"],
                                "source_ids": ["SRC-DEMO-AMENDMENT"],
                                "requires_human_review": True,
                            }
                        ],
                        "review_questions": [],
                        "limitations": [],
                    },
                }
                semantic_repairs = {
                    "status": "completed",
                    "model": "test-model",
                    "proposals": [
                        {
                            "proposal_id": "semantic-overlap",
                            "finding_id": "semantic-001",
                            "section_id": "S-SYNOPSIS",
                            "original_text": original,
                            "proposed_text": original.replace("Week 12", "Week 18"),
                            "rationale": "Alternative interpretation requiring a decision.",
                            "fact_ids": ["F-PRIMARY-ENDPOINT-WEEK"],
                            "evidence_source_ids": ["SRC-DEMO-AMENDMENT"],
                        }
                    ],
                }
                state = workflow.run(
                    document,
                    semantic_review=semantic_review,
                    semantic_repairs=semantic_repairs,
                    max_rounds=3,
                )
                self.assertEqual(2, state["round_index"])
                self.assertTrue(state["quality"]["accepted"])
                decision_finding_ids = {
                    finding_id
                    for request in state["decision_requests"]
                    for finding_id in request["finding_ids"]
                }
                self.assertIn("semantic-001", decision_finding_ids)
                self.assertIn(
                    "week-conflict-F-PRIMARY-ENDPOINT-WEEK-S-SYNOPSIS",
                    decision_finding_ids,
                )
                self.assertFalse(state["repair_conflicts"])
                self.assertEqual("awaiting_qualified_decisions", state["workflow_status"])
                self.assertIsNone(state["experience_candidate"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
