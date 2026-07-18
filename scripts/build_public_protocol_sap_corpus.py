"""Build a frozen metadata corpus of public ClinicalTrials.gov Protocol+SAP cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pypdf import PdfReader

API = "https://clinicaltrials.gov/api/v2"
CDN = "https://cdn.clinicaltrials.gov/large-docs"


def get_json(url: str, *, attempts: int = 4) -> dict[str, Any]:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "TrialCompiler-research/1"}
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def download(url: str, target: Path, *, attempts: int = 4) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 4:
        return
    partial = target.with_suffix(target.suffix + ".partial")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "TrialCompiler-research/1"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                partial.write_bytes(response.read())
            partial.replace(target)
            return
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt + 1 == attempts:
                raise
            time.sleep(2 * (attempt + 1))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_sha256(payload: Any) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def document_url(nct_id: str, filename: str) -> str:
    return f"{CDN}/{nct_id[-2:]}/{nct_id}/{urllib.parse.quote(filename)}"


def pdf_role_signals(reader: PdfReader, *, max_pages: int = 40) -> dict[str, Any]:
    """Find auditable role terms without unbounded extraction on very large PDFs."""
    protocol = False
    sap = False
    extracted_chars = 0
    page_count = len(reader.pages)
    if page_count <= max_pages:
        indices = range(page_count)
    else:
        # Titles and document labels normally occur near the front. Sampling the
        # tail and evenly spaced body pages also catches appendices and SAP
        # sections without allowing one huge PDF to stall the corpus build.
        front = list(range(25))
        tail = list(range(page_count - 5, page_count))
        body_slots = max_pages - len(front) - len(tail)
        body = [
            round(25 + index * (page_count - 31) / max(body_slots - 1, 1))
            for index in range(body_slots)
        ]
        indices = sorted(set(front + body + tail))
    for index in indices:
        text = (reader.pages[index].extract_text() or "").lower()
        extracted_chars += len(text.strip())
        protocol = protocol or any(
            term in text for term in ("protocol", "clinical study", "study plan")
        )
        sap = sap or any(
            term in text
            for term in (
                "statistical analysis plan",
                "statistical analysis",
                "analysis plan",
                "statistical methods",
            )
        )
    return {
        "protocol": protocol,
        "sap": sap,
        "extracted_chars": extracted_chars,
        "sampled_pages": len(indices),
    }


def candidate_documents(study: dict[str, Any]) -> tuple[dict, dict] | None:
    docs = (
        study.get("documentSection", {})
        .get("largeDocumentModule", {})
        .get("largeDocs", [])
    )
    protocols = sorted(
        (item for item in docs if item.get("hasProtocol")),
        key=lambda item: (int(item.get("size", 10**12)), item.get("filename", "")),
    )
    saps = sorted(
        (item for item in docs if item.get("hasSap")),
        key=lambda item: (int(item.get("size", 10**12)), item.get("filename", "")),
    )
    return (protocols[0], saps[0]) if protocols and saps else None


def validate_case(study: dict[str, Any], cache: Path) -> dict[str, Any]:
    identification = study["protocolSection"]["identificationModule"]
    nct_id = identification["nctId"]
    selected = candidate_documents(study)
    if selected is None:
        raise ValueError("protocol_and_sap_required")
    protocol, sap = selected
    document_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role, item in (("protocol", protocol), ("sap", sap)):
        filename = str(item["filename"])
        url = document_url(nct_id, filename)
        target = cache / nct_id / filename
        download(url, target)
        if target.read_bytes()[:4] != b"%PDF":
            raise ValueError(f"not_pdf:{filename}")
        reader = PdfReader(str(target), strict=False)
        pages = len(reader.pages)
        if pages < 1:
            raise ValueError(f"empty_pdf:{filename}")
        signals = pdf_role_signals(reader)
        if signals["extracted_chars"] < 100:
            raise ValueError(f"insufficient_extractable_text:{filename}")
        if filename in seen:
            document_rows[0]["roles"] = "protocol;sap"
            document_rows[0]["content_signals"] = signals
            continue
        seen.add(filename)
        document_rows.append(
            {
                "roles": role,
                "filename": filename,
                "official_url": url,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
                "pages": pages,
                "document_date": item.get("date"),
                "upload_date": item.get("uploadDate"),
                "content_signals": signals,
            }
        )
    return {
        "nct_id": nct_id,
        "brief_title": identification.get("briefTitle", ""),
        "official_study_url": f"https://clinicaltrials.gov/study/{nct_id}",
        "api_url": f"{API}/studies/{nct_id}",
        "documents": document_rows,
        "tier": "T1_protocol_and_sap",
    }


def discover(limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = "AREA[LargeDocHasProtocol]true AND AREA[LargeDocHasSAP]true"
    fields = ",".join(
        [
            "NCTId",
            "BriefTitle",
            "LargeDocTypeAbbrev",
            "LargeDocHasProtocol",
            "LargeDocHasSAP",
            "LargeDocHasICF",
            "LargeDocFilename",
            "LargeDocSize",
            "LargeDocDate",
            "LargeDocUploadDate",
        ]
    )
    url = (
        f"{API}/studies?query.term={urllib.parse.quote(query)}"
        f"&pageSize={max(limit + 20, int(limit * 1.5))}"
        f"&format=json&fields={fields}"
    )
    response = get_json(url)
    version = get_json(f"{API}/version")
    studies = sorted(
        response.get("studies", []),
        key=lambda item: item["protocolSection"]["identificationModule"]["nctId"],
    )
    studies = studies[: max(limit + 20, int(limit * 1.5))]
    return studies, {
        "query": query,
        "api_url": url,
        "api_total_count": response.get("totalCount"),
        "retrieved_candidate_count": len(studies),
        "clinicaltrials_gov_version": version,
    }


def write_outputs(
    cases: list[dict[str, Any]],
    failures: list[dict[str, str]],
    discovery: dict[str, Any],
    output: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    registry_dir = output / "registry"
    registry_dir.mkdir(exist_ok=True)
    contracts_dir = output / "case_contracts"
    contracts_dir.mkdir(exist_ok=True)
    selected_ids = {case["nct_id"] for case in cases}
    for directory in (registry_dir, contracts_dir):
        for stale in directory.glob("NCT*.json"):
            if stale.stem not in selected_ids:
                stale.unlink()
    rows: list[dict[str, Any]] = []
    for case in cases:
        registry_path = registry_dir / f"{case['nct_id']}.json"
        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        else:
            registry = get_json(case["api_url"])
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        case["registry_sha256"] = canonical_json_sha256(registry)
        protocol = registry.get("protocolSection", {})
        design = protocol.get("designModule", {})
        status = protocol.get("statusModule", {})
        outcomes = protocol.get("outcomesModule", {})
        case_contract = {
            "schema": "trialcompiler.public_case/v1",
            "case_id": case["nct_id"],
            "source_class": "real_public_clinicaltrials_gov",
            "split": "unassigned",
            "registry": {
                "nct_id": case["nct_id"],
                "study_type": design.get("studyType"),
                "phases": design.get("phases", []),
                "overall_status": status.get("overallStatus"),
                "enrollment": design.get("enrollmentInfo", {}),
                "primary_outcomes": outcomes.get("primaryOutcomes", []),
            },
            "documents": case["documents"],
            "available_actions": [
                {
                    "action_id": f"read:{item['filename']}",
                    "roles": item["roles"],
                    "cost_unit": max(1, int(item["pages"])),
                    "content_digest": item["sha256"],
                }
                for item in case["documents"]
            ],
            "gold_status": "not_annotated",
            "allowed_use": "corpus_integrity_and_future_blinded_annotation",
        }
        contract_path = contracts_dir / f"{case['nct_id']}.json"
        contract_path.write_text(
            json.dumps(case_contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        case["case_contract_path"] = f"case_contracts/{case['nct_id']}.json"
        case["case_contract_sha256"] = canonical_json_sha256(case_contract)
        for document in case["documents"]:
            rows.append(
                {
                    "nct_id": case["nct_id"],
                    "tier": case["tier"],
                    "brief_title": case["brief_title"],
                    "roles": document["roles"],
                    "filename": document["filename"],
                    "official_url": document["official_url"],
                    "sha256": document["sha256"],
                    "bytes": document["bytes"],
                    "pages": document["pages"],
                    "document_date": document["document_date"],
                    "upload_date": document["upload_date"],
                    "protocol_text_signal": document["content_signals"]["protocol"],
                    "sap_text_signal": document["content_signals"]["sap"],
                    "sampled_pages": document["content_signals"]["sampled_pages"],
                    "extracted_chars": document["content_signals"]["extracted_chars"],
                    "registry_path": f"registry/{case['nct_id']}.json",
                    "registry_sha256": case["registry_sha256"],
                    "case_contract_path": case["case_contract_path"],
                    "case_contract_sha256": case["case_contract_sha256"],
                }
            )
    fields = list(rows[0])
    with (output / "corpus_manifest.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output / "cases.json").write_text(
        json.dumps(
            {"schema": "trialcompiler.public_corpus/v1", "cases": cases},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "build_report.json").write_text(
        json.dumps(
            {
                "schema": "trialcompiler.public_corpus_build/v1",
                "validated_case_count": len(cases),
                "document_count": len(rows),
                "content_audit": {
                    "extractable_document_count": sum(
                        int(row["extracted_chars"]) >= 100 for row in rows
                    ),
                    "protocol_signal_document_count": sum(
                        row["protocol_text_signal"] for row in rows
                    ),
                    "sap_signal_document_count": sum(
                        row["sap_text_signal"] for row in rows
                    ),
                    "role_authority": "ClinicalTrials.gov large-document metadata",
                    "keyword_signals_are": "auxiliary_audit_not_role_ground_truth",
                },
                "discovery": discovery,
                "failures": failures,
                "claim_boundary": "public_source_integrity_not_model_performance",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    parser.add_argument(
        "--cache", type=Path, default=Path("data/public_case_cache")
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    studies, discovery = discover(args.limit)
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    cursor = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while len(cases) < args.limit and cursor < len(studies):
            batch = studies[cursor : cursor + args.workers]
            cursor += len(batch)
            future_map = {
                pool.submit(validate_case, study, args.cache): study for study in batch
            }
            for future in as_completed(future_map):
                study = future_map[future]
                nct_id = study["protocolSection"]["identificationModule"]["nctId"]
                try:
                    cases.append(future.result())
                    print(
                        f"validated {len(cases)}/{args.limit}: {nct_id}", flush=True
                    )
                except Exception as exc:
                    failures.append(
                        {"nct_id": nct_id, "error": f"{type(exc).__name__}: {exc}"}
                    )
                    print(f"rejected {nct_id}: {exc}", flush=True)
    cases = sorted(cases, key=lambda item: item["nct_id"])[: args.limit]
    if len(cases) < args.limit:
        raise RuntimeError(f"only {len(cases)} valid cases; required {args.limit}")
    write_outputs(cases, failures, discovery, args.output)
    print(json.dumps({"validated_cases": len(cases), "failures": len(failures)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
