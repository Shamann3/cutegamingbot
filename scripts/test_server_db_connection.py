"""Проверка пула server/db.py (WebApp API)."""

import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))


async def main() -> int:
    db_mod = importlib.import_module("db")
    db = db_mod.db
    try:
        await db.connect()
    except Exception as exc:
        print(f"[test_server_db] FAIL — {exc}")
        return 1
    if not db.pool:
        print("[test_server_db] FAIL — pool is None")
        return 1
    async with db.pool.acquire() as conn:
        name = await conn.fetchval("SELECT current_database()")
        users = await conn.fetchval("SELECT COUNT(*)::int FROM users") or 0
    print(f"[test_server_db] OK — {name} users={users}")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
