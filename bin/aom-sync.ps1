param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
& "$PSScriptRoot\aom.ps1" sync @Arguments; exit $LASTEXITCODE
