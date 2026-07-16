import json
import unittest
from pathlib import Path

from trialcompiler.documents import ClinicalDocumentGraph
from trialcompiler.models import TrialDocument

ROOT = Path(__file__).resolve().parents[1]


class DocumentGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(
            (ROOT / "data/fixtures/synthetic_protocol_conflict.json").read_text(
                encoding="utf-8"
            )
        )
        self.graph = ClinicalDocumentGraph(TrialDocument.from_dict(payload))

    def test_detects_both_cross_section_conflicts(self) -> None:
        findings = self.graph.review()
        self.assertEqual(2, len(findings))
        self.assertEqual(
            {"S-SCHEDULE", "S-SYNOPSIS"},
            {finding.section_ids[0] for finding in findings},
        )

    def test_impact_set_includes_every_declared_dependency(self) -> None:
        self.assertEqual(
            ["S-OBJECTIVES", "S-SCHEDULE", "S-SYNOPSIS"],
            self.graph.impact_set("F-PRIMARY-ENDPOINT-WEEK"),
        )

    def test_repairs_preserve_non_conflicting_content(self) -> None:
        proposals = self.graph.propose_repairs(self.graph.review())
        synopsis = next(item for item in proposals if item.section_id == "S-SYNOPSIS")
        self.assertIn("Week 16", synopsis.proposed_text)
        self.assertIn("120 participants", synopsis.proposed_text)


if __name__ == "__main__":
    unittest.main()
