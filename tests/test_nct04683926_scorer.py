import json
from pathlib import Path

from scripts.score_nct04683926_benchmark import score_benchmark


def _write_case(tmp_path: Path, tests: list[dict], findings: list[dict]) -> tuple[Path, Path]:
    benchmark = tmp_path / "benchmark"
    run = tmp_path / "run"
    (benchmark / "gold").mkdir(parents=True)
    run.mkdir()
    (benchmark / "gold" / "gold_tests.json").write_text(
        json.dumps({"case_id": "NCT04683926", "gold_version": "test", "tests": tests}),
        encoding="utf-8",
    )
    (run / "workflow_state.json").write_text(
        json.dumps({"findings": findings}), encoding="utf-8"
    )
    (run / "run_summary.json").write_text(
        json.dumps({"release_status": "requires_qualified_human_review"}),
        encoding="utf-8",
    )
    return benchmark, run


def _water_finding(message: str) -> dict:
    return {
        "finding_id": "water-1",
        "finding_type": "definition_conflict",
        "fact_ids": ["F018"],
        "requires_human_review": True,
        "message": message,
    }


def test_correct_semantic_match_is_true_positive(tmp_path: Path) -> None:
    tests = [{"id": "TC-SD-001", "expected_label": "hard_operational_instruction_conflict"}]
    findings = [_water_finding(
        "Synopsis says no water is allowed, while the protocol body says only water is allowed; "
        "these instructions are logically contradictory."
    )]

    result = score_benchmark(*_write_case(tmp_path, tests, findings))

    assert result["counts"] == {
        "true_positive": 1,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 0,
        "negative_control_false_positive": 0,
    }
    assert result["tests"][0]["matching_finding_ids"] == ["water-1"]
    assert all(check["passed"] for check in result["tests"][0]["evidence"][0]["checks"])


def test_keyword_only_claim_is_false_positive_and_miss(tmp_path: Path) -> None:
    tests = [{"id": "TC-SD-001", "expected_label": "hard_operational_instruction_conflict"}]
    findings = [_water_finding("Potential water restriction conflict involving F018.")]

    result = score_benchmark(*_write_case(tmp_path, tests, findings))

    assert result["counts"]["true_positive"] == 0
    assert result["counts"]["false_negative"] == 1
    assert result["counts"]["false_positive"] == 1
    assert result["unmatched_reportable_findings"] == ["water-1"]


def test_missing_finding_is_false_negative_without_false_positive(tmp_path: Path) -> None:
    tests = [{
        "id": "TC-XD-002",
        "expected_label": "inclusive_boundary_or_participant_language_difference",
    }]

    result = score_benchmark(*_write_case(tmp_path, tests, []))

    assert result["recall"] == 0.0
    assert result["counts"]["false_negative"] == 1
    assert result["counts"]["false_positive"] == 0


def test_negative_control_scores_absence_and_semantic_false_alarm(tmp_path: Path) -> None:
    tests = [{
        "id": "TC-XD-003",
        "expected_label": "valid_dual_time_axis_mapping",
        "must_not_report_as_conflict": True,
    }]
    benchmark, clean_run = _write_case(tmp_path / "clean", tests, [])
    clean = score_benchmark(benchmark, clean_run)
    assert clean["negative_control_accuracy"] == 1.0
    assert clean["tests"][0]["violation_detected"] is False

    alarm = {
        "finding_id": "axis-1",
        "finding_type": "time_axis_inconsistency",
        "fact_ids": ["F022", "F023"],
        "requires_human_review": True,
        "message": (
            "The protocol continuous Day -1 through Day 11 axis conflicts with four "
            "period-specific "
            "Day 1 representations and is ambiguous."
        ),
    }
    benchmark, alarm_run = _write_case(tmp_path / "alarm", tests, [alarm])
    scored = score_benchmark(benchmark, alarm_run)
    assert scored["negative_control_accuracy"] == 0.0
    assert scored["counts"]["negative_control_false_positive"] == 1
    assert scored["tests"][0]["matching_finding_ids"] == ["axis-1"]
