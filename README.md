# TrialCompiler

## Research thesis: uncertainty-guided evidence acquisition

TrialCompiler is not a workflow product with an LLM attached. Its central AI
question is: **how can a probabilistic model reason actively over incomplete and
conflicting clinical documents while making its uncertainty inspectable and
preventing fluency from becoming authority?**

The research target is not a free-form confidence label. TrialCompiler models a
document-review run as an action-observation trajectory: the latent state is the
canonical fact that should govern a document set; protocols, SAPs, consent
forms, registries, tools and reviewers provide heterogeneous observations. The
agent must decide whether to acquire another observation, deliberate, abstain,
defer, or submit a candidate patch. We distinguish reducible epistemic
uncertainty from irreducible environmental stochasticity, and distinguish where
uncertainty resides: observation, belief state, action, or trajectory outcome.

Missing evidence and source disagreement are treated as diagnostic signals,
not as canonical uncertainty classes. A numeric score is never called
calibrated unless it names a calibrator, target event and calibration dataset.

The compilation plane checks provenance, minimum edit scope, cross-artifact
invariants, sandbox regressions, negative controls, unresolved decision debt,
and qualified-human release gates. An AI result is useful only when it arrives
as a falsifiable claim with evidence and a testable patch. If it cannot prove a
unique safe revision, the uncertainty becomes an explicit decision request.
Thus the graph, rules, state machine and audit trail are the safety substrate;
the research question is whether uncertainty-guided evidence acquisition can
improve selective patch accuracy per unit review cost. Explanations are tested
behaviorally by removing or replacing cited evidence and replaying the decision;
the model's own rationale is not presumed faithful.

TrialCompiler is an early-stage research and product prototype for compiling,
reviewing, testing, and incrementally updating clinical trial protocols and
their related documents.

The project starts from one concrete problem in the 2026 AI for Future Talent
competition: key design facts such as endpoints, assessment timepoints, sample
size, eligibility criteria, visit schedules, and statistical principles are
repeated across protocol sections, tables, and related files. Manual drafting
and revision therefore create long review cycles, stale values, version drift,
and missed downstream changes.

The intended system turns professionally confirmed facts into a versioned Trial
Fact Sheet and maps them to a testable Clinical Document Graph. It uses that
graph to support section drafting, consistency review, and change-impact
analysis while keeping medical, statistical, regulatory, and quality decisions
under qualified human control. Patient-record screening and clinical-data
cleaning are outside the current competition scope.

## Current Status

The repository now contains a runnable, review-only MVP for cross-section
consistency review. It represents a trial document as canonical facts, source
references, sections, and dependencies; runs a six-role LangGraph workflow;
retrieves only approved and in-scope experience; proposes minimal redlines; and
produces an auditable report for qualified human review.

The MVP includes a CLI, FastAPI service, synthetic fixtures, a Feishu Aily
intake contract, and automated tests. It does **not** support clinical
production use or real patient data.

The uncertainty research harness now executes finite-belief evidence updates,
cost-aware expected-information-gain selection, and explicit commit/acquire/defer
stopping decisions. A separate evaluator reports Brier score, ECE,
risk--coverage/AURC, pairwise ranking accuracy, and behavioral counterfactual
faithfulness metrics. The included fixture demonstrates the protocol only; it
is not empirical evidence that a model is calibrated. Run it with:

```powershell
python scripts/evaluate_uncertainty_experiment.py `
  data/fixtures/uncertainty_experiment_demo.json --bins 2
```

The paired six-arm ablation evaluator rejects case leakage, unpaired arm case
sets, digest drift, incomplete arm matrices, and results below a prespecified
minimum case count. Its preregistration-style protocol is documented in
[`docs/research/uncertainty_ablation_protocol_20260719.md`](docs/research/uncertainty_ablation_protocol_20260719.md).

The review API also accepts an optional governed `evidence_acquisition` object.
Only allowlisted action IDs can be fetched; each observation records a source ID,
source version, content SHA-256, cost, posterior, and realized information gain.
Budget exhaustion, duplicate access, and unknown observations fail closed. Even
when the updated belief exceeds its threshold, acquired evidence must re-enter
the B/C/D verification loop before a candidate can be submitted. A synthetic
request fixture is provided at
`data/fixtures/evidence_acquisition_demo.json`.
Raw evidence content is discarded from the final workflow state after its digest
and governed observation record are created.

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
- Keep project facts, regulatory and enterprise constraints, and learned expert
  experience in separate governed layers.
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

For component boundaries, dependency direction, governed data flows, and the
mapping from architecture concepts to implementation modules, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

Repository contribution and security guidance are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md).

## Documentation

- Competition submission set, each document containing a concise form-ready
  version followed by a detailed proposal-ready version:
  - [`docs/competition_01_solution_overview_zh.md`](docs/competition_01_solution_overview_zh.md):
    overall problem, product scope, human workflow, validation boundary, and
    competition demonstration storyline.
  - [`docs/competition_02_architecture_modules_zh.md`](docs/competition_02_architecture_modules_zh.md):
    layered architecture, core modules, A-H active-compilation workflow,
    human quality gates, audit, and MVP roadmap.
  - [`docs/competition_03_core_innovations_zh.md`](docs/competition_03_core_innovations_zh.md):
    technical, operating-model, and process innovations; conventional-solution
    comparison; hypotheses, metrics, baselines, ablations, and originality
    boundaries.
- [`docs/medical_teammate_material_integration_zh.md`](docs/medical_teammate_material_integration_zh.md):
  summary of the medical teammate's source package and how it strengthens the
  Trial Fact Sheet, Clinical Document Graph, unit tests, and change-impact
  analysis.
- [`docs/medical_source_to_system_mapping_zh.md`](docs/medical_source_to_system_mapping_zh.md):
  mapping from the medical source package modules M1-M4 to TrialCompiler system
  modules, plus follow-up questions for medical review.
- [`docs/competitor_analysis_integration_zh.md`](docs/competitor_analysis_integration_zh.md):
  integration notes from the teammate competitor-analysis document, including
  direct competitors, adjacent platforms, realistic substitutes, differentiation
  points, and measurable validation metrics.
- [`docs/attachment_package_review_20260717_zh.md`](docs/attachment_package_review_20260717_zh.md):
  review of the architecture, regulatory-mapping, and attachment-task-list
  deliverables, including current-repository reconciliation and remaining gaps.
- [`docs/business_attachment_review_20260717_zh.md`](docs/business_attachment_review_20260717_zh.md):
  review of the industry analysis, value model, and project risk-control
  attachments, with explicit separation of verified claims, internal parameters,
  POC targets, and unsupported assumptions.
- [`references/metadata/business_claim_validation.tsv`](references/metadata/business_claim_validation.tsv):
  evidence-status register for market, regulatory, productivity, cost, and
  company claims appearing in the business attachments.
- [`references/metadata/value_model_parameter_register.tsv`](references/metadata/value_model_parameter_register.tsv):
  governed parameter register for labor savings, quality benefit, opportunity
  value, implementation cost, and benchmark metrics.
- [`references/metadata/business_risk_control_register.tsv`](references/metadata/business_risk_control_register.tsv):
  structured risk, control, evidence-artifact, and MVP-status register.
- [`references/metadata/regulatory_function_mapping.tsv`](references/metadata/regulatory_function_mapping.tsv):
  machine-readable mapping from clinical standards and governance principles to
  product controls, output evidence, responsibility boundaries, and prototype status.
- [`references/metadata/attachment_task_reconciliation.tsv`](references/metadata/attachment_task_reconciliation.tsv):
  reconciliation of the 14-item attachment plan against the current repository.
- [`references/metadata/trialdocbench_metric_catalog.tsv`](references/metadata/trialdocbench_metric_catalog.tsv):
  structured metric catalog for the proposed synthetic benchmark, covering
  extraction, consistency, change impact, redline quality, task closure, audit,
  rule scope, memory reuse, and local-adaptation dimensions.
- [`docs/trialdocbench_synthetic_case_design_zh.md`](docs/trialdocbench_synthetic_case_design_zh.md):
  synthetic public-source benchmark case-package design for evaluating Trial
  Fact Sheet extraction, document-graph dependencies, injected defects, change
  impact analysis, and redline generation without real clinical or enterprise
  data.
- [`references/metadata/trialdocbench_synthetic_case_schema.tsv`](references/metadata/trialdocbench_synthetic_case_schema.tsv):
  machine-readable schema for synthetic benchmark case packages, including
  case profile, gold facts, document graph, injected defects, change requests,
  and expected impact matrices.
- [`docs/teammate_public_research_tasks_zh.md`](docs/teammate_public_research_tasks_zh.md):
  non-coding public-source verification tasks for medical, business, and Feishu
  teammates, with explicit boundaries against real clinical data or internal
  enterprise documents.
- [`docs/public_source_gap_and_next_steps_zh.md`](docs/public_source_gap_and_next_steps_zh.md):
  current source coverage, stable conclusions, remaining gaps, and recommended
  next public-research tasks.
- [`docs/20260717_evening_handoff_zh.md`](docs/20260717_evening_handoff_zh.md):
  evening handoff checklist summarizing completed source ingestion, competitor
  integration, TrialDocBench assets, and next tasks for medical, business, and
  AI members.
- [`docs/product_definition_zh.md`](docs/product_definition_zh.md): authoritative
  Chinese product scope, problem definition, human workflow, functions, and
  professional responsibility boundary.
- [`docs/technical_innovations_zh.md`](docs/technical_innovations_zh.md):
  technical contributions, borrowed-method boundaries, testable hypotheses,
  implementation status, and evaluation design.
- [`docs/mathematical_technical_analysis_zh.md`](docs/mathematical_technical_analysis_zh.md):
  full mathematical formulation of global goal alignment, hard governance
  constraints, trajectory drift, local module losses, human escalation,
  preference learning, and TrialDocBench evaluation.
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
  non-technical, public-source-only literature search checklist for the medical
  and finance/business team members; real cases and interviews are deferred
  until an authorized validation phase.
- [`docs/data_processing_internal_plan_zh.md`](docs/data_processing_internal_plan_zh.md):
  AI-side plan for deduplication, parsing, normalization, knowledge layering,
  synthetic benchmark construction, and review-table generation.
- [`docs/feishu_aily_integration_zh.md`](docs/feishu_aily_integration_zh.md): Aily
  clarification and field-extraction workflow before TrialCompiler.
- [`references/notes/public_source_collection_20260717.md`](references/notes/public_source_collection_20260717.md):
  public-source collection record, module mapping, and remaining gaps for the
  current competition research phase.

## Quick Start

TrialCompiler requires Python 3.11 or later. Create an isolated environment and
install the package with its development dependencies:

```powershell
git clone https://github.com/ZiliShao222/TrialCompiler.git
cd TrialCompiler
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Build and initialize a reproducible multi-document case
python scripts\build_trialdocbench_fixture.py
python -m trialcompiler init `
  --workspace outputs\workspaces\trialdocbench `
  --document data\fixtures\trialdocbench_case_001.json

# Inspect facts and create a governed candidate change
python -m trialcompiler facts `
  --workspace outputs\workspaces\trialdocbench
python -m trialcompiler change `
  --workspace outputs\workspaces\trialdocbench `
  --fact-id FACT-TIMEPOINT-001 --value 16 `
  --reason "Evaluate a proposed Week 16 primary endpoint"

# Compile deterministic checks plus Qwen semantic review
$env:DASHSCOPE_API_KEY = "<your-key>"
python -m trialcompiler compile `
  --workspace outputs\workspaces\trialdocbench `
  --llm on --llm-model qwen-plus

# Inspect the audit trail. Applying or rejecting a change remains explicit.
python -m trialcompiler audit `
  --workspace outputs\workspaces\trialdocbench

# Alternatively, use the guided terminal workspace.
python -m trialcompiler workspace `
  --workspace outputs\workspaces\guided-demo

# Validate the Feishu Aily hand-off contract
python -m trialcompiler feishu-intake `
  --payload data/fixtures/feishu_aily_intake.json

# Start the API
python -m uvicorn apps.api.app:app `
  --host 127.0.0.1 --port 8810
```

The full CLI command reference and artifact layout are documented in
[`docs/cli_prototype_guide_zh.md`](docs/cli_prototype_guide_zh.md). The web UI is
intentionally deferred until the terminal workflow and governance contract are stable.

### Governed Protocol Generation Benchmark

The generative benchmark uses a strict visibility boundary: Phase 1 and Phase 2
can read only their designated AI-visible folders, while evaluator-only files
are withheld until the generated outputs have been frozen. Keep API credentials
in an external dotenv file; TrialCompiler reads the key without copying the file
or its contents into run artifacts.

```powershell
$env:PYTHONPATH = "src"
$package = "docs\TrialCompiler_Generative_Protocol_Test_Metformin_PAD_v1.0\TrialCompiler_Generative_Protocol_Test_Metformin_PAD"

# Phase 1: evidence matrix, synopsis, questions, and candidate facts
python -m trialcompiler generate-protocol `
  --phase phase1 --package $package `
  --output outputs\metformin_pad_phase1 `
  --llm-model qwen-plus --env-file D:\path\outside-repo\.env.local

# Phase 2: reconcile sponsor/regulatory/site feedback and revise the full package
python -m trialcompiler generate-protocol `
  --phase phase2 --package $package `
  --phase1-run outputs\metformin_pad_phase1\run.json `
  --output outputs\metformin_pad_phase2 `
  --llm-model qwen-plus --env-file D:\path\outside-repo\.env.local

# Blind evaluation: evaluator-only references become visible only here
python -m trialcompiler evaluate-protocol `
  --package $package `
  --phase1-run outputs\metformin_pad_phase1\run.json `
  --phase2-run outputs\metformin_pad_phase2\run.json `
  --output outputs\metformin_pad_evaluation `
  --llm-model qwen-plus --env-file D:\path\outside-repo\.env.local
```

`--plan-only` is intentionally unavailable for Phase 2 because an incremental
revision without actual generated sections would create a misleading completed
run. Benchmark scores are simulation results, not clinical, statistical,
regulatory, or quality approval. The current end-to-end validation results,
known failures, simulated-reviewer findings, and machine-gate status are
documented in
[`docs/two_workflow_closure_report_zh.md`](docs/two_workflow_closure_report_zh.md).

Open `http://127.0.0.1:8810/docs` for the generated API console. The main
endpoints are:

- `GET /health`
- `POST /api/v1/intake/feishu`
- `POST /api/v1/review`
- `POST /api/v1/memory/search`

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m ruff check src tests
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
