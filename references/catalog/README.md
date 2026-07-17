# Canonical Reference Catalog

This directory is the single logical register for TrialCompiler evidence.
Original downloads remain under `references/inbox/`; internal team attachments
remain under `docs/attachments/`. Do not manually edit generated catalog files.

Regenerate the catalog with:

```powershell
python scripts/build_reference_catalog.py
```

Generated outputs:

- `SOURCE_REGISTER.md`: human-readable source register for competition reports.
- `source_register.csv`: spreadsheet-ready canonical register.
- `sources.jsonl`: machine-readable source-of-truth for later knowledge ingestion.
- `source_aliases.csv`: duplicate IDs reconciled to canonical IDs.
- `duplicate_files_to_review.csv`: identical local bytes that require manual
  review and are not automatically treated as the same source.
- `catalog_summary.json`: coverage and evidence-tier statistics.
- `collections/`: lightweight logical collection indexes; files are not copied.

Evidence tiers are intentionally strict:

- `A`: official regulators, formal guidelines, or standards bodies.
- `B`: public institutional templates, registries, or industry standards.
- `C`: peer-reviewed/open research and technical methods.
- `D`: vendors, market pages, and industry commentary.
- `INTERNAL`: team-produced material that is not external evidence.
