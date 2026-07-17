import csv
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "references" / "catalog"


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


class ReferenceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = [
            json.loads(line)
            for line in (CATALOG / "sources.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_catalog_has_unique_ids_and_urls(self) -> None:
        ids = [record["source_id"] for record in self.records]
        urls = [
            normalize_url(record["source_url"]) for record in self.records if record["source_url"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))

    def test_every_record_has_a_name_tier_and_permitted_use(self) -> None:
        for record in self.records:
            self.assertTrue(record["title"], record["source_id"])
            self.assertIn(record["evidence_tier"], {"A", "B", "C", "D", "INTERNAL"})
            self.assertTrue(record["intended_use"], record["source_id"])

    def test_all_catalogued_local_paths_exist(self) -> None:
        missing = [
            path
            for record in self.records
            for path in record["local_paths"]
            if not (REPO_ROOT / path).is_file()
        ]
        self.assertEqual([], missing)

    def test_internal_material_is_not_regulatory_evidence(self) -> None:
        internal = [record for record in self.records if record["evidence_tier"] == "INTERNAL"]
        self.assertTrue(internal)
        for record in internal:
            self.assertEqual("project", record["authority_level"])
            self.assertEqual("08_internal_project_materials", record["collection"])

    def test_minimum_expected_coverage(self) -> None:
        self.assertGreaterEqual(len(self.records), 200)
        self.assertTrue(any(record["source_id"] == "MED-001" for record in self.records))
        self.assertTrue(any("M1-08" in record["aliases"] for record in self.records))

    def test_confirmed_snapshot_mismatches_are_metadata_only(self) -> None:
        by_id = {record["source_id"]: record for record in self.records}
        for source_id in {"ADOC-013", "ADOC-014", "M3-01", "M3-02"}:
            self.assertEqual("metadata_only", by_id[source_id]["lifecycle_status"])
            self.assertEqual("local_snapshot_mismatch", by_id[source_id]["access_status"])

    def test_business_research_evidence_is_gated(self) -> None:
        register = REPO_ROOT / "references/metadata/business_research_evidence.tsv"
        with register.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(60, len(rows))
        social = [row for row in rows if row["source_group"] == "social_media_candidate"]
        self.assertEqual(55, len(social))
        self.assertTrue(all(row["verification_status"] == "unverified_candidate" for row in social))


if __name__ == "__main__":
    unittest.main()
