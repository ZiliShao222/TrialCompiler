# Prompt Contracts

Prompt text is kept outside Python source code. Planned groups:

```text
agents/   role-specific contracts for context, retrieval, writing, review, and reporting
memory/   experience extraction and memory promotion contracts
system/   shared operating, evidence, safety, and escalation rules
```

Each prompt must define structured input and output contracts and must be covered
by a fixture or benchmark before material changes are accepted.

