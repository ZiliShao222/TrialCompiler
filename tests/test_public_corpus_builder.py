import hashlib

from pypdf import PdfReader, PdfWriter

from scripts.build_public_protocol_sap_corpus import (
    candidate_documents,
    canonical_json_sha256,
    document_url,
    pdf_role_signals,
    sha256,
)


def test_canonical_json_digest_ignores_key_order_and_formatting():
    left = {"b": [2, 3], "a": "trial"}
    right = {"a": "trial", "b": [2, 3]}
    assert canonical_json_sha256(left) == canonical_json_sha256(right)


def test_candidate_selection_prefers_smallest_protocol_and_sap():
    study = {
        "documentSection": {
            "largeDocumentModule": {
                "largeDocs": [
                    {"filename": "large-prot.pdf", "hasProtocol": True, "size": 900},
                    {"filename": "small-prot.pdf", "hasProtocol": True, "size": 100},
                    {"filename": "sap.pdf", "hasSap": True, "size": 200},
                ]
            }
        }
    }
    protocol, sap = candidate_documents(study)
    assert protocol["filename"] == "small-prot.pdf"
    assert sap["filename"] == "sap.pdf"


def test_combined_protocol_sap_document_can_fill_both_roles():
    combined = {"filename": "Prot_SAP.pdf", "hasProtocol": True, "hasSap": True}
    selected = candidate_documents(
        {"documentSection": {"largeDocumentModule": {"largeDocs": [combined]}}}
    )
    assert selected == (combined, combined)


def test_cdn_url_uses_nct_suffix_and_url_quotes_filename():
    assert document_url("NCT01234567", "Prot SAP 001.pdf") == (
        "https://cdn.clinicaltrials.gov/large-docs/67/"
        "NCT01234567/Prot%20SAP%20001.pdf"
    )


def test_file_digest_matches_sha256(tmp_path):
    path = tmp_path / "item.bin"
    path.write_bytes(b"trialcompiler")
    assert sha256(path) == hashlib.sha256(b"trialcompiler").hexdigest().upper()


def test_pdf_role_signals_extract_actual_content(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as handle:
        writer.write(handle)
    assert pdf_role_signals(PdfReader(path)) == {
        "protocol": False,
        "sap": False,
        "extracted_chars": 0,
        "sampled_pages": 1,
    }
