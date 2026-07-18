import argparse
import json
from pathlib import Path

from trialcompiler.assurance import build_assurance_case

parser = argparse.ArgumentParser()
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--summary", type=Path)
parser.add_argument("--score", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path else None


case = build_assurance_case(
    read(args.state), summary=read(args.summary), scorer_result=read(args.score)
)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(args.output), "outcome": case["outcome"]}))
