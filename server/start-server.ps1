# Farm API server (Python 3.12, .venv)
Set-Location $PSScriptRoot

function Stop-StalePort {
    param([int]$Port)
    for ($round = 0; $round -lt 3; $round++) {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($conns.Count -eq 0) { return }
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -in @('python', 'python3')) {
                Write-Host "Stopping stale API on port $Port (PID $($c.OwningProcess))..." -ForegroundColor Yellow
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 2
    }
}
Stop-StalePort -Port 8000

$venvDir = Join-Path $PSScriptRoot '.venv'
$python = Join-Path $venvDir 'Scripts\python.exe'

function Invoke-Pip {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & $python -m pip @Args
}

function Test-Import {
    param([string]$Name)
    & $python -c ('import ' + $Name) 2>$null
    return $LASTEXITCODE -eq 0
}

# Работает ли venv на ЭТОЙ машине? .venv не переносимый: в pyvenv.cfg зашит
# абсолютный путь к Python того ПК, где его создавали. При копировании проекта
# python.exe остаётся на месте (файл есть), но ссылается на несуществующий путь
# ("No Python at '...'") — поэтому проверяем не наличие файла, а реальный запуск.
function Test-VenvWorks {
    if (-not (Test-Path $python)) { return $false }
    & $python -c 'import sys' 2>$null
    return $LASTEXITCODE -eq 0
}

# Ищем рабочий Python на машине пользователя: сначала py -3.12, затем любой py -3,
# затем python/python3 из PATH.
function Find-PythonLauncher {
    $candidates = @(
        @{ Cmd = 'py';      Args = @('-3.12') },
        @{ Cmd = 'py';      Args = @('-3') },
        @{ Cmd = 'python';  Args = @() },
        @{ Cmd = 'python3'; Args = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Cmd -ErrorAction SilentlyContinue)) { continue }
        & $c.Cmd @($c.Args + @('-c', 'import sys')) 2>$null
        if ($LASTEXITCODE -eq 0) { return $c }
    }
    return $null
}

if (-not (Test-VenvWorks)) {
    # Сломанный или «чужой» .venv (скопирован с другого ПК) — удаляем и создаём заново.
    if (Test-Path $venvDir) {
        Write-Host 'Existing .venv is broken or from another PC - recreating...' -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    }

    $launcher = Find-PythonLauncher
    if (-not $launcher) {
        Write-Host '[ERROR] Python 3.12 not found on this PC.' -ForegroundColor Red
        Write-Host '        Install it from https://www.python.org/downloads/' -ForegroundColor Red
        Write-Host '        During install tick "Add python.exe to PATH", then run this again.' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }

    Write-Host 'Creating venv...'
    & $launcher.Cmd @($launcher.Args + @('-m', 'venv', '.venv'))
    if ($LASTEXITCODE -ne 0 -or -not (Test-VenvWorks)) {
        Write-Host '[ERROR] Failed to create venv. Install Python 3.12 and try again.' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host ''
Write-Host 'Checking server dependencies...'
$sitePackages = Join-Path $PSScriptRoot '.venv\Lib\site-packages'
if (Test-Path $sitePackages) {
    Get-ChildItem $sitePackages -Directory -Filter '~*' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
}
Invoke-Pip install -q -r requirements-server.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] pip install failed' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

& $python -c 'import aiogram' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing bot dependencies (aiogram)...'
    Invoke-Pip install -q aiogram==3.17.0
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Failed to install aiogram' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

if (-not (Test-Import 'aiohttp') -or -not (Test-Import 'multipart') -or -not (Test-Import 'tzdata')) {
    Write-Host 'Installing extra packages (aiohttp, python-multipart, tzdata)...'
    Invoke-Pip install -q aiohttp python-multipart tzdata
}

& $python -c "from config import APP_MODE, MAIN_DB_TARGET, app_mode_summary; print('Mode:', app_mode_summary())"
if ($LASTEXITCODE -eq 0) {
    $mode = & $python -c "from config import APP_MODE; print(APP_MODE)"
    if ($mode -eq 'test') {
        Write-Host ''
        Write-Host '[TEST] Local cutebase :5432, no SSH tunnel' -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot 'ensure-postgres.ps1') | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host '[WARN] Start PostgreSQL 17 or run start-test.bat' -ForegroundColor Yellow
        } else {
            Write-Host '[OK] Local PostgreSQL ready' -ForegroundColor Green
        }
        Write-Host ''
    }
    $target = & $python -c "from config import MAIN_DB_TARGET; print(MAIN_DB_TARGET)"
    if ($mode -eq 'main' -and $target -eq 'remote') {
        if ($env:CF_TUNNEL_READY -eq '1') {
            Write-Host '[OK] SSH tunnel already verified by start-main.bat' -ForegroundColor Green
        } else {
            function Test-SshTunnel {
                return [bool](Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue)
            }

            if (-not (Test-SshTunnel)) {
                Write-Host ''
                Write-Host '[MAIN] SSH tunnel on port 15432 is not running.' -ForegroundColor Yellow
                $tunnelBat = Join-Path (Split-Path $PSScriptRoot -Parent) 'start-ssh-cutehost.bat'
                if (Test-Path $tunnelBat) {
                    Write-Host '       Opening tunnel window — enter root password there.' -ForegroundColor Yellow
                    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "`"$tunnelBat`"" -WindowStyle Normal
                } else {
                    Write-Host "       Run first: $tunnelBat" -ForegroundColor Yellow
                }
                Write-Host '       Waiting for port 15432 (up to 2 min)...' -ForegroundColor Yellow
                Write-Host ''

                $deadline = (Get-Date).AddSeconds(120)
                while ((Get-Date) -lt $deadline) {
                    if (Test-SshTunnel) {
                        Write-Host '[OK] SSH tunnel port 15432 is listening' -ForegroundColor Green
                        break
                    }
                    Start-Sleep -Seconds 2
                    Write-Host -NoNewline '.'
                }
                Write-Host ''

                if (-not (Test-SshTunnel)) {
                    Write-Host ''
                    Write-Host '[ERROR] Tunnel did not start on port 15432.' -ForegroundColor Red
                    Write-Host '        1) Open start-ssh-cutehost.bat in a separate window' -ForegroundColor Red
                    Write-Host '        2) Enter root password for 207.154.219.208' -ForegroundColor Red
                    Write-Host '        3) Keep that window open, then run start-1-server.bat again' -ForegroundColor Red
                    Write-Host ''
                    Read-Host 'Press Enter to close'
                    exit 1
                }
            } else {
                Write-Host '[OK] SSH tunnel port 15432 is listening' -ForegroundColor Green
            }
        }
    }
}

Write-Host ''
Write-Host 'API:  http://127.0.0.1:8000/health'
Write-Host 'Site: http://127.0.0.1:5173/  (run start.bat if Vite is not open)'
Write-Host 'Stop: Ctrl+C'
Write-Host ''

& $python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] Server exited with error' -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
