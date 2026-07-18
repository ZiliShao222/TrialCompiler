import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "trialdocbench"
CASES = ("public_case_002_nct03232983", "public_case_003_nct03117738")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def test_public_benchmark_sources_match_manifests() -> None:
    for case_name in CASES:
        case = ROOT / case_name
        with (case / "source_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        assert rows
        for row in rows:
            source = case / row["local_path"]
            assert source.is_file(), source
            assert _sha256(source) == row["sha256"], source
            assert row["official_url"].startswith("https://")
            assert row["status"] == "public_official"


def test_public_benchmark_gold_is_traceable_and_has_negative_controls() -> None:
    for case_name in CASES:
        case = ROOT / case_name
        gold = json.loads((case / "gold" / "gold_tests.json").read_text(encoding="utf-8"))
        source_ids = {
            row["source_id"]
            for row in csv.DictReader(
                (case / "source_manifest.tsv").read_text(encoding="utf-8").splitlines(),
                delimiter="\t",
            )
        }
        assert gold["tests"]
        assert any(
            test["expected_action"] == "do_not_report_as_conflict"
            for test in gold["tests"]
        )
        for test in gold["tests"]:
            assert test["gold_statement"]
            assert test["evidence"]
            assert all(item["source_id"] in source_ids for item in test["evidence"])


def test_public_benchmark_runtime_fixtures_load() -> None:
    from trialcompiler.demo import load_document

    fixture_root = Path(__file__).resolve().parents[1] / "data" / "fixtures"
    for filename, project_id in (
        ("nct03232983_public_case.json", "NCT03232983"),
        ("nct03117738_public_case.json", "NCT03117738"),
    ):
        document = load_document(fixture_root / filename)
        assert document.project_id == project_id
        assert len(document.sources) >= 3
        assert len(document.facts) >= 6
        assert len(document.sections) >= 7


def test_nct_identifier_conflict_is_deterministic() -> None:
    from trialcompiler.demo import load_document
    from trialcompiler.documents import ClinicalDocumentGraph

    fixture = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "fixtures"
        / "nct03232983_public_case.json"
    )
    findings = ClinicalDocumentGraph(load_document(fixture)).review()
    assert any(
        finding.finding_type == "canonical_trial_identifier_conflict"
        and finding.section_ids == ["PROT-COVER"]
        for finding in findings
    )


def test_nct04683926_boundary_trace_and_valid_time_axis_are_deterministic() -> None:
    from trialcompiler.demo import load_document
    from trialcompiler.documents import ClinicalDocumentGraph

    fixture = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "fixtures"
        / "nct04683926_public_case.json"
    )
    document = load_document(fixture)
    findings = ClinicalDocumentGraph(document).review()
    finding_ids = {finding.finding_id for finding in findings}
    assert "numeric-boundary-dose-interval-F005-F007" in finding_ids
    assert "cross-source-review-F008" in finding_ids
    assert "cross-source-review-F009" in finding_ids
    assert "traceability-complete-fact-register" in finding_ids
    assert not any(finding.finding_type == "time_axis_inconsistency" for finding in findings)
