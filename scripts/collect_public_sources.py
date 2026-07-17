from __future__ import annotations

import csv
import html
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "references" / "metadata" / "public_source_index.tsv"
STATUS_PATH = ROOT / "references" / "metadata" / "public_source_download_status.csv"


def load_existing_ids() -> set[str]:
    if not INDEX_PATH.exists():
        return set()
    with INDEX_PATH.open("r", encoding="utf-8", newline="") as f:
        return {row["source_id"] for row in csv.DictReader(f, delimiter="\t")}


def safe_download(url: str, local_path: Path, title: str) -> str:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content = response.read()
        local_path.write_bytes(content)
        return "downloaded"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        fallback = local_path.with_suffix(".html")
        fallback.write_text(
            "<!doctype html>\n"
            "<meta charset=\"utf-8\">\n"
            f"<title>{html.escape(title)}</title>\n"
            f"<h1>{html.escape(title)}</h1>\n"
            "<p>This source could not be downloaded automatically. "
            "The official link is retained for manual review.</p>\n"
            f"<p><a href=\"{html.escape(url)}\">{html.escape(url)}</a></p>\n"
            f"<p>Download error: {html.escape(str(exc))}</p>\n",
            encoding="utf-8",
        )
        return f"placeholder:{type(exc).__name__}"


def append_sources(sources: list[dict[str, str]]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "category",
        "title",
        "organization",
        "year",
        "url",
        "source_type",
        "primary_use",
        "access_status",
        "local_path",
    ]
    existing = load_existing_ids()
    append_header = not INDEX_PATH.exists()
    with INDEX_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        if append_header:
            writer.writeheader()
        for source in sources:
            if source["source_id"] in existing:
                continue
            local_path = ROOT / source["local_path"]
            status = safe_download(source["url"], local_path, source["title"])
            source = dict(source)
            if status.startswith("placeholder:"):
                source["local_path"] = str(local_path.with_suffix(".html").relative_to(ROOT)).replace("\\", "/")
                if source["access_status"] == "public_pdf":
                    source["access_status"] = "metadata_only"
            writer.writerow(source)
            print(f"{source['source_id']}\t{status}\t{source['title']}")
            time.sleep(0.5)


def regenerate_status() -> None:
    if not INDEX_PATH.exists():
        return
    with INDEX_PATH.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    with STATUS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source_id", "exists", "bytes", "local_path", "url"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            path = ROOT / row["local_path"]
            writer.writerow(
                {
                    "source_id": row["source_id"],
                    "exists": str(path.exists()).lower(),
                    "bytes": path.stat().st_size if path.exists() else 0,
                    "local_path": row["local_path"],
                    "url": row["url"],
                }
            )


def main() -> int:
    # The source list is intentionally close to raw metadata: interpretation lives
    # in downstream mapping tables, not in this downloader.
    sources: list[dict[str, str]] = [
        {
            "source_id": "ADOC-001",
            "category": "associated_documents",
            "title": "WHO informed consent form template for clinical studies",
            "organization": "WHO",
            "year": "2026",
            "url": "https://cdn.who.int/media/docs/default-source/documents/ethics/ethics-informedconsent-clinicalstudies.doc?sfvrsn=d69ff68a_0",
            "source_type": "template",
            "primary_use": "ICF structure and informed consent document unit mapping",
            "access_status": "public_doc",
            "local_path": "references/inbox/associated_documents/WHO_informed_consent_template.doc",
        },
        {
            "source_id": "ADOC-002",
            "category": "associated_documents",
            "title": "NIH consent templates",
            "organization": "NIH OHSRP",
            "year": "2026",
            "url": "https://irbo.nih.gov/nih-irb-templates/consent-templates/",
            "source_type": "template_index",
            "primary_use": "ICF template source and consent section requirements",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/NIH_consent_templates.html",
        },
        {
            "source_id": "ADOC-003",
            "category": "associated_documents",
            "title": "NIAID protocols and informed consent",
            "organization": "NIAID",
            "year": "2025",
            "url": "https://www.niaid.nih.gov/research/dmid-protocols-informed-consent",
            "source_type": "template_index",
            "primary_use": "Protocol and ICF template references for document catalog",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/NIAID_protocols_informed_consent.html",
        },
        {
            "source_id": "ADOC-004",
            "category": "associated_documents",
            "title": "FDA informed consent template for individual patient expanded access",
            "organization": "US FDA",
            "year": "2026",
            "url": "https://www.fda.gov/news-events/expanded-access/informed-consent-template-individual-patient-expanded-access",
            "source_type": "template",
            "primary_use": "Consent language constraints and regulatory boundary examples",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/FDA_expanded_access_informed_consent_template.html",
        },
        {
            "source_id": "ADOC-005",
            "category": "associated_documents",
            "title": "TransCelerate Common Statistical Analysis Plan template",
            "organization": "TransCelerate BioPharma",
            "year": "2026",
            "url": "https://www.transceleratebiopharmainc.com/initiatives/common-statistical-analysis-plan-sap-template/",
            "source_type": "template_page",
            "primary_use": "SAP structure and protocol-SAP dependency mapping",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/TransCelerate_common_SAP_template.html",
        },
        {
            "source_id": "ADOC-006",
            "category": "associated_documents",
            "title": "TransCelerate Clinical Content and Reuse assets",
            "organization": "TransCelerate BioPharma",
            "year": "2026",
            "url": "https://www.transceleratebiopharmainc.com/assets/clinical-content-reuse-solutions/",
            "source_type": "template_index",
            "primary_use": "Protocol SAP CSR template suite and reuse rationale",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/TransCelerate_clinical_content_reuse_assets.html",
        },
        {
            "source_id": "ADOC-007",
            "category": "associated_documents",
            "title": "TransCelerate Clinical Content and Reuse initiative",
            "organization": "TransCelerate BioPharma",
            "year": "2026",
            "url": "https://www.transceleratebiopharmainc.com/initiatives/clinical-content-reuse/",
            "source_type": "initiative_page",
            "primary_use": "Harmonized model content and template suite reference",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/TransCelerate_clinical_content_reuse.html",
        },
        {
            "source_id": "ADOC-008",
            "category": "associated_documents",
            "title": "EU-PEARL Statistical Analysis Plan template",
            "organization": "EU-PEARL",
            "year": "2023",
            "url": "https://eu-pearl.eu/wp-content/uploads/2023/05/3.EU-PEARL_SAP_Template_V3-25April2023.docx",
            "source_type": "template",
            "primary_use": "SAP section examples and analysis-plan fact dependencies",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/EU_PEARL_SAP_Template_2023.docx",
        },
        {
            "source_id": "ADOC-009",
            "category": "associated_documents",
            "title": "Duke Statistical Analysis Plan template",
            "organization": "Duke Biostatistics",
            "year": "2020",
            "url": "https://biostat.duke.edu/sites/default/files/2022-06/SAP%20template%20for%20website%202020-06-09.docx",
            "source_type": "template",
            "primary_use": "SAP checklist and analysis plan unit tests",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/Duke_SAP_template_2020.docx",
        },
        {
            "source_id": "ADOC-010",
            "category": "associated_documents",
            "title": "DAC Trials Statistical Analysis Plan template",
            "organization": "DAC Trials",
            "year": "2026",
            "url": "https://dac-trials.org/resources/statistical-analysis-plan-template/",
            "source_type": "template_page",
            "primary_use": "SAP purpose and best-practice wording",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/DAC_trials_SAP_template.html",
        },
        {
            "source_id": "ADOC-011",
            "category": "associated_documents",
            "title": "A template for the authoring of statistical analysis plans",
            "organization": "Trials / PMC",
            "year": "2023",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10300078/",
            "source_type": "open_access_article",
            "primary_use": "Evidence for structured SAP authoring and SAP checklist content",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/PMC_SAP_authoring_template_2023.html",
        },
        {
            "source_id": "ADOC-012",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov protocol registration data element definitions",
            "organization": "ClinicalTrials.gov",
            "year": "2026",
            "url": "https://clinicaltrials.gov/policy/protocol-definitions",
            "source_type": "registry_definitions",
            "primary_use": "Registry field mapping and outcome measure consistency checks",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/ClinicalTrialsGov_protocol_definitions.html",
        },
        {
            "source_id": "ADOC-013",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov results data element definitions",
            "organization": "ClinicalTrials.gov",
            "year": "2026",
            "url": "https://clinicaltrials.gov/policy/results-definitions",
            "source_type": "registry_definitions",
            "primary_use": "Outcome result consistency and endpoint traceability",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/ClinicalTrialsGov_results_definitions.html",
        },
        {
            "source_id": "ADOC-014",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov glossary terms",
            "organization": "ClinicalTrials.gov",
            "year": "2026",
            "url": "https://clinicaltrials.gov/study-basics/glossary",
            "source_type": "glossary",
            "primary_use": "Terminology normalization for registry/protocol consistency",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/ClinicalTrialsGov_glossary.html",
        },
        {
            "source_id": "ADOC-015",
            "category": "associated_documents",
            "title": "ICH E3 Structure and Content of Clinical Study Reports",
            "organization": "ICH",
            "year": "1995",
            "url": "https://database.ich.org/sites/default/files/E3_Guideline.pdf",
            "source_type": "regulatory_guideline",
            "primary_use": "CSR document units and protocol-to-CSR traceability",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/ICH_E3_Clinical_Study_Report.pdf",
        },
        {
            "source_id": "ADOC-016",
            "category": "associated_documents",
            "title": "NIH-FDA Phase 2 and 3 IND IDE Clinical Trial Protocol Template annotated by MRCT",
            "organization": "MRCT Center / NIH / FDA",
            "year": "2022",
            "url": "https://mrctcenter.org/diversity-in-clinical-research/wp-content/uploads/sites/8/2022/06/MRCT-Center-NIH-Protocol-Template-Version-1.0.pdf",
            "source_type": "template",
            "primary_use": "Protocol section catalog and schedule/endpoint dependencies",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/MRCT_NIH_FDA_protocol_template_2022.pdf",
        },
        {
            "source_id": "ADOC-017",
            "category": "associated_documents",
            "title": "NIA informed consent document template and guidelines",
            "organization": "National Institute on Aging",
            "year": "2022",
            "url": "https://www.nia.nih.gov/sites/default/files/2022-03/nia-informed-consent-template.docx",
            "source_type": "template",
            "primary_use": "Informed consent section requirements and wording patterns",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/NIA_informed_consent_template_2022.docx",
        },
        {
            "source_id": "ADOC-018",
            "category": "associated_documents",
            "title": "NYU standard consent template for clinical trials and biomedical research",
            "organization": "NYU Langone Health",
            "year": "2018",
            "url": "https://med.nyu.edu/departments-institutes/clinical-translational-science/sites/default/files/standard-consent-template-for-clinical-trials-and-biomedical-research.pdf",
            "source_type": "template",
            "primary_use": "Consent document unit examples and risk/benefit wording checks",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/NYU_standard_consent_template_2018.pdf",
        },
        {
            "source_id": "ADOC-019",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov reporting basic results article",
            "organization": "PMC",
            "year": "2010",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2821287/",
            "source_type": "open_access_article",
            "primary_use": "Registry results reporting background and outcome data dependencies",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/PMC_ClinicalTrialsGov_basic_results_2010.html",
        },
        {
            "source_id": "ADOC-020",
            "category": "associated_documents",
            "title": "University of Buffalo ClinicalTrials.gov registration and results guide",
            "organization": "University at Buffalo CTSI",
            "year": "2024",
            "url": "https://www.buffalo.edu/content/dam/www/ctsi/Cores/ClinicalResearchOffice/ClinicalTrialsgov%20Registration%20and%20Results%20Guide%201.16.2024.docx",
            "source_type": "guide",
            "primary_use": "Registry required-field workflow and completion date dependencies",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/Buffalo_ClinicalTrialsGov_registration_results_guide_2024.docx",
        },
        {
            "source_id": "AI-001",
            "category": "ai_protocol_authoring",
            "title": "From RAGs to riches: Using large language models to write documents for clinical trials",
            "organization": "arXiv",
            "year": "2024",
            "url": "https://arxiv.org/pdf/2402.16406",
            "source_type": "preprint",
            "primary_use": "LLM and RAG baseline for clinical trial document authoring",
            "access_status": "public_pdf",
            "local_path": "references/inbox/ai_protocol_authoring/Markey_RAGs_to_riches_clinical_trial_documents_2024.pdf",
        },
        {
            "source_id": "AI-002",
            "category": "ai_protocol_authoring",
            "title": "Clinical Trials Protocol Authoring using LLMs",
            "organization": "arXiv",
            "year": "2024",
            "url": "https://arxiv.org/pdf/2404.05044",
            "source_type": "preprint",
            "primary_use": "Protocol authoring baseline and LLM workflow comparison",
            "access_status": "public_pdf",
            "local_path": "references/inbox/ai_protocol_authoring/Clinical_trials_protocol_authoring_using_LLMs_2024.pdf",
        },
        {
            "source_id": "AI-003",
            "category": "ai_protocol_authoring",
            "title": "Large Language Models for Clinical Trial Protocol Assessments",
            "organization": "PMC",
            "year": "2026",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12816432/",
            "source_type": "open_access_article",
            "primary_use": "Evidence that LLMs can assess SAP and protocol-related content",
            "access_status": "public_html",
            "local_path": "references/inbox/ai_protocol_authoring/PMC_LLMs_for_clinical_trial_protocol_assessments.html",
        },
        {
            "source_id": "AI-004",
            "category": "ai_protocol_authoring",
            "title": "Large language models in clinical trials: applications and challenges",
            "organization": "PMC",
            "year": "2025",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12522288/",
            "source_type": "open_access_article",
            "primary_use": "Broad review of LLM applications and risk boundaries in clinical trials",
            "access_status": "public_html",
            "local_path": "references/inbox/ai_protocol_authoring/PMC_LLMs_in_clinical_trials_review.html",
        },
        {
            "source_id": "AI-005",
            "category": "ai_protocol_authoring",
            "title": "Revolutionizing Clinical Trials with Intelligent Protocol Automation",
            "organization": "PHUSE / LexJansen",
            "year": "2025",
            "url": "https://www.lexjansen.com/phuse-us/2025/ml/PAP_ML08.pdf",
            "source_type": "conference_paper",
            "primary_use": "Industry-style intelligent protocol automation reference",
            "access_status": "public_pdf",
            "local_path": "references/inbox/ai_protocol_authoring/PHUSE_intelligent_protocol_automation_2025.pdf",
        },
        {
            "source_id": "AI-006",
            "category": "ai_protocol_authoring",
            "title": "Using Large Language Models to Assess the Consistency of Randomized Controlled Trials on AI Interventions",
            "organization": "JMIR",
            "year": "2025",
            "url": "https://www.jmir.org/2025/1/e72412",
            "source_type": "open_access_article",
            "primary_use": "Method reference for LLM-based consistency assessment and deterministic API evaluation",
            "access_status": "public_html",
            "local_path": "references/inbox/ai_protocol_authoring/JMIR_LLM_consistency_RCT_AI_interventions_2025.html",
        },
        {
            "source_id": "AI-007",
            "category": "ai_protocol_authoring",
            "title": "AI-Driven Protocol Authoring Accelerates Phase III Clinical Trials",
            "organization": "AlphaLifeSci",
            "year": "2025",
            "url": "https://alphalifesci.com/blog/blueprint-for-breakthrough-ai-driven-protocol-authoring-accelerates-phase-iii-clinical-trials",
            "source_type": "industry_article",
            "primary_use": "Competitor narrative for cross-section consistency and structured protocol authoring",
            "access_status": "public_html",
            "local_path": "references/inbox/ai_protocol_authoring/AlphaLifeSci_AI_driven_protocol_authoring.html",
        },
        {
            "source_id": "AI-008",
            "category": "ai_protocol_authoring",
            "title": "AI Agents for Clinical Trial Protocol Automation",
            "organization": "Narrativa",
            "year": "2026",
            "url": "https://www.narrativa.com/protocol-clinical-trials-automation-with-ai-agents/",
            "source_type": "industry_article",
            "primary_use": "Agent-based clinical protocol automation competitor reference",
            "access_status": "public_html",
            "local_path": "references/inbox/ai_protocol_authoring/Narrativa_AI_agents_protocol_automation.html",
        },
        {
            "source_id": "BURDEN-011",
            "category": "burden",
            "title": "Impact of Protocol Amendments, Personnel Experience and Social Support on Clinical Trial Site Performance",
            "organization": "PMC",
            "year": "2025",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12579691/",
            "source_type": "open_access_article",
            "primary_use": "Evidence for amendment, complexity and operational performance burden",
            "access_status": "public_html",
            "local_path": "references/inbox/business/PMC_protocol_amendments_site_performance_2025.html",
        },
        {
            "source_id": "BURDEN-012",
            "category": "burden",
            "title": "Assessing Protocol Complexity and its Impact on Trial Outcomes",
            "organization": "IQVIA",
            "year": "2026",
            "url": "https://www.iqvia.com/blogs/2026/01/assessing-protocol-complexity-and-its-impact-on-trial-outcomes",
            "source_type": "industry_article",
            "primary_use": "Recent industry framing of protocol complexity, burden and amendments",
            "access_status": "public_html",
            "local_path": "references/inbox/business/IQVIA_protocol_complexity_trial_outcomes_2026.html",
        },
        {
            "source_id": "BURDEN-013",
            "category": "burden",
            "title": "The Amendment Trap: why clinical trials face costly protocol changes",
            "organization": "Precision for Medicine",
            "year": "2025",
            "url": "https://www.precisionformedicine.com/blog/the-amendment-trap-why-76-of-clinical-trials-face-six-figure-protocol-changes",
            "source_type": "industry_article",
            "primary_use": "Amendment cost narrative and risk framing",
            "access_status": "public_html",
            "local_path": "references/inbox/business/Precision_for_Medicine_amendment_trap.html",
        },
        {
            "source_id": "BURDEN-014",
            "category": "burden",
            "title": "Cost of Protocol Amendments: How Changes Penalize Learning in Phase 1",
            "organization": "Prelude EDC",
            "year": "2026",
            "url": "https://preludeedc.com/resource/cost-of-protocol-amendments-phase-1/",
            "source_type": "industry_article",
            "primary_use": "Change propagation and amendment-ready system framing",
            "access_status": "public_html",
            "local_path": "references/inbox/business/Prelude_cost_of_protocol_amendments_phase1.html",
        },
        {
            "source_id": "BURDEN-015",
            "category": "burden",
            "title": "The Rising Complexity of Study Design",
            "organization": "CRIO",
            "year": "2025",
            "url": "https://clinicalresearch.io/blog/the-rising-complexity-of-study-design-what-it-means-for-clinical-research-sites/",
            "source_type": "industry_article",
            "primary_use": "Study complexity and deviation/rework narrative",
            "access_status": "public_html",
            "local_path": "references/inbox/business/CRIO_rising_complexity_study_design.html",
        },
        {
            "source_id": "REG-001",
            "category": "regulatory_constraints",
            "title": "FDA Informed Consent Guidance for IRBs, Clinical Investigators, and Sponsors",
            "organization": "US FDA",
            "year": "2023",
            "url": "https://www.fda.gov/downloads/regulatoryinformation/guidances/ucm405006.pdf",
            "source_type": "regulatory_guidance",
            "primary_use": "Consent rule constraints and participant-facing document checks",
            "access_status": "public_pdf",
            "local_path": "references/inbox/regulatory_constraints/FDA_informed_consent_guidance_2023.pdf",
        },
        {
            "source_id": "REG-002",
            "category": "regulatory_constraints",
            "title": "HHS OHRP Informed Consent Checklist",
            "organization": "HHS OHRP",
            "year": "2026",
            "url": "https://www.hhs.gov/ohrp/regulations-and-policy/guidance/checklists/index.html",
            "source_type": "checklist",
            "primary_use": "Consent required elements checklist for ICF unit tests",
            "access_status": "public_html",
            "local_path": "references/inbox/regulatory_constraints/HHS_OHRP_informed_consent_checklist.html",
        },
        {
            "source_id": "REG-003",
            "category": "regulatory_constraints",
            "title": "FDA and HHS Use of Electronic Informed Consent in Clinical Investigations",
            "organization": "US FDA / HHS",
            "year": "2016",
            "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/use-electronic-informed-consent-clinical-investigations-questions-and-answers",
            "source_type": "regulatory_guidance",
            "primary_use": "Digital consent and electronic record boundary for Feishu workflow story",
            "access_status": "public_html",
            "local_path": "references/inbox/regulatory_constraints/FDA_HHS_electronic_informed_consent.html",
        },
        {
            "source_id": "REG-004",
            "category": "regulatory_constraints",
            "title": "ICH E17 General Principles for Planning and Design of Multi-Regional Clinical Trials",
            "organization": "ICH",
            "year": "2017",
            "url": "https://database.ich.org/sites/default/files/E17EWG_Step4_2017_1116.pdf",
            "source_type": "regulatory_guideline",
            "primary_use": "Global protocol design constraints and region-related design facts",
            "access_status": "public_pdf",
            "local_path": "references/inbox/regulatory_constraints/ICH_E17_Multi_Regional_Clinical_Trials_2017.pdf",
        },
        {
            "source_id": "REG-005",
            "category": "regulatory_constraints",
            "title": "EMA ICH E17 scientific guideline page",
            "organization": "EMA",
            "year": "2026",
            "url": "https://www.ema.europa.eu/en/ich-guideline-e17-general-principles-planning-design-multi-regional-clinical-trials-scientific-guideline",
            "source_type": "regulatory_page",
            "primary_use": "EMA context for ICH E17 and global submission acceptability",
            "access_status": "public_html",
            "local_path": "references/inbox/regulatory_constraints/EMA_ICH_E17_guideline_page.html",
        },
        {
            "source_id": "REG-006",
            "category": "regulatory_constraints",
            "title": "FDA E17 General Principles for Planning and Design of Multi-Regional Clinical Trials",
            "organization": "US FDA",
            "year": "2018",
            "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e17-general-principles-planning-and-design-multi-regional-clinical-trials",
            "source_type": "regulatory_page",
            "primary_use": "US adoption context for multi-region protocol constraints",
            "access_status": "public_html",
            "local_path": "references/inbox/regulatory_constraints/FDA_ICH_E17_guidance_page.html",
        },
        {
            "source_id": "ADOC-021",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov Protocol and SAP Upload and Redaction Guidance",
            "organization": "Weill Cornell Medicine",
            "year": "2019",
            "url": "https://research.weill.cornell.edu/sites/default/files/policy_forms/wcm_clinicaltrials.gov_protocol_and_sap_upload_and_redaction_guidance_v1.0_11.9.19.pdf",
            "source_type": "guide",
            "primary_use": "Protocol/SAP disclosure and redaction workflow dependencies",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/Weill_Cornell_ClinicalTrialsGov_protocol_SAP_redaction_2019.pdf",
        },
        {
            "source_id": "ADOC-022",
            "category": "associated_documents",
            "title": "ISCB Clinical Trial Protocol Template",
            "organization": "International Society for Clinical Biostatistics",
            "year": "2016",
            "url": "https://www.iscb.international/files/folders/sira_files/protocol_template_05feb2016_508.pdf",
            "source_type": "template",
            "primary_use": "Additional public protocol template for unit catalog validation",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/ISCB_clinical_trial_protocol_template_2016.pdf",
        },
        {
            "source_id": "ADOC-023",
            "category": "associated_documents",
            "title": "NIA Informed Consent Checklist",
            "organization": "National Institute on Aging",
            "year": "2008",
            "url": "https://www.nia.nih.gov/sites/default/files/2017-06/informed_consent_checklist_1_14_08_updated%20%281%29.doc",
            "source_type": "checklist",
            "primary_use": "ICF element checklist for deterministic consent unit tests",
            "access_status": "public_doc",
            "local_path": "references/inbox/associated_documents/NIA_informed_consent_checklist_2008.doc",
        },
        {
            "source_id": "ADOC-024",
            "category": "associated_documents",
            "title": "ClinicalTrials.gov sample informed consent document",
            "organization": "ClinicalTrials.gov",
            "year": "2017",
            "url": "https://cdn.clinicaltrials.gov/large-docs/95/NCT01873495/ICF_001.pdf",
            "source_type": "public_example_document",
            "primary_use": "Public example of ICF structure and participant-facing phrasing",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/ClinicalTrialsGov_sample_ICF_NCT01873495.pdf",
        },
        {
            "source_id": "SOA-001",
            "category": "schedule_of_activities",
            "title": "SPIRIT schedule of enrolment, interventions, and assessments template",
            "organization": "SPIRIT Statement",
            "year": "2013",
            "url": "https://www.spirit-statement.org/wp-content/uploads/2013/01/SPIRIT-Figure.doc",
            "source_type": "template",
            "primary_use": "Canonical schedule of enrolment/interventions/assessments table",
            "access_status": "public_doc",
            "local_path": "references/inbox/associated_documents/SPIRIT_schedule_figure_template.doc",
        },
        {
            "source_id": "SOA-002",
            "category": "schedule_of_activities",
            "title": "CONSORT-SPIRIT participant timeline explanation",
            "organization": "CONSORT-SPIRIT",
            "year": "2026",
            "url": "https://www.consort-spirit.org/item18-participanttimeline",
            "source_type": "guideline_page",
            "primary_use": "Rationale for participant timeline, visit schedule and burden checks",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/CONSORT_SPIRIT_participant_timeline.html",
        },
        {
            "source_id": "SOA-003",
            "category": "schedule_of_activities",
            "title": "BU Schedule of Events tool",
            "organization": "Boston University Medical Campus",
            "year": "2023",
            "url": "https://www.bumc.bu.edu/crro/files/2023/09/CRRO-Tool_Schedule-of-Events_9122023.docx",
            "source_type": "template",
            "primary_use": "Schedule-of-events table template for protocol and manual of procedures",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/BU_Schedule_of_Events_2023.docx",
        },
        {
            "source_id": "SOA-004",
            "category": "schedule_of_activities",
            "title": "Allina Health instructions for the Schedule of Events",
            "organization": "Allina Health",
            "year": "2026",
            "url": "https://www.allinahealth.org/-/media/allina-health/files/for-medical-professionals/instructions-for-the-schedule-of-events.doc",
            "source_type": "guide",
            "primary_use": "Practical schedule-of-events instructions and protocol care-plan mapping",
            "access_status": "public_doc",
            "local_path": "references/inbox/associated_documents/Allina_schedule_of_events_instructions.doc",
        },
        {
            "source_id": "SOA-005",
            "category": "schedule_of_activities",
            "title": "UAB simplified clinical trial protocol template",
            "organization": "University of Alabama at Birmingham",
            "year": "2026",
            "url": "https://www.uab.edu/ccts/images/kiosk/Simplified_clinical_trial_protocol_template.docx",
            "source_type": "template",
            "primary_use": "Protocol template containing Schedule of Activities section",
            "access_status": "public_docx",
            "local_path": "references/inbox/associated_documents/UAB_simplified_clinical_trial_protocol_template.docx",
        },
        {
            "source_id": "SOA-006",
            "category": "schedule_of_activities",
            "title": "UAB all clinical trial templates and tools",
            "organization": "University of Alabama at Birmingham",
            "year": "2026",
            "url": "https://www.uab.edu/ccts/clinical-trials-kiosk/all-templates-and-tools",
            "source_type": "template_index",
            "primary_use": "Protocol-driven source document and schedule-of-activities workflow context",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/UAB_all_templates_and_tools.html",
        },
        {
            "source_id": "SOA-007",
            "category": "schedule_of_activities",
            "title": "Automated protocol templates with efficient schedule of activities",
            "organization": "PMC",
            "year": "2025",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12167819/",
            "source_type": "open_access_article",
            "primary_use": "Method evidence for automated protocol templates and SoA generation",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/PMC_automated_protocol_templates_SoA_2025.html",
        },
        {
            "source_id": "SOA-008",
            "category": "schedule_of_activities",
            "title": "SPIRIT 2025 statement updated guideline for protocols",
            "organization": "PMC",
            "year": "2025",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12035670/",
            "source_type": "open_access_guideline",
            "primary_use": "Updated SPIRIT checklist and participant timeline context",
            "access_status": "public_html",
            "local_path": "references/inbox/associated_documents/PMC_SPIRIT_2025_statement.html",
        },
        {
            "source_id": "SOA-009",
            "category": "schedule_of_activities",
            "title": "ClinicalTrials.gov public protocol with schedule of activities",
            "organization": "ClinicalTrials.gov",
            "year": "2019",
            "url": "https://cdn.clinicaltrials.gov/large-docs/86/NCT04671186/Prot_SAP_000.pdf",
            "source_type": "public_example_document",
            "primary_use": "Public example of protocol and SAP containing SoA section",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/ClinicalTrialsGov_public_protocol_SoA_NCT04671186.pdf",
        },
        {
            "source_id": "SOA-010",
            "category": "schedule_of_activities",
            "title": "SPIRIT-PRO protocol template",
            "organization": "The PROTEUS Consortium",
            "year": "2023",
            "url": "https://theproteusconsortium.org/wp-content/uploads/2023/02/230220-SPIRIT-PRO-PROtocol-template.pdf",
            "source_type": "template",
            "primary_use": "PRO assessment schedule and time-window requirements",
            "access_status": "public_pdf",
            "local_path": "references/inbox/associated_documents/SPIRIT_PRO_protocol_template_2023.pdf",
        },
    ]
    append_sources(sources)
    regenerate_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
