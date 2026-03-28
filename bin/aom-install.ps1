param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
& "$PSScriptRoot\aom.ps1" install @Arguments; exit $LASTEXITCODE
