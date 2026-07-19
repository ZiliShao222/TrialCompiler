"""Generate one submission-ready Markdown bibliography from the canonical catalog."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "references" / "catalog" / "sources.jsonl"
OUTPUT = ROOT / "docs" / "项目完整参考文献.md"

COLLECTIONS = {
    "01_regulatory_and_ethics": "一、法规、监管指南与研究伦理",
    "02_templates_and_associated_documents": "二、临床文件模板与关联文件",
    "03_data_standards_and_structured_protocols": "三、数据标准与结构化方案",
    "04_ai_methods_and_governance": "四、人工智能方法、不确定性、可解释性与治理",
    "05_industry_competitors_and_value": "五、行业产品、竞品与价值证据",
    "06_platform_and_integration": "六、平台与系统集成",
    "08_internal_project_materials": "七、项目内部材料（不作为外部证据）",
}


def main() -> int:
    sources = [
        json.loads(line)
        for line in CATALOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for source in sources:
        grouped[str(source["collection"])].append(source)
    tiers = Counter(str(source["evidence_tier"]) for source in sources)
    lines = [
        "# TrialCompiler 项目完整参考文献",
        "",
        "> 本文件是项目提交使用的统一参考文献表，由规范化来源总账自动生成。",
        "> A级主要为监管机构、国际标准组织或正式指南；B级主要为公共机构模板与行业标准；",
        "> C级为同行评议论文和公开研究；D级为厂商页面、行业材料与市场背景。",
        "> INTERNAL仅记录项目形成过程，不作为外部事实或效果声明的依据。",
        "",
        "## 引用原则",
        "",
        "- 法规、伦理、统计与文件要求优先引用A级来源。",
        "- 系统结构和模板映射可引用A级或B级来源。",
        "- 人工智能、不确定性与可解释性方法引用原始论文或正式出版页面。",
        "- 厂商材料只支持功能声明和市场比较，不支持监管合规或临床有效性结论。",
        "- ClinicalTrials.gov公开登记及附件在本项目评测中作为冻结正确基线；受控变异副本才是缺陷正例。",
        "",
        "## 目录统计",
        "",
        f"- 规范化来源共 **{len(sources)}** 条。",
        f"- 证据等级：A={tiers['A']}，B={tiers['B']}，C={tiers['C']}，D={tiers['D']}，INTERNAL={tiers['INTERNAL']}。",
        "- 每条记录保留来源编号、题名、发布机构、年份、证据等级、用途和原始链接。",
        "",
    ]
    number = 0
    for collection, heading in COLLECTIONS.items():
        items = sorted(grouped.get(collection, []), key=lambda item: str(item["source_id"]))
        lines.extend([f"## {heading}", ""])
        if not items:
            lines.extend(["本类别暂无来源。", ""])
            continue
        for source in items:
            number += 1
            title = str(source["title"]).strip()
            organization = str(source["organization"]).strip()
            year = str(source["year"]).strip()
            source_id = str(source["source_id"])
            tier = str(source["evidence_tier"])
            purpose = str(source.get("intended_use", "")).strip()
            url = str(source.get("source_url", "")).strip()
            citation = f"{number}. **[{source_id}] {title}**. {organization}, {year}. 证据等级：{tier}."
            if url:
                citation += f" [原始来源]({url})"
            lines.append(citation)
            if purpose:
                lines.append(f"   - 项目用途：{purpose}")
            lines.append("")
    lines.extend(
        [
            "## 数据来源与评测基线说明",
            "",
            "本项目的真实案例基线来自 ClinicalTrials.gov API v2、研究登记页及其公开附件。",
            "未经修改的登记快照、研究方案、统计分析计划和知情同意文件在评测中统一视为正确基线；",
            "系统只在隔离副本中应用有记录、可逆的受控变异，以构造答案确定的缺陷正例。",
            "因此，公开原始材料中的关键词或表面差异不被直接标记为缺陷，而作为复杂负对照用于测试误报控制。",
            "",
            "## 可复现性说明",
            "",
            "规范化机器可读总账位于 `references/catalog/sources.jsonl`；来源别名、重复项、",
            "本地快照和校验信息位于 `references/catalog/` 与 `references/metadata/`。",
            "重新运行 `python -m scripts.build_submission_references` 可生成本文件。",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(OUTPUT), "source_count": len(sources)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
