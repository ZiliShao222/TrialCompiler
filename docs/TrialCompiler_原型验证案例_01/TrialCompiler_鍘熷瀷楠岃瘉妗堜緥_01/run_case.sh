#!/usr/bin/env bash
set -euo pipefail

CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${1:-$(pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUTPUT_DIR="$CASE_DIR/outputs"

if [[ ! -d "$REPO_ROOT/src/trialcompiler" ]]; then
  echo "错误：未在 $REPO_ROOT 找到 src/trialcompiler。"
  echo "用法：./run_case.sh /TrialCompiler仓库绝对路径"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
export PYTHONPATH="$REPO_ROOT/src"

echo "[1/2] 验证飞书 Aily 结构化输入"
"$PYTHON_BIN" -m trialcompiler feishu-intake \
  --payload "$CASE_DIR/01_feishu_aily_intake.json"

echo "[2/2] 运行 TrialCompiler 审阅工作流"
"$PYTHON_BIN" -m trialcompiler demo \
  --document "$CASE_DIR/02_trial_document.json" \
  --db "$OUTPUT_DIR/memory.sqlite3" \
  --output "$OUTPUT_DIR" \
  --max-rounds 2

echo "完成。请查看：$OUTPUT_DIR/review_report.md"
