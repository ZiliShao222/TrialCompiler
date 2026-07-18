import csv
import json
from pathlib import Path
from urllib.parse import urlparse

from scripts.build_public_protocol_sap_corpus import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "trialdocbench" / "public_corpus_050"


def load_manifest() -> list[dict[str, str]]:
    with (CORPUS / "corpus_manifest.tsv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_public_corpus_contains_exactly_fifty_unique_real_cases():
    cases = json.loads((CORPUS / "cases.json").read_text(encoding="utf-8"))["cases"]
    nct_ids = [item["nct_id"] for item in cases]
    assert len(cases) == 50
    assert len(set(nct_ids)) == 50
    assert all(nct_id.startswith("NCT") and len(nct_id) == 11 for nct_id in nct_ids)
    assert all(item["tier"] == "T1_protocol_and_sap" for item in cases)


def test_each_case_has_protocol_and_sap_with_validated_pdf_metadata():
    rows = load_manifest()
    roles_by_case: dict[str, set[str]] = {}
    for row in rows:
        roles_by_case.setdefault(row["nct_id"], set()).update(row["roles"].split(";"))
        assert int(row["bytes"]) > 4
        assert int(row["pages"]) > 0
        assert len(row["sha256"]) == 64
        parsed = urlparse(row["official_url"])
        assert parsed.scheme == "https"
        assert parsed.netloc == "cdn.clinicaltrials.gov"
        assert row["protocol_text_signal"] in {"True", "False"}
        assert row["sap_text_signal"] in {"True", "False"}
        assert int(row["sampled_pages"]) > 0
        assert int(row["extracted_chars"]) >= 100
    assert len(roles_by_case) == 50
    assert all({"protocol", "sap"}.issubset(roles) for roles in roles_by_case.values())


def test_frozen_registry_snapshots_match_manifest_and_nct_identity():
    rows = load_manifest()
    first_row_by_case = {row["nct_id"]: row for row in rows}
    assert len(first_row_by_case) == 50
    assert len(list((CORPUS / "registry").glob("NCT*.json"))) == 50
    assert len(list((CORPUS / "case_contracts").glob("NCT*.json"))) == 50
    for nct_id, row in first_row_by_case.items():
        registry = CORPUS / row["registry_path"]
        assert registry.exists()
        payload = json.loads(registry.read_text(encoding="utf-8"))
        assert canonical_json_sha256(payload) == row["registry_sha256"]
        observed = payload["protocolSection"]["identificationModule"]["nctId"]
        assert observed == nct_id
        contract = CORPUS / row["case_contract_path"]
        assert contract.exists()
        case = json.loads(contract.read_text(encoding="utf-8"))
        assert canonical_json_sha256(case) == row["case_contract_sha256"]
        assert case["case_id"] == nct_id
        assert case["source_class"] == "real_public_clinicaltrials_gov"
        assert case["gold_status"] == "not_annotated"
        assert case["available_actions"]


def test_build_report_has_integrity_only_claim_boundary():
    report = json.loads((CORPUS / "build_report.json").read_text(encoding="utf-8"))
    assert report["validated_case_count"] == 50
    assert report["document_count"] >= 50
    assert report["content_audit"]["extractable_document_count"] == report["document_count"]
    assert report["content_audit"]["keyword_signals_are"] == (
        "auxiliary_audit_not_role_ground_truth"
    )
    assert report["claim_boundary"] == "public_source_integrity_not_model_performance"
