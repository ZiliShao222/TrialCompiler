import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trialcompiler.generation import BlindProtocolEvaluator, GenerativeCasePackage


class _EvaluatorClient:
    config = SimpleNamespace(model="test-evaluator")

    def __init__(self, *, critical: bool = False) -> None:
        self.critical = critical

    def complete_json(self, *, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        assert "evaluator-only" in system_prompt
        assert user_payload["evaluator_only_materials"]
        return {
            "rubric_scores": [],
            "hard_fails": [
                {
                    "hard_fail_id": "HF01",
                    "triggered": self.critical,
                    "severity": "Critical",
                    "evidence": [],
                    "rationale": "test",
                }
            ],
            "fact_checks": [],
            "difference_classifications": [],
            "leakage_audit": {"passed": True, "findings": [], "evidence": []},
            "weighted_score": 95,
            "gate_status": "pass",
            "limitations": [],
        }


def _setup(tmp_path: Path) -> tuple[GenerativeCasePackage, Path, Path]:
    package_root = tmp_path / "package"
    for name in ("01_AI_VISIBLE_PHASE1", "02_AI_VISIBLE_PHASE2", "03_EVALUATOR_ONLY"):
        (package_root / name).mkdir(parents=True)
    (package_root / "01_AI_VISIBLE_PHASE1" / "brief.txt").write_text("brief", encoding="utf-8")
    (package_root / "02_AI_VISIBLE_PHASE2" / "decision.txt").write_text(
        "decision", encoding="utf-8"
    )
    (package_root / "03_EVALUATOR_ONLY" / "gold.json").write_text(
        json.dumps({"reference_design": {"randomized_n": 200}}), encoding="utf-8"
    )
    phase1 = tmp_path / "phase1.json"
    phase2 = tmp_path / "phase2.json"
    phase1.write_text(
        json.dumps({"run_type": "phase1", "evaluator_materials_used": False}),
        encoding="utf-8",
    )
    phase2.write_text(
        json.dumps({"run_type": "phase2", "evaluator_materials_used": False}),
        encoding="utf-8",
    )
    return GenerativeCasePackage(package_root), phase1, phase2


def test_blind_evaluator_keeps_hidden_material_outside_generation(tmp_path: Path) -> None:
    package, phase1, phase2 = _setup(tmp_path)
    evaluator = BlindProtocolEvaluator(
        package=package,
        client=_EvaluatorClient(),  # type: ignore[arg-type]
        prompt_path=Path(__file__).parents[1]
        / "prompts"
        / "agents"
        / "G8_blind_benchmark_evaluator.md",
    )
    output = tmp_path / "evaluation"

    result = evaluator.evaluate(output, phase1_run=phase1, phase2_run=phase2)

    saved = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert result["status"] == "candidate_for_qualified_human_revision"
    assert saved["simulation_only"] is True
    assert saved["not_clinical_or_regulatory_approval"] is True
    assert saved["evaluation"]["requires_qualified_human_review"] is True


def test_critical_hard_fail_overrides_high_weighted_score(tmp_path: Path) -> None:
    package, phase1, phase2 = _setup(tmp_path)
    evaluator = BlindProtocolEvaluator(
        package=package,
        client=_EvaluatorClient(critical=True),  # type: ignore[arg-type]
        prompt_path=Path(__file__).parents[1]
        / "prompts"
        / "agents"
        / "G8_blind_benchmark_evaluator.md",
    )

    result = evaluator.evaluate(tmp_path / "evaluation", phase1_run=phase1, phase2_run=phase2)

    assert result["weighted_score"] == 95
    assert result["critical_hard_fail"] is True
    assert result["status"] == "gate_fail"


def test_generation_payload_excludes_audit_log_hidden_identifiers() -> None:
    run = {
        "run_type": "generative_protocol_phase2_revision",
        "protocol_sections": [{"section_id": "1", "content": "clean"}],
        "package_audit": {"sanitization_events": ["Redacted hidden reference NCT05132439"]},
        "input_lineage": {"private_path": "03_EVALUATOR_ONLY"},
    }

    payload = BlindProtocolEvaluator._generation_payload(run)

    serialized = json.dumps(payload)
    assert "NCT05132439" not in serialized
    assert "03_EVALUATOR_ONLY" not in serialized
    assert payload["protocol_sections"][0]["content"] == "clean"


def test_govern_result_recomputes_score_from_rubric() -> None:
    raw = {
        "rubric_scores": [
            {"rubric_id": "R01", "raw_score_0_to_4": 3, "weight": 1},
            {"rubric_id": "R02", "raw_score_0_to_4": 4, "weight": 1},
        ],
        "hard_fails": [],
        "fact_checks": [],
        "difference_classifications": [],
        "leakage_audit": {"passed": True},
        "weighted_score": 12,
        "gate_status": "pass",
        "limitations": [],
    }

    governed = BlindProtocolEvaluator._govern_result(raw, [])

    assert governed["model_reported_weighted_score"] == 12
    assert governed["weighted_score"] == 87.5
    assert governed["score_recomputed_from_rubric"] is True
