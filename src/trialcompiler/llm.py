"""Small OpenAI-compatible client used only when explicit LLM mode is enabled."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 90

    @classmethod
    def from_json(cls, path: str | Path) -> LLMConfig:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        missing = [name for name in ("base_url", "api_key", "model") if not payload.get(name)]
        if missing:
            raise ValueError(f"LLM config missing fields: {', '.join(missing)}")
        return cls(**payload)

    @classmethod
    def from_env(
        cls,
        *,
        model: str = "qwen-plus",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env: str = "DASHSCOPE_API_KEY",
        timeout_seconds: int = 90,
    ) -> LLMConfig:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise ValueError(f"Environment variable {api_key_env} is not configured")
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": self.config.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM connection failed: {exc.reason}") from exc
        content = result["choices"][0]["message"]["content"]
        try:
            return _sanitize_text(json.loads(content))
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM returned invalid JSON") from exc


def _sanitize_text(value: Any) -> Any:
    """Normalize common transport artifacts without changing model semantics."""
    if isinstance(value, str):
        replacements = {
            "\ufffd": "-",
            "\u9225?": " - ",
            "\u9225": " - ",
        }
        for broken, clean in replacements.items():
            value = value.replace(broken, clean)
        return value
    if isinstance(value, list):
        return [_sanitize_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_text(item) for key, item in value.items()}
    return value


def govern_semantic_review(
    result: dict[str, Any],
    *,
    section_ids: set[str],
    fact_ids: set[str],
    source_ids: set[str],
) -> tuple[dict[str, Any], list[str]]:
    """Constrain untrusted model JSON to supplied evidence and the review schema."""
    required = {"summary", "semantic_findings", "review_questions", "limitations"}
    missing = required - set(result)
    if missing:
        raise RuntimeError(f"Semantic review is missing keys: {', '.join(sorted(missing))}")
    warnings: list[str] = []
    governed = {
        "summary": str(result.get("summary", "")),
        "semantic_findings": [],
        "review_questions": [],
        "limitations": [],
    }
    id_scopes = {
        "section_ids": section_ids,
        "fact_ids": fact_ids,
        "source_ids": source_ids,
    }
    raw_findings = result.get("semantic_findings", [])
    if not isinstance(raw_findings, list):
        warnings.append("semantic_findings was not a list and was ignored")
        raw_findings = []
    for index, finding in enumerate(raw_findings):
        if not isinstance(finding, dict):
            warnings.append(f"Dropped non-object semantic finding at index {index}")
            continue
        clean = dict(finding)
        clean["finding_id"] = f"semantic-{index + 1:03d}"
        for field, allowed in id_scopes.items():
            raw_ids = clean.get(field, [])
            if isinstance(raw_ids, str):
                warnings.append(f"Coerced scalar {field} to a one-item list in finding {index}")
                raw_ids = [raw_ids]
            elif not isinstance(raw_ids, list):
                warnings.append(f"Dropped invalid {field} in finding {index}")
                raw_ids = []
            supplied = [str(item) for item in raw_ids]
            unknown = sorted(set(supplied) - allowed)
            if unknown:
                warnings.append(
                    f"Removed unsupported {field} from finding {index}: {', '.join(unknown)}"
                )
            clean[field] = [item for item in supplied if item in allowed]
        clean["requires_human_review"] = True
        governed["semantic_findings"].append(clean)

    unsupported_absence_phrases = (
        "companion document",
        "unspecified document",
        "whether any document exists",
    )
    for field in ("review_questions", "limitations"):
        raw_items = result.get(field, [])
        if isinstance(raw_items, str):
            warnings.append(f"Coerced scalar {field} to a one-item list")
            raw_items = [raw_items]
        elif not isinstance(raw_items, list):
            warnings.append(f"Dropped invalid {field}")
            raw_items = []
        for item in raw_items:
            text = str(item)
            if any(phrase in text.lower() for phrase in unsupported_absence_phrases):
                warnings.append(f"Removed unsupported absent-document speculation from {field}")
                continue
            governed[field].append(text)
    return governed, warnings


def govern_semantic_repairs(
    result: dict[str, Any],
    *,
    findings: list[dict[str, Any]],
    section_texts: dict[str, str],
    fact_ids: set[str],
    source_ids: set[str],
) -> tuple[dict[str, Any], list[str]]:
    """Validate model-proposed redlines against exact supplied document state."""
    warnings: list[str] = []
    allowed_findings = {str(item["finding_id"]) for item in findings}
    raw_proposals = result.get("repair_proposals", [])
    if not isinstance(raw_proposals, list):
        warnings.append("repair_proposals was not a list and was ignored")
        raw_proposals = []
    proposals: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_proposals):
        if not isinstance(item, dict):
            warnings.append(f"Dropped non-object repair proposal at index {index}")
            continue
        finding_id = str(item.get("finding_id", ""))
        section_id = str(item.get("section_id", ""))
        if finding_id not in allowed_findings or section_id not in section_texts:
            warnings.append(f"Dropped out-of-scope repair proposal at index {index}")
            continue
        if (finding_id, section_id) in seen:
            warnings.append(f"Dropped duplicate repair proposal for {finding_id}/{section_id}")
            continue
        original = str(item.get("original_text", ""))
        proposed = str(item.get("proposed_text", ""))
        if original != section_texts[section_id]:
            warnings.append(f"Dropped repair with non-matching original text at index {index}")
            continue
        if not proposed.strip() or proposed == original:
            warnings.append(f"Dropped empty or unchanged repair at index {index}")
            continue
        supplied_facts = item.get("fact_ids", [])
        supplied_sources = item.get("source_ids", [])
        if isinstance(supplied_facts, str):
            supplied_facts = [supplied_facts]
        if isinstance(supplied_sources, str):
            supplied_sources = [supplied_sources]
        clean_facts = [str(value) for value in supplied_facts if str(value) in fact_ids]
        clean_sources = [str(value) for value in supplied_sources if str(value) in source_ids]
        proposals.append(
            {
                "proposal_id": f"semantic-repair-{index + 1:03d}",
                "finding_id": finding_id,
                "section_id": section_id,
                "original_text": original,
                "proposed_text": proposed,
                "rationale": str(item.get("rationale", "Qualified review required.")),
                "fact_ids": clean_facts,
                "evidence_source_ids": clean_sources,
                "requires_human_review": True,
            }
        )
        seen.add((finding_id, section_id))
    limitations = result.get("limitations", [])
    if isinstance(limitations, str):
        limitations = [limitations]
    if not isinstance(limitations, list):
        limitations = []
    return {
        "proposals": proposals,
        "limitations": [str(value) for value in limitations],
    }, warnings


def load_prompt(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()
