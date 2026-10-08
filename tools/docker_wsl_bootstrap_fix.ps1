# Docker Desktop WSL bootstrap repair (CuteUpdate1) — read-only by default
# Run: powershell -ExecutionPolicy Bypass -File tools\docker_wsl_bootstrap_fix.ps1
# Apply WSL data reset (LOSES all Docker images/containers/volumes): add -ResetDockerWsl
param(
    [switch]$ResetDockerWsl,
    [string]$BackupRoot = 'D:\DockerWslBackup'
)

$ErrorActionPreference = 'Continue'
$MinFreeGB = 3.0

function Write-Section($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

Write-Section 'Disk C:'
$freeGB = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
$usedGB = [math]::Round((Get-PSDrive C).Used / 1GB, 2)
Write-Host "Free: $freeGB GB | Used: $usedGB GB"
if ($freeGB -lt $MinFreeGB) {
    Write-Host "WARNING: need at least $MinFreeGB GB free for Docker WSL bootstrap (mkfs/expand)." -ForegroundColor Yellow
}

Write-Section 'Docker WSL VHDX'
$wslRoot = Join-Path $env:LOCALAPPDATA 'Docker\wsl'
$paths = @(
    (Join-Path $wslRoot 'disk\docker_data.vhdx'),
    (Join-Path $wslRoot 'main\ext4.vhdx')
)
foreach ($p in $paths) {
    if (Test-Path -LiteralPath $p) {
        $f = Get-Item -LiteralPath $p
        $mb = [math]::Round($f.Length / 1MB, 1)
        Write-Host "OK  $mb MB  $($f.LastWriteTime)  $p"
    } else {
        Write-Host "MISSING  $p" -ForegroundColor Red
    }
}
if (Test-Path $wslRoot) {
    Get-ChildItem -LiteralPath $wslRoot -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host ("  extra: {0:N1} MB {1}" -f ($_.Length / 1MB), $_.FullName) }
}

Write-Section 'WSL'
wsl --status
wsl -l -v

Write-Section 'Shutdown WSL'
wsl --shutdown 2>&1 | Out-Host
Start-Sleep -Seconds 3
Write-Host 'wsl --shutdown done'

if (-not $ResetDockerWsl) {
    Write-Section 'Next steps (no changes made)'
    Write-Host @'
1) Free 3+ GB on C: (installers/cache only — do NOT delete CuteUpdate1 or state.vscdb unless you accept data loss).
2) Quit Docker Desktop (tray icon -> Quit).
3) Start Docker Desktop again.

If error persists (mkfs exit 1 after docker_data.vhdx was deleted/corrupted):
   Re-run this script with -ResetDockerWsl
   That backs up %LOCALAPPDATA%\Docker\wsl to D: (if possible), unregisters docker-desktop distros, lets Docker recreate disks.
   ALL Docker images, containers, volumes (including postgres_data) are lost unless you had pg_dump backups.

CuteUpdate1 rebuild: cd CuteUpdate1 && docker compose up -d --build
'@
    exit 0
}

Write-Section 'Reset Docker WSL (destructive)'
Write-Host 'Stopping Docker services...' -ForegroundColor Yellow
Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue

wsl --shutdown 2>&1 | Out-Null
Start-Sleep -Seconds 2

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dest = Join-Path $BackupRoot $stamp
if (Test-Path $wslRoot) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    Write-Host "Copying $wslRoot -> $dest (may fail if D: full)..."
    try {
        Copy-Item -LiteralPath $wslRoot -Destination $dest -Recurse -Force -ErrorAction Stop
        Write-Host "Backup copy OK: $dest"
    } catch {
        Write-Host ('Backup copy failed: ' + $_.Exception.Message + '; continuing with rename on C drive only') -ForegroundColor Yellow
        $ren = "$wslRoot.bak.$stamp"
        Rename-Item -LiteralPath $wslRoot -NewName (Split-Path $ren -Leaf) -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "No wsl folder at $wslRoot — Docker will create fresh"
}

foreach ($distro in @('docker-desktop-data', 'docker-desktop')) {
    $line = wsl -l -v 2>&1 | Out-String
    if ($line -match $distro) {
        Write-Host "Unregistering $distro..."
        wsl --unregister $distro 2>&1 | Out-Host
    }
}

Write-Section 'Start Docker Desktop'
$dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerExe) {
    Start-Process $dockerExe
    Write-Host "Started Docker Desktop — wait 2-5 min for first-time WSL provisioning."
} else {
    Write-Host "Start Docker Desktop manually from Start menu."
}
