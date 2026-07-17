# TrialDocBench Public Case 001: NCT04683926

## Case identity

- Registry: `NCT04683926`
- Protocol: `OMNI-PAIN-103`
- Phase: Phase 1
- Design: randomized, open-label, four-treatment, four-period, four-sequence crossover
- Investigational product: desmetramadol
- Data boundary: public study-level documents and explicitly labelled synthetic changes only

This case is the first public-document benchmark for TrialCompiler. It uses the official
Protocol, SAP, ICF, and ClinicalTrials.gov registry record. It contains no participant-level
records.

## Why this case is useful

The document set contains several different reasoning tasks rather than a single string-match
problem:

1. a genuine operational-instruction contradiction about water restriction;
2. a numeric-boundary difference around the dosing interval;
3. source-specific duration and screening-window descriptions that require expert adjudication;
4. two valid but different time-axis models between Protocol and CRF/SAP;
5. planned, target, and actual enrollment values that must not be collapsed into a conflict;
6. a synthetic 32 h -> 36 h PK sampling change for impact propagation testing.

## Important gold-label corrections

The submitted package was checked against the official PDFs. The reviewed gold set intentionally
does **not** treat every difference as a hard conflict:

- `11 days` versus `about 12 days` is a duration-definition/counting difference requiring human
  adjudication.
- `<=30 days` versus `up to 31 days` is an inclusive-boundary/participant-language difference.
- Protocol `evaluable` and SAP `Safety/PP` populations must be interpreted in light of the SAP's
  stated safety-only scope.
- Protocol continuous study days and CRF period-specific Day 1 values are a valid mapping, not an
  error.

## Contents

- `public_sources/`: official downloadable documents and registry JSON.
- `source_manifest.tsv`: provenance and allowed use of each source.
- `gold/trial_fact_sheet_gold.tsv`: 27 reviewed study-level facts.
- `gold/gold_tests.json`: reviewed labels and required system behavior.
- `gold/submitted_ground_truth_original.json`: original submitted machine-readable labels,
  retained for audit comparison.
- `synthetic_changes/pk_32h_to_36h.md`: explicitly synthetic change request.

## Current implementation boundary

The current deterministic MVP only has a dedicated rule for approved study-week conflicts. This
case therefore defines the next benchmark target; merely loading the files does not mean the
current agent already passes the tests. Benchmark scores must be reported only after prediction
outputs are evaluated against `gold/gold_tests.json`.

