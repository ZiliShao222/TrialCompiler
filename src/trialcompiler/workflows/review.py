"""LangGraph orchestration for TrialCompiler's review-only MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from trialcompiler.agents import ReviewAgents
from trialcompiler.memory import SemanticElementStore
from trialcompiler.memory.experience import ExperienceRepository
from trialcompiler.models import TrialDocument, to_plain


class ReviewWorkflowState(TypedDict, total=False):
    document: dict[str, Any]
    context_lock: dict[str, Any]
    findings: list[dict[str, Any]]
    semantic_review: dict[str, Any]
    semantic_repairs: dict[str, Any]
    review_coverage: dict[str, Any]
    change_context: dict[str, Any] | None
    impact_matrix: list[dict[str, Any]]
    experience_cards: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    raw_proposals: list[dict[str, Any]]
    repair_conflicts: list[dict[str, Any]]
    repair_feedback: dict[str, Any]
    deferred_finding_ids: list[str]
    authorization_blocks: list[dict[str, Any]]
    decision_requests: list[dict[str, Any]]
    workflow_status: str
    verification: dict[str, Any]
    quality: dict[str, Any]
    report_markdown: str
    experience_candidate: dict[str, Any] | None
    round_index: int
    max_rounds: int
    trace: list[dict[str, Any]]


class ReviewWorkflow:
    def __init__(self, store: SemanticElementStore) -> None:
        self.store = store
        self.experience_repository = ExperienceRepository(store)
        self.agents = ReviewAgents(self.experience_repository)
        self.graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is required. Install the project in the iGEM environment first."
            ) from exc

        builder = StateGraph(ReviewWorkflowState)
        builder.add_node("A_context", self.agents.context_agent)
        builder.add_node("B_evidence", self.agents.evidence_agent)
        builder.add_node("C_repair", self.agents.repair_agent)
        builder.add_node("D_quality", self.agents.quality_agent)
        builder.add_node("E_reporter", self.agents.reporter_agent)
        builder.add_node("F_experience", self.agents.experience_agent)
        builder.add_edge(START, "A_context")
        builder.add_edge("A_context", "B_evidence")
        builder.add_edge("B_evidence", "C_repair")
        builder.add_edge("C_repair", "D_quality")
        builder.add_conditional_edges(
            "D_quality",
            self._route_quality,
            {"repair": "C_repair", "report": "E_reporter"},
        )
        builder.add_edge("E_reporter", "F_experience")
        builder.add_edge("F_experience", END)
        return builder.compile()

    @staticmethod
    def _route_quality(state: ReviewWorkflowState) -> str:
        if state.get("quality", {}).get("accepted"):
            return "report"
        if int(state.get("round_index", 0)) >= int(state.get("max_rounds", 2)):
            return "report"
        return "repair"

    def run(
        self,
        document: TrialDocument,
        *,
        max_rounds: int = 2,
        semantic_review: dict[str, Any] | None = None,
        semantic_repairs: dict[str, Any] | None = None,
        change_context: dict[str, Any] | None = None,
        impact_matrix: list[dict[str, Any]] | None = None,
    ) -> ReviewWorkflowState:
        initial: ReviewWorkflowState = {
            "document": document.to_dict(),
            "semantic_review": semantic_review
            or {"status": "not_run", "reason": "No semantic reviewer supplied"},
            "semantic_repairs": semantic_repairs
            or {"status": "not_run", "reason": "No semantic repair builder supplied"},
            "change_context": change_context,
            "impact_matrix": impact_matrix or [],
            "round_index": 0,
            "max_rounds": max_rounds,
            "trace": [],
        }
        return self.graph.invoke(initial)

    @staticmethod
    def save_run(state: ReviewWorkflowState, output_dir: str | Path) -> dict[str, str]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        state_path = output / "workflow_state.json"
        report_path = output / "review_report.md"
        trace_path = output / "agent_trace.jsonl"
        decision_requests_path = output / "decision_requests.json"
        state_path.write_text(
            json.dumps(to_plain(state), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report_path.write_text(state.get("report_markdown", ""), encoding="utf-8")
        decision_requests_path.write_text(
            json.dumps(
                to_plain(state.get("decision_requests", [])),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        trace_path.write_text(
            "\n".join(
                json.dumps(to_plain(event), ensure_ascii=False) for event in state.get("trace", [])
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "state": str(state_path),
            "report": str(report_path),
            "trace": str(trace_path),
            "decision_requests": str(decision_requests_path),
        }
