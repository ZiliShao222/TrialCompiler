import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trialcompiler.generation import GenerativeCasePackage
from trialcompiler.generation.workflow import SECTION_SPECS, ProtocolGenerationWorkflow


def test_quality_output_governs_list_shaped_tbd_compliance() -> None:
    output = ProtocolGenerationWorkflow._govern_quality_output(
        {
            "gate_status": "revise_before_human_review",
            "findings": [],
            "unsupported_claims": [],
            "tbd_compliance": [
                "TBD items are listed.",
                "However, declarative text violates the TBD boundary.",
            ],
            "limitations": [],
        }
    )
    assert output["tbd_compliance"]["compliant"] is False
    assert len(output["tbd_compliance"]["issues"]) == 2


class _Phase2Client:
    config = SimpleNamespace(model="test-model")

    def complete_json(self, *, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if "fact-governance" in system_prompt:
            return {
                "active_fact_sheet": [],
                "decision_log": [],
                "change_plan": [],
                "superseded_values": [],
                "open_issues": [],
            }
        if "incremental section reviser" in system_prompt:
            return {
                "title": user_payload["section_specification"],
                "content": "Revised candidate section.",
                "fact_ids": [],
                "source_citations": [],
                "tbd_items": [],
                "change_summary": "Applied Phase 2 constraints.",
                "superseded_value_check": {
                    "checked_terms": [],
                    "residual_terms": [],
                    "status": "clear",
                },
            }
        if "controlled artifact compiler" in system_prompt:
            return {
                "trial_fact_sheet": {},
                "schedule_of_activities": {},
                "primary_estimand": {},
                "sample_size_and_statistics": {},
                "fda_regulatory_rationale": {},
                "nmpa_regulatory_rationale": {},
                "site_and_recruitment_plan": {},
                "change_impact_matrix": [],
                "superseded_value_scan": [],
                "open_issues_register": [],
            }
        return {
            "gate_status": "pass_for_qualified_human_review",
            "findings": [],
            "unsupported_claims": [],
            "tbd_compliance": True,
            "limitations": [],
        }


def test_phase2_revision_excludes_evaluator_material_and_writes_all_artifacts(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "package"
    for directory in ("01_AI_VISIBLE_PHASE1", "02_AI_VISIBLE_PHASE2", "03_EVALUATOR_ONLY"):
        (package_root / directory).mkdir(parents=True)
    (package_root / "01_AI_VISIBLE_PHASE1" / "brief.txt").write_text(
        "Visible evidence", encoding="utf-8"
    )
    (package_root / "02_AI_VISIBLE_PHASE2" / "decision.txt").write_text(
        "Synthetic sponsor decision", encoding="utf-8"
    )
    (package_root / "03_EVALUATOR_ONLY" / "gold.txt").write_text(
        "MOBILE IC", encoding="utf-8"
    )
    phase1_dir = tmp_path / "phase1"
    phase1_dir.mkdir()
    (phase1_dir / "run.json").write_text(
        json.dumps(
                {
                    "run_type": "generative_protocol_phase1",
                    "planner": {},
                "quality_gate": {},
                "protocol_sections": [
                    {"title": spec, "content": "Prior"} for spec in SECTION_SPECS
                ],
                    "evaluator_materials_used": False,
                    "phase2_materials_used": False,
                }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "phase2"
    workflow = ProtocolGenerationWorkflow(
        package=GenerativeCasePackage(package_root),
        client=_Phase2Client(),  # type: ignore[arg-type]
        prompt_root=Path(__file__).parents[1] / "prompts" / "agents",
    )

    result = workflow.run_phase2(output, phase1_run=phase1_dir)

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    payload = json.loads(
        (output / "checkpoints" / "package_payload.json").read_text(encoding="utf-8")
    )
    assert result["sections_revised"] == len(SECTION_SPECS)
    assert run["phase2_materials_used"] is True
    assert run["evaluator_materials_used"] is False
    assert len(run["associated_artifacts"]) == 10
    assert all("03_EVALUATOR_ONLY" not in item["path"] for item in payload["source_documents"])
