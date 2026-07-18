"""Paired ablation evaluation for uncertainty-governed review agents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import mean

from trialcompiler.evaluation.uncertainty import OutcomePrediction, evaluate_predictions


class ExperimentArm(StrEnum):
    RULES = "A_rules"
    SINGLE_LLM = "B_single_llm"
    FIXED_RAG = "C_fixed_rag"
    PASSIVE_UQ = "D_passive_uq"
    ACTIVE_ACQUISITION = "E_active_acquisition"
    ACTIVE_WITH_FAITHFULNESS = "F_active_with_faithfulness"


@dataclass(frozen=True, slots=True)
class AblationRecord:
    case_id: str
    arm: ExperimentArm
    split: str
    patch_valid: bool
    selected_action: str
    probability: float | None = None
    acquisition_count: int = 0
    evidence_cost: float = 0.0
    necessity_flip: bool | None = None
    contrastive_effect: bool | None = None

    @classmethod
    def from_dict(cls, item: dict) -> AblationRecord:
        return cls(**{**item, "arm": ExperimentArm(item["arm"])})

    def validate(self) -> list[str]:
        failures: list[str] = []
        if not self.case_id.strip():
            failures.append("case_id_required")
        if self.split not in {"calibration", "test"}:
            failures.append("invalid_split")
        if self.selected_action not in {
            "commit_candidate",
            "defer_to_human",
            "abstain",
        }:
            failures.append("invalid_selected_action")
        if self.probability is not None and not 0 <= self.probability <= 1:
            failures.append("probability_out_of_range")
        if self.acquisition_count < 0:
            failures.append("acquisition_count_out_of_range")
        if self.evidence_cost < 0:
            failures.append("evidence_cost_out_of_range")
        return failures


def ablation_dataset_digest(records: list[AblationRecord]) -> str:
    payload = [
        asdict(item)
        for item in sorted(records, key=lambda item: (item.case_id, str(item.arm)))
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_ablation_records(records: list[AblationRecord]) -> None:
    if not records:
        raise ValueError("ablation_records_required")
    failures = [failure for record in records for failure in record.validate()]
    keys = [(record.case_id, record.arm) for record in records]
    if len(keys) != len(set(keys)):
        failures.append("duplicate_case_arm")
    split_by_case: dict[str, set[str]] = {}
    for record in records:
        split_by_case.setdefault(record.case_id, set()).add(record.split)
    if any(len(splits) > 1 for splits in split_by_case.values()):
        failures.append("case_leaks_across_splits")
    arms = {record.arm for record in records}
    case_sets = {
        arm: {record.case_id for record in records if record.arm is arm} for arm in arms
    }
    if len({frozenset(case_ids) for case_ids in case_sets.values()}) > 1:
        failures.append("unpaired_arm_case_sets")
    if failures:
        raise ValueError(", ".join(sorted(set(failures))))


def _arm_metrics(records: list[AblationRecord]) -> dict[str, object]:
    committed = [item for item in records if item.selected_action == "commit_candidate"]
    failures = [item for item in records if not item.patch_valid]
    deferred_failures = [
        item
        for item in failures
        if item.selected_action in {"defer_to_human", "abstain"}
    ]
    probability_records = [item for item in records if item.probability is not None]
    uncertainty = None
    if len(probability_records) == len(records):
        uncertainty = evaluate_predictions(
            [
                OutcomePrediction(
                    prediction_id=f"{item.arm}:{item.case_id}",
                    probability=float(item.probability),
                    outcome=item.patch_valid,
                    split=item.split,
                )
                for item in records
            ]
        )
    faithfulness = [item for item in records if item.necessity_flip is not None]
    contrastive = [item for item in records if item.contrastive_effect is not None]
    return {
        "n": len(records),
        "patch_valid_rate": mean(item.patch_valid for item in records),
        "auto_commit_rate": len(committed) / len(records),
        "error_auto_commit_rate": sum(not item.patch_valid for item in committed)
        / len(records),
        "selective_risk": (
            sum(not item.patch_valid for item in committed) / len(committed)
            if committed
            else None
        ),
        "defer_recall_on_failures": (
            len(deferred_failures) / len(failures) if failures else None
        ),
        "mean_acquisitions": mean(item.acquisition_count for item in records),
        "mean_evidence_cost": mean(item.evidence_cost for item in records),
        "uncertainty": uncertainty,
        "necessity_flip_rate": (
            mean(bool(item.necessity_flip) for item in faithfulness)
            if faithfulness
            else None
        ),
        "contrastive_sensitivity": (
            mean(bool(item.contrastive_effect) for item in contrastive)
            if contrastive
            else None
        ),
    }


def evaluate_ablation(
    records: list[AblationRecord],
    *,
    reference_arm: ExperimentArm = ExperimentArm.FIXED_RAG,
    minimum_cases: int = 30,
) -> dict[str, object]:
    if minimum_cases < 1:
        raise ValueError("minimum_cases_must_be_positive")
    validate_ablation_records(records)
    by_arm = {
        arm: sorted(
            (item for item in records if item.arm is arm), key=lambda item: item.case_id
        )
        for arm in sorted({item.arm for item in records}, key=str)
    }
    metrics = {str(arm): _arm_metrics(items) for arm, items in by_arm.items()}
    comparisons: dict[str, dict[str, float]] = {}
    if reference_arm in by_arm:
        reference = metrics[str(reference_arm)]
        for arm in by_arm:
            if arm is reference_arm:
                continue
            current = metrics[str(arm)]
            comparisons[str(arm)] = {
                "delta_patch_valid_rate": float(current["patch_valid_rate"])
                - float(reference["patch_valid_rate"]),
                "delta_error_auto_commit_rate": float(current["error_auto_commit_rate"])
                - float(reference["error_auto_commit_rate"]),
                "delta_mean_evidence_cost": float(current["mean_evidence_cost"])
                - float(reference["mean_evidence_cost"]),
            }
    splits = sorted({item.split for item in records})
    complete_arms = set(by_arm) == set(ExperimentArm)
    paired_cases = len({item.case_id for item in records})
    claim_allowed = splits == ["test"] and complete_arms and paired_cases >= minimum_cases
    return {
        "schema": "trialcompiler.uncertainty_ablation/v1",
        "dataset_digest": ablation_dataset_digest(records),
        "paired_cases": paired_cases,
        "minimum_cases": minimum_cases,
        "complete_six_arm_matrix": complete_arms,
        "splits": splits,
        "arms": metrics,
        "comparisons_vs_reference": comparisons,
        "reference_arm": str(reference_arm),
        "result_claim_allowed": claim_allowed,
        "claim_note": (
            "held_out_complete_ablation"
            if claim_allowed
            else "insufficient_cases_arms_or_held_out_separation"
        ),
    }
