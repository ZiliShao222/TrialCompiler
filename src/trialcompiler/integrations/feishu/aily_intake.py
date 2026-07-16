"""Contract for a Feishu Aily workflow to call TrialCompiler."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from trialcompiler.models import FeishuIntakeEnvelope

ALLOWED_INTENTS = {
    "review_document",
    "compile_section",
    "propagate_change",
    "explain_finding",
}


def validate_aily_payload(payload: dict[str, Any]) -> FeishuIntakeEnvelope:
    """Validate output produced by Aily's question and extraction nodes."""
    required = ("request_id", "project_id", "actor_id", "user_request")
    missing = [name for name in required if not str(payload.get(name, "")).strip()]
    if missing:
        raise ValueError(f"Aily intake missing required fields: {', '.join(missing)}")
    task_intent = str(payload.get("task_intent", "review_document"))
    if task_intent not in ALLOWED_INTENTS:
        raise ValueError(
            f"Unsupported task_intent {task_intent!r}; allowed: {sorted(ALLOWED_INTENTS)}"
        )
    normalized = {
        **payload,
        "task_intent": task_intent,
        "document_type": str(payload.get("document_type", "protocol")),
        "locale": str(payload.get("locale", "zh-CN")),
        "file_refs": list(payload.get("file_refs", [])),
        "structured_fields": dict(payload.get("structured_fields", {})),
        "source": "feishu_aily",
    }
    return FeishuIntakeEnvelope.from_dict(normalized)


def aily_acknowledgement(envelope: FeishuIntakeEnvelope) -> dict[str, Any]:
    """Return a stable response shape consumable by the next Aily workflow node."""
    return {
        "accepted": True,
        "request_id": envelope.request_id,
        "project_id": envelope.project_id,
        "task_intent": envelope.task_intent,
        "next_step": "upload_or_select_document"
        if not envelope.file_refs
        else "start_trialcompiler_review",
        "normalized_intake": asdict(envelope),
    }
