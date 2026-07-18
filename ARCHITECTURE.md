# TrialCompiler Architecture

TrialCompiler is an evidence-grounded, human-governed compiler for clinical
trial documents. Its architecture separates deterministic document controls
from model-assisted review so that an unavailable or unreliable model cannot
silently bypass traceability, quality gates, or qualified human approval.

## System Context

```text
Users / Feishu Aily / CLI / API
                |
                v
       Application adapters
                |
                v
     Governed workflow control plane
        |          |          |
        v          v          v
  Document      Evidence    Experience
  compiler      retrieval   memory
        \          |          /
         \         |         /
          v        v        v
       Versioned project state
                |
                v
   Audit trail + human decision gate
```

The current release is review-only. It produces findings, impact sets,
candidate redlines, decision requests, and audit artifacts. It does not make
autonomous clinical, statistical, regulatory, or release decisions.

## Architectural Layers

### 1. Application adapters

The outer layer translates user and integration requests into domain commands.
It does not own clinical rules or persistence semantics.

- CLI entry point: `src/trialcompiler/cli.py`
- FastAPI service: `apps/api/app.py`
- Feishu Aily intake contract: `src/trialcompiler/integrations/feishu/`
- External model client and response governance: `src/trialcompiler/llm.py`

### 2. Workflow control plane

The workflow layer owns role sequencing, bounded repair loops, quality-gate
routing, and hand-off state. Agents communicate through explicit state rather
than untracked free-form conversation.

- A-F review orchestration: `src/trialcompiler/workflows/review.py`
- Role implementations: `src/trialcompiler/agents/review_agents.py`
- Generative protocol workflow: `src/trialcompiler/generation/workflow.py`
- Phase-specific validators: `src/trialcompiler/generation/validators.py`

The A-F responsibilities are:

1. A locks task context and scope.
2. B assembles evidence and admitted experience.
3. C proposes minimal, traceable repairs.
4. D independently rechecks the candidate state.
5. E packages approved review artifacts without introducing new facts.
6. F proposes reusable experience that remains inactive until human approval.

### 3. Document compiler

The compiler represents repeated trial facts and their document occurrences as
a dependency graph. A proposed fact change is compiled into an impact set,
candidate edit operations, and deterministic checks.

- Clinical Document Graph: `src/trialcompiler/documents/graph.py`
- Atomic repair composition: `src/trialcompiler/documents/repairs.py`
- Shared domain contracts: `src/trialcompiler/models.py`

Candidate edits are rejected or escalated when their source text no longer
matches, evidence is missing, edit ranges overlap, or independent re-review
detects unresolved or newly introduced findings.

### 4. Governed knowledge and experience

Project facts, external evidence, and learned organizational experience remain
separate. Only approved, active, in-scope experience is admitted to downstream
agent context.

- Semantic element store: `src/trialcompiler/memory/semantic_store.py`
- Experience lifecycle and action cards: `src/trialcompiler/memory/experience.py`
- Versioned prompt contracts: `prompts/`
- Structured knowledge and source metadata: `knowledge/`, `references/`

This separation prevents a draft model reflection from becoming an implicit
clinical rule.

### 5. Project state, decisions, and audit

The project workspace persists the Trial Fact Sheet, document versions, change
requests, qualified decisions, and append-only audit events.

- Persistent workspace: `src/trialcompiler/project.py`
- JSON contracts: `schemas/`
- Non-secret runtime examples: `config/`
- Generated local runs: `outputs/` (ignored except for `.gitkeep`)

AI proposals and human decisions are distinct records. Applying or rejecting a
candidate change is an explicit operation, not a side effect of generation.

### 6. Evaluation and reproducibility

Evaluation artifacts are isolated from application state and use declared
sources, immutable fixtures, gold findings, negative controls, and deterministic
scoring scripts.

- Public benchmark cases: `benchmarks/trialdocbench/`
- Benchmark and integrity tests: `tests/`
- Reproducible build and scoring commands: `scripts/`
- Continuous validation: `.github/workflows/ci.yml`

## Dependency Direction

Dependencies point inward:

```text
apps / CLI
    -> workflows and integrations
        -> documents, generation, memory, project
            -> models and standard-library infrastructure
```

Core domain modules do not import FastAPI or user-interface code. External LLM
access is explicit and can be disabled; deterministic review and benchmark
paths remain available without network access.

## Governed Change Flow

```text
Proposed fact or document change
  -> validate scope and source evidence
  -> locate dependent document units
  -> generate atomic candidate edits
  -> compose non-overlapping patch set
  -> re-run deterministic and semantic review
  -> pass, repair within a bounded loop, or escalate
  -> request qualified human decision
  -> record decision and resulting version in the audit trail
```

No candidate output is treated as released content merely because a workflow
completed successfully.

## Extension Points

- Add a model provider behind the existing OpenAI-compatible client contract.
- Add a document parser that emits existing fact, section, source, and
  dependency contracts.
- Add deterministic checks in the validator layer without changing adapters.
- Add an enterprise retrieval backend behind the semantic-store interface.
- Add a collaboration surface that calls the API or intake contract instead of
  duplicating domain logic.

## Deliberate Boundaries

The MVP does not process real patient data, autonomously approve documents, or
claim production regulatory validation. Frontend work is deferred; the CLI and
API are the supported demonstration surfaces. These boundaries keep the public
prototype reproducible while preserving the qualified-human responsibility
model required for clinical documentation.
