#Requires -Version 5.1
<#
.SYNOPSIS
  AI Operation Manager — Windows PowerShell entry point.

.DESCRIPTION
  Wraps the Python aom CLI.

  aom install  complex-evaluator:1.0.2 --global
  aom list
  aom sync
  aom remove   complex-evaluator --local
  aom update   complex-evaluator --global
  aom env      --check

.EXAMPLE
  .\aom.ps1 list
  .\aom.ps1 install create-jira-story:1.0.0 --global
  .\aom.ps1 sync --project-dir C:\MyProject
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir

# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------

$Python = $null
foreach ($candidate in @("py", "python3", "python")) {
    try {
        $null = & $candidate --version 2>&1
        $Python = $candidate
        break
    } catch { }
}

if (-not $Python) {
    Write-Error "Python 3 is required but was not found. Install from https://python.org"
    exit 1
}

# ---------------------------------------------------------------------------
# Invoke aom CLI
# ---------------------------------------------------------------------------

Push-Location $RepoRoot
try {
    & $Python -m aom.cli @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
