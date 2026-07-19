"""Build the full engineering report chapter from all frozen submission narratives."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINEERING = ROOT / "docs" / "final_submission" / "engineering"


def nested_markdown(path: Path, minimum_level: int = 4) -> str:
    """Embed a standalone Markdown source without destroying fenced code blocks."""
    output: list[str] = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(line)
            continue
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match and not in_fence:
            level = min(6, minimum_level + len(match.group(1)) - 1)
            output.append(f"{'#' * level} {match.group(2)}")
        else:
            output.append(line)
    return "\n".join(output).strip()


def build(base: Path) -> str:
    base_text = base.read_text(encoding="utf-8").rstrip()
    base_text = base_text.replace(
        "# TrialCompiler 共享报告工科章节（待合并稿）",
        "# TrialCompiler 共享报告工科部分完整版",
        1,
    )
    base_text = base_text.replace(
        "> 建议替换共享报告中的第六部分和第七部分。本稿只覆盖“工”负责的技术方案、数学正确性、\n"
        "> 原型验证与复现内容；市场规模、企业内部现状、医学判断和商业收益仍由对应成员负责。\n"
        "> 数据冻结时间：2026-07-19；对应 Git commit：\n"
        "> `948c33daba21075c5024d3372dc2f171922f1737`。",
        "> 本稿可整体并入唯一文字报告，覆盖“工”负责的技术方案、数学证明、系统实现、原型验证、\n"
        "> 失败整改、人工修订闭环、GitHub 复现和证据索引。市场规模、企业内部事实、医学结论和\n"
        "> 商业收益仍由对应成员负责。数据冻结时间：2026-07-19；代码与结果以 GitHub `main`\n"
        "> 的最新成功 CI 提交为准。",
        1,
    )
    sections = [
        base_text,
        """
## 第八部分 工科研究与验证的完整技术依据

> 本部分不是额外宣传材料，而是将此前分散在工科附件中的详细技术研究、数学证明、
> 原型验证、可复现说明和运行指南并入唯一文字报告。与前文重复的少量定义予以保留，
> 目的是使评审者不依赖外部附件也能检查假设、公式、实验条件、失败案例和声明边界。

### 8.1 技术分析、原理研究与不确定性/可解释性主线

以下内容整合自冻结的《TrialCompiler 技术分析与原理研究笔记》。它记录了项目从普通
多 Agent 文档流程转向“事实依赖图 + 不确定性治理 + 可解释决策 + 人工质量门”的完整
研究逻辑，并保留实现对象、理论定义、评价指标、公开语料和研究边界。
""".strip(),
        nested_markdown(
            ENGINEERING / "01_TrialCompiler技术分析与原理研究笔记.md"
        ),
        """
### 8.2 数学技术证明全文

以下证明用于说明系统在明确假设、已登记来源、已编码依赖和确定性门禁范围内具备哪些
工程性质。它不证明所有医学结论正确，也不把语言模型置信度解释为临床概率。保留全文是
为了让评审者能够核对符号、假设、命题、证明和适用边界，而不是只看到结论性摘要。
""".strip(),
        nested_markdown(ENGINEERING / "02_TrialCompiler数学技术证明_v2.md"),
        """
## 第九部分 原型验证的完整证据与失败整改

### 9.1 原型验证报告全文

以下内容整合自冻结的原型验证报告，覆盖 NCT04683926、Metformin-PAD、50 例真实公开
Protocol/SAP、130 个官方角色标签、200 个受控缺陷标签、197 条自然候选的裁决前冻结，
以及模拟人工批准后的最小修订闭环。报告同时保留失败、整改和不可外推范围。
""".strip(),
        nested_markdown(ENGINEERING / "04_TrialCompiler原型验证报告.md"),
        """
### 9.2 NCT04683926 可复现验证流程全文

以下内容给出公开案例的资料边界、目录结构、环境配置、基线运行、变更运行、独立评分、
人工门控和结果解释。该流程是对前述指标的操作性补充，使评审者能够区分“报告数字”与
“能够按固定输入重新得到数字的复现实验”。
""".strip(),
        nested_markdown(ENGINEERING / "05_NCT04683926可复现验证说明.md"),
        """
### 9.3 GitHub、Demo 与全部复现入口

以下内容整合自冻结的 GitHub 与 Demo 说明，包含仓库结构、安装、静态检查、自动化测试、
API、公开案例、受控生成案例、50 例语料和对外展示边界。最终数字应以对应 Git commit
和 GitHub Actions 为准。
""".strip(),
        nested_markdown(ENGINEERING / "07_GitHub与Demo运行说明.md"),
        """
## 第十部分 工科交付物、证据索引与最终结论

### 10.1 工科提交材料索引

以下索引说明本报告所依据的主文件、机器可读证据、GitHub 提交、CI 状态和最终压缩包。
即使最终平台只允许提交一份文字报告，索引仍用于说明每项结论在代码仓库中的证据位置。
""".strip(),
        nested_markdown(ENGINEERING / "00_工科提交材料索引.md"),
        """
### 10.2 最终可陈述结论

TrialCompiler 已形成一套以版本化临床事实和显式文档依赖为核心、组合大模型语义能力、
确定性检查、不确定性治理、独立评测、人工授权和沙箱复检的可运行研究原型。项目已经在
公开或完全合成材料上验证两条端到端工作流，并将系统发现、修订建议、来源证据、人工决定、
回归结果和发布门禁组织为可审计对象。

当前最有力的工程证据不是一个孤立高分，而是一组相互约束的结果：NCT04683926 深度案例
具有独立 Gold Scorer 和负对照；50 个真实公开案例具有可复核来源和冻结摘要；130 个文档
角色标签来自官方元数据；200 个受控缺陷标签在案例隔离的 held-out test 中保持正负对照；
50 个经模拟人工批准且具备安全确定性补丁的 enrollment 问题全部完成正确、最小、可追溯
修订；系统对 50 个无法唯一决定编辑方式的试验标识符问题拒绝自动替换；130 项自动化测试
及 GitHub Actions 均通过。

项目同样明确披露尚未完成的部分：197 条真实自然语义候选没有外部合格专家 Gold，因而
不计算临床总体 Precision、Recall、F1 或 Accuracy；模拟人工不等于真实专业批准；当前
原型没有完成企业生产环境、真实患者数据、正式监管申报、跨治疗领域或商业 ROI 验证。
因此，本项目可以被评价为一个具有真实数据底座、明确理论主线、可运行代码、可复现实验、
失败整改和安全责任边界的临床文档 AI 研究原型，但不能被描述为已经替代专业人员或获得
临床生产批准的自动化系统。
""".strip(),
    ]
    return "\n\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=ROOT / "report_工科章节待合并.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "report_工科章节完整版.md",
    )
    args = parser.parse_args()
    args.output.write_text(build(args.base), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
