# ============================================================
#  Switch the project's MASTER database selector.
#
#  The single source of truth is bot/config/config.py:
#      DATABASE_MODE      = "test" | "main"
#      DATABASE_LOCATION  = "local" | "remote"
#  (.env APP_MODE / DB_LOCATION are only a fallback and are kept in
#   sync here purely so nothing looks contradictory.)
#
#  Usage (via set-mode.bat):
#      set-mode.bat test            -> test  + local
#      set-mode.bat main            -> main  + remote
#      set-mode.bat test remote     -> test  + remote
#      set-mode.bat main local      -> main  + local
#      (no args)                    -> show current selection
# ============================================================
param(
    [string]$Mode = '',
    [string]$Location = '',
    [switch]$Show
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$configPy = Join-Path $root 'bot\config\config.py'
$envFile = Join-Path $root '.env'

function Get-ConfigVar {
    param([string]$Name)
    if (-not (Test-Path $configPy)) { return '' }
    $hit = Select-String -Path $configPy `
        -Pattern ('^\s*' + [regex]::Escape($Name) + '\s*=\s*["'']([^"'']*)["'']') |
        Select-Object -First 1
    if ($hit) { return $hit.Matches.Groups[1].Value.Trim() }
    return ''
}

function Show-Current {
    $m = Get-ConfigVar 'DATABASE_MODE'
    $l = Get-ConfigVar 'DATABASE_LOCATION'
    if (-not $m) { $m = '(пусто -> .env APP_MODE)' }
    if (-not $l) { $l = '(пусто -> авто)' }
    Write-Host ''
    Write-Host '  Текущий выбор базы (bot\config\config.py):' -ForegroundColor Cyan
    Write-Host "    DATABASE_MODE     = $m"
    Write-Host "    DATABASE_LOCATION = $l"
    Write-Host ''
}

if ($Show -or (-not $Mode)) {
    Show-Current
    exit 0
}

$modeAliases = @{ 'test' = 'test'; 'dev' = 'test'; 'local' = 'test';
    'main' = 'main'; 'prod' = 'main'; 'production' = 'main'; 'live' = 'main'; 'work' = 'main'
}
$locAliases = @{ 'local' = 'local'; 'localhost' = 'local'; 'pg17' = 'local';
    'remote' = 'remote'; 'ssh' = 'remote'; 'server' = 'remote'; 'cutehost' = 'remote'
}

$m = $modeAliases[$Mode.ToLower()]
if (-not $m) {
    Write-Host "[ERROR] режим должен быть test или main (получено: '$Mode')" -ForegroundColor Red
    exit 1
}

if ($Location) {
    $loc = $locAliases[$Location.ToLower()]
    if (-not $loc) {
        Write-Host "[ERROR] расположение должно быть local или remote (получено: '$Location')" -ForegroundColor Red
        exit 1
    }
} else {
    # Default location by profile: test -> local sandbox, main -> remote CuteHost.
    if ($m -eq 'main') { $loc = 'remote' } else { $loc = 'local' }
}

if (-not (Test-Path $configPy)) {
    Write-Host "[ERROR] не найден $configPy" -ForegroundColor Red
    exit 1
}

# UTF-8 without BOM (Python reads config.py/.env; a BOM can corrupt the first key).
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# --- Rewrite the two master-switch lines in config.py (keep trailing comments) ---
$text = Get-Content -LiteralPath $configPy -Raw -Encoding UTF8
$text = [regex]::Replace($text, '(?m)^(\s*DATABASE_MODE\s*=\s*)(".*?"|''.*?'')', ('${1}"' + $m + '"'))
$text = [regex]::Replace($text, '(?m)^(\s*DATABASE_LOCATION\s*=\s*)(".*?"|''.*?'')', ('${1}"' + $loc + '"'))
[System.IO.File]::WriteAllText($configPy, $text, $utf8NoBom)

# --- Keep .env fallback cosmetically in sync (config.py always wins anyway) ---
if (Test-Path $envFile) {
    $lines = Get-Content -LiteralPath $envFile -Encoding UTF8
    $haveMode = $false; $haveLoc = $false; $haveTgt = $false
    $out = foreach ($line in $lines) {
        if ($line -match '^\s*APP_MODE\s*=') { $haveMode = $true; "APP_MODE=$m" }
        elseif ($line -match '^\s*DB_LOCATION\s*=') { $haveLoc = $true; "DB_LOCATION=$loc" }
        elseif ($line -match '^\s*MAIN_DB_TARGET\s*=') { $haveTgt = $true; "MAIN_DB_TARGET=$loc" }
        else { $line }
    }
    if (-not $haveMode) { $out = @("APP_MODE=$m") + $out }
    if (-not $haveLoc) { $out += "DB_LOCATION=$loc" }
    if (-not $haveTgt) { $out += "MAIN_DB_TARGET=$loc" }
    [System.IO.File]::WriteAllText($envFile, (($out -join "`r`n") + "`r`n"), $utf8NoBom)
}

Write-Host ''
Write-Host '  Готово. Главный переключатель обновлён (bot\config\config.py):' -ForegroundColor Green
Write-Host "    DATABASE_MODE     = $m"   -ForegroundColor Green
Write-Host "    DATABASE_LOCATION = $loc" -ForegroundColor Green
Write-Host ''
if ($loc -eq 'remote') {
    Write-Host '  БАЗА: CuteHost cutebase @ 127.0.0.1:15432 (SSH-туннель поднимется автоматически)' -ForegroundColor Yellow
    if ($m -eq 'main') {
        Write-Host '  !!! БОЕВАЯ база — живые игроки, изменения РЕАЛЬНЫЕ !!!' -ForegroundColor Red
    }
} else {
    Write-Host '  БАЗА: локальная cutebase @ 127.0.0.1:5432 (без SSH)' -ForegroundColor Green
    Write-Host '  Локальный PostgreSQL: start-0-postgres-cutebase.bat (если ещё не запущен)' -ForegroundColor DarkGray
}
Write-Host ''
exit 0
