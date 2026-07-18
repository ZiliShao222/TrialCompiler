"""Revalidate a frozen Phase 2 run and write its governed remediation package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trialcompiler.generation.validators import (
    build_phase2_remediation_plan,
    validate_phase2_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_path = args.run / "run.json" if args.run.is_dir() else args.run
    run = json.loads(run_path.read_text(encoding="utf-8"))
    findings = validate_phase2_candidate(
        run["fact_reconciliation"],
        run["protocol_sections"],
        run["associated_artifacts"],
    )
    payload = {
        "source_run": str(run_path.resolve()),
        "source_status": run.get("status"),
        "deterministic_findings": findings,
        "remediation_plan": build_phase2_remediation_plan(findings),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
