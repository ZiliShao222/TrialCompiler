"""FastAPI surface for the TrialCompiler MVP."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from trialcompiler.integrations.feishu import aily_acknowledgement, validate_aily_payload
from trialcompiler.memory import RetrievalQuery, SemanticElementStore
from trialcompiler.models import TrialDocument, to_plain
from trialcompiler.workflows import ReviewWorkflow


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Build an isolated API instance so tests and deployments own their storage."""

    resolved_db = Path(
        db_path or os.getenv("TRIALCOMPILER_DB", "outputs/api/memory.sqlite3")
    )
    store = SemanticElementStore(resolved_db)
    workflow = ReviewWorkflow(store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        store.close()

    api = FastAPI(
        title="TrialCompiler MVP API",
        version="0.1.0",
        description="Review-only prototype. Every proposal requires qualified human approval.",
        lifespan=lifespan,
    )
    api.state.store = store

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "memory": store.metrics(), "release_mode": "review_only"}

    @api.post("/api/v1/intake/feishu")
    def feishu_intake(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return aily_acknowledgement(validate_aily_payload(payload))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/api/v1/review")
    def review_document(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            document_payload = payload.get("document", payload)
            document = TrialDocument.from_dict(document_payload)
            state = workflow.run(document, max_rounds=int(payload.get("max_rounds", 2)))
            return to_plain(state)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/api/v1/memory/search")
    def memory_search(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            query = RetrievalQuery(**payload)
            hits = store.retrieve(query)
            return {
                "hits": [
                    {
                        "element": to_plain(hit.element),
                        "coarse_score": hit.coarse_score,
                        "fine_score": hit.fine_score,
                        "reasons": hit.reasons,
                    }
                    for hit in hits
                ],
                "metrics": store.metrics(),
            }
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return api


app = create_app()
