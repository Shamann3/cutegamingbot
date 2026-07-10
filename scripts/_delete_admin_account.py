"""Delete a single admin_accounts row (admin panel registration only)."""
import asyncio
import sys
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

UID = int(sys.argv[1]) if len(sys.argv) > 1 else 6801702632


async def main() -> None:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, db_ssl_mode
    import asyncpg

    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl=db_ssl_mode(),
    )
    try:
        before = await conn.fetchrow(
            "SELECT user_id, role, status, registered_at FROM admin_accounts WHERE user_id = $1",
            UID,
        )
        if not before:
            print(f"NOT_FOUND: admin_accounts user_id={UID}")
            return

        print("BEFORE:", dict(before))
        result = await conn.execute(
            "DELETE FROM admin_accounts WHERE user_id = $1",
            UID,
        )
        print("DELETE:", result)

        after = await conn.fetchrow(
            "SELECT user_id FROM admin_accounts WHERE user_id = $1",
            UID,
        )
        print("AFTER:", "row still exists" if after else "ok — no row")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
