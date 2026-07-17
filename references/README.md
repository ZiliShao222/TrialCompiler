# References

The canonical source register is generated under `references/catalog/`.
Use `references/catalog/SOURCE_REGISTER.md` for human review and competition
report citations, and `references/catalog/sources.jsonl` for downstream code.

`references/inbox/` is an immutable landing area for downloaded source files.
Do not infer authority from a file being present in the inbox: authority,
evidence tier, permitted use, aliases, and source URLs are governed by the
canonical catalog.

Maintain literature and official-source metadata here. Prefer DOI, publisher,
regulator, or standards-body links. Store full text only when licensing permits.

## Public Source Collection

- [`metadata/public_source_index.tsv`](metadata/public_source_index.tsv): main
  machine-readable index for public sources collected for TrialCompiler.
- [`metadata/public_source_download_status.csv`](metadata/public_source_download_status.csv):
  local snapshot availability and file sizes.
- [`metadata/public_source_category_summary.tsv`](metadata/public_source_category_summary.tsv):
  category-level count and primary-use summary for the public source library.
- [`metadata/trial_fact_field_dictionary.tsv`](metadata/trial_fact_field_dictionary.tsv):
  candidate Trial Fact Sheet fields, expected data types, impacted document
  units, risk level, confirmation roles, and source support.
- [`metadata/document_unit_catalog.tsv`](metadata/document_unit_catalog.tsv):
  protocol, SAP, ICF, registry, CSR, and generated review-report units that can
  be connected in the Clinical Document Graph.
- [`metadata/document_unit_test_catalog.tsv`](metadata/document_unit_test_catalog.tsv):
  candidate compile-style tests such as endpoint consistency, stale-value scan,
  eligibility threshold consistency, and change-impact completeness.
- [`metadata/source_to_module_map.tsv`](metadata/source_to_module_map.tsv):
  mapping from public sources to TrialCompiler modules.
- [`metadata/competitor_capability_matrix.tsv`](metadata/competitor_capability_matrix.tsv):
  official-source-based competitor and baseline comparison matrix.
- [`metadata/trialdocbench_metric_catalog.tsv`](metadata/trialdocbench_metric_catalog.tsv):
  proposed evaluation metrics for the synthetic TrialDocBench benchmark,
  including fact extraction, conflict detection, stale-value scan, impact
  recall, over-edit control, task closure, audit trace completeness, rule-scope
  errors, and experience-reuse precision.
- [`metadata/trialdocbench_synthetic_case_schema.tsv`](metadata/trialdocbench_synthetic_case_schema.tsv):
  schema for synthetic benchmark case packages, covering case profiles, gold
  Trial Fact Sheet rows, document-graph edges, injected defects, change
  requests, and expected impact matrices.
- [`notes/public_source_collection_20260717.md`](notes/public_source_collection_20260717.md):
  human-readable summary, source-to-module mapping, and remaining gaps.
- [`notes/competitor_public_evidence_notes_20260717.md`](notes/competitor_public_evidence_notes_20260717.md):
  public-source evidence notes for competitor positioning and claims that still
  require manual verification.

Current collection scope:

- public regulatory guidance and clinical protocol templates;
- public associated-document templates and definitions, including SAP, ICF,
  registry fields, CSR, and protocol templates;
- public standards such as ICH M11, SPIRIT, TransCelerate, CDISC, and NIH;
- public competitor or alternative product pages;
- public AI governance sources for health and medicinal-product development;
- public AI protocol-authoring and semantic consistency assessment papers or
  industry references.

Do not place real clinical project files, patient data, enterprise internal SOPs,
private comments, emails, or meeting records in this folder.
