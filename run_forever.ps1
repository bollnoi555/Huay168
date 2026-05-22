$ErrorActionPreference = "Continue"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectDir "logs"
$LogFile = Join-Path $LogDir "bot.log"
$ErrFile = Join-Path $LogDir "bot.err.log"
$BotFile = Join-Path $ProjectDir "bot.py"
$KnownPython = @(
    (Join-Path $env:LocalAppData "Python\pythoncore-3.14-64\python.exe"),
    (Join-Path $env:LocalAppData "Programs\Python\Python314\python.exe"),
    (Join-Path $env:LocalAppData "Programs\Python\Python313\python.exe"),
    (Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe")
)

$PythonExe = ($KnownPython | Where-Object { Test-Path $_ } | Select-Object -First 1)

if (-not $PythonExe) {
    $PythonExe = (Get-Command python.exe -All |
        Where-Object { $_.Source -and $_.Source -notlike "*\WindowsApps\*" } |
        Select-Object -First 1 -ExpandProperty Source)
}

if (-not $PythonExe) {
    $PythonExe = "python"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectDir

while ($true) {
    $started = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$started] starting bot.py"

    try {
        & $PythonExe $BotFile >> $LogFile 2>> $ErrFile
    }
    catch {
        $message = $_ | Out-String
        Add-Content -Path $ErrFile -Value $message
    }

    $stopped = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $ErrFile -Value "[$stopped] bot stopped; restarting in 10 seconds"
    Start-Sleep -Seconds 10
}
