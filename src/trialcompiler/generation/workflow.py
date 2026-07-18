"""Controlled multi-stage workflow for evidence-bounded protocol generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trialcompiler.generation.package import GenerativeCasePackage
from trialcompiler.generation.validators import (
    build_phase2_remediation_plan,
    validate_phase2_candidate,
)
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

    def run_phase2(
        self,
        output: str | Path,
        *,
        phase1_run: str | Path,
        full: bool = True,
    ) -> dict[str, Any]:
        """Revise a Phase 1 draft using only the Phase 1 and Phase 2 visible material."""
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        checkpoint_path = output_path / "checkpoints"
        checkpoint_path.mkdir(parents=True, exist_ok=True)

        phase1_path = Path(phase1_run)
        if phase1_path.is_dir():
            phase1_path = phase1_path / "run.json"
        if not phase1_path.exists():
            raise FileNotFoundError(f"Phase 1 run not found: {phase1_path}")
        phase1 = json.loads(phase1_path.read_text(encoding="utf-8"))
        if phase1.get("run_type") != "generative_protocol_phase1":
            raise RuntimeError("--phase1-run must point to a Phase 1 generation run")
        if phase1.get("evaluator_materials_used"):
            raise RuntimeError("Refusing a Phase 1 run contaminated by evaluator-only material")
        if phase1.get("phase2_materials_used"):
            raise RuntimeError("Refusing a parent run that already used Phase 2 material")
        if full and len(phase1.get("protocol_sections", [])) != len(SECTION_SPECS):
            raise RuntimeError("Full Phase 2 revision requires all nine Phase 1 sections")

        source_payload = self.package.prompt_payload("phase2", strict=True)
        prompt_names = (
            "G4_phase2_fact_reconciler.md",
            "G5_phase2_incremental_reviser.md",
            "G6_associated_artifact_compiler.md",
            "G7_phase2_quality_judge.md",
        )
        checkpoint_context = {
            "phase1_sha256": self._sha256_file(phase1_path),
            "phase2_visible_payload_sha256": self._sha256_payload(source_payload),
            "prompt_sha256": {
                name: self._sha256_file(self.prompt_root / name) for name in prompt_names
            },
            "model": self.client.config.model,
            "full": full,
        }
        checkpoint_context["input_digest"] = self._sha256_payload(checkpoint_context)
        context_path = checkpoint_path / "checkpoint_context.json"
        if context_path.exists():
            prior_context = json.loads(context_path.read_text(encoding="utf-8"))
            if prior_context.get("input_digest") != checkpoint_context["input_digest"]:
                raise RuntimeError(
                    "Phase 2 inputs changed but the output directory contains stale checkpoints; "
                    "use a new output directory or remove its checkpoints"
                )
        self._write_json(context_path, checkpoint_context)
        self._write_json(checkpoint_path / "package_payload.json", source_payload)
        self._write_json(checkpoint_path / "phase1_input.json", phase1)

        fact_checkpoint = checkpoint_path / "fact_reconciliation.json"
        if fact_checkpoint.exists():
            reconciliation = json.loads(fact_checkpoint.read_text(encoding="utf-8"))
        else:
            reconciliation = self.client.complete_json(
                system_prompt=load_prompt(self.prompt_root / "G4_phase2_fact_reconciler.md"),
                user_payload={
                    "phase1_planner": phase1.get("planner", {}),
                    "phase1_quality_gate": phase1.get("quality_gate", {}),
                    "phase2_source_documents": source_payload["source_documents"],
                    "visibility_policy": source_payload["visibility_policy"],
                },
            )
        self._require_keys(
            reconciliation,
            {
                "active_fact_sheet",
                "decision_log",
                "change_plan",
                "superseded_values",
                "open_issues",
            },
            "G4 Phase 2 fact reconciler",
        )
        self._write_json(fact_checkpoint, reconciliation)

        prior_sections = phase1.get("protocol_sections", [])
        sections: list[dict[str, Any]] = []
        if full:
            for index, section_spec in enumerate(SECTION_SPECS, start=1):
                section_checkpoint = checkpoint_path / f"revised_section_{index:02d}.json"
                prior = prior_sections[index - 1] if index <= len(prior_sections) else {}
                if section_checkpoint.exists():
                    result = json.loads(section_checkpoint.read_text(encoding="utf-8"))
                else:
                    result = self.client.complete_json(
                        system_prompt=load_prompt(
                            self.prompt_root / "G5_phase2_incremental_reviser.md"
                        ),
                        user_payload={
                            "section_number": index,
                            "section_specification": section_spec,
                            "prior_section": prior,
                            "fact_reconciliation": reconciliation,
                            "phase2_source_documents": source_payload["source_documents"],
                            "visibility_policy": source_payload["visibility_policy"],
                        },
                    )
                self._require_keys(
                    result,
                    {
                        "title",
                        "content",
                        "fact_ids",
                        "source_citations",
                        "tbd_items",
                        "change_summary",
                        "superseded_value_check",
                    },
                    f"G5 revised section {index}",
                )
                sections.append(result)
                self._write_json(section_checkpoint, result)

        artifact_checkpoint = checkpoint_path / "associated_artifacts.json"
        if artifact_checkpoint.exists():
            artifacts = json.loads(artifact_checkpoint.read_text(encoding="utf-8"))
        else:
            artifacts = self.client.complete_json(
                system_prompt=load_prompt(self.prompt_root / "G6_associated_artifact_compiler.md"),
                user_payload={
                    "fact_reconciliation": reconciliation,
                    "revised_protocol_sections": sections,
                    "phase2_source_documents": source_payload["source_documents"],
                    "visibility_policy": source_payload["visibility_policy"],
                },
            )
        self._require_keys(
            artifacts,
            {
                "trial_fact_sheet",
                "schedule_of_activities",
                "primary_estimand",
                "sample_size_and_statistics",
                "fda_regulatory_rationale",
                "nmpa_regulatory_rationale",
                "site_and_recruitment_plan",
                "change_impact_matrix",
                "superseded_value_scan",
                "open_issues_register",
            },
            "G6 associated artifact compiler",
        )
        self._write_json(artifact_checkpoint, artifacts)

        quality_checkpoint = checkpoint_path / "phase2_quality_gate.json"
        if quality_checkpoint.exists():
            quality = json.loads(quality_checkpoint.read_text(encoding="utf-8"))
        else:
            quality = self.client.complete_json(
                system_prompt=load_prompt(self.prompt_root / "G7_phase2_quality_judge.md"),
                user_payload={
                    "fact_reconciliation": reconciliation,
                    "revised_protocol_sections": sections,
                    "associated_artifacts": artifacts,
                    "visible_source_documents": source_payload["source_documents"],
                    "visible_source_paths": [
                        item["path"] for item in source_payload["source_documents"]
                    ],
                    "visibility_policy": source_payload["visibility_policy"],
                },
            )
        self._require_keys(
            quality,
            {"gate_status", "findings", "unsupported_claims", "tbd_compliance", "limitations"},
            "G7 Phase 2 quality judge",
        )
        quality = self._govern_quality_output(quality)
        deterministic_findings = validate_phase2_candidate(reconciliation, sections, artifacts)
        quality["deterministic_findings"] = deterministic_findings
        quality["remediation_plan"] = build_phase2_remediation_plan(deterministic_findings)
        if deterministic_findings:
            quality["gate_status"] = "blocked_missing_evidence"
            quality["findings"].extend(
                f"{item['finding_id']}: {item['message']}" for item in deterministic_findings
            )
            quality["limitations"].append(
                "The machine gate was blocked by deterministic findings that cannot be "
                "overridden by the language-model judge."
            )
        self._write_json(quality_checkpoint, quality)

        audit = self.package.audit("phase2").to_dict()
        gate_status = quality.get("gate_status")
        run_status = (
            "blocked_machine_gate"
            if gate_status in {"blocked", "blocked_missing_evidence"}
            else "awaiting_qualified_human_review"
        )
        run = {
            "schema_version": "1.0",
            "run_type": "generative_protocol_phase2_revision",
            "status": run_status,
            "created_at": datetime.now(UTC).isoformat(),
            "model": self.client.config.model,
            "package_audit": audit,
            "input_lineage": checkpoint_context,
            "phase1_run": str(phase1_path),
            "fact_reconciliation": reconciliation,
            "protocol_sections": sections,
            "associated_artifacts": artifacts,
            "quality_gate": quality,
            "human_approval_required": True,
            "phase2_materials_used": True,
            "evaluator_materials_used": False,
        }
        self._write_json(output_path / "run.json", run)
        (output_path / "revised_protocol.md").write_text(
            self._render_phase2_markdown(reconciliation, sections, artifacts, quality),
            encoding="utf-8",
        )
        self._write_json(output_path / "package_audit.json", audit)
        return {
            "status": run_status,
            "output": str(output_path),
            "quality_gate": quality.get("gate_status"),
            "sections_revised": len(sections),
            "associated_artifacts_generated": len(artifacts),
            "package_audit_passed": audit["passed"],
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _sha256_payload(payload: dict[str, Any]) -> str:
        normalized = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

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
        else:
            tbd = dict(tbd)
            tbd["compliant"] = bool(tbd.get("compliant", False))
            issues = tbd.get("issues", [])
            issues = issues if isinstance(issues, list) else [str(issues)]
            if not tbd["compliant"] and all(
                str(item).strip().lower() in {"", "compliant"} for item in issues
            ):
                issues = ["TBD compliance was marked false without an actionable explanation."]
            tbd["issues"] = [str(item) for item in issues]
            governed["tbd_compliance"] = tbd
        if governed["gate_status"] == "pass_for_qualified_human_review" and (
            governed["unsupported_claims"] or not governed["tbd_compliance"].get("compliant", False)
        ):
            governed["gate_status"] = "revise_before_human_review"
            governed["limitations"].append(
                "The machine gate was downgraded because unsupported claims or unresolved "
                "TBD-boundary violations remain."
            )
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

    @staticmethod
    def _render_phase2_markdown(
        reconciliation: dict[str, Any],
        sections: list[dict[str, Any]],
        artifacts: dict[str, Any],
        quality: dict[str, Any],
    ) -> str:
        lines = ["# TrialCompiler Phase 2 Incremental Revision", ""]
        lines.extend(
            [
                "## Controlled Fact Reconciliation",
                "",
                "```json",
                json.dumps(reconciliation, ensure_ascii=False, indent=2),
                "```",
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
                    "**Change summary:** " + str(section.get("change_summary", "")),
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
                "## Associated Controlled Artifacts",
                "",
                "```json",
                json.dumps(artifacts, ensure_ascii=False, indent=2),
                "```",
                "",
                "## Phase 2 Quality Gate",
                "",
                "```json",
                json.dumps(quality, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
        return "\n".join(lines)
