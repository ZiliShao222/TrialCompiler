"""Build a runnable TrialCompiler fixture for the public NCT04683926 benchmark.

The benchmark gold files remain the source of truth. This adapter only maps the
reviewed fact sheet and public-document excerpts into the current MVP input
contract. The PK 32 h -> 36 h mutation is deliberately excluded from the base
fixture and is created later as a governed synthetic change request.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "benchmarks" / "trialdocbench" / "public_case_001_nct04683926"
OUTPUT = ROOT / "data" / "fixtures" / "nct04683926_public_case.json"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def status_for(value: str) -> str:
    return "approved" if value == "confirmed" else "requires_human_review"


def split_ids(value: str) -> list[str]:
    return [item for item in value.split("|") if item]


def main() -> None:
    manifest = read_tsv(CASE / "source_manifest.tsv")
    fact_rows = read_tsv(CASE / "gold" / "trial_fact_sheet_gold.tsv")

    sources = [
        {
            "source_id": row["source_id"],
            "title": f"NCT04683926 {row['document_type']}",
            "locator": row["official_url"] or row["local_path"],
            "authority": "official_public" if row["status"] == "verified_public" else "synthetic",
            "version": row["version_date"],
            "access_scope": row["allowed_use"],
        }
        for row in manifest
        if row["source_id"] != "SRC-MUT"
    ]
    facts = [
        {
            "fact_id": row["fact_id"],
            "name": row["name"],
            "value": row["value"],
            "unit": row["unit"] or None,
            "status": status_for(row["status"]),
            "source_ids": split_ids(row["source_ids"]),
            "owner_role": "qualified_clinical_reviewer",
            "version": 1,
        }
        for row in fact_rows
    ]

    # These are traceable benchmark excerpts, not reconstructed full documents.
    # Their role is to exercise cross-section reasoning after fact extraction.
    sections = [
        {
            "section_id": "PROT-SYNOPSIS",
            "title": "Protocol Synopsis",
            "document_type": "protocol",
            "source_ids": ["SRC-PROT"],
            "fact_refs": ["F005", "F007", "F009", "F010", "F011", "F015", "F018"],
            "text": (
                "Participants receive treatments on Study Days 1, 4, 7, and 10 with a "
                "washout interval of greater than 3 days. Participants remain in the study "
                "for 11 days. No water is allowed one hour before and one hour after dosing. "
                "Nominal PK samples are collected at 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, "
                "6, 8, 12, 16, 24, and 32 hours after each dose. Up to 32 participants may "
                "be randomized to obtain 24 PK-complete participants."
            ),
        },
        {
            "section_id": "PROT-BODY-PROCEDURES",
            "title": "Protocol Study Design and Procedures",
            "document_type": "protocol",
            "source_ids": ["SRC-PROT"],
            "fact_refs": ["F007", "F015", "F016", "F017", "F018", "F022"],
            "text": (
                "The four doses are administered on continuous Study Days 1, 4, 7, and 10, "
                "providing 3 days between doses. During the period from one hour before to one "
                "hour after dosing, only water is allowed. The study runs from Day -1 through "
                "Day 11. The final nominal PK sample is obtained 32 hours post-dose."
            ),
        },
        {
            "section_id": "PROT-SCHEDULE",
            "title": "Protocol Appendix A Schedule of Procedures",
            "document_type": "schedule_of_activities",
            "source_ids": ["SRC-PROT"],
            "fact_refs": ["F007", "F015", "F022"],
            "text": (
                "The schedule uses one continuous Day -1 to Day 11 study timeline. PK sampling "
                "for each treatment includes a final 32-hour time point."
            ),
        },
        {
            "section_id": "PROT-POPULATIONS",
            "title": "Protocol Analysis Populations",
            "document_type": "protocol",
            "source_ids": ["SRC-PROT"],
            "fact_refs": ["F019", "F020", "F021"],
            "text": (
                "The Safety Population includes all participants who receive at least one dose. "
                "The Per-Protocol Population must meet eligibility, complete Day 11, receive all "
                "four doses, and provide at least 13 of 15 PK samples per dose. The Evaluable "
                "Population has calculable AUC0-inf or AUC0-t and/or Cmax and is used for dose "
                "proportionality and food-effect analyses."
            ),
        },
        {
            "section_id": "SAP-DESIGN",
            "title": "SAP Study Design and Scope",
            "document_type": "statistical_analysis_plan",
            "source_ids": ["SRC-SAP"],
            "fact_refs": ["F009", "F018", "F019", "F020", "F023", "F024"],
            "text": (
                "Participants remain in the study for 11 days. No water is allowed one hour "
                "before and one hour after dosing. The SAP is limited to safety analysis. The "
                "CRF represents the crossover as four separate periods, with dosing recorded as "
                "Day 1 within each period, while the Protocol uses continuous Days 1, 4, 7, and 10."
            ),
        },
        {
            "section_id": "SAP-PK-SPEC",
            "title": "SAP PK Dataset and TFL Specification",
            "document_type": "statistical_analysis_plan",
            "source_ids": ["SRC-SAP"],
            "fact_refs": ["F015", "F020", "F021", "F023"],
            "text": (
                "PK records use period-specific nominal time points through 32 hours. Population "
                "mapping and PK completeness rules require statistical review because the SAP's "
                "stated scope is safety analysis."
            ),
        },
        {
            "section_id": "ICF-PARTICIPATION",
            "title": "ICF Study Participation and Burden",
            "document_type": "informed_consent_form",
            "source_ids": ["SRC-ICF"],
            "fact_refs": ["F008", "F009", "F015"],
            "text": (
                "Screening may occur up to 31 days before dosing. Participants will stay at the "
                "research unit for about 12 days and undergo blood sampling extending through the "
                "final 32-hour post-dose collection."
            ),
        },
        {
            "section_id": "PROT-SCREENING",
            "title": "Protocol Screening Window",
            "document_type": "protocol",
            "source_ids": ["SRC-PROT"],
            "fact_refs": ["F008"],
            "text": "Screening is performed no more than 30 days before dosing.",
        },
        {
            "section_id": "CRF-PK",
            "title": "Synthetic CRF Nominal PK Time Field",
            "document_type": "crf",
            "source_ids": ["SRC-SAP"],
            "fact_refs": ["F015", "F023"],
            "text": (
                "For prototype testing, each period has its own Day 1 and allows nominal PK "
                "times through 32 hours. This CRF representation is synthetic and is not a real "
                "study record."
            ),
        },
        {
            "section_id": "REG-RESULTS",
            "title": "ClinicalTrials.gov Registration and Results",
            "document_type": "registry_results",
            "source_ids": ["SRC-REG"],
            "fact_refs": ["F001", "F012", "F015", "F026", "F027"],
            "text": (
                "NCT04683926 is completed with actual enrollment of 24. Aggregate result time "
                "frames and PK descriptions are currently aligned to the public 32-hour sampling "
                "schedule."
            ),
        },
    ]
    payload = {
        "project_id": "NCT04683926",
        "document_id": "OMNI-PAIN-103-PUBLIC-PACKAGE",
        "title": "NCT04683926 / OMNI-PAIN-103 public document package",
        "document_type": "multi_document_clinical_trial_package",
        "jurisdiction": "United States",
        "therapeutic_area": "clinical pharmacology / analgesia",
        "version": "public-benchmark-reviewed-1.0",
        "sources": sources,
        "facts": facts,
        "sections": sections,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Sources: {len(sources)} | Facts: {len(facts)} | Sections: {len(sections)}")


if __name__ == "__main__":
    main()
