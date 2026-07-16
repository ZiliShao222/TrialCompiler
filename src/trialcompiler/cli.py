"""Command-line entry point for the TrialCompiler MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trialcompiler.demo import load_document, seed_demo_experience
from trialcompiler.integrations.feishu import aily_acknowledgement, validate_aily_payload
from trialcompiler.memory import RetrievalQuery, SemanticElementStore
from trialcompiler.models import to_plain
from trialcompiler.workflows import ReviewWorkflow

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "data" / "fixtures" / "synthetic_protocol_conflict.json"


def _json_print(payload: Any) -> None:
    print(json.dumps(to_plain(payload), ensure_ascii=False, indent=2))


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
            "experience_candidate_status": (
                state.get("experience_candidate") or {}
            ).get("status"),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trialcompiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
