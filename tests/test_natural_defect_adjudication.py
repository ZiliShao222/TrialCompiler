import json
from pathlib import Path

from scripts.build_natural_defect_adjudication_set import select


def test_adjudication_set_is_real_evidence_and_not_premature_gold():
    path = Path(
        "benchmarks/trialdocbench/public_corpus_050/adjudication/diverse_review_set.jsonl"
    )
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(items) >= 100
    assert len({item["case_id"] for item in items}) >= 45
    assert len({item["category"] for item in items}) >= 6
    assert all(item["page"] > 0 and item["excerpt"] for item in items)
    assert all(item["label_status"] == "candidate_not_gold" for item in items)
    assert all(item["adjudication"]["label"] is None for item in items)
    assert all(len(item["candidate_digest"]) == 64 for item in items)


def test_selector_keeps_one_candidate_per_case_category():
    base = {
        "case_id": "NCT00000001",
        "category": "missing_data",
        "excerpt": "Missing data will be reviewed.",
        "candidate_id": "one",
    }
    selected = select([base, {**base, "candidate_id": "two", "excerpt": "Missing data."}])
    assert len(selected) == 1
