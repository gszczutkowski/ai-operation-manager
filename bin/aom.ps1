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
# AI Agent map
# ---------------------------------------------------------------------------
# Maps each supported AI agent to its deployment directory.
# Extend this table when you add new agents.
# The full configuration (config_file, type_dirs, etc.) lives in
# aom\config.py — keep the names in sync.
# ---------------------------------------------------------------------------
$AgentFolderMap = [ordered]@{
    "ClaudeCode" = ".claude"
    # "OpenCode"   = ".open-code"    # uncomment when paths are confirmed
    # "Cursor"     = ".cursor"
}

# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------
# Resolution order:
#   1. AI_AGENT_DEFAULT environment variable (already set)
#   2. Auto-select when only one agent is defined above
#   3. Interactive prompt listing all available agents
# ---------------------------------------------------------------------------

$ActiveAgent = $null

if ($env:AI_AGENT_DEFAULT) {
    if ($AgentFolderMap.Contains($env:AI_AGENT_DEFAULT)) {
        $ActiveAgent = $env:AI_AGENT_DEFAULT
    } else {
        Write-Warning "AI_AGENT_DEFAULT='$($env:AI_AGENT_DEFAULT)' is not a known agent."
        Write-Warning "Available agents: $($AgentFolderMap.Keys -join ', ')"
    }
}

if (-not $ActiveAgent) {
    $AgentNames = @($AgentFolderMap.Keys)

    if ($AgentNames.Count -eq 1) {
        $ActiveAgent = $AgentNames[0]
        Write-Host "  Using AI agent: $ActiveAgent  (set AI_AGENT_DEFAULT to skip this message)"
    } else {
        Write-Host ""
        Write-Host "Available AI agents:"
        for ($i = 0; $i -lt $AgentNames.Count; $i++) {
            $dir = $AgentFolderMap[$AgentNames[$i]]
            Write-Host ("  [{0}] {1,-20}  ->  {2}" -f ($i + 1), $AgentNames[$i], $dir)
        }
        Write-Host ""

        $choice = Read-Host "Select agent (1-$($AgentNames.Count)) or enter name"

        if ($choice -match '^\d+$') {
            $idx = [int]$choice - 1
            if ($idx -ge 0 -and $idx -lt $AgentNames.Count) {
                $ActiveAgent = $AgentNames[$idx]
            }
        } elseif ($AgentFolderMap.Contains($choice)) {
            $ActiveAgent = $choice
        }

        if (-not $ActiveAgent) {
            Write-Error "Invalid selection: '$choice'. Valid options: $($AgentNames -join ', ')"
            exit 1
        }
    }

    # Persist for this PowerShell session so subprocesses inherit it
    $env:AI_AGENT_DEFAULT = $ActiveAgent
}

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir

if (-not $env:AI_SKILLS_SCRIPTS_PATH) {
    $env:AI_SKILLS_SCRIPTS_PATH = $RepoRoot
}
if (-not $env:AI_SKILLS_REPO_PATH) {
    $env:AI_SKILLS_REPO_PATH = Split-Path -Parent $RepoRoot
}

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
# The Python layer reads AI_AGENT_DEFAULT from the environment to resolve
# agent-specific paths (install dirs, config file, artifact sub-dirs).
# ---------------------------------------------------------------------------

Push-Location $RepoRoot
try {
    & $Python -m aom.cli @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
