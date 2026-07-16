# TrialCompiler

TrialCompiler is an early-stage research and product prototype for compiling,
reviewing, validating, and reusing expert knowledge from long-form clinical
trial documents.

The project starts from one concrete problem in the 2026 AI for Future Talent
competition: clinical trial protocols and reports can span hundreds of pages,
require repeated expert review, and leave valuable review experience scattered
across documents and messages.

The intended system turns static documents into structured, testable clinical
document graphs. It then uses evidence-grounded agents to draft, review, repair,
and report changes while keeping qualified humans in control.

## Current Status

This repository currently contains the initial project structure and the Chinese
competition solution description. No clinical production use is supported yet.

## Design Principles

- Treat the clinical document as a structured dependency graph, not one prompt.
- Keep regulatory knowledge, enterprise knowledge, project facts, and learned
  experience in separate layers.
- Require traceable evidence for high-risk claims and review findings.
- Preserve every AI action, human decision, and document version in an audit log.
- Use human approval as the source of truth for reusable organizational memory.
- Evaluate the system with reproducible benchmarks and ablation studies.

## Repository Layout

```text
apps/                    User-facing API and web applications
benchmarks/              TrialDocBench task definitions and dataset cards
config/                  Versioned, non-secret runtime configuration examples
data/                    Local and benchmark data lifecycle documentation
docs/                    Product, architecture, decisions, and research documents
knowledge/               Regulatory, enterprise, project, and experience assets
outputs/                 Generated runs and reports; ignored by Git by default
prompts/                 Agent, system, and memory prompt contracts
references/              Literature and official-source metadata
schemas/                 JSON Schemas and structured document contracts
scripts/                 Reproducible ingestion, evaluation, and maintenance tools
src/trialcompiler/       Python implementation
tests/                   Unit, integration, workflow, and benchmark tests
```

The first product proposal is in
[`docs/competition_solution_zh.md`](docs/competition_solution_zh.md).
