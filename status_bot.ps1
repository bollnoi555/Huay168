$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BotPath = Join-Path $ProjectDir "bot.py"
$RunnerPath = Join-Path $ProjectDir "run_forever.ps1"

Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match [regex]::Escape($BotPath) -or
    $_.CommandLine -match [regex]::Escape($RunnerPath)
} | Select-Object ProcessId, Name, CommandLine
