# Main bot launcher (main.py: main + payment)
Set-Location $PSScriptRoot

$runner = Join-Path $PSScriptRoot 'scripts\run-with-log.ps1'
$logPath = Join-Path $PSScriptRoot 'logs\main-bot.log'
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null

function Test-PythonExe {
    param([string]$ExePath)
    if (-not (Test-Path $ExePath)) { return $false }
    try {
        $proc = Start-Process -FilePath $ExePath -ArgumentList @('-c', 'import sys') `
            -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop
        return $proc.ExitCode -eq 0
    } catch { return $false }
}

$venvPy = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (Test-PythonExe $venvPy) {
    $py = $venvPy
    $args = '-X utf8 -W ignore::UserWarning'
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $py = 'py'
    $args = '-3 -X utf8 -W ignore::UserWarning'
} else {
    $py = 'python'
    $args = '-X utf8 -W ignore::UserWarning'
}

& $runner -Title 'CuteGamingBot (main.py)' -WorkingDirectory $PSScriptRoot `
    -PythonExe $py -PythonArgs $args -Script 'main.py' -LogPath $logPath
exit $LASTEXITCODE
