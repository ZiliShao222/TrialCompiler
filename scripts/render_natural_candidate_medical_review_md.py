"""Render the frozen natural-candidate queue as a human-review Markdown packet."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

CATEGORY_NAMES = {
    "analysis_population": "分析人群",
    "enrollment_scope_or_state_difference": "入组人数范围或状态差异",
    "estimand_intercurrent_event": "Estimand 与伴发事件",
    "missing_data": "缺失数据处理",
    "multiplicity": "多重性控制",
    "primary_endpoint_time": "主要终点或时间框架",
    "terminal_event": "终末事件与安全性语境",
    "trial_identifier_scope": "试验标识符范围",
}

LABELS = (
    "confirmed_defect",
    "legitimate_difference",
    "insufficient_evidence",
    "out_of_scope_reference",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def compact(text: object) -> str:
    return " ".join(str(text).split())


def registry_summary(contract: dict[str, Any]) -> str:
    registry = contract["registry"]
    enrollment = registry.get("enrollment") or {}
    outcomes = registry.get("primary_outcomes") or []
    outcome_text = "; ".join(
        f"{compact(item.get('measure', ''))} [{compact(item.get('timeFrame', ''))}]"
        for item in outcomes
    )
    return (
        f"study_type={registry.get('study_type')}; phases={registry.get('phases')}; "
        f"status={registry.get('overall_status')}; enrollment={enrollment.get('count')} "
        f"({enrollment.get('type')}); primary_outcomes={outcome_text or '未登记'}"
    )


def render(corpus: Path) -> str:
    candidates = load_jsonl(corpus / "adjudication" / "diverse_review_set.jsonl")
    predictions = {
        item["candidate_id"]: item
        for item in load_jsonl(
            corpus / "results" / "natural_candidate_predictions_pre_gold.jsonl"
        )
    }
    contracts = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (corpus / "case_contracts").glob("NCT*.json")
    }
    counts = Counter(item["category"] for item in candidates)
    routes = Counter(item["adjudication_route"] for item in candidates)
    lines = [
        "# TrialCompiler 真实自然临床语义候选专业核查包",
        "",
        "> 用途：由医学、统计或注册同学对真实公开 Protocol/SAP 候选进行独立裁决。",
        "> 本文件中的 197 条记录目前都不是已确认缺陷；不要根据系统提示直接给阳性标签。",
        "> 冻结候选和预测在人工标签之前生成，核查时不得修改候选文本或重新运行预测。",
        "",
        "## 一、核查范围与当前状态",
        "",
        f"- 候选数：{len(candidates)}；研究数：{len({x['case_id'] for x in candidates})}。",
        "- 来源：ClinicalTrials.gov 公开注册快照和官方上传 Protocol/SAP PDF。",
        "- 当前 Gold 数：0；当前 Precision、Recall、F1 和 Accuracy：不可计算。",
        "- 系统自动确认缺陷数：0；全部候选均要求合格人员复核。",
        "- 冻结预测摘要：",
        "  `59E16BEAEB7B6C07ABD9F0601300CC96EF4F41D3AB890F41DE94F1DC7F239FA2`。",
        "- 医学同学可以先完成医学判断；涉及分析集、缺失数据、多重性和 estimand 的项目",
        "  建议再由统计同学第二复核。试验标识符范围问题建议由注册或数据治理角色复核。",
        "",
        "### 分类数量",
        "",
        "| 类别 | 数量 | 建议主审角色 |",
        "|---|---:|---|",
    ]
    roles = {
        "analysis_population": "统计",
        "enrollment_scope_or_state_difference": "医学/统计",
        "estimand_intercurrent_event": "医学+统计",
        "missing_data": "统计",
        "multiplicity": "统计",
        "primary_endpoint_time": "医学+统计",
        "terminal_event": "医学+统计",
        "trial_identifier_scope": "注册/数据治理",
    }
    for category, count in sorted(counts.items()):
        lines.append(f"| {CATEGORY_NAMES[category]} (`{category}`) | {count} | {roles[category]} |")
    lines.extend(
        [
            "",
            "### 当前路由数量",
            "",
            *[f"- `{route}`：{count}" for route, count in sorted(routes.items())],
            "",
            "## 二、统一标签定义",
            "",
            "每条记录只能选择一个主标签：",
            "",
            "1. `confirmed_defect`：在相同研究、版本、分析范围、人群和时间框架下，公开证据",
            "   足以证明两个应一致的陈述实质冲突，且该差异会影响解释、执行或分析。",
            "2. `legitimate_difference`：差异真实存在，但由计划值/实际值、总人群/亚组、筛选/",
            "   随机化、Protocol/SAP 职责差异或其他明确语境合理解释。",
            "3. `insufficient_evidence`：当前页摘录或可见资料不足以确定是否缺陷；必须写明还需",
            "   哪一页、哪一版本、哪一来源或哪一专业判断。",
            "4. `out_of_scope_reference`：命中的数字、NCT ID、死亡、安全术语或统计术语仅用于",
            "   背景、相关研究引用、定义、模板或非目标分析，不属于当前待比较事实。",
            "",
            "不得使用“看起来可疑”“系统认为高风险”作为 `confirmed_defect` 的理由。阳性标签",
            "至少需要明确：比较的两条陈述、相同的适用范围、无法合理解释的冲突以及证据位置。",
            "",
            "## 三、每条记录的填写要求",
            "",
            "请在每条候选下填写：",
            "",
            "- 主审人/角色：姓名或代号，以及医学、统计、注册或数据治理角色；",
            f"- 标签：`{'` / `'.join(LABELS)}`；",
            "- `scope_relation`：same_scope / different_scope / unclear_scope；",
            "- 严重程度：critical / high / medium / low / not_applicable；",
            "- 裁决理由：说明比较对象、版本、人群、时间框架和判断依据；",
            "- 补充证据：填写实际查看的 PDF 页码、注册字段或其他公开来源；",
            "- 第二复核：required / completed / not_required，并记录第二复核者。",
            "",
            "如果只能查看本文件中的短摘录而不能打开官方 PDF，应优先标记",
            "`insufficient_evidence`，不得凭截断文本确认专业缺陷。",
            "",
            "## 四、逐条候选",
            "",
        ]
    )

    ordered = sorted(candidates, key=lambda x: (x["category"], x["case_id"], x["candidate_id"]))
    for index, item in enumerate(ordered, start=1):
        contract = contracts[item["case_id"]]
        prediction = predictions[item["candidate_id"]]
        document = next(
            doc for doc in contract["documents"] if doc["filename"] == item["filename"]
        )
        evidence = ", ".join(
            f"{key}={compact(value)}" for key, value in item["evidence"].items()
        )
        lines.extend(
            [
                f"### {index:03d}. {item['case_id']}｜{CATEGORY_NAMES[item['category']]}",
                "",
                f"- **Candidate ID**：`{item['candidate_id']}`",
                f"- **Candidate digest**：`{item['candidate_digest']}`",
                f"- **建议路由**：`{item['adjudication_route']}`",
                f"- **系统冻结 disposition**：`{prediction['disposition']}`（不是 Gold 标签）",
                f"- **系统说明**：{prediction['explanation']}",
                f"- **下一步建议**：`{prediction['next_action']}`",
                f"- **注册摘要**：{registry_summary(contract)}",
                (
                    f"- **PDF**：[{item['filename']}]({document['official_url']})，"
                    f"第 {item['page']} 页，SHA-256 `{document['sha256']}`"
                ),
                f"- **命中线索**：{evidence}",
                "- **候选原文**：",
                "",
                f"> {compact(item['excerpt'])}",
                "",
                "**请填写裁决**",
                "",
                "- 主审人/角色：",
                "- 标签：",
                "- scope_relation：",
                "- 严重程度：",
                "- 裁决理由：",
                "- 补充证据及页码：",
                "- 第二复核状态/复核者：",
                "- 备注：",
                "",
                "---",
                "",
            ]
        )
    lines.extend(
        [
            "## 五、提交给工科同学时的最低完整性检查",
            "",
            "- 197 条候选均有且仅有一个允许标签，不能留空或使用自定义标签；",
            "- 所有 `confirmed_defect` 均有具体比较证据和范围说明；",
            "- 所有 `insufficient_evidence` 均说明缺失的证据；",
            "- 统计语义和医学安全性阳性结论完成相应专业第二复核；",
            "- 第二复核不得由同一人用同一身份自审；",
            "- 不修改 Candidate ID、候选摘要、PDF 页码、官方链接和冻结预测；",
            "- 返回时保留本文件，并另附新增证据或更正页码清单。",
            "",
            "完成上述检查后，工科同学会将人工标签回填到机器可读 Gold 文件，并使用已经",
            "冻结的预测计算 Precision、Recall、F1、Accuracy、混淆矩阵和分类错误分布。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/trialdocbench/public_corpus_050"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/自然临床语义候选_专业核查包.md"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(args.corpus), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
