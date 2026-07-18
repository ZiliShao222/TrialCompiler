import json
import subprocess
import sys
from pathlib import Path


def test_uncertainty_experiment_script_emits_machine_readable_report(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "evaluate_uncertainty_experiment.py"),
            str(root / "data" / "fixtures" / "uncertainty_experiment_demo.json"),
            "--output",
            str(output),
            "--bins",
            "2",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["uncertainty"]["calibration_claim_allowed"] is True
    assert report["faithfulness"]["necessity_flip_rate"] == 0.5
