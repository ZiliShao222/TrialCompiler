"""Small OpenAI-compatible client used only when explicit LLM mode is enabled."""

from __future__ import annotations

import json
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
        return json.loads(content)


def load_prompt(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()
