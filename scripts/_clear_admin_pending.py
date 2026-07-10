"""Clear admin_register_pending for a Telegram user_id (stuck registration)."""
import asyncio
import sys
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

UID = int(sys.argv[1]) if len(sys.argv) > 1 else 0


async def main() -> None:
    if UID <= 0:
        print("Usage: python scripts/_clear_admin_pending.py <telegram_user_id>")
        return

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
        rows = await conn.fetch(
            """
            SELECT setup_token, user_id, expires_at, key_type
            FROM admin_register_pending
            WHERE user_id = $1
            """,
            UID,
        )
        if not rows:
            print(f"No pending registration for user_id={UID}")
            return
        for row in rows:
            print("PENDING:", dict(row))
        result = await conn.execute(
            "DELETE FROM admin_register_pending WHERE user_id = $1",
            UID,
        )
        print("DELETE:", result)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
