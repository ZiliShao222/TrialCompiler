import tempfile
import unittest
from pathlib import Path

from trialcompiler.demo import load_document, seed_demo_experience
from trialcompiler.memory import SemanticElementStore
from trialcompiler.workflows import ReviewWorkflow

ROOT = Path(__file__).resolve().parents[1]


class ReviewWorkflowTests(unittest.TestCase):
    def test_end_to_end_review_is_traceable_and_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SemanticElementStore(Path(temp) / "memory.sqlite3")
            workflow = ReviewWorkflow(store)
            seed_demo_experience(workflow.experience_repository)
            document = load_document(
                ROOT / "data/fixtures/synthetic_protocol_conflict.json"
            )
            state = workflow.run(document)
            self.assertEqual(2, len(state["findings"]))
            self.assertEqual(2, len(state["proposals"]))
            self.assertEqual(1, len(state["experience_cards"]))
            self.assertTrue(state["quality"]["accepted"])
            self.assertEqual("draft", state["experience_candidate"]["status"])
            self.assertEqual(["A", "B", "C", "D", "E", "F"], [e["agent"] for e in state["trace"]])
            self.assertIn("requires qualified human review", state["report_markdown"])
            store.close()


if __name__ == "__main__":
    unittest.main()
