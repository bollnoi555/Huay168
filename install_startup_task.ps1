$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectDir "run_forever.ps1"
$TaskName = "Huay168TelegramBot"
$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

schtasks /Create /F /TN $TaskName /SC ONLOGON /TR $Action | Out-Host
Write-Host "Startup task installed: $TaskName"

