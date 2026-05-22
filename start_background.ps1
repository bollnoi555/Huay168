$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectDir "run_forever.ps1"

Start-Process powershell.exe `
    -WindowStyle Hidden `
    -WorkingDirectory $ProjectDir `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

Write-Host "Telegram lotto bot started in background."

