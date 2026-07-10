# SSH tunnel via plink (password from .env)
param(
    [switch]$Quiet,
    [switch]$Background
)

Set-Location $PSScriptRoot
$cfg = . (Join-Path $PSScriptRoot 'read-ssh-env.ps1')

function Test-TunnelPort {
    return [bool](Get-NetTCPConnection -LocalPort $cfg.LocalPort -State Listen -ErrorAction SilentlyContinue)
}

if (Test-TunnelPort) {
    if (-not $Quiet) { Write-Host "[OK] Tunnel already on :$($cfg.LocalPort)." -ForegroundColor Green }
    exit 0
}

$forward = "$($cfg.LocalPort):$($cfg.RemoteHost):$($cfg.RemotePgPort)"
$pass = $cfg.Password
if (-not $pass) {
    Write-Host '[ERROR] SSH_PASSWORD missing in .env' -ForegroundColor Red
    exit 1
}

function Find-Plink {
    $c = Get-Command plink.exe -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = 'C:\Program Files\PuTTY\plink.exe'
    if (Test-Path $p) { return $p }
    return $null
}

$plink = Find-Plink
if (-not $plink) {
    Write-Host '[ERROR] plink.exe not found. Install PuTTY or use WinSCP tunnel.' -ForegroundColor Red
    Write-Host '        start-with-winscp.bat - manual WinSCP tunnel' -ForegroundColor Yellow
    exit 1
}

if (-not $Quiet) {
    Write-Host '============================================'
    Write-Host "  Tunnel :$($cfg.LocalPort) -> $($cfg.Host):$($cfg.RemotePgPort)"
    Write-Host '  Method: plink + SSH_PASSWORD from .env'
    Write-Host '============================================'
    Write-Host ''
}

$accept = "echo y| `"$plink`" -ssh -P $($cfg.Port) -l $($cfg.User) -pw `"$pass`" $($cfg.Host) exit"
cmd /c $accept 2>$null | Out-Null

$plinkArgs = @(
    '-batch', '-ssh',
    '-P', $cfg.Port,
    '-l', $cfg.User,
    '-pw', $pass,
    '-N', '-L', $forward,
    $cfg.Host
)

if ($Background) {
    if (-not $Quiet) { Write-Host 'Starting tunnel in background...' }
    $proc = Start-Process -FilePath $plink -ArgumentList $plinkArgs -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if (Test-TunnelPort) {
            if (-not $Quiet) {
                Write-Host "[OK] Tunnel up on :$($cfg.LocalPort) (pid $($proc.Id))" -ForegroundColor Green
            }
            exit 0
        }
        if ($proc.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $Quiet) {
        Write-Host ''
        Write-Host '[ERROR] plink could not open tunnel.' -ForegroundColor Red
        Write-Host '  Check SSH_PASSWORD in .env or use start-with-winscp.bat' -ForegroundColor Yellow
    }
    if (-not $proc.HasExited) { $proc | Stop-Process -Force -ErrorAction SilentlyContinue }
    exit 1
}

if (-not $Quiet) { Write-Host 'Tunnel running. Do not close this window.' -ForegroundColor Green }
& $plink @plinkArgs
exit $LASTEXITCODE
