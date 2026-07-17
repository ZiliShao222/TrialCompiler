import unittest

from trialcompiler.documents.repairs import compose_repair_proposals


def proposal(proposal_id, finding_id, original, proposed):
    return {
        "proposal_id": proposal_id,
        "finding_id": finding_id,
        "section_id": "S1",
        "original_text": original,
        "proposed_text": proposed,
        "rationale": f"Repair {finding_id}",
        "fact_ids": [finding_id],
        "evidence_source_ids": ["SRC1"],
        "origin": "test",
    }


class RepairCompositionTests(unittest.TestCase):
    def test_non_overlapping_edits_share_one_section_patch(self):
        original = "No water is allowed. Final sample at 32 hours."
        proposals = [
            proposal("P1", "F1", original, original.replace("No water", "Only water")),
            proposal("P2", "F2", original, original.replace("32 hours", "36 hours")),
        ]
        composed, conflicts = compose_repair_proposals(proposals)
        self.assertFalse(conflicts)
        self.assertEqual(1, len(composed))
        self.assertEqual(
            "Only water is allowed. Final sample at 36 hours.",
            composed[0]["proposed_text"],
        )
        self.assertEqual(["F1", "F2"], composed[0]["finding_ids"])
        self.assertEqual(2, len(composed[0]["edit_operations"]))

    def test_overlapping_edits_are_not_silently_merged(self):
        original = "Final sample at 32 hours."
        proposals = [
            proposal("P1", "F1", original, original.replace("32", "36")),
            proposal("P2", "F2", original, original.replace("32", "40")),
        ]
        composed, conflicts = compose_repair_proposals(proposals)
        self.assertFalse(composed)
        self.assertEqual(1, len(conflicts))
        self.assertEqual(["F1", "F2"], conflicts[0]["finding_ids"])


if __name__ == "__main__":
    unittest.main()
