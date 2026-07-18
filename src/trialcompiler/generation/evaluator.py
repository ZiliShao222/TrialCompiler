"""Evaluator-only benchmark runner kept outside the generative context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trialcompiler.generation.package import GenerativeCasePackage, extract_document_text
from trialcompiler.llm import OpenAICompatibleClient, load_prompt

CRITICAL_HIDDEN_TERMS = ("NCT05132439", "MOBILE IC", "PMC9862509")
ALLOWED_DIFFERENCE_CLASSES = {
    "equivalent",
    "different_but_defensible",
    "unsupported",
    "unsafe_or_unregistrable",
    "possible_leakage",
}


@dataclass(slots=True)
class BlindProtocolEvaluator:
    package: GenerativeCasePackage
    client: OpenAICompatibleClient
    prompt_path: Path

    def evaluate(
        self,
        output: str | Path,
        *,
        phase1_run: str | Path,
        phase2_run: str | Path,
    ) -> dict[str, Any]:
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        phase1 = self._load_run(phase1_run)
        phase2 = self._load_run(phase2_run)
        self._assert_uncontaminated_generation(phase1, "Phase 1")
        self._assert_uncontaminated_generation(phase2, "Phase 2")

        generation_outputs = {
            "phase1": self._generation_payload(phase1),
            "phase2": self._generation_payload(phase2),
        }
        generated_text = json.dumps(generation_outputs, ensure_ascii=False)
        deterministic_leaks = [
            term for term in CRITICAL_HIDDEN_TERMS if term.lower() in generated_text.lower()
        ]
        evaluator_materials = self._load_evaluator_materials()
        raw = self.client.complete_json(
            system_prompt=load_prompt(self.prompt_path),
            user_payload={
                "generation_outputs": generation_outputs,
                "evaluator_only_materials": evaluator_materials,
                "deterministic_leak_scan": {
                    "terms_checked": list(CRITICAL_HIDDEN_TERMS),
                    "detected_terms": deterministic_leaks,
                },
            },
        )
        governed = self._govern_result(raw, deterministic_leaks)
        result = {
            "run_type": "blind_protocol_benchmark_evaluation",
            "created_at": datetime.now(UTC).isoformat(),
            "model": self.client.config.model,
            "simulation_only": True,
            "not_clinical_or_regulatory_approval": True,
            "generation_materials_used_by_evaluator": True,
            "evaluator_materials_used": True,
            "evaluation": governed,
        }
        self._write_json(output_path / "evaluation.json", result)
        (output_path / "evaluation_report.md").write_text(
            self._render_report(result), encoding="utf-8"
        )
        return {
            "status": governed["gate_status"],
            "weighted_score": governed["weighted_score"],
            "critical_hard_fail": governed["critical_hard_fail"],
            "output": str(output_path),
        }

    @staticmethod
    def _generation_payload(run: dict[str, Any]) -> dict[str, Any]:
        """Expose generated deliverables, not internal audit logs, to blind scoring.

        Package-audit sanitization logs intentionally name the hidden terms they
        removed. Including those logs in the scored payload creates a false
        leakage signal and also reveals benchmark identifiers to the judge.
        """
        allowed = {
            "run_type",
            "model",
            "evidence_plan",
            "protocol_synopsis",
            "protocol_sections",
            "fact_reconciliation",
            "associated_artifacts",
            "quality_gate",
            "human_approval_required",
        }
        return {key: run[key] for key in allowed if key in run}

    @staticmethod
    def _load_run(path: str | Path) -> dict[str, Any]:
        candidate = Path(path)
        if candidate.is_dir():
            candidate = candidate / "run.json"
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Run payload must be an object: {candidate}")
        return payload

    @staticmethod
    def _assert_uncontaminated_generation(run: dict[str, Any], label: str) -> None:
        if run.get("evaluator_materials_used"):
            raise RuntimeError(f"{label} declares evaluator-only material usage")

    def _load_evaluator_materials(self) -> list[dict[str, Any]]:
        root = self.package.root / "03_EVALUATOR_ONLY"
        if not root.exists():
            raise FileNotFoundError(f"Evaluator-only directory not found: {root}")
        materials: list[dict[str, Any]] = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            text, warnings = extract_document_text(path)
            materials.append(
                {
                    "path": path.relative_to(self.package.root).as_posix(),
                    "text": text,
                    "extraction_warnings": warnings,
                }
            )
        return materials

    @staticmethod
    def _govern_result(raw: dict[str, Any], deterministic_leaks: list[str]) -> dict[str, Any]:
        required = {
            "rubric_scores",
            "hard_fails",
            "fact_checks",
            "difference_classifications",
            "leakage_audit",
            "weighted_score",
            "gate_status",
            "limitations",
        }
        missing = required - set(raw)
        if missing:
            raise RuntimeError(f"Evaluator output missing keys: {', '.join(sorted(missing))}")
        result = dict(raw)
        result["rubric_scores"] = BlindProtocolEvaluator._list_of_dicts(
            result.get("rubric_scores")
        )
        result["hard_fails"] = BlindProtocolEvaluator._list_of_dicts(
            result.get("hard_fails")
        )
        result["fact_checks"] = BlindProtocolEvaluator._list_of_dicts(
            result.get("fact_checks")
        )
        differences = BlindProtocolEvaluator._list_of_dicts(
            result.get("difference_classifications")
        )
        for item in differences:
            if item.get("classification") not in ALLOWED_DIFFERENCE_CLASSES:
                item["classification"] = "unsupported"
        result["difference_classifications"] = differences
        result["limitations"] = [str(value) for value in result.get("limitations", [])]

        try:
            model_reported_score = float(result.get("weighted_score", 0))
        except (TypeError, ValueError):
            model_reported_score = 0.0
        result["model_reported_weighted_score"] = max(
            0.0, min(100.0, model_reported_score)
        )
        weighted_numerator = 0.0
        total_weight = 0.0
        for item in result["rubric_scores"]:
            try:
                raw_score = max(0.0, min(4.0, float(item["raw_score_0_to_4"])))
                weight = max(0.0, float(item["weight"]))
            except (KeyError, TypeError, ValueError):
                continue
            item["raw_score_0_to_4"] = raw_score
            item["weight"] = weight
            item["deterministic_weighted_points"] = raw_score * weight / 4.0
            weighted_numerator += raw_score * weight
            total_weight += weight
        score = (
            100.0 * weighted_numerator / (4.0 * total_weight)
            if total_weight > 0
            else result["model_reported_weighted_score"]
        )
        result["weighted_score"] = round(max(0.0, min(100.0, score)), 2)
        result["score_recomputed_from_rubric"] = total_weight > 0
        critical = bool(deterministic_leaks) or any(
            bool(item.get("triggered"))
            and str(item.get("severity", "")).lower() == "critical"
            for item in result["hard_fails"]
        )
        result["critical_hard_fail"] = critical
        result["deterministic_leak_terms"] = deterministic_leaks
        result["requires_qualified_human_review"] = True
        if critical:
            result["gate_status"] = "gate_fail"
        elif result["weighted_score"] >= 85:
            result["gate_status"] = "candidate_for_qualified_human_revision"
        elif result["weighted_score"] >= 70:
            result["gate_status"] = "substantial_revision_required"
        else:
            result["gate_status"] = "major_redesign_required"
        return result

    @staticmethod
    def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _render_report(result: dict[str, Any]) -> str:
        evaluation = result["evaluation"]
        return "\n".join(
            [
                "# TrialCompiler Blind Benchmark Evaluation",
                "",
                "> Simulation-only benchmark output. This is not clinical, statistical, "
                "regulatory, or quality approval.",
                "",
                f"- Model: `{result['model']}`",
                f"- Weighted score: `{evaluation['weighted_score']:.2f}`",
                f"- Gate: `{evaluation['gate_status']}`",
                f"- Critical hard fail: `{evaluation['critical_hard_fail']}`",
                "",
                "## Full Auditable Result",
                "",
                "```json",
                json.dumps(evaluation, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
