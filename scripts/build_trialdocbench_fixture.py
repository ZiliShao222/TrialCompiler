"""Compile TrialDocBench synthetic case 001 into the runtime document contract."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "benchmarks/trialdocbench/synthetic_case_001_week12_to_week16"
OUTPUT = ROOT / "data/fixtures/trialdocbench_case_001.json"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def source_id(filename: str) -> str:
    stem = Path(filename).stem.upper().replace("_", "-")
    return f"SRC-{stem}"


def fact_value(row: dict[str, str]):
    if row["fact_type"] == "primary_endpoint_timepoint":
        match = re.search(r"(\d+)", row["current_value"])
        return int(match.group(1)) if match else row["current_value"]
    return row["current_value"]


def fact_name(row: dict[str, str]) -> str:
    if row["fact_type"] == "primary_endpoint_timepoint":
        return "primary endpoint assessment week"
    return row["fact_type"].replace("_", " ")


def main() -> None:
    fact_rows = read_tsv(CASE_DIR / "trial_fact_sheet_gold.tsv")
    edge_rows = read_tsv(CASE_DIR / "document_graph_gold.tsv")
    facts_by_unit: dict[str, list[str]] = defaultdict(list)
    for edge in edge_rows:
        facts_by_unit[edge["document_unit"]].append(edge["fact_id"])

    document_units = sorted((CASE_DIR / "document_units").glob("*.md"))
    source_names = sorted(
        {path.name for path in document_units} | {row["source_unit"] for row in fact_rows}
    )
    sources = [
        {
            "source_id": source_id(name),
            "title": Path(name).stem.replace("_", " ").title(),
            "locator": f"trialdocbench://case-001/{name}",
            "authority": "synthetic_benchmark",
            "version": "1",
            "effective_date": "2026-07-17",
            "access_scope": "public_synthetic_demo",
        }
        for name in source_names
    ]
    source_ids = {source["source_id"] for source in sources}
    facts = []
    for row in fact_rows:
        fact_source = source_id(row["source_unit"])
        facts.append(
            {
                "fact_id": row["fact_id"],
                "name": fact_name(row),
                "value": fact_value(row),
                "unit": row["unit_or_format"],
                "status": "approved" if row["status"] == "confirmed" else "draft",
                "source_ids": [fact_source] if fact_source in source_ids else [],
                "owner_role": row["owner_role"],
                "version": int(row["version"].lstrip("v") or "0"),
            }
        )

    sections = []
    for path in document_units:
        text = path.read_text(encoding="utf-8").strip()
        heading = next(
            (line.lstrip("# ") for line in text.splitlines() if line.startswith("#")),
            path.stem.replace("_", " ").title(),
        )
        sections.append(
            {
                "section_id": f"UNIT-{path.stem.upper().replace('_', '-')}",
                "title": heading,
                "text": text,
                "document_type": path.stem,
                "fact_refs": sorted(set(facts_by_unit[path.name])),
                "source_ids": [source_id(path.name)],
            }
        )

    payload = {
        "project_id": "TRIALDOCBENCH-SYNTH-001",
        "document_id": "PROTOCOL-PACKAGE-SYNTH-001",
        "title": "Synthetic Phase II protocol package: Week 12 to Week 16",
        "document_type": "protocol_package",
        "jurisdiction": "CN-demo",
        "therapeutic_area": "general_medicine_synthetic",
        "version": "1.0",
        "sources": sources,
        "facts": facts,
        "sections": sections,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(facts)} facts and {len(sections)} document units")


if __name__ == "__main__":
    main()
