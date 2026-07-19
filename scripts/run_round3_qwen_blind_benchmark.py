"""Run the frozen round-3 test split through the real DashScope Qwen API."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Direct execution (``python scripts/...py``) places only ``scripts`` on
# ``sys.path``.  Add the repository root so sibling script modules resolve in
# the same way they do under pytest.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_and_score_public_role_gold import metrics


SYSTEM = """You are an independent clinical-document consistency reviewer.
Compare the supplied authoritative frozen fact with the candidate document statement.
Do not assume a defect merely because this is a benchmark. A defect exists only when the
candidate field value does not equal the authoritative value for the same field and scope.
Return one JSON object only, with keys defect_present, observed_value,
authoritative_value, recommended_replacement, confidence, and reason.
Use an empty recommended_replacement when no defect exists. Do not infer beyond evidence."""


def call_api(model: str, key: str, payload: dict[str, Any], timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    latency = time.perf_counter() - started
    output = json.loads(raw["choices"][0]["message"]["content"])
    return output, {"latency_seconds": latency, "usage": raw.get("usage", {}), "request_id": raw.get("id")}


def blind_payload(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record["old_value"] if record["expected"] else record["new_value"]
    unit = " participants" if record["task"] == "enrollment" else " arms" if record["task"] == "arm_count" else ""
    return {
        "case_id": record["case_id"],
        "field_name": record["task"].replace("_", " "),
        "scope": "same trial, same field, same controlled document unit",
        "authoritative_frozen_fact": str(record["new_value"]),
        "candidate_document_statement": f"The document field value is {candidate}{unit}.",
        "instruction": "Decide whether repair is required and give the exact authoritative replacement if required.",
    }


def run_one(record: dict[str, Any], model: str, key: str, timeout: int) -> dict[str, Any]:
    last_error = ""
    for attempt in range(3):
        try:
            output, transport = call_api(model, key, blind_payload(record), timeout)
            predicted = bool(output["defect_present"])
            replacement = str(output.get("recommended_replacement", "")).strip()
            replacement_correct = replacement == str(record["new_value"]) if record["expected"] else replacement in {"", str(record["new_value"])}
            return {
                "record_id": record["record_id"], "case_id": record["case_id"],
                "split": record["split"], "task": record["task"], "expected": record["expected"],
                "predictions": {model: predicted}, "model_output": output,
                "replacement_correct": replacement_correct, **transport, "error": None,
            }
        except (KeyError, ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.5 * (attempt + 1))
    return {
        "record_id": record["record_id"], "case_id": record["case_id"],
        "split": record["split"], "task": record["task"], "expected": record["expected"],
        "predictions": {model: False}, "model_output": None, "replacement_correct": False,
        "latency_seconds": None, "usage": {}, "request_id": None, "error": last_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, default=Path("benchmarks/trialdocbench/public_corpus_050/round3_rich_defects/records.jsonl"))
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/trialdocbench/public_corpus_050/round3_qwen_api"))
    args = parser.parse_args()
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    records = [json.loads(line) for line in args.records.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [item for item in records if item["split"] == args.split]
    if args.limit:
        selected = selected[: args.limit]
    started_at = datetime.now(UTC)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda item: run_one(item, args.model, key, args.timeout), selected))
    completed_at = datetime.now(UTC)
    valid = [item for item in results if not item["error"]]
    scored = metrics(valid, args.model) if valid else {}
    report = {
        "schema": "trialcompiler.round3_real_qwen_api_blind/v1",
        "model": args.model,
        "api": "DashScope OpenAI-compatible chat/completions",
        "split": args.split,
        "requested_count": len(selected), "completed_count": len(valid),
        "error_count": len(results) - len(valid),
        "started_at": started_at.isoformat(), "completed_at": completed_at.isoformat(),
        "wall_seconds": (completed_at - started_at).total_seconds(),
        "metrics": scored,
        "replacement_correct_count": sum(item["replacement_correct"] for item in valid),
        "mean_latency_seconds": sum(item["latency_seconds"] for item in valid) / len(valid) if valid else None,
        "total_prompt_tokens": sum(item["usage"].get("prompt_tokens", 0) for item in valid),
        "total_completion_tokens": sum(item["usage"].get("completion_tokens", 0) for item in valid),
        "request_id_count": sum(bool(item["request_id"]) for item in valid),
        "claim_boundary": "real qwen-plus API blind classification of controlled field-value consistency; not expert clinical-semantic adjudication",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    suffix = f"{args.split}_{len(selected):03d}"
    (args.output / f"records_{suffix}.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in results), encoding="utf-8"
    )
    (args.output / f"report_{suffix}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not report["error_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
