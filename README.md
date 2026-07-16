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

The repository now contains a runnable, review-only MVP for cross-section
consistency review. It represents a trial document as canonical facts, source
references, sections, and dependencies; runs a six-role LangGraph workflow;
retrieves only approved and in-scope experience; proposes minimal redlines; and
produces an auditable report for qualified human review.

The MVP includes a CLI, FastAPI service, synthetic fixtures, a Feishu Aily
intake contract, and automated tests. It does **not** support clinical
production use or real patient data.

## MVP Workflow

```text
Feishu Aily intake
  -> A: context lock
  -> B: evidence + approved experience
  -> C: repair proposals
  -> D: independent quality gate
       -> C when revision is required
       -> E when ready
  -> E: review packet
  -> F: draft experience candidate
  -> qualified human approval (separate governance step)
  -> reusable organizational memory
```

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

## Documentation

- [`docs/detailed_solution_design_zh.md`](docs/detailed_solution_design_zh.md):
  detailed Chinese product, architecture, workflow, data-contract, benchmark,
  safety, MVP, and roadmap design.
- [`docs/competition_solution_zh.md`](docs/competition_solution_zh.md): concise
  Chinese competition proposal covering the overall solution, architecture,
  and core innovations.
- [`docs/repository_structure_zh.md`](docs/repository_structure_zh.md): repository
  ownership boundaries, knowledge layers, and data-management rules.
- [`docs/mvp_implementation_zh.md`](docs/mvp_implementation_zh.md): runnable MVP,
  workflow, demonstration result, and safety boundary.
- [`docs/memory_retrieval_and_experience_reuse_zh.md`](docs/memory_retrieval_and_experience_reuse_zh.md):
  Semantic Element storage, coarse-to-fine retrieval, metadata gates, lifecycle,
  Decision Capsules, and evaluation metrics.
- [`docs/knowledge_base_collection_plan_zh.md`](docs/knowledge_base_collection_plan_zh.md):
  concrete two-week collection plan for the AI, medical, and finance/business
  team members.
- [`docs/feishu_aily_integration_zh.md`](docs/feishu_aily_integration_zh.md): Aily
  clarification and field-extraction workflow before TrialCompiler.

## Quick Start

The current development environment is `D:\miniconda\envs\iGEM`.

```powershell
cd D:\TrialCompiler
$env:PYTHONPATH = "src"

# Reproducible synthetic review
D:\miniconda\envs\iGEM\python.exe -m trialcompiler demo

# Validate the Feishu Aily hand-off contract
D:\miniconda\envs\iGEM\python.exe -m trialcompiler feishu-intake `
  --payload data/fixtures/feishu_aily_intake.json

# Start the API
D:\miniconda\envs\iGEM\python.exe -m uvicorn apps.api.app:app `
  --host 127.0.0.1 --port 8810
```

Open `http://127.0.0.1:8810/docs` for the generated API console. The main
endpoints are:

- `GET /health`
- `POST /api/v1/intake/feishu`
- `POST /api/v1/review`
- `POST /api/v1/memory/search`

## Verification

```powershell
$env:PYTHONPATH = "src"
D:\miniconda\envs\iGEM\python.exe -m unittest discover -s tests -v
```

The synthetic case intentionally sets the approved primary-endpoint assessment
to Week 16 while two dependent sections still say Week 12. The workflow detects
both conflicts, preserves unrelated participant-count text, admits one approved
experience card, produces two source-linked redlines, passes the independent
quality gate, and stores the new experience only as `draft`.

## Safety Boundary

- Every generated repair remains a proposal; no source document is overwritten.
- A quality-gate pass is not medical, regulatory, or ethical approval.
- Draft, expired, or wrong-scope memories are rejected before agent context.
- The current API has no production identity, tenant, or file-access controls.
- Only synthetic data may be used until RBAC, encryption, audit retention,
  qualified electronic approval, and data-governance review are implemented.
