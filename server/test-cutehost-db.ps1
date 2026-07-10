# Test CuteHost DB through SSH tunnel
param([switch]$NoPause)

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host '[ERROR] venv not found. Run start-1-server.bat first.' -ForegroundColor Red
    if (-not $NoPause) { Read-Host 'Press Enter' }
    exit 1
}

$tunnel = Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue
if (-not $tunnel) {
    Write-Host '[ERROR] SSH tunnel not running on port 15432.' -ForegroundColor Red
    Write-Host '        Run start-ssh-cutehost.bat first.' -ForegroundColor Yellow
    if (-not $NoPause) { Read-Host 'Press Enter' }
    exit 1
}

Write-Host 'Testing CuteHost DB...' -ForegroundColor Cyan

& $python -c @"
import asyncio
import asyncpg
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, db_ssl_mode, app_mode_summary

async def main():
    print('Profile:', app_mode_summary())
    try:
        conn = await asyncpg.connect(
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
            host=DB_HOST, port=int(DB_PORT), ssl=db_ssl_mode(), timeout=15,
        )
        db = await conn.fetchval('SELECT current_database()')
        users = 0
        if await conn.fetchval(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='users')\"
        ):
            users = await conn.fetchval('SELECT COUNT(*)::int FROM users')
        await conn.close()
        print('[OK] Connected: database=%s users=%s' % (db, users))
    except asyncpg.InvalidPasswordError:
        print('[FAIL] Wrong postgres password. Run set-cutehost-password.bat')
        raise SystemExit(1)
    except Exception as exc:
        print('[FAIL]', exc)
        raise SystemExit(1)

asyncio.run(main())
"@

if ($LASTEXITCODE -ne 0) {
    if (-not $NoPause) { Read-Host 'Press Enter' }
    exit 1
}

if (-not $NoPause) { Read-Host 'Press Enter' }
exit 0
