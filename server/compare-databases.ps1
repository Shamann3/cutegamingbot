# Compare local PG (5432) vs CuteHost tunnel (15432)
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host '[ERROR] venv not found' -ForegroundColor Red
    exit 1
}

$tunnelUp = [bool](Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue)
if (-not $tunnelUp) {
    Write-Host '[WARN] SSH tunnel :15432 is not running. Remote test skipped.' -ForegroundColor Yellow
    Write-Host '       Run start-ssh-cutehost.bat first for full compare.' -ForegroundColor Yellow
    Write-Host ''
}

$includeRemote = if ($tunnelUp) { 'True' } else { 'False' }

& $python -c @"
import asyncio
import asyncpg
from config import DB_PASSWORD, DB_USER, db_ssl_mode

INCLUDE_REMOTE = $includeRemote
TARGETS = [
    ('LOCAL  PostgreSQL 17', '127.0.0.1', 5432, 'cutebase'),
    ('LOCAL  test postgres', '127.0.0.1', 5432, 'postgres'),
]
if INCLUDE_REMOTE:
    TARGETS += [
        ('REMOTE CuteHost tunnel', '127.0.0.1', 15432, 'cutebase'),
        ('REMOTE CuteHost postgres', '127.0.0.1', 15432, 'postgres'),
    ]

async def probe(label, host, port, db):
    print(f'--- {label} ({host}:{port}/{db}) ---')
    try:
        conn = await asyncpg.connect(
            user=DB_USER, password=DB_PASSWORD, database=db,
            host=host, port=port, ssl=db_ssl_mode(), timeout=8,
        )
        users = 0
        if await conn.fetchval(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='users')\"
        ):
            users = await conn.fetchval('SELECT COUNT(*)::int FROM users')
        ver = await conn.fetchval('SELECT version()')
        await conn.close()
        print(f'  OK  users={users}')
        print(f'      {ver[:70]}...')
        return True
    except asyncpg.InvalidPasswordError:
        print('  FAIL  password authentication failed (TCP password wrong on this host)')
        return False
    except Exception as exc:
        print(f'  FAIL  {exc}')
        return False

async def main():
    print(f'user={DB_USER!r}  password_len={len(DB_PASSWORD)}')
    print('')
    for t in TARGETS:
        await probe(*t)
        print('')

asyncio.run(main())
"@
