import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "benchmarks" / "trialdocbench" / "public_case_001_nct04683926"


class NCT04683926BenchmarkIntegrityTests(unittest.TestCase):
    def test_manifest_sources_exist_and_are_explicitly_scoped(self) -> None:
        with (CASE_ROOT / "source_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(5, len(rows))
        self.assertEqual(
            {"SRC-REG", "SRC-PROT", "SRC-SAP", "SRC-ICF", "SRC-MUT"},
            {row["source_id"] for row in rows},
        )
        for row in rows:
            self.assertTrue((CASE_ROOT / row["local_path"]).is_file())
            self.assertIn(row["status"], {"verified_public", "synthetic_only"})

    def test_reviewed_fact_sheet_contains_27_traceable_facts(self) -> None:
        with (CASE_ROOT / "gold" / "trial_fact_sheet_gold.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(27, len(rows))
        self.assertEqual(27, len({row["fact_id"] for row in rows}))
        for row in rows:
            self.assertTrue(row["source_ids"])
            self.assertTrue(row["source_locator"])
            self.assertTrue(row["status"])

    def test_gold_distinguishes_conflicts_from_valid_mappings(self) -> None:
        payload = json.loads((CASE_ROOT / "gold" / "gold_tests.json").read_text(encoding="utf-8"))
        tests = {item["id"]: item for item in payload["tests"]}

        self.assertEqual(
            "hard_operational_instruction_conflict",
            tests["TC-SD-001"]["expected_label"],
        )
        self.assertTrue(tests["TC-SD-001"]["must_not_auto_resolve"])
        self.assertEqual(
            "valid_dual_time_axis_mapping",
            tests["TC-XD-003"]["expected_label"],
        )
        self.assertTrue(tests["TC-XD-003"]["must_not_report_as_conflict"])
        self.assertEqual(
            "planned_target_actual_state_difference",
            tests["TC-VS-001"]["expected_label"],
        )
        self.assertTrue(tests["TC-VS-001"]["must_not_report_as_conflict"])

    def test_synthetic_change_is_never_presented_as_real_amendment(self) -> None:
        payload = json.loads((CASE_ROOT / "gold" / "gold_tests.json").read_text(encoding="utf-8"))
        change = next(item for item in payload["tests"] if item["id"] == "TC-MUT-001")

        self.assertEqual("32 h", change["old_value"])
        self.assertEqual("36 h", change["new_value"])
        self.assertTrue(change["must_preserve_original_version"])
        self.assertTrue(change["must_require_human_approval"])


if __name__ == "__main__":
    unittest.main()
