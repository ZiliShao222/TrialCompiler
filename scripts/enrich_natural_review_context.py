"""Build expert-review context from the complete cached public PDFs.

The output augments each frozen candidate with a longer translated source window and,
where available, an independently located comparison window or registry fact.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "trialdocbench" / "public_corpus_050"
CACHE = ROOT / "data" / "public_case_cache"
PACKET = ROOT / "docs" / "自然临床语义候选_专业核查包.md"
TRANSLATIONS = ROOT / "data" / "public_adjudication" / "context_translation_cache.json"

PATTERNS = {
    "analysis_population": re.compile(
        r"intention[- ]to[- ]treat|intent[- ]to[- ]treat|ITT population|"
        r"full analysis set|safety population|per[- ]protocol population",
        re.I,
    ),
    "missing_data": re.compile(
        r"missing data|missing values|missing at random|not missing at random|"
        r"imput(?:e|ed|ation)|last observation carried forward|LOCF",
        re.I,
    ),
    "multiplicity": re.compile(
        r"multiplicity|multiple comparisons|multiple testing|hierarch(?:y|ical)|"
        r"type I error|alpha control",
        re.I,
    ),
    "estimand_intercurrent_event": re.compile(
        r"intercurrent event|estimand|treatment policy|hypothetical strategy|"
        r"while on treatment|discontinuation of treatment",
        re.I,
    ),
    "terminal_event": re.compile(
        r"death|mortality|terminal event|treatment discontinuation|withdrawal",
        re.I,
    ),
    "primary_endpoint_time": re.compile(
        r"primary (?:endpoint|outcome).{0,180}(?:day|week|month|year)|"
        r"(?:day|week|month|year).{0,180}primary (?:endpoint|outcome)",
        re.I | re.S,
    ),
}


def clean(text: str) -> str:
    return " ".join(text.replace("\x00", " ").split())


@lru_cache(maxsize=None)
def pdf_pages(case_id: str, filename: str) -> tuple[str, ...]:
    """Extract each cached PDF once; candidates often reuse the same document."""
    pdf = CACHE / case_id / filename
    reader = PdfReader(str(pdf), strict=False)
    return tuple(clean(page.extract_text() or "") for page in reader.pages)


def window(text: str, start: int, end: int, radius: int = 850) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right]
    first = min((pos for pos in (snippet.find(". "), snippet.find("; ")) if pos >= 0), default=-1)
    if left > 0 and 0 <= first < 240:
        snippet = snippet[first + 2 :]
    last = max(snippet.rfind(". "), snippet.rfind("; "))
    if right < len(text) and last > len(snippet) - 260:
        snippet = snippet[: last + 1]
    return clean(snippet)


def main_context(item: dict[str, Any]) -> tuple[str, str]:
    pages = pdf_pages(item["case_id"], item["filename"])
    page_index = max(0, min(len(pages) - 1, int(item["page"]) - 1))
    text = pages[page_index]
    matched = clean(str(item.get("evidence", {}).get("matched", "")))
    if matched:
        occurrences = list(re.finditer(re.escape(matched), text, re.I))
        ordinal = int(item.get("evidence", {}).get("ordinal", 1))
        hit = occurrences[min(max(ordinal - 1, 0), len(occurrences) - 1)] if occurrences else None
    else:
        hit = None
    if hit:
        return window(text, hit.start(), hit.end()), f"{item['filename']} 第{item['page']}页"
    excerpt = clean(item["excerpt"])
    return excerpt, f"{item['filename']} 第{item['page']}页（未能扩展定位）"


def comparison_context(item: dict[str, Any], contracts: dict[str, Any]) -> tuple[str, str] | None:
    category = item["category"]
    evidence = item.get("evidence", {})
    contract = contracts[item["case_id"]]
    registry = contract["registry"]
    if category == "enrollment_scope_or_state_difference":
        return (
            f"ClinicalTrials.gov登记：当前研究{item['case_id']}的入组人数为"
            f"{evidence.get('registry_count')}人，登记状态为{evidence.get('registry_type')}。"
            f"候选原文出现{evidence.get('observed_count')}人。",
            "ClinicalTrials.gov注册快照",
        )
    if category == "trial_identifier_scope":
        return (
            f"ClinicalTrials.gov登记的当前研究编号为{evidence.get('registry_nct_id')}；"
            f"候选原文出现{evidence.get('observed_nct_id')}。",
            "ClinicalTrials.gov注册快照",
        )
    if category == "primary_endpoint_time":
        outcomes = registry.get("primary_outcomes") or []
        if outcomes:
            joined = "；".join(
                f"{clean(str(x.get('measure', '')))}（时间范围：{clean(str(x.get('timeFrame', '未登记'))) }）"
                for x in outcomes[:3]
            )
            return f"ClinicalTrials.gov登记的主要结局：{joined}", "ClinicalTrials.gov注册快照"

    # A second keyword occurrence is not automatically a comparable fact.
    # For semantic-method candidates, show full local context and study background,
    # but leave the decision as "insufficient" unless a qualified reviewer can
    # establish the missing scope relation from the supplied material.
    return None


def study_background(case_id: str) -> str:
    registry_path = CORPUS / "registry" / f"{case_id}.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    protocol = registry.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    conditions = protocol.get("conditionsModule", {})
    design = protocol.get("designModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    design_info = design.get("designInfo", {})
    arm_names = [str(x.get("label", "")) for x in arms.get("armGroups", []) if x.get("label")]
    study_type = {"INTERVENTIONAL": "干预性研究", "OBSERVATIONAL": "观察性研究"}.get(
        design.get("studyType"), design.get("studyType", "未登记")
    )
    allocation = {"RANDOMIZED": "随机分配", "NON_RANDOMIZED": "非随机分配"}.get(
        design_info.get("allocation"), design_info.get("allocation", "未登记")
    )
    model = {"PARALLEL": "平行分组", "CROSSOVER": "交叉设计", "SINGLE_GROUP": "单组设计"}.get(
        design_info.get("interventionModel"), design_info.get("interventionModel", "未登记")
    )
    masking = {"NONE": "开放标签", "SINGLE": "单盲", "DOUBLE": "双盲", "TRIPLE": "三盲", "QUADRUPLE": "四盲"}.get(
        design_info.get("maskingInfo", {}).get("masking"),
        design_info.get("maskingInfo", {}).get("masking", "未登记"),
    )
    parts = [
        f"研究题目：{identification.get('officialTitle') or identification.get('briefTitle') or case_id}。",
        f"疾病或研究对象：{', '.join(conditions.get('conditions', [])) or '未登记'}。",
        f"设计：{study_type}，{allocation}，{model}，{masking}。",
        f"组别：{', '.join(arm_names) or '未登记'}。",
    ]
    return " ".join(parts)


def translate(text: str, cache: dict[str, str]) -> str:
    if not text:
        return ""
    if not re.search(r"[A-Za-z]{3}", text):
        return text
    if text in cache:
        return cache[text]
    chunks = [text[i : i + 1800] for i in range(0, len(text), 1800)]
    translated = []
    for chunk in chunks:
        url = (
            "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
            + urllib.parse.quote(chunk)
        )
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "TrialCompiler-research/1"})
                with urllib.request.urlopen(request, timeout=40) as response:
                    payload = json.load(response)
                translated.append("".join(part[0] for part in payload[0] if part[0]))
                break
            except Exception:
                if attempt == 3:
                    translated.append("【机器翻译失败，请查看英文原文】" + chunk)
                else:
                    time.sleep(1.5 * (attempt + 1))
    result = "".join(translated)
    cache[text] = result
    return result


def main() -> int:
    items = [
        json.loads(line)
        for line in (CORPUS / "adjudication" / "diverse_review_set.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    items.sort(key=lambda x: (x["category"], x["case_id"], x["candidate_id"]))
    contracts = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (CORPUS / "case_contracts").glob("NCT*.json")
    }
    cache = json.loads(TRANSLATIONS.read_text(encoding="utf-8")) if TRANSLATIONS.exists() else {}
    blocks = []
    paired = 0
    for index, item in enumerate(items, start=1):
        source_text, source_location = main_context(item)
        comparison = comparison_context(item, contracts)
        background_zh = study_background(item["case_id"])
        source_zh = translate(source_text, cache)
        if comparison:
            comparison_text, comparison_location = comparison
            comparison_zh = translate(comparison_text, cache)
            paired += 1
            status = "已提供两组材料，请先判断两者是否属于相同范围，再判断是否存在问题。"
            comparison_block = (
                f"**对照材料B（{comparison_location}）：**\n\n"
                f"> {comparison_zh}\n\n"
            )
        else:
            status = "目前只定位到一组有效材料，不足以确认跨文档缺陷；如无法仅凭专业常识判断，请选“看不出来”。"
            comparison_block = ""
        blocks.append(
            f"- **材料状态：**{status}\n\n"
            f"**研究背景（ClinicalTrials.gov登记信息，机器辅助翻译）：**\n\n"
            f"> {background_zh}\n\n"
            f"**材料A（{source_location}，机器辅助翻译）：**\n\n"
            f"> {source_zh}\n\n"
            f"{comparison_block}"
        )
        if index % 10 == 0:
            TRANSLATIONS.parent.mkdir(parents=True, exist_ok=True)
            TRANSLATIONS.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"processed {index}/{len(items)}", flush=True)

    text = PACKET.read_text(encoding="utf-8")
    old_short = r"\*\*请阅读：\*\*\n\n> .*?\n\n"
    enriched = r"- \*\*材料状态：\*\*.*?\n\n(?=\*\*您的判断：\*\*)"
    pattern = re.compile(rf"(?ms)(?:{old_short}|{enriched})")
    matches = list(pattern.finditer(text))
    if len(matches) != len(items):
        raise RuntimeError(f"evidence blocks {len(matches)} != candidates {len(items)}")
    result, count = pattern.subn(lambda _: blocks.pop(0), text)
    if count != len(items) or blocks:
        raise RuntimeError("evidence replacement incomplete")
    PACKET.write_text(result, encoding="utf-8", newline="\n")
    TRANSLATIONS.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATIONS.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "candidate_count": len(items),
        "paired_or_registry_comparison_count": paired,
        "single_context_only_count": len(items) - paired,
        "rule": "single-context items must not be forced into a defect/non-defect decision",
    }
    (CORPUS / "adjudication" / "expert_packet_context_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
