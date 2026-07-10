"""Read-only inspection of staff_actions: columns, distinct action types, sample rows."""
import asyncio
import sys
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))


async def main() -> None:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, db_ssl_mode
    import asyncpg

    print(f"Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl=db_ssl_mode(),
        timeout=10,
    )
    try:
        print("\n=== staff_actions columns ===")
        cols = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'staff_actions'
            ORDER BY ordinal_position
            """
        )
        for c in cols:
            print(dict(c))

        print("\n=== distinct action_type counts ===")
        rows = await conn.fetch(
            "SELECT action_type, COUNT(*) AS n FROM staff_actions GROUP BY action_type ORDER BY n DESC"
        )
        for r in rows:
            print(dict(r))

        print("\n=== chat_id distribution (0 => project-wide) ===")
        try:
            rows = await conn.fetch(
                """
                SELECT action_type,
                       COUNT(*) FILTER (WHERE chat_id IS NULL) AS chat_null,
                       COUNT(*) FILTER (WHERE chat_id = 0) AS chat_zero,
                       COUNT(*) FILTER (WHERE chat_id <> 0) AS chat_specific
                FROM staff_actions GROUP BY action_type ORDER BY action_type
                """
            )
            for r in rows:
                print(dict(r))
        except Exception as e:
            print(f"(chat_id column missing or error: {e})")

        print("\n=== last 15 rows ===")
        rows = await conn.fetch(
            "SELECT * FROM staff_actions ORDER BY created_at DESC, id DESC LIMIT 15"
        )
        for r in rows:
            d = dict(r)
            if d.get("proof_media_id"):
                d["proof_media_id"] = str(d["proof_media_id"])[:20] + "...(truncated)"
            print(d)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
