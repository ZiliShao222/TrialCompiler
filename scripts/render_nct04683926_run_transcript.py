"""Render a readable, secret-free transcript from an NCT04683926 workflow run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    return json.loads(text)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fence(payload: Any) -> str:
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def normalize_display(value: Any) -> Any:
    """Repair a known display artifact while preserving raw files for audit."""
    if isinstance(value, list):
        if value and all(isinstance(item, str) and len(item) == 1 for item in value):
            return {
                "display_normalization": "joined character array returned by current governor",
                "text": "".join(value),
            }
        return [normalize_display(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_display(item) for key, item in value.items()}
    return value


def trace_dialogue(events: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    names = {
        "A": "Context Lock",
        "B": "Evidence Scanner",
        "C": "Repair Builder",
        "D": "Independent Quality Gate",
        "E": "Reporter",
        "F": "Experience Candidate",
    }
    for event in events:
        agent = event["agent"]
        lines.extend(
            [
                f"**{agent} - {names.get(agent, agent)}**",
                "",
                f"> {event['summary']}",
                "",
                f"- Action: `{event['action']}`",
                f"- Metadata: `{json.dumps(event.get('metadata', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    run_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        (ROOT / "outputs" / "latest_nct_workflow_path.txt").read_text(encoding="utf-8-sig").strip()
    )
    if not run_root.is_absolute():
        run_root = ROOT / run_root
    workspace = run_root / "workspace"
    runs = sorted(path for path in (workspace / "runs").iterdir() if path.is_dir())
    if len(runs) != 2:
        raise RuntimeError(f"Expected exactly two compile runs, found {len(runs)}")
    baseline_run, change_run = runs

    init = read_json(run_root / "01_init.stdout.json")
    status = read_json(run_root / "02_status.stdout.json")
    baseline = read_json(run_root / "03_baseline_compile.stdout.json")
    change_request = read_json(run_root / "04_change_request.stdout.json")
    impact = read_json(run_root / "05_impact_preview.stdout.json")
    change_compile = read_json(run_root / "06_change_compile.stdout.json")
    rejection = read_json(run_root / "07_human_rejection.stdout.json")
    final_status = read_json(run_root / "08_final_status.stdout.json")
    audit = read_json(run_root / "09_audit.stdout.json")
    baseline_trace = read_jsonl(baseline_run / "agent_trace.jsonl")
    change_trace = read_jsonl(change_run / "agent_trace.jsonl")

    baseline_semantic = normalize_display(baseline["semantic_review"])
    change_semantic = normalize_display(change_compile["semantic_review"])
    lines = [
        "# NCT04683926 TrialCompiler 全流程真实 API 测试记录",
        "",
        "> 本记录使用公开的研究级文件、人工复核 Fact Sheet 与明确标记的合成变更。",
        "> 未使用患者级数据；未记录或展示 API 密钥；Qwen 输出仅作为待人工复核建议。",
        "",
        "## 0. 测试输入",
        "",
        "- 案例：`NCT04683926 / OMNI-PAIN-103`",
        "- 输入：4 个公开来源、27 条人工复核事实、10 个可追踪章节摘录",
        "- 模型：`qwen-plus`，真实 DashScope OpenAI-compatible API",
        "- 基线任务：识别跨文档不一致、合法差异和人工复核点",
        "- 变更任务：完全合成的 PK 最终采样时间 `32 h -> 36 h`",
        "- 安全边界：任何修改都必须经过独立质量门和明确人工决定",
        "",
        "## 1. 人类：创建公开案例工作区",
        "",
        "**人类输入**",
        "",
        "> 请载入 NCT04683926 的公开文档包，并保持 review-only 模式。",
        "",
        "**TrialCompiler 回答**",
        "",
        fence(init),
        "",
        "**随后查询状态**",
        "",
        fence(status),
        "",
        "## 2. 人类：执行基线编译",
        "",
        "**人类输入**",
        "",
        "> 在不修改正式事实的前提下，执行 A-F 审阅工作流，并调用 qwen-plus 复核语义问题。",
        "",
        "### 2.1 A-F 协作轨迹",
        "",
        trace_dialogue(baseline_trace),
        "### 2.2 Qwen 语义复核完整输出",
        "",
        fence(baseline_semantic),
        "",
        "### 2.3 基线编译摘要",
        "",
        fence(
            {
                "run_id": baseline["run_id"],
                "deterministic_findings": baseline["findings"],
                "repair_proposals": baseline["proposals"],
                "quality": baseline["quality"],
                "semantic_review_status": baseline["semantic_review"]["status"],
            }
        ),
        "",
        "## 3. 人类：创建完全合成变更",
        "",
        "**人类输入**",
        "",
        "> 仅作为 benchmark，把 F015 的最终 PK 采样时间从 32 h 改为 36 h，先分析影响，不得自动覆盖正式版本。",
        "",
        "**TrialCompiler 创建候选变更**",
        "",
        fence(change_request),
        "",
        "### 3.1 依赖图影响预览",
        "",
        fence(impact),
        "",
        "## 4. 人类：编译候选变更",
        "",
        "**人类输入**",
        "",
        "> 对候选变更执行 A-F 工作流和真实 Qwen 语义复核，生成红线与质量结论。",
        "",
        "### 4.1 A-F 协作轨迹",
        "",
        trace_dialogue(change_trace),
        "### 4.2 Qwen 语义复核完整输出",
        "",
        fence(change_semantic),
        "",
        "### 4.3 变更编译摘要",
        "",
        fence(
            {
                "run_id": change_compile["run_id"],
                "change_id": change_compile["change_id"],
                "deterministic_findings": change_compile["findings"],
                "repair_proposals": change_compile["proposals"],
                "quality": change_compile["quality"],
                "impact_count": len(change_compile["impact_matrix"]),
                "semantic_review_status": change_compile["semantic_review"]["status"],
            }
        ),
        "",
        "## 5. 人工审核门",
        "",
        "**审核人员判断**",
        "",
        "> 当前非 Week 型变更没有获得确定性 repair 覆盖，质量门却给出 1.0；拒绝该候选变更并保留公开原版本。",
        "",
        "**系统记录**",
        "",
        fence(rejection),
        "",
        "**最终项目状态**",
        "",
        fence(final_status),
        "",
        "## 6. 完整审计轨迹",
        "",
        fence(audit),
        "",
        "## 7. Gold 对照结论",
        "",
        "| Gold 任务 | 本次表现 | 结论 |",
        "|---|---|---|",
        "| 水限制硬冲突 | Qwen 正确识别，确定性层漏检 | 部分通过 |",
        "| `>3 days` / `3 days` 数值边界 | 未明确识别 | 未通过 |",
        "| 11 天 / 约 12 天 | 未识别 | 未通过 |",
        "| 30 天 / 31 天边界 | 未识别 | 未通过 |",
        "| 双时间轴合法映射 | Qwen 误报为风险/冲突 | 未通过 |",
        "| SAP safety-only scope 与 population mapping | Qwen 识别 scope 风险 | 部分通过 |",
        "| planned / target / actual enrollment | 未误报，但未显式解释 | 部分通过 |",
        "| 27 条事实来源追踪 | source IDs 完整；Fact 模型没有 locator 字段 | 部分通过 |",
        "| 32 h -> 36 h 影响传播 | 找到 7 个位置和 6 类目标文件 | 通过依赖覆盖 |",
        "| 不静默覆盖、保留人工批准 | 人工拒绝后原版本未变化 | 通过 |",
        "",
        "## 8. 本次发现的问题",
        "",
        "1. **确定性覆盖过窄**：主图只检查 Week 型事实，NCT 案例的真实冲突全部漏检。",
        "2. **质量门存在 vacuous pass**：0 findings + 0 proposals 被错误解释为 score 1.0。",
        "3. **Qwen 不在 A-F 主循环内**：语义发现不会进入 C 修复和 D 复核。",
        "4. **非标量变更检测失败**：F015 是采样序列，影响矩阵按整串匹配，导致 old/new presence 全部为 false。",
        "5. **未传递变更理由**：Qwen payload 未包含 ChangeRequest.reason，因此模型误称缺乏变更 rationale。",
        "6. **输出 schema 治理不足**：模型把 limitations 返回为字符串时，当前 governor 将其拆成字符数组。",
        "7. **gold 语义边界不足**：模型把合法双时间轴映射误报为冲突，说明需要 scope-aware benchmark examples。",
        "8. **来源定位模型不完整**：FactRecord 只有 source_ids，没有 source_locator，无法完整满足 traceability gold。",
        "",
        "## 9. 原始证据位置",
        "",
        f"- 本次运行目录：`{run_root}`",
        f"- 基线运行：`{baseline_run}`",
        f"- 变更运行：`{change_run}`",
        "- 原始 stdout、workflow_state、agent_trace、semantic_review、impact_matrix、audit 均保留在上述目录。",
        "- 本文对字符数组仅做可读性拼接；原始异常结构未改写。",
    ]
    transcript = "\n".join(lines) + "\n"
    local_output = run_root / "10_full_interaction_transcript_zh.md"
    docs_output = ROOT / "docs" / "nct04683926_full_workflow_test_20260718_zh.md"
    local_output.write_text(transcript, encoding="utf-8")
    docs_output.write_text(transcript, encoding="utf-8")
    print(local_output)
    print(docs_output)


if __name__ == "__main__":
    main()
