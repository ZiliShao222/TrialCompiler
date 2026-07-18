from scripts.profile_public_protocol_sap_corpus import profile


def test_profile_reports_coverage_and_preserves_claim_boundary():
    from pathlib import Path

    corpus = Path("benchmarks/trialdocbench/public_corpus_050")
    result = profile(corpus)
    assert result["case_count"] == 50
    assert sum(result["document_layouts"].values()) == 50
    assert result["action_page_cost"]["min"] > 0
    assert result["action_page_cost"]["max"] >= result["action_page_cost"]["median"]
    assert "model accuracy claims" in result["interpretation"]["not_yet_usable_for"]
