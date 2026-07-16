# Data Lifecycle

```text
raw/        immutable local source files; ignored by Git
interim/    parsed and partially normalized artifacts; ignored by Git
processed/  model-ready local datasets; ignored by Git
fixtures/   small, synthetic, or authorized test examples
```

No identifiable clinical participant data should be committed to this
repository. Every shared dataset must have provenance, license, de-identification,
and split documentation.

\n