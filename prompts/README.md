# Prompt Contracts

Prompt text is kept outside Python source code. Implemented groups:

```text
agents/   A-F role contracts for context, evidence, repair, quality, reporting, and experience
memory/   semantic-equivalence and memory-promotion contracts
system/   shared operating, evidence, safety, and escalation rules
```

Each prompt must define structured input and output contracts and must be covered
by a fixture or benchmark before material changes are accepted. The deterministic
MVP mirrors these contracts in code; model-backed execution must load these files
rather than embedding prompt prose in Python.
