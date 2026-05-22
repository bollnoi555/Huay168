$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BotPath = Join-Path $ProjectDir "bot.py"
$RunnerPath = Join-Path $ProjectDir "run_forever.ps1"

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match [regex]::Escape($BotPath) -or
    $_.CommandLine -match [regex]::Escape($RunnerPath)
}

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "Stopped $($processes.Count) bot process(es)."
