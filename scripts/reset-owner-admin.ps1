# Reset owner admin registration (pending session + account row).
param(
    [string]$UserId = ''
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$py = $null
foreach ($candidate in @(
    (Join-Path $Root '.venv\Scripts\python.exe'),
    (Join-Path $Root 'venv\Scripts\python.exe')
)) {
    if (Test-Path -LiteralPath $candidate) {
        $py = $candidate
        break
    }
}
if (-not $py) {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) { $py = 'py' }
}
if (-not $py) {
    Write-Host 'ERROR: Python not found (.venv, venv, or py -3).' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '=== Reset owner admin registration ===' -ForegroundColor Cyan
Write-Host 'Clears admin_register_pending and admin_accounts for one Telegram user_id.'
Write-Host 'After that, register again in the admin bot (Registration tab).'
Write-Host ''

if (-not $UserId) {
    $UserId = Read-Host 'Telegram user_id'
}
$UserId = $UserId.Trim()
if (-not $UserId) {
    Write-Host 'ERROR: user_id is empty.' -ForegroundColor Red
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$clearScript = Join-Path $Root 'scripts\_clear_admin_pending.py'
$deleteScript = Join-Path $Root 'scripts\_delete_admin_account.py'

Write-Host ''
Write-Host '[1/2] Clear admin_register_pending...' -ForegroundColor Yellow
if ($py -eq 'py') {
    & py -3 $clearScript $UserId
} else {
    & $py $clearScript $UserId
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: failed to clear pending (exit $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '[2/2] Delete admin_accounts row...' -ForegroundColor Yellow
if ($py -eq 'py') {
    & py -3 $deleteScript $UserId
} else {
    & $py $deleteScript $UserId
}
# NOT_FOUND is OK when the account was never created.

Write-Host ''
Write-Host 'Done.' -ForegroundColor Green
Write-Host '1. Delete ALL "CuteFarming Panel" entries in Google Authenticator.'
Write-Host '2. Restart the API server (if you have not since the TOTP fix).'
Write-Host '3. Open the panel via admin-bot -> Registration.'
Write-Host '4. Access key: ADMIN_LOGIN_KEY from your .env (not TOTP).'
Write-Host '5. Scan the new QR and enter the 6-digit code from Authenticator.'
Write-Host ''
exit 0
