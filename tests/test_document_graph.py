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

    def test_proposed_change_repairs_only_primary_endpoint_context(self) -> None:
        payload = json.loads(
            (ROOT / "data/fixtures/trialdocbench_case_001.json").read_text(
                encoding="utf-8"
            )
        )
        for fact in payload["facts"]:
            if fact["fact_id"] == "FACT-TIMEPOINT-001":
                fact["previous_value"] = 12
                fact["value"] = 16
                fact["status"] = "proposed_change"
        graph = ClinicalDocumentGraph(TrialDocument.from_dict(payload))
        proposals = graph.propose_repairs(graph.review())
        synopsis = next(
            item for item in proposals if item.section_id == "UNIT-PROTOCOL-SYNOPSIS"
        )
        self.assertIn("primary endpoint is the change", synopsis.proposed_text)
        self.assertIn("at Week 16", synopsis.proposed_text)
        self.assertIn("Week 4, Week 8, Week 12", synopsis.proposed_text)
        objectives = next(
            item
            for item in proposals
            if item.section_id == "UNIT-OBJECTIVES-AND-ENDPOINTS"
        )
        self.assertIn("primary endpoint is the change", objectives.proposed_text)
        self.assertIn("Secondary endpoints include", objectives.proposed_text)
        self.assertIn("quality-of-life score at Week 12", objectives.proposed_text)


if __name__ == "__main__":
    unittest.main()
