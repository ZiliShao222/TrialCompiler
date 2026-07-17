import unittest

from trialcompiler.llm import govern_semantic_repairs, govern_semantic_review


class SemanticReviewGovernanceTests(unittest.TestCase):
    def test_repair_governance_requires_exact_original_text_and_known_ids(self) -> None:
        result = {
            "repair_proposals": [
                {
                    "finding_id": "semantic-001",
                    "section_id": "S-1",
                    "original_text": "Original text.",
                    "proposed_text": "Revised text.",
                    "rationale": "Clarify the supplied conflict.",
                    "fact_ids": ["F-1", "F-UNKNOWN"],
                    "source_ids": ["SRC-1"],
                },
                {
                    "finding_id": "semantic-001",
                    "section_id": "S-2",
                    "original_text": "Invented text.",
                    "proposed_text": "Other text.",
                    "fact_ids": [],
                    "source_ids": [],
                },
            ],
            "limitations": [],
        }
        governed, warnings = govern_semantic_repairs(
            result,
            findings=[{"finding_id": "semantic-001"}],
            section_texts={"S-1": "Original text.", "S-2": "Actual text."},
            fact_ids={"F-1"},
            source_ids={"SRC-1"},
        )
        self.assertEqual(1, len(governed["proposals"]))
        self.assertEqual(["F-1"], governed["proposals"][0]["fact_ids"])
        self.assertTrue(any("non-matching original" in warning for warning in warnings))

    def test_scalar_list_fields_are_not_split_into_characters(self) -> None:
        result = {
            "summary": "Review summary",
            "semantic_findings": [],
            "review_questions": "Confirm the timeline?",
            "limitations": "Public documents only.",
        }
        governed, warnings = govern_semantic_review(
            result,
            section_ids=set(),
            fact_ids=set(),
            source_ids=set(),
        )
        self.assertEqual(["Confirm the timeline?"], governed["review_questions"])
        self.assertEqual(["Public documents only."], governed["limitations"])
        self.assertTrue(any("Coerced scalar" in warning for warning in warnings))

    def test_removes_unknown_ids_and_absent_document_speculation(self) -> None:
        result = {
            "summary": "Review summary",
            "semantic_findings": [
                {
                    "finding_type": "conflict",
                    "severity": "high",
                    "section_ids": ["S-1", "S-UNKNOWN"],
                    "fact_ids": ["F-1"],
                    "source_ids": ["SRC-UNKNOWN"],
                    "message": "Observed conflict",
                    "requires_human_review": False,
                }
            ],
            "review_questions": ["Does any companion document exist?", "Confirm F-1?"],
            "limitations": ["No companion documents were supplied.", "No patient data."],
        }

        governed, warnings = govern_semantic_review(
            result,
            section_ids={"S-1"},
            fact_ids={"F-1"},
            source_ids={"SRC-1"},
        )

        finding = governed["semantic_findings"][0]
        self.assertEqual(["S-1"], finding["section_ids"])
        self.assertEqual([], finding["source_ids"])
        self.assertTrue(finding["requires_human_review"])
        self.assertEqual(["Confirm F-1?"], governed["review_questions"])
        self.assertEqual(["No patient data."], governed["limitations"])
        self.assertGreaterEqual(len(warnings), 3)


if __name__ == "__main__":
    unittest.main()
