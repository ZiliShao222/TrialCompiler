from trialcompiler.generation.validators import validate_phase2_candidate


def _candidate() -> tuple[dict, list[dict], dict]:
    reconciliation = {
        "source": "SYNTHETIC FDA meeting minutes",
        "claim": "FDA explicitly accepts the endpoint",
    }
    sections = [
        {"content": "No formal alpha allocation or hierarchical testing is planned."},
        {"content": "Death is handled using multiple imputation under MAR."},
    ]
    artifacts = {
        "primary_estimand": {"population": "All randomized participants"},
        "sample_size_and_statistics": {
            "target_sample_size": 220,
            "power_calculation": {
                "effect_size": 20,
                "standard_deviation": 65,
                "alpha": 0.05,
                "dropout_rate": 0.15,
                "power": 0.85,
            },
            "analysis_populations": {
                "full_analysis_set": (
                    "All randomized subjects with at least one dose and at least one "
                    "post-baseline assessment."
                )
            },
            "statistical_methods": {
                "secondary_endpoints": "Multiplicity controlled using hierarchical testing."
            },
        },
    }
    return reconciliation, sections, artifacts


def test_validator_catches_independent_reviewer_findings() -> None:
    findings = validate_phase2_candidate(*_candidate())
    ids = {item["finding_id"] for item in findings}
    assert ids == {
        "DET-REG-001",
        "DET-STAT-001",
        "DET-STAT-002",
        "DET-STAT-003",
        "DET-STAT-004",
    }


def test_validator_accepts_reproducible_minimal_statistics() -> None:
    reconciliation, sections, artifacts = _candidate()
    reconciliation = {"source": "Sponsor decision", "claim": "Candidate design"}
    sections = [{"content": "Secondary endpoints are descriptive."}]
    artifacts["sample_size_and_statistics"]["target_sample_size"] = 500
    artifacts["sample_size_and_statistics"]["analysis_populations"] = {
        "full_analysis_set": "All randomized participants"
    }
    findings = validate_phase2_candidate(reconciliation, sections, artifacts)
    assert findings == []
