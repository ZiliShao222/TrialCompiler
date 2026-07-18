# TrialDocBench

This directory will define reproducible tasks, dataset cards, splits, baselines,
metrics, and ablation protocols for:

1. clinical fact extraction;
2. document defect detection;
3. change-impact analysis;
4. repair quality and experience transfer.

Large or restricted datasets do not belong here. Store only manifests, schemas,
small public fixtures, and evaluation specifications in Git.

## Synthetic Cases

- [`trialdocbench/synthetic_case_001_week12_to_week16`](trialdocbench/synthetic_case_001_week12_to_week16):
  first minimal synthetic package for the `Week 12 -> Week 16` endpoint
  assessment change demo. It includes a gold Trial Fact Sheet, document units,
  document graph, injected defects, change request, expected impact matrix, and
  evaluation notes.

## Public-document Cases

- [`trialdocbench/public_corpus_050`](trialdocbench/public_corpus_050): frozen integrity corpus of
  50 real public ClinicalTrials.gov studies with both Protocol and SAP coverage, 65 validated PDF
  documents, official registry snapshots, SHA-256 manifests, acquisition-cost contracts, and a
  deterministic coverage profile. These cases are not yet independently gold-annotated and must
  not be used for model-accuracy or six-arm effect-size claims.

- [`trialdocbench/public_case_001_nct04683926`](trialdocbench/public_case_001_nct04683926):
  official Protocol, SAP, ICF, and registry data for `NCT04683926 / OMNI-PAIN-103`,
  with a reviewed 27-fact gold sheet and scope-aware consistency labels. Public
  documents are study-level; the case contains no participant-level records.
