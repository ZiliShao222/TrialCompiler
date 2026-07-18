"""Command-line entry point for the TrialCompiler MVP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trialcompiler.demo import load_document, seed_demo_experience
from trialcompiler.documents import ClinicalDocumentGraph
from trialcompiler.generation import (
    BlindProtocolEvaluator,
    GenerativeCasePackage,
    ProtocolGenerationWorkflow,
)
from trialcompiler.integrations.feishu import aily_acknowledgement, validate_aily_payload
from trialcompiler.llm import (
    LLMConfig,
    OpenAICompatibleClient,
    govern_semantic_repairs,
    govern_semantic_review,
    load_prompt,
)
from trialcompiler.memory import RetrievalQuery, SemanticElementStore
from trialcompiler.models import to_plain
from trialcompiler.project import ProjectWorkspace
from trialcompiler.workflows import ReviewWorkflow

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "data" / "fixtures" / "synthetic_protocol_conflict.json"
SEMANTIC_REVIEW_PROMPT = REPO_ROOT / "prompts" / "agents" / "semantic_document_reviewer.md"
SEMANTIC_REPAIR_PROMPT = REPO_ROOT / "prompts" / "agents" / "semantic_repair_builder.md"
GENERATION_PROMPT_ROOT = REPO_ROOT / "prompts" / "agents"


def _json_print(payload: Any) -> None:
    print(json.dumps(to_plain(payload), ensure_ascii=False, indent=2))


def _workspace(args: argparse.Namespace) -> ProjectWorkspace:
    return ProjectWorkspace(args.workspace)


def _coerce_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def run_init(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    document = load_document(args.document)
    workspace.initialize(document, actor=args.actor, replace=args.replace)
    _json_print({"status": "initialized", "workspace": str(workspace.root), **workspace.status()})
    return 0


def run_status(args: argparse.Namespace) -> int:
    _json_print(_workspace(args).status())
    return 0


def run_facts(args: argparse.Namespace) -> int:
    document = _workspace(args).load_document()
    _json_print(
        [
            {
                "fact_id": fact.fact_id,
                "name": fact.name,
                "value": fact.value,
                "unit": fact.unit,
                "status": fact.status.value,
                "version": fact.version,
                "owner_role": fact.owner_role,
                "source_ids": fact.source_ids,
            }
            for fact in document.facts
        ]
    )
    return 0


def run_change_create(args: argparse.Namespace) -> int:
    change = _workspace(args).create_change(
        fact_id=args.fact_id,
        proposed_value=_coerce_value(args.value),
        reason=args.reason,
        requested_by=args.actor,
    )
    _json_print(change)
    return 0


def run_fact_decide(args: argparse.Namespace) -> int:
    _json_print(
        _workspace(args).decide_fact(
            fact_id=args.fact_id,
            decision=args.decision,
            reviewer=args.reviewer,
            note=args.note,
        )
    )
    return 0


def run_changes(args: argparse.Namespace) -> int:
    _json_print(_workspace(args).list_changes())
    return 0


def run_impact(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    change = workspace.load_change(args.change_id)
    _json_print({"change": change, "impact_matrix": workspace.impact_matrix(change)})
    return 0


def _compile_workspace_change(
    workspace: ProjectWorkspace,
    *,
    change_id: str | None,
    db: str,
    max_rounds: int,
    seed_demo: bool,
    actor: str = "trialcompiler",
    llm_mode: str = "auto",
    llm_model: str = "qwen-plus",
) -> dict[str, Any]:
    change = workspace.load_change(change_id) if change_id else workspace.latest_actionable_change()
    document = workspace.candidate_document(change) if change else workspace.load_document()
    store = SemanticElementStore(db)
    try:
        workflow = ReviewWorkflow(store)
        if seed_demo:
            seed_demo_experience(workflow.experience_repository)
        impact = workspace.impact_matrix(change) if change else []
        change_context = asdict(change) if change else None
        semantic_review: dict[str, Any] = {
            "status": "not_run",
            "reason": "LLM mode is off",
            "model": None,
        }
        if llm_mode != "off":
            try:
                config = LLMConfig.from_env(model=llm_model)
                client = OpenAICompatibleClient(config)
                raw_result = client.complete_json(
                    system_prompt=load_prompt(SEMANTIC_REVIEW_PROMPT),
                    user_payload={
                        "document": document.to_dict(),
                        "change_context": change_context,
                        "change_reason": change.reason if change else None,
                        "deterministic_findings": [
                            asdict(item) for item in ClinicalDocumentGraph(document).review()
                        ],
                        "impact_matrix": impact,
                    },
                )
                governed_result, governance_warnings = govern_semantic_review(
                    raw_result,
                    section_ids={section.section_id for section in document.sections},
                    fact_ids={fact.fact_id for fact in document.facts},
                    source_ids={source.source_id for source in document.sources},
                )
                semantic_review = {
                    "status": "completed",
                    "model": config.model,
                    "result": governed_result,
                    "governance_warnings": governance_warnings,
                }
            except (RuntimeError, ValueError) as exc:
                if llm_mode == "on":
                    raise
                semantic_review = {
                    "status": "not_run",
                    "reason": str(exc),
                    "model": llm_model,
                }
        semantic_repairs: dict[str, Any] = {
            "status": "not_run",
            "reason": "Semantic review did not complete",
            "model": None,
            "proposals": [],
        }
        if semantic_review.get("status") == "completed":
            try:
                raw_repairs = client.complete_json(
                    system_prompt=load_prompt(SEMANTIC_REPAIR_PROMPT),
                    user_payload={
                        "document": document.to_dict(),
                        "semantic_findings": semantic_review["result"]["semantic_findings"],
                        "review_questions": semantic_review["result"]["review_questions"],
                        "change_context": change_context,
                        "impact_matrix": impact,
                    },
                )
                governed_repairs, repair_warnings = govern_semantic_repairs(
                    raw_repairs,
                    findings=semantic_review["result"]["semantic_findings"],
                    section_texts={
                        section.section_id: section.text for section in document.sections
                    },
                    fact_ids={fact.fact_id for fact in document.facts},
                    source_ids={source.source_id for source in document.sources},
                )
                semantic_repairs = {
                    "status": "completed",
                    "model": config.model,
                    **governed_repairs,
                    "governance_warnings": repair_warnings,
                }
            except (RuntimeError, ValueError) as exc:
                if llm_mode == "on":
                    raise
                semantic_repairs = {
                    "status": "not_run",
                    "reason": str(exc),
                    "model": llm_model,
                    "proposals": [],
                }
        state = workflow.run(
            document,
            max_rounds=max_rounds,
            semantic_review=semantic_review,
            semantic_repairs=semantic_repairs,
            change_context=change_context,
            impact_matrix=impact,
        )
        run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        run_dir = workspace.root / "runs" / run_id
        paths = workflow.save_run(state, run_dir)
        workspace.write_run_artifacts(
            run_id=run_id,
            change=change,
            state=state,
            workflow_paths=paths,
            impact=impact,
        )
        if change:
            change.status = "compiled"
            change.compiled_run_id = run_id
            workspace.save_change(change)
        workspace.audit(
            actor=actor,
            action="review_compiled",
            object_type="change_request" if change else "document",
            object_id=change.change_id if change else document.document_id,
            detail={
                "run_id": run_id,
                "findings": len(state.get("findings", [])),
                "proposals": len(state.get("proposals", [])),
                "quality": state.get("quality", {}),
                "semantic_review_status": semantic_review.get("status"),
                "semantic_review_model": semantic_review.get("model"),
            },
        )
        return {
            "status": "ready_for_qualified_human_review",
            "run_id": run_id,
            "change_id": change.change_id if change else None,
            "findings": state.get("findings", []),
            "proposals": state.get("proposals", []),
            "quality": state.get("quality", {}),
            "impact_matrix": impact,
            "semantic_review": semantic_review,
            "artifacts": paths,
        }
    finally:
        store.close()


def run_compile(args: argparse.Namespace) -> int:
    _json_print(
        _compile_workspace_change(
            _workspace(args),
            change_id=args.change_id,
            db=args.db,
            max_rounds=args.max_rounds,
            seed_demo=args.seed_demo_experience,
            actor=args.actor,
            llm_mode=args.llm,
            llm_model=args.llm_model,
        )
    )
    return 0


def run_decide(args: argparse.Namespace) -> int:
    _json_print(
        _workspace(args).decide_change(
            change_id=args.change_id,
            decision=args.decision,
            reviewer=args.reviewer,
            note=args.note,
        )
    )
    return 0


def run_decision_request(args: argparse.Namespace) -> int:
    _json_print(
        _workspace(args).resolve_decision_request(
            change_id=args.change_id,
            request_id=args.request_id,
            decision=args.decision,
            reviewer=args.reviewer,
            note=args.note,
        )
    )
    return 0


def run_audit(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    workspace.require()
    lines = workspace.audit_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line]
    _json_print(events[-args.limit :])
    return 0


def run_workspace_session(args: argparse.Namespace) -> int:
    """Guided shell for non-programmers; all work still uses atomic commands."""
    workspace = _workspace(args)
    if not workspace.manifest_path.exists():
        actor = input("Your name or role [demo-user]: ").strip() or "demo-user"
        workspace.initialize(load_document(args.document), actor=actor)
        print(f"Workspace created at {workspace.root}\n")
    while True:
        status = workspace.status()
        print(
            f"\nTrialCompiler | {status['title']} | document v{status['document_version']}\n"
            "1. Show project status\n"
            "2. List confirmed facts\n"
            "3. Request a fact change\n"
            "4. Compile a change and inspect impact\n"
            "5. Approve or reject a compiled change\n"
            "6. Show audit trail\n"
            "0. Exit\n"
        )
        choice = input("Select [0-6]: ").strip()
        try:
            if choice == "0":
                return 0
            if choice == "1":
                _json_print(status)
            elif choice == "2":
                run_facts(argparse.Namespace(workspace=str(workspace.root)))
            elif choice == "3":
                fact_id = input("Fact ID: ").strip()
                value = input("Proposed value (JSON or text): ").strip()
                reason = input("Reason for change: ").strip()
                actor = input("Requested by: ").strip() or "demo-user"
                change = workspace.create_change(
                    fact_id=fact_id,
                    proposed_value=_coerce_value(value),
                    reason=reason,
                    requested_by=actor,
                )
                _json_print(change)
            elif choice == "4":
                change_id = input("Change ID: ").strip()
                _json_print(
                    _compile_workspace_change(
                        workspace,
                        change_id=change_id,
                        db=args.db,
                        max_rounds=args.max_rounds,
                        seed_demo=True,
                        actor="guided-cli",
                        llm_mode=args.llm,
                        llm_model=args.llm_model,
                    )
                )
            elif choice == "5":
                change_id = input("Change ID: ").strip()
                decision = input("Decision [approve/reject]: ").strip().lower()
                reviewer = input("Qualified reviewer: ").strip()
                note = input("Review note: ").strip()
                _json_print(
                    workspace.decide_change(
                        change_id=change_id,
                        decision=decision,
                        reviewer=reviewer,
                        note=note,
                    )
                )
            elif choice == "6":
                lines = workspace.audit_path.read_text(encoding="utf-8").splitlines()
                events = [json.loads(line) for line in lines if line]
                _json_print(events[-20:])
            else:
                print("Unknown selection.")
        except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
            print(f"Cannot continue: {exc}")


def run_review(args: argparse.Namespace, *, seed_demo: bool = False) -> int:
    store = SemanticElementStore(args.db)
    workflow = ReviewWorkflow(store)
    if seed_demo:
        seed_demo_experience(workflow.experience_repository)
    document = load_document(args.document)
    state = workflow.run(document, max_rounds=args.max_rounds)
    paths = workflow.save_run(state, args.output)
    _json_print(
        {
            "status": "completed_for_human_review",
            "findings": len(state.get("findings", [])),
            "proposals": len(state.get("proposals", [])),
            "quality": state.get("quality"),
            "experience_cards": len(state.get("experience_cards", [])),
            "experience_candidate_status": (state.get("experience_candidate") or {}).get("status"),
            "artifacts": paths,
            "memory_metrics": store.metrics(),
        }
    )
    store.close()
    return 0


def run_feishu_intake(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    envelope = validate_aily_payload(payload)
    _json_print(aily_acknowledgement(envelope))
    return 0


def run_memory_search(args: argparse.Namespace) -> int:
    store = SemanticElementStore(args.db)
    hits = store.retrieve(
        RetrievalQuery(
            text=args.query,
            namespace=args.namespace,
            approval_statuses=args.approval_status,
            top_k=args.top_k,
        )
    )
    _json_print(
        [
            {
                "element_id": hit.element.element_id,
                "semantic_key": hit.element.semantic_key,
                "fine_score": hit.fine_score,
                "authority": hit.element.authority,
                "value": hit.element.value,
            }
            for hit in hits
        ]
    )
    store.close()
    return 0


def run_package_audit(args: argparse.Namespace) -> int:
    package = GenerativeCasePackage(args.package)
    files = package.materialize(args.stage, strict=False)
    audit = package.audit(args.stage, files=files)
    _json_print(audit.to_dict())
    return 0 if audit.passed else 3


def run_generate_protocol(args: argparse.Namespace) -> int:
    package = GenerativeCasePackage(args.package)
    config = (
        LLMConfig.from_env_file(
            args.env_file,
            model=args.llm_model,
            timeout_seconds=args.timeout_seconds,
        )
        if args.env_file
        else LLMConfig.from_env(
            model=args.llm_model,
            timeout_seconds=args.timeout_seconds,
        )
    )
    workflow = ProtocolGenerationWorkflow(
        package=package,
        client=OpenAICompatibleClient(config),
        prompt_root=GENERATION_PROMPT_ROOT,
    )
    if args.phase == "phase2":
        if args.plan_only:
            raise ValueError(
                "--plan-only is only supported for Phase 1; Phase 2 must run the "
                "complete reconciliation, revision, artifact, and quality-gate chain"
            )
        if not args.phase1_run:
            raise ValueError("--phase1-run is required when --phase phase2")
        result = workflow.run_phase2(
            args.output,
            phase1_run=args.phase1_run,
            full=not args.plan_only,
        )
    else:
        result = workflow.run_phase1(args.output, full=not args.plan_only)
    _json_print(result)
    return 0


def run_evaluate_protocol(args: argparse.Namespace) -> int:
    package = GenerativeCasePackage(args.package)
    config = (
        LLMConfig.from_env_file(
            args.env_file,
            model=args.llm_model,
            timeout_seconds=args.timeout_seconds,
        )
        if args.env_file
        else LLMConfig.from_env(
            model=args.llm_model,
            timeout_seconds=args.timeout_seconds,
        )
    )
    evaluator = BlindProtocolEvaluator(
        package=package,
        client=OpenAICompatibleClient(config),
        prompt_path=GENERATION_PROMPT_ROOT / "G8_blind_benchmark_evaluator.md",
    )
    _json_print(
        evaluator.evaluate(
            args.output,
            phase1_run=args.phase1_run,
            phase2_run=args.phase2_run,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trialcompiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a persistent project workspace")
    init.add_argument("--workspace", default="outputs/workspaces/demo")
    init.add_argument("--document", default=str(DEFAULT_FIXTURE))
    init.add_argument("--actor", default=os.getenv("USERNAME", "demo-user"))
    init.add_argument("--replace", action="store_true")
    init.set_defaults(handler=run_init)

    status = subparsers.add_parser("status", help="Show project and review state")
    status.add_argument("--workspace", default="outputs/workspaces/demo")
    status.set_defaults(handler=run_status)

    facts = subparsers.add_parser("facts", help="List the versioned Trial Fact Sheet")
    facts.add_argument("--workspace", default="outputs/workspaces/demo")
    facts.set_defaults(handler=run_facts)

    fact_decision = subparsers.add_parser(
        "fact-decision", help="Confirm or reject a sourced candidate fact"
    )
    fact_decision.add_argument("--workspace", default="outputs/workspaces/demo")
    fact_decision.add_argument("--fact-id", required=True)
    fact_decision.add_argument("--decision", choices=["confirm", "reject"], required=True)
    fact_decision.add_argument("--reviewer", required=True)
    fact_decision.add_argument("--note", default="")
    fact_decision.set_defaults(handler=run_fact_decide)

    change = subparsers.add_parser("change", help="Create a governed fact change request")
    change.add_argument("--workspace", default="outputs/workspaces/demo")
    change.add_argument("--fact-id", required=True)
    change.add_argument("--value", required=True, help="JSON scalar or text")
    change.add_argument("--reason", required=True)
    change.add_argument("--actor", required=True)
    change.set_defaults(handler=run_change_create)

    changes = subparsers.add_parser("changes", help="List project change requests")
    changes.add_argument("--workspace", default="outputs/workspaces/demo")
    changes.set_defaults(handler=run_changes)

    impact = subparsers.add_parser("impact", help="Preview direct document dependencies")
    impact.add_argument("--workspace", default="outputs/workspaces/demo")
    impact.add_argument("--change-id", required=True)
    impact.set_defaults(handler=run_impact)

    compile_change = subparsers.add_parser(
        "compile", help="Run A-F review and generate a human review packet"
    )
    compile_change.add_argument("--workspace", default="outputs/workspaces/demo")
    compile_change.add_argument("--change-id")
    compile_change.add_argument("--db", default="outputs/runtime/memory.sqlite3")
    compile_change.add_argument("--max-rounds", type=int, default=2)
    compile_change.add_argument("--seed-demo-experience", action="store_true")
    compile_change.add_argument("--actor", default=os.getenv("USERNAME", "trialcompiler"))
    compile_change.add_argument("--llm", choices=["auto", "on", "off"], default="auto")
    compile_change.add_argument("--llm-model", default="qwen-plus")
    compile_change.set_defaults(handler=run_compile)

    decide = subparsers.add_parser("decide", help="Approve or reject a compiled change")
    decide.add_argument("--workspace", default="outputs/workspaces/demo")
    decide.add_argument("--change-id", required=True)
    decide.add_argument("--decision", choices=["approve", "reject"], required=True)
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--note", default="")
    decide.set_defaults(handler=run_decide)

    decision_request = subparsers.add_parser(
        "decision-request",
        help="Resolve or defer one qualified decision request from a compiled run",
    )
    decision_request.add_argument("--workspace", default="outputs/workspaces/demo")
    decision_request.add_argument("--change-id", required=True)
    decision_request.add_argument("--request-id", required=True)
    decision_request.add_argument(
        "--decision",
        choices=["accept_documented", "require_recompile"],
        required=True,
    )
    decision_request.add_argument("--reviewer", required=True)
    decision_request.add_argument("--note", required=True)
    decision_request.set_defaults(handler=run_decision_request)

    audit = subparsers.add_parser("audit", help="Read the append-only project audit trail")
    audit.add_argument("--workspace", default="outputs/workspaces/demo")
    audit.add_argument("--limit", type=int, default=20)
    audit.set_defaults(handler=run_audit)

    session = subparsers.add_parser("workspace", help="Start the guided CLI product session")
    session.add_argument("--workspace", default="outputs/workspaces/demo")
    session.add_argument("--document", default=str(DEFAULT_FIXTURE))
    session.add_argument("--db", default="outputs/workspaces/demo/memory.sqlite3")
    session.add_argument("--max-rounds", type=int, default=2)
    session.add_argument("--llm", choices=["auto", "on", "off"], default="auto")
    session.add_argument("--llm-model", default="qwen-plus")
    session.set_defaults(handler=run_workspace_session)

    demo = subparsers.add_parser("demo", help="Run the synthetic end-to-end demo")
    demo.add_argument("--document", default=str(DEFAULT_FIXTURE))
    demo.add_argument("--db", default="outputs/demo/memory.sqlite3")
    demo.add_argument("--output", default="outputs/demo")
    demo.add_argument("--max-rounds", type=int, default=2)
    demo.set_defaults(handler=lambda args: run_review(args, seed_demo=True))

    review = subparsers.add_parser("review", help="Review a structured trial document")
    review.add_argument("--document", required=True)
    review.add_argument("--db", default="outputs/runtime/memory.sqlite3")
    review.add_argument("--output", default="outputs/runtime/latest")
    review.add_argument("--max-rounds", type=int, default=2)
    review.set_defaults(handler=run_review)

    intake = subparsers.add_parser("feishu-intake", help="Validate an Aily output payload")
    intake.add_argument("--payload", required=True)
    intake.set_defaults(handler=run_feishu_intake)

    search = subparsers.add_parser("memory-search", help="Search admitted memory elements")
    search.add_argument("--db", required=True)
    search.add_argument("--namespace", default="approved_experience")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--approval-status", nargs="+", default=["approved"])
    search.set_defaults(handler=run_memory_search)

    package_audit = subparsers.add_parser(
        "package-audit",
        help="Audit stage visibility and hidden-answer leakage in a generative test package",
    )
    package_audit.add_argument("--package", required=True)
    package_audit.add_argument("--stage", choices=["phase1", "phase2"], default="phase1")
    package_audit.set_defaults(handler=run_package_audit)

    generate = subparsers.add_parser(
        "generate-protocol",
        help="Run a controlled Phase 1 generation or Phase 2 incremental revision",
    )
    generate.add_argument("--package", required=True)
    generate.add_argument("--output", default="outputs/generative_protocol/phase1")
    generate.add_argument("--llm-model", default="qwen-plus")
    generate.add_argument(
        "--env-file",
        help="External dotenv file containing DASHSCOPE_API_KEY; never copied to outputs",
    )
    generate.add_argument("--timeout-seconds", type=int, default=180)
    generate.add_argument("--phase", choices=["phase1", "phase2"], default="phase1")
    generate.add_argument(
        "--phase1-run",
        help="Phase 1 output directory or run.json; required for Phase 2",
    )
    generate.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate evidence plan and synopsis without the full section set",
    )
    generate.set_defaults(handler=run_generate_protocol)

    evaluate = subparsers.add_parser(
        "evaluate-protocol",
        help="Blind-score frozen Phase 1/2 outputs with evaluator-only benchmark material",
    )
    evaluate.add_argument("--package", required=True)
    evaluate.add_argument("--phase1-run", required=True)
    evaluate.add_argument("--phase2-run", required=True)
    evaluate.add_argument("--output", default="outputs/generative_protocol/evaluation")
    evaluate.add_argument("--llm-model", default="qwen-plus")
    evaluate.add_argument(
        "--env-file",
        help="External dotenv file containing DASHSCOPE_API_KEY; never copied to outputs",
    )
    evaluate.add_argument("--timeout-seconds", type=int, default=180)
    evaluate.set_defaults(handler=run_evaluate_protocol)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (FileNotFoundError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"TrialCompiler error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
