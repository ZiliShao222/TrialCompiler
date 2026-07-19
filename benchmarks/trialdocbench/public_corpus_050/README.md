# TrialDocBench public Protocol+SAP corpus (50 cases)

This corpus freezes 50 real public ClinicalTrials.gov studies for TrialCompiler development.
Every admitted case has an official registry snapshot and provider-uploaded document metadata
covering both a study protocol and a statistical analysis plan. Documents are downloaded to an
ignored local cache during integrity validation; the repository stores official URLs, byte sizes,
page counts, SHA-256 digests, registry snapshots, and machine-readable case contracts.

## What this corpus proves

The build proves that 50 distinct public cases and their selected documents were retrievable,
parseable as non-empty PDFs, scope-identifiable, and digest-frozen at build time. It does **not**
prove TrialCompiler accuracy. Case contracts deliberately use `gold_status=not_annotated` until
independent findings and patch-validity labels are produced without test leakage.

## Files

- `corpus_manifest.tsv`: one row per selected document, including official URL, pages, bytes,
  document SHA-256, registry path/digest, and case-contract path/digest.
- `cases.json`: the frozen 50-case index.
- `case_contracts/`: available observations and cost units for future active-acquisition runs.
- `registry/`: official ClinicalTrials.gov API snapshots.
- `build_report.json`: discovery query, admitted counts, rejected candidates, and claim boundary.
- `corpus_profile.json`: deterministic coverage profile for study type, phase, status,
  combined/separate documents, acquisition page cost, and missing registry fields.
- `gold/document_role_labels.jsonl`: 130 official-metadata gold labels for Protocol/SAP roles,
  grouped into 30/10/10 train/calibration/test cases without case leakage.
- `gold/role_baseline_results.json`: text, filename, and hybrid baseline metrics with Wilson 95%
  intervals, including held-out test results.
- `gold/seeded_defect_labels.jsonl`: 200 balanced defect labels derived from 50 frozen real
  cases—one identifier conflict, one enrollment-propagation defect, and matched negative controls
  per case.
- `gold/seeded_defect_results.json`: TrialCompiler deterministic detector results on the grouped
  30/10/10 split, with Wilson 95% intervals and a controlled-defect claim boundary.
- `adjudication/diverse_review_set.jsonl`: 197 case-balanced candidates mined from actual PDF
  pages across eight semantic categories. These remain explicitly non-gold until independent
  adjudication; the complete 1,393-candidate high-recall dump stays in ignored local data.

## Frozen profile (2026-07-19)

The admitted set contains 48 interventional and 2 observational studies. It includes 35 cases
with one combined Protocol/SAP and 15 with separate documents. The 65 selected PDFs total 3,025
pages; per-document acquisition cost ranges from 1 to 241 pages (median 33, p90 99). All 50
contracts contain enrollment and primary-outcome registry fields. One additional candidate was
rejected because its PDF had insufficient extractable text.

All 65 admitted PDFs have at least 100 extracted characters. Keyword auditing found a Protocol
signal in 59 and an SAP signal in 48. These signals are diagnostics, not role ground truth:
ClinicalTrials.gov's `hasProtocol` and `hasSap` document metadata define eligibility, because a
fixed English keyword list creates false negatives for combined documents and image-layer titles.

## Rebuild and validate

```powershell
python scripts/build_public_protocol_sap_corpus.py --limit 50 --workers 8
python scripts/profile_public_protocol_sap_corpus.py
python scripts/build_and_score_public_role_gold.py
python -m scripts.build_and_score_seeded_defect_gold
python scripts/mine_public_natural_defect_candidates.py
python scripts/build_natural_defect_adjudication_set.py
python -m pytest tests/test_public_corpus_050.py tests/test_public_corpus_profile.py -q
```

ClinicalTrials.gov is a living registry, so a later rebuild may retrieve changed snapshots or
documents. Do not silently overwrite an experiment corpus after labels or test results exist;
create a new version and preserve both digests.
