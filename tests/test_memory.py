import tempfile
import unittest
from pathlib import Path

from trialcompiler.memory import RetrievalQuery, SemanticElement, SemanticElementStore


class SemanticMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = SemanticElementStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_only_approved_and_in_scope_memory_is_admitted(self) -> None:
        approved = SemanticElement(
            element_id="approved",
            namespace="approved_experience",
            semantic_key="canonical_fact_conflict",
            value={"recommendation": "propagate approved fact"},
            element_type="decision_capsule",
            document_type="protocol",
            jurisdiction="CN",
            approval_status="approved",
            authority="human_review",
            tags=["canonical_fact_conflict"],
        )
        draft = SemanticElement(
            element_id="draft",
            namespace="approved_experience",
            semantic_key="canonical_fact_conflict",
            value={"recommendation": "unreviewed suggestion"},
            element_type="decision_capsule",
            document_type="protocol",
            jurisdiction="CN",
            approval_status="draft",
            tags=["canonical_fact_conflict"],
        )
        self.store.upsert(approved)
        self.store.upsert(draft)
        hits = self.store.retrieve(
            RetrievalQuery(
                text="canonical_fact_conflict",
                namespace="approved_experience",
                element_types=["decision_capsule"],
                document_type="protocol",
                jurisdiction="CN",
            )
        )
        self.assertEqual(["approved"], [hit.element.element_id for hit in hits])

    def test_expired_memory_is_rejected(self) -> None:
        self.store.upsert(
            SemanticElement(
                element_id="expired",
                namespace="approved_experience",
                semantic_key="canonical_fact_conflict",
                value={"recommendation": "old"},
                element_type="decision_capsule",
                approval_status="approved",
                valid_until="2020-01-01T00:00:00+00:00",
            )
        )
        hits = self.store.retrieve(
            RetrievalQuery(
                text="canonical_fact_conflict",
                namespace="approved_experience",
            )
        )
        self.assertEqual([], hits)

    def test_lcfu_eviction_keeps_high_authority_approved_element(self) -> None:
        self.store.upsert(
            SemanticElement(
                element_id="regulatory",
                namespace="knowledge",
                semantic_key="approved guideline",
                value={"text": "authority"},
                element_type="evidence",
                authority="regulatory",
                approval_status="approved",
            )
        )
        self.store.upsert(
            SemanticElement(
                element_id="generated",
                namespace="knowledge",
                semantic_key="temporary model note",
                value={"text": "temporary"},
                element_type="note",
                authority="generated",
                approval_status="draft",
            )
        )
        removed = self.store.evict(1)
        self.assertEqual(["generated"], removed)
        self.assertIsNotNone(self.store.get("regulatory"))


if __name__ == "__main__":
    unittest.main()
