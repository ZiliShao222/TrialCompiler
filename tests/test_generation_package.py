import json
from pathlib import Path

from trialcompiler.generation import GenerativeCasePackage


def _package(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    (root / "01_AI_VISIBLE_PHASE1").mkdir(parents=True)
    (root / "02_AI_VISIBLE_PHASE2").mkdir()
    (root / "03_EVALUATOR_ONLY").mkdir()
    (root / "01_AI_VISIBLE_PHASE1" / "facts.json").write_text(
        json.dumps(
            {
                "visible": {"dose": "TBD"},
                "phase2_confirmed_decisions": {"dose": 1000},
            }
        ),
        encoding="utf-8",
    )
    (root / "02_AI_VISIBLE_PHASE2" / "answers.txt").write_text("dose 1000", encoding="utf-8")
    (root / "03_EVALUATOR_ONLY" / "gold.txt").write_text("MOBILE IC", encoding="utf-8")
    return root


def test_phase1_strips_hidden_json_key_and_excludes_later_directories(tmp_path: Path) -> None:
    package = GenerativeCasePackage(_package(tmp_path))
    files = package.materialize("phase1")
    assert [item.path for item in files] == ["01_AI_VISIBLE_PHASE1/facts.json"]
    assert "phase2_confirmed_decisions" not in files[0].text
    assert "1000" not in files[0].text
    assert files[0].sanitization_events
    audit = package.audit("phase1")
    assert audit.passed
    assert audit.hidden_directory_present


def test_phase2_never_includes_evaluator_directory(tmp_path: Path) -> None:
    package = GenerativeCasePackage(_package(tmp_path))
    paths = [item.path for item in package.materialize("phase2")]
    assert paths == [
        "01_AI_VISIBLE_PHASE1/facts.json",
        "02_AI_VISIBLE_PHASE2/answers.txt",
    ]
    assert all(not path.startswith("03_EVALUATOR_ONLY") for path in paths)


def test_hidden_reference_in_phase1_is_redacted_before_prompting(tmp_path: Path) -> None:
    root = _package(tmp_path)
    (root / "01_AI_VISIBLE_PHASE1" / "leak.txt").write_text("NCT05132439", encoding="utf-8")
    package = GenerativeCasePackage(root)
    files = package.materialize("phase1", strict=True)
    leak = next(item for item in files if item.path.endswith("leak.txt"))
    assert "NCT05132439" not in leak.text
    assert "REDACTED_HIDDEN_REFERENCE" in leak.text
    assert package.audit("phase1", files=files).passed
