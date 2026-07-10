# Check pending admin registration TOTP (diagnostic).
param(
    [string]$UserId = '',
    [string]$Code = ''
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$py = $null
foreach ($candidate in @(
    (Join-Path $Root '.venv\Scripts\python.exe'),
    (Join-Path $Root 'venv\Scripts\python.exe')
)) {
    if (Test-Path -LiteralPath $candidate) { $py = $candidate; break }
}
if (-not $py) { $py = 'py' }

Write-Host ''
Write-Host '=== Check admin registration TOTP ===' -ForegroundColor Cyan
Write-Host 'Compare SERVER EXPECTED CODE with Google Authenticator.' -ForegroundColor DarkGray
Write-Host ''

if (-not $UserId) { $UserId = Read-Host 'Telegram user_id' }
if (-not $Code) { $Code = Read-Host '6-digit code from Authenticator (optional)' }

$script = Join-Path $Root 'scripts\debug_admin_register_code.py'
if ($py -eq 'py') {
    & py -3 $script $UserId $Code
} else {
    & $py $script $UserId $Code
}
exit $LASTEXITCODE
