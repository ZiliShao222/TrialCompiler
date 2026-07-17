"""Controlled multi-stage workflow for evidence-bounded protocol generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trialcompiler.generation.package import GenerativeCasePackage
from trialcompiler.llm import OpenAICompatibleClient, load_prompt

SECTION_SPECS = (
    "Synopsis and study rationale",
    "Objectives, endpoints, and estimands",
    "Study design and treatment",
    "Population and eligibility criteria",
    "Schedule of activities and assessments",
    "Safety monitoring and stopping rules",
    "Statistical design and sample-size rationale",
    "Operational feasibility and quality controls",
    "FDA and NMPA regional regulatory rationale",
)


@dataclass(slots=True)
class ProtocolGenerationWorkflow:
    package: GenerativeCasePackage
    client: OpenAICompatibleClient
    prompt_root: Path

    def run_phase1(self, output: str | Path, *, full: bool = True) -> dict[str, Any]:
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        checkpoint_path = output_path / "checkpoints"
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        source_payload = self.package.prompt_payload("phase1", strict=True)
        self._write_json(checkpoint_path / "package_payload.json", source_payload)
        planner_checkpoint = checkpoint_path / "planner.json"
        if planner_checkpoint.exists():
            planner = json.loads(planner_checkpoint.read_text(encoding="utf-8"))
        else:
            planner = self.client.complete_json(
                system_prompt=load_prompt(self.prompt_root / "G1_evidence_planner.md"),
                user_payload=source_payload,
            )
        self._require_keys(
            planner,
            {
                "critical_questions",
                "evidence_matrix",
                "candidate_fact_sheet",
                "assumptions_and_tbd",
                "protocol_synopsis",
            },
            "G1 evidence planner",
        )
        self._write_json(checkpoint_path / "planner.json", planner)
        sections: list[dict[str, Any]] = []
        if full:
            for index, section_spec in enumerate(SECTION_SPECS, start=1):
                section_checkpoint = checkpoint_path / f"section_{index:02d}.json"
                if section_checkpoint.exists():
                    result = json.loads(section_checkpoint.read_text(encoding="utf-8"))
                else:
                    result = self.client.complete_json(
                        system_prompt=load_prompt(self.prompt_root / "G2_section_writer.md"),
                        user_payload={
                            "section_number": index,
                            "section_specification": section_spec,
                            "planner_output": planner,
                            "source_documents": source_payload["source_documents"],
                            "visibility_policy": source_payload["visibility_policy"],
                        },
                    )
                self._require_keys(
                    result,
                    {"title", "content", "fact_ids", "source_citations", "tbd_items"},
                    f"G2 section {index}",
                )
                sections.append(result)
                self._write_json(
                    checkpoint_path / f"section_{index:02d}.json",
                    result,
                )
        quality_checkpoint = checkpoint_path / "quality_gate.json"
        if quality_checkpoint.exists():
            quality = json.loads(quality_checkpoint.read_text(encoding="utf-8"))
        else:
            quality = self.client.complete_json(
                system_prompt=load_prompt(self.prompt_root / "G3_quality_judge.md"),
                user_payload={
                    "planner_output": planner,
                    "protocol_sections": sections,
                    "visible_source_paths": [
                        item["path"] for item in source_payload["source_documents"]
                    ],
                    "visibility_policy": source_payload["visibility_policy"],
                },
            )
        self._require_keys(
            quality,
            {"gate_status", "findings", "unsupported_claims", "tbd_compliance", "limitations"},
            "G3 quality judge",
        )
        quality = self._govern_quality_output(quality)
        self._write_json(checkpoint_path / "quality_gate.json", quality)
        audit = self.package.audit("phase1").to_dict()
        run = {
            "run_type": "generative_protocol_phase1",
            "created_at": datetime.now(UTC).isoformat(),
            "model": self.client.config.model,
            "package_audit": audit,
            "planner": planner,
            "protocol_sections": sections,
            "quality_gate": quality,
            "human_approval_required": True,
            "phase2_materials_used": False,
            "evaluator_materials_used": False,
        }
        (output_path / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_path / "protocol_draft.md").write_text(
            self._render_markdown(planner, sections, quality), encoding="utf-8"
        )
        (output_path / "package_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "status": "awaiting_qualified_human_review",
            "output": str(output_path),
            "quality_gate": quality.get("gate_status"),
            "sections_generated": len(sections),
            "package_audit_passed": audit["passed"],
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _govern_quality_output(payload: dict[str, Any]) -> dict[str, Any]:
        allowed_gates = {
            "pass_for_qualified_human_review",
            "revise_before_human_review",
            "blocked_missing_evidence",
        }
        governed = dict(payload)
        if governed.get("gate_status") not in allowed_gates:
            governed["gate_status"] = "blocked_missing_evidence"

        for field in (
            "findings",
            "unsupported_claims",
            "cross_section_consistency",
            "source_boundary_check",
            "required_human_reviews",
            "limitations",
        ):
            value = governed.get(field, [])
            governed[field] = value if isinstance(value, list) else [str(value)]

        tbd = governed.get("tbd_compliance")
        if isinstance(tbd, bool):
            governed["tbd_compliance"] = {"compliant": tbd, "issues": []}
        elif isinstance(tbd, list):
            governed["tbd_compliance"] = {
                "compliant": not any(
                    token in str(item).lower()
                    for item in tbd
                    for token in ("however", "violation", "non-compliant", "不合规")
                ),
                "issues": [str(item) for item in tbd],
            }
        elif not isinstance(tbd, dict):
            governed["tbd_compliance"] = {
                "compliant": False,
                "issues": [str(tbd)],
            }
        return governed

    @staticmethod
    def _require_keys(payload: dict[str, Any], keys: set[str], label: str) -> None:
        missing = keys - set(payload)
        if missing:
            raise RuntimeError(f"{label} output is missing keys: {', '.join(sorted(missing))}")

    @staticmethod
    def _render_markdown(
        planner: dict[str, Any],
        sections: list[dict[str, Any]],
        quality: dict[str, Any],
    ) -> str:
        lines = ["# TrialCompiler Controlled Protocol Draft", ""]
        synopsis = planner.get("protocol_synopsis", {})
        lines.extend(
            [
                "## Protocol Synopsis",
                "",
                json.dumps(synopsis, ensure_ascii=False, indent=2),
                "",
            ]
        )
        for section in sections:
            lines.extend(
                [
                    f"## {section['title']}",
                    "",
                    str(section["content"]),
                    "",
                    "**Source citations:** "
                    + ", ".join(map(str, section.get("source_citations", []))),
                    "",
                    "**TBD items:** "
                    + (", ".join(map(str, section.get("tbd_items", []))) or "None"),
                    "",
                ]
            )
        lines.extend(
            [
                "## Automated Quality Gate",
                "",
                "```json",
                json.dumps(quality, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
        return "\n".join(lines)
