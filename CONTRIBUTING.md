# Contributing to TrialCompiler

TrialCompiler is a research prototype for governed clinical-document review.
Contributions must preserve traceability, deterministic validation, and the
separation between AI proposals and qualified human decisions.

## Development setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Required checks

Run both checks before submitting a change:

```powershell
python -m ruff check src tests
python -m pytest -q
```

GitHub Actions runs the same checks for pushes and pull requests.

## Change guidelines

- Keep domain rules out of API and user-interface adapters.
- Use explicit dataclasses or schemas for workflow state and persisted records.
- Preserve source identifiers and audit metadata for generated findings or edits.
- Add deterministic tests for new rules, including at least one negative control.
- Do not silently fall back from model-assisted mode to a different behavior.
- Do not commit API keys, private endpoints, real patient data, or proprietary
  sponsor documents.
- Keep generated runs in `outputs/`; the directory is ignored by default.

## Pull request scope

Prefer a focused change with a concise explanation of:

1. the problem and affected architectural layer;
2. the safety or governance implications;
3. the validation performed; and
4. any known limitation or deferred work.
