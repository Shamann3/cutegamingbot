@echo off
chcp 65001 >nul
title CF - stop bots, API and Vite
cd /d "%~dp0"

echo Stopping main bot (main.py) if running...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Write-Host ('Stop main.py PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"

echo Stopping processes on ports 8000 and 5173...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "foreach ($port in 8000,5173) { for ($r=0; $r -lt 3; $r++) { $c=@(Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue); if (-not $c) { break }; foreach ($x in $c) { $n=(Get-Process -Id $x.OwningProcess -EA SilentlyContinue).ProcessName; if ($n -in 'python','node') { Write-Host ('Stop ' + $n + ' PID ' + $x.OwningProcess); Stop-Process -Id $x.OwningProcess -Force -EA SilentlyContinue } }; Start-Sleep 2 } }"

echo Done. Now run start.bat or start-all.bat
pause
