param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
& "$PSScriptRoot\aom.ps1" list @Arguments; exit $LASTEXITCODE
