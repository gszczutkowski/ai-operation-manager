#Requires -Version 5.1
<#
.SYNOPSIS
  Build the aom executable for Windows.

.DESCRIPTION
  Installs PyInstaller, then runs PyInstaller with aom.spec to produce
  dist\aom.exe.

.PARAMETER Clean
  Remove previous build artefacts (dist\, build\) before building.

.EXAMPLE
  .\build.ps1
  .\build.ps1 -Clean
#>

param(
    [switch]$Clean,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------
$Python = $null
foreach ($candidate in @("py", "python3", "python")) {
    try {
        $versionOutput = & $candidate -c "import sys; print(sys.version_info >= (3,8))" 2>&1
        if ($versionOutput -eq "True") {
            $Python = $candidate
            break
        }
    } catch {
        # candidate not found, try next
    }
}

if (-not $Python) {
    Write-Error "Python 3.8+ is required but was not found.`nInstall from https://python.org or via winget: winget install Python.Python.3"
    exit 1
}

$pyVersion = & $Python --version 2>&1
Write-Host "==> Using Python: $pyVersion"

# ---------------------------------------------------------------------------
# Install build dependency
# ---------------------------------------------------------------------------
Write-Host "==> Installing PyInstaller..."
& $Python -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install PyInstaller."
    exit 1
}

# ---------------------------------------------------------------------------
# Optional clean
# ---------------------------------------------------------------------------
if ($Clean) {
    Write-Host "==> Cleaning previous build artefacts..."
    foreach ($dir in @("dist", "build")) {
        if (Test-Path $dir) {
            Remove-Item -Recurse -Force $dir
            Write-Host "    Removed: $dir"
        }
    }
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
Write-Host "==> Building aom.exe (Windows)..."
& $Python -m PyInstaller --clean aom.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

# ---------------------------------------------------------------------------
# Verify output
# ---------------------------------------------------------------------------
$Output = "dist\aom.exe"
if (-not (Test-Path $Output)) {
    Write-Error "Build finished but expected output not found: $Output"
    exit 1
}

$Size = (Get-Item $Output).Length / 1MB
Write-Host ""
Write-Host "==> Build complete!"
Write-Host "    Executable : $ScriptDir\$Output"
Write-Host ("    Size       : {0:N1} MB" -f $Size)
Write-Host ""
Write-Host "Quick test:"
Write-Host "    $Output --help"
