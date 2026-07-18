"""Deterministic safety checks for generated Phase 2 protocol candidates."""

from __future__ import annotations

import json
import math
import re
from statistics import NormalDist
from typing import Any


def _text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _finding(
    finding_id: str,
    category: str,
    message: str,
    evidence: str,
    *,
    severity: str = "major",
) -> dict[str, str]:
    return {
        "finding_id": finding_id,
        "category": category,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "source": "deterministic_phase2_validator",
    }


def _sample_size_check(artifacts: dict[str, Any]) -> dict[str, str] | None:
    statistics = artifacts.get("sample_size_and_statistics", {})
    calculation = statistics.get("power_calculation", {})
    try:
        total = float(statistics["target_sample_size"])
        effect = abs(float(calculation["effect_size"]))
        sd = float(calculation["standard_deviation"])
        alpha = float(calculation["alpha"])
        dropout = float(calculation["dropout_rate"])
        power = float(calculation["power"])
    except (KeyError, TypeError, ValueError):
        return _finding(
            "DET-STAT-001",
            "sample_size_reproducibility",
            "The sample-size claim is not machine-reproducible from the generated artifact.",
            "One or more of target_sample_size, effect_size, standard_deviation, alpha, "
            "dropout_rate, or power is missing or non-numeric.",
        )
    if not (effect > 0 and sd > 0 and 0 < alpha < 1 and 0 <= dropout < 1 and 0.5 < power < 1):
        return _finding(
            "DET-STAT-001",
            "sample_size_reproducibility",
            "The generated sample-size inputs are outside valid numeric ranges.",
            f"n={total}, effect={effect}, sd={sd}, alpha={alpha}, dropout={dropout}, power={power}",
        )

    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    evaluable_per_arm = 2 * ((z_alpha + z_power) * sd / effect) ** 2
    required_total = math.ceil(2 * evaluable_per_arm / (1 - dropout))
    achieved_z = effect * math.sqrt((total * (1 - dropout)) / (4 * sd**2)) - z_alpha
    approximate_power = normal.cdf(achieved_z)
    if total + 1e-9 < required_total:
        return _finding(
            "DET-STAT-001",
            "sample_size_reproducibility",
            "The claimed total sample size is insufficient under the generated two-arm "
            "normal-approximation assumptions.",
            f"Claimed n={total:g}; reproducible approximation requires n>={required_total}; "
            f"approximate achieved power={approximate_power:.3f}. A different MMRM or "
            "simulation-based derivation must provide executable assumptions and output.",
            severity="critical",
        )
    return None


def validate_phase2_candidate(
    reconciliation: dict[str, Any],
    sections: list[dict[str, Any]],
    artifacts: dict[str, Any],
) -> list[dict[str, str]]:
    """Return conservative deterministic findings that the LLM gate cannot override."""
    findings: list[dict[str, str]] = []
    candidate_text = _text(
        {
            "fact_reconciliation": reconciliation,
            "protocol_sections": sections,
            "associated_artifacts": artifacts,
        }
    )
    lowered = candidate_text.lower()

    sample_size = _sample_size_check(artifacts)
    if sample_size:
        findings.append(sample_size)

    synthetic_source = bool(re.search(r"synthetic|模拟|妯.{0,3}嫙", candidate_text, re.I))
    authority_claim = bool(
        re.search(
            r"(?:fda|cde).{0,80}(?:explicitly\s+accept|acceptance|requires?|endorsed?|"
            r"satisf(?:y|ies).{0,20}expectation)",
            candidate_text,
            re.I,
        )
    )
    if synthetic_source and authority_claim:
        findings.append(
            _finding(
                "DET-REG-001",
                "synthetic_regulatory_authority",
                "A synthetic regulator input appears to be restated as an authoritative "
                "FDA/CDE acceptance, requirement, endorsement, or satisfied expectation.",
                "Synthetic scenario materials may guide testing but must remain explicitly "
                "non-binding at every downstream claim.",
                severity="critical",
            )
        )

    estimand = _text(artifacts.get("primary_estimand", {})).lower()
    populations = _text(
        artifacts.get("sample_size_and_statistics", {}).get("analysis_populations", {})
    ).lower()
    if "all randomized" in estimand and (
        "at least one dose" in populations or "at least one post-baseline" in populations
    ):
        findings.append(
            _finding(
                "DET-STAT-002",
                "estimand_population_mismatch",
                "The estimand targets all randomized participants, but the generated full "
                "analysis set applies post-randomization dose or outcome requirements.",
                "The analysis population can exclude randomized participants and therefore "
                "does not implement the stated estimand population.",
                severity="critical",
            )
        )

    no_hierarchy = bool(
        re.search(r"no\s+(?:formal\s+)?(?:alpha allocation|hierarchical testing)", lowered)
    )
    uses_hierarchy = bool(re.search(r"multiplicity.{0,40}hierarchical testing", lowered))
    if no_hierarchy and uses_hierarchy:
        findings.append(
            _finding(
                "DET-STAT-003",
                "multiplicity_strategy_conflict",
                "The candidate both rejects formal hierarchical testing and prescribes a "
                "hierarchical multiplicity procedure.",
                "Protocol sections and associated statistical artifacts contain incompatible "
                "secondary-endpoint testing strategies.",
            )
        )

    if "death" in lowered and "mar" in lowered and "multiple imputation" in lowered:
        findings.append(
            _finding(
                "DET-STAT-004",
                "terminal_event_estimand_risk",
                "Death appears inside a MAR multiple-imputation strategy for a functional "
                "outcome that is undefined after death.",
                "A qualified statistician must specify a clinically interpretable terminal-"
                "event strategy and corresponding sensitivity analyses.",
            )
        )

    return findings


REMEDIATION_RULES: dict[str, dict[str, Any]] = {
    "DET-STAT-001": {
        "owner_role": "qualified_biostatistician",
        "affected_artifacts": [
            "trial_fact_sheet",
            "sample_size_and_statistics",
            "protocol_section_07",
            "schedule_of_activities",
            "site_and_recruitment_plan",
        ],
        "required_actions": [
            "Choose and document one evidence-supported effect size and variance assumption.",
            "Either increase target enrollment to the reproducible requirement or attach an "
            "executable MMRM/simulation derivation supporting a different total.",
            "Propagate the approved total to recruitment, SoA, synopsis, and statistics outputs.",
        ],
        "exit_criteria": [
            "All six numeric inputs are machine-readable and within valid ranges.",
            "The target total meets the reproduced requirement, or an executable alternative "
            "derivation and output are attached.",
        ],
    },
    "DET-REG-001": {
        "owner_role": "qualified_regulatory_reviewer",
        "affected_artifacts": [
            "fact_reconciliation",
            "fda_regulatory_rationale",
            "nmpa_regulatory_rationale",
            "protocol_section_09",
        ],
        "required_actions": [
            "Relabel every simulated FDA/CDE statement as synthetic and non-binding.",
            "Replace acceptance, endorsement, and requirement language with a sponsor proposal "
            "that remains subject to agency feedback.",
        ],
        "exit_criteria": [
            "No synthetic source is represented as an actual agency decision.",
            "Every regional claim cites public guidance or is explicitly marked TBD/proposal.",
        ],
    },
    "DET-STAT-002": {
        "owner_role": "qualified_biostatistician",
        "affected_artifacts": [
            "primary_estimand",
            "sample_size_and_statistics.analysis_populations",
            "protocol_section_02",
            "protocol_section_07",
        ],
        "required_actions": [
            "Choose whether the estimand population is all randomized participants or a "
            "post-randomization subset.",
            "Align the FAS definition, intercurrent-event strategy, missing-data rules, and "
            "sensitivity analyses to that choice.",
        ],
        "exit_criteria": [
            "Estimand population and FAS inclusion rules are logically identical.",
            "No randomized participant is silently removed by dose or post-baseline criteria.",
        ],
    },
    "DET-STAT-003": {
        "owner_role": "qualified_biostatistician",
        "affected_artifacts": [
            "sample_size_and_statistics",
            "protocol_section_02",
            "protocol_section_07",
        ],
        "required_actions": [
            "Select one multiplicity strategy and remove contradictory hierarchy language.",
            "Define the ordered hypotheses, alpha flow, and handling after a failed test.",
        ],
        "exit_criteria": [
            "All sections prescribe the same multiplicity strategy.",
        ],
    },
    "DET-STAT-004": {
        "owner_role": "qualified_biostatistician_and_clinician",
        "affected_artifacts": [
            "primary_estimand",
            "sample_size_and_statistics",
            "protocol_section_02",
            "protocol_section_06",
            "protocol_section_07",
        ],
        "required_actions": [
            "Define death, amputation, and revascularization as explicit intercurrent events.",
            "Specify clinically interpretable composite, while-on-treatment, hypothetical, or "
            "principal-stratum handling instead of ordinary MAR imputation.",
            "Add aligned sensitivity analyses for terminal events.",
        ],
        "exit_criteria": [
            "Death is not represented as an ordinary MAR-missing functional outcome.",
            "Terminal-event handling is consistent across estimand and analysis sections.",
        ],
    },
}


def build_phase2_remediation_plan(
    findings: list[dict[str, str]],
) -> dict[str, Any]:
    """Convert blocking findings into an auditable, role-gated revision package."""
    work_items: list[dict[str, Any]] = []
    for finding in findings:
        finding_id = finding["finding_id"]
        rule = REMEDIATION_RULES.get(finding_id)
        if rule is None:
            continue
        work_items.append(
            {
                "work_item_id": f"REMEDIATE-{finding_id}",
                "finding_id": finding_id,
                "severity": finding["severity"],
                **rule,
                "status": "pending_qualified_revision",
                "automatic_application_allowed": False,
            }
        )
    return {
        "plan_status": "blocked_pending_qualified_revision" if work_items else "clear",
        "work_items": work_items,
        "required_sequence": [
            "qualified_decision",
            "fact_reconciliation_update",
            "cross_artifact_propagation",
            "deterministic_revalidation",
            "independent_quality_review",
        ],
        "release_condition": (
            "All work items must meet exit criteria and deterministic revalidation must return "
            "zero blocking findings."
        ),
    }
