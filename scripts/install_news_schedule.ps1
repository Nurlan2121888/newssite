$ErrorActionPreference = 'Stop'

# The project uses Baku time. Windows triggers follow the computer's local zone.
if ((Get-TimeZone).Id -ne 'Azerbaijan Standard Time') {
    throw 'Set the computer time zone to Baku before installing the news schedule.'
}

$newsProjectRoot = Split-Path -Parent $PSScriptRoot
$newsPython = Join-Path $newsProjectRoot 'venv\Scripts\pythonw.exe'
$newsRunner = Join-Path $PSScriptRoot 'run_news_fetch.py'
$newsTaskName = 'Gundem-News-Fetch'

if (-not (Test-Path -LiteralPath $newsPython)) {
    throw "Virtual environment Python was not found: $newsPython"
}
if (-not (Test-Path -LiteralPath $newsRunner)) {
    throw "News runner was not found: $newsRunner"
}

$newsAction = New-ScheduledTaskAction `
    -Execute $newsPython `
    -Argument ('-B -X utf8 "{0}"' -f $newsRunner) `
    -WorkingDirectory $newsProjectRoot

$newsTriggers = @(
    New-ScheduledTaskTrigger -Daily -At '09:00'
    New-ScheduledTaskTrigger -Daily -At '15:00'
    New-ScheduledTaskTrigger -Daily -At '21:00'
)

$newsSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45)

$newsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$newsPrincipal = New-ScheduledTaskPrincipal `
    -UserId $newsUser `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $newsTaskName `
    -Description 'Update the local Gundem news database daily at 09:00, 15:00 and 21:00 Baku time.' `
    -Action $newsAction `
    -Trigger $newsTriggers `
    -Settings $newsSettings `
    -Principal $newsPrincipal `
    -Force | Out-Null

Write-Output 'Installed Gundem-News-Fetch: 09:00, 15:00, 21:00 Baku time.'
