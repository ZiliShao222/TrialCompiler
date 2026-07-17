param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$CaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputDir = Join-Path $CaseDir "outputs"
$SourceDir = Join-Path $RepoRoot "src"
$TrialCompilerDir = Join-Path $SourceDir "trialcompiler"

if (-not (Test-Path $TrialCompilerDir)) {
    throw "未在 $RepoRoot 找到 src\trialcompiler。请传入 TrialCompiler 仓库绝对路径。"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$env:PYTHONPATH = $SourceDir

Write-Host "[1/2] 验证飞书 Aily 结构化输入"
& $PythonExe -m trialcompiler feishu-intake `
    --payload (Join-Path $CaseDir "01_feishu_aily_intake.json")

Write-Host "[2/2] 运行 TrialCompiler 审阅工作流"
& $PythonExe -m trialcompiler demo `
    --document (Join-Path $CaseDir "02_trial_document.json") `
    --db (Join-Path $OutputDir "memory.sqlite3") `
    --output $OutputDir `
    --max-rounds 2

Write-Host "完成。请查看：$(Join-Path $OutputDir 'review_report.md')"
