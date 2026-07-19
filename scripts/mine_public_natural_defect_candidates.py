"""Mine evidence-grounded natural defect candidates from the 50-case PDF corpus."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pypdf import PdfReader

NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
ENROLLMENT_PATTERN = re.compile(
    r"\b(\d{1,5})\s+(participants?|subjects?|patients?|volunteers?)\b", re.IGNORECASE
)
TOPICS = {
    "analysis_population": re.compile(
        r"\b(?:intent(?:ion)?[- ]to[- ]treat|ITT|per[- ]protocol|safety population|"
        r"evaluable population|analysis population|full analysis set)\b",
        re.IGNORECASE,
    ),
    "estimand_intercurrent_event": re.compile(
        r"\b(?:estimand|intercurrent event|treatment policy|hypothetical strategy|"
        r"composite strategy|principal stratum|while[- ]on[- ]treatment)\b",
        re.IGNORECASE,
    ),
    "missing_data": re.compile(
        r"\b(?:missing data|multiple imputation|last observation carried forward|LOCF|"
        r"missing at random|MAR|pattern mixture|tipping point)\b",
        re.IGNORECASE,
    ),
    "terminal_event": re.compile(
        r"\b(?:death|died|mortality|amputation|transplantation|terminal event)\b",
        re.IGNORECASE,
    ),
    "multiplicity": re.compile(
        r"\b(?:multiplicity|multiple testing|hierarchical testing|gatekeeping|"
        r"Bonferroni|Hochberg|Holm|alpha allocation|family[- ]wise)\b",
        re.IGNORECASE,
    ),
    "primary_endpoint_time": re.compile(
        r"\b(?:primary (?:endpoint|outcome)|week\s*\d+|day\s*\d+|month\s*\d+)\b",
        re.IGNORECASE,
    ),
}


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def excerpt(text: str, start: int, end: int, radius: int = 180) -> str:
    return compact(text[max(0, start - radius) : min(len(text), end + radius)])[:420]


def page_records(pdf: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf), strict=False)
    return [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]


def candidate(
    *,
    case_id: str,
    filename: str,
    page: int,
    category: str,
    text: str,
    evidence: dict[str, Any],
    adjudication: str,
) -> dict[str, Any]:
    return {
        "candidate_id": f"{case_id}:{filename}:p{page}:{category}:{evidence.get('ordinal', 0)}",
        "case_id": case_id,
        "filename": filename,
        "page": page,
        "category": category,
        "excerpt": text,
        "evidence": evidence,
        "label_status": "candidate_not_gold",
        "adjudication_route": adjudication,
        "claim_boundary": "real PDF evidence candidate; no defect claim before adjudication",
    }


def mine_case(contract: dict[str, Any], cache: Path) -> list[dict[str, Any]]:
    case_id = contract["case_id"]
    enrollment = contract["registry"]["enrollment"].get("count")
    outputs: list[dict[str, Any]] = []
    topic_limit: Counter[str] = Counter()
    for document in contract["documents"]:
        filename = document["filename"]
        pdf = cache / case_id / filename
        if not pdf.exists():
            raise FileNotFoundError(pdf)
        for page, text in page_records(pdf):
            for ordinal, match in enumerate(NCT_PATTERN.finditer(text), 1):
                observed = match.group().upper()
                if observed != case_id:
                    outputs.append(
                        candidate(
                            case_id=case_id,
                            filename=filename,
                            page=page,
                            category="trial_identifier_scope",
                            text=excerpt(text, *match.span()),
                            evidence={
                                "ordinal": ordinal,
                                "registry_nct_id": case_id,
                                "observed_nct_id": observed,
                            },
                            adjudication="data_governance_scope_review",
                        )
                    )
            if enrollment is not None:
                for ordinal, match in enumerate(ENROLLMENT_PATTERN.finditer(text), 1):
                    observed = int(match.group(1))
                    if observed != int(enrollment):
                        outputs.append(
                            candidate(
                                case_id=case_id,
                                filename=filename,
                                page=page,
                                category="enrollment_scope_or_state_difference",
                                text=excerpt(text, *match.span()),
                                evidence={
                                    "ordinal": ordinal,
                                    "registry_count": int(enrollment),
                                    "registry_type": contract["registry"]["enrollment"].get(
                                        "type"
                                    ),
                                    "observed_count": observed,
                                },
                                adjudication="statistical_and_version_state_review",
                            )
                        )
            for topic, pattern in TOPICS.items():
                if topic_limit[topic] >= 3:
                    continue
                match = pattern.search(text)
                if match:
                    topic_limit[topic] += 1
                    outputs.append(
                        candidate(
                            case_id=case_id,
                            filename=filename,
                            page=page,
                            category=topic,
                            text=excerpt(text, *match.span()),
                            evidence={"ordinal": topic_limit[topic], "matched": match.group()},
                            adjudication=(
                                "statistical_expert_review"
                                if topic
                                in {
                                    "analysis_population",
                                    "estimand_intercurrent_event",
                                    "missing_data",
                                    "multiplicity",
                                }
                                else "medical_and_statistical_review"
                            ),
                        )
                    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    parser.add_argument("--cache", type=Path, default=Path("data/public_case_cache"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/public_adjudication")
    )
    args = parser.parse_args()
    candidates: list[dict[str, Any]] = []
    for path in sorted((args.corpus / "case_contracts").glob("NCT*.json")):
        contract = json.loads(path.read_text(encoding="utf-8"))
        candidates.extend(mine_case(contract, args.cache))
        print(f"mined {contract['case_id']}: total={len(candidates)}", flush=True)
    output = args.output
    output.mkdir(exist_ok=True)
    target = output / "natural_defect_candidates.jsonl"
    target.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in candidates),
        encoding="utf-8",
    )
    counts = Counter(item["category"] for item in candidates)
    report = {
        "schema": "trialcompiler.natural_defect_candidate_mining/v1",
        "case_count": 50,
        "candidate_count": len(candidates),
        "category_counts": dict(sorted(counts.items())),
        "cases_with_candidates": len({item["case_id"] for item in candidates}),
        "gold_count": 0,
        "claim_boundary": "candidate evidence only; independent adjudication required",
    }
    (output / "mining_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
