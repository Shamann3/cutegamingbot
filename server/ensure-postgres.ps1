# Ensure PostgreSQL 17 is running on port 5432. Exit 0 if OK, 1 if failed.
param(
    [int]$Port = 5432
)

$pgHome = 'C:\Program Files\PostgreSQL\17'
$pgData = Join-Path $pgHome 'data'
$service = 'postgresql-x64-17'

function Test-PgPort {
    param([int]$TargetPort = 5432)
    return [bool](Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue)
}

if (Test-PgPort -TargetPort $Port) { exit 0 }

$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root 'docker-compose.yml'
if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path $compose)) {
    Push-Location $root
    docker compose stop postgres 2>$null | Out-Null
    Pop-Location
    Start-Sleep -Seconds 1
}

if (Test-PgPort -TargetPort $Port) { exit 0 }

Write-Host '[..] PostgreSQL не запущен. Запускаю...'

$svc = Get-Service -Name $service -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne 'Running') {
    try {
        Start-Service $service -ErrorAction Stop
        Start-Sleep -Seconds 2
    } catch {
        Write-Host '[!!] Службу не удалось запустить (нужен администратор). Пробую postgres.exe...' -ForegroundColor Yellow
    }
}

if (-not (Test-PgPort -TargetPort $Port)) {
    $postgresExe = Join-Path $pgHome 'bin\postgres.exe'
    if (Test-Path $postgresExe) {
        Start-Process -FilePath $postgresExe -ArgumentList "-D `"$pgData`"" -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(15)
        while (-not (Test-PgPort -TargetPort $Port) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 1
        }
    }
}

if (Test-PgPort -TargetPort $Port) {
    Write-Host "[OK] PostgreSQL слушает порт $Port." -ForegroundColor Green
    exit 0
}

Write-Host "[ОШИБКА] PostgreSQL не запустился на порту $Port." -ForegroundColor Red
exit 1
