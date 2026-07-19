# Natural-defect adjudication queue

`diverse_review_set.jsonl` is a case-balanced set of short excerpts mined from the actual 65 public
PDFs. Each item includes the real NCT ID, filename, page, evidence fields, excerpt, digest, and the
qualified role required for adjudication. It is deliberately **not** named gold: empty adjudication
fields must be completed and independently reviewed before an item can enter a natural-defect gold
set.

Allowed labels are `confirmed_defect`, `legitimate_difference`, `insufficient_evidence`, and
`out_of_scope_reference`. A confirmed defect requires at least two scope-matched sources, an
explicit semantic relation, a rationale, an adjudicator role, and second review. Planned-versus-
actual enrollment, total-versus-subgroup counts, related-study NCT IDs, and descriptive mentions of
missing data or multiplicity must not be promoted to conflicts merely because values or keywords
differ.

The complete high-recall mining output remains under ignored local data because it contains many
duplicate excerpts. The repository stores the balanced review set, not a large unreviewed text dump.
