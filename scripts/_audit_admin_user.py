"""Read-only audit of admin-panel data for a Telegram user_id."""
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
        rows = await conn.fetch(
            """
            SELECT user_id, role, status, registered_at, username, first_name,
                   login_key IS NOT NULL AS has_login_key,
                   totp_secret IS NOT NULL AS has_totp,
                   session_fingerprint IS NOT NULL AS has_fingerprint,
                   force_reauth_at, last_seen_at
            FROM admin_accounts WHERE user_id = $1
            """,
            UID,
        )
        print("=== admin_accounts ===")
        for r in rows:
            print(dict(r))
        if not rows:
            print("(no row)")

        rows = await conn.fetch(
            """
            SELECT setup_token, user_id, expires_at, key_type,
                   invite_token IS NOT NULL AS has_invite
            FROM admin_register_pending WHERE user_id = $1
            """,
            UID,
        )
        print("=== admin_register_pending ===")
        for r in rows:
            print(dict(r))
        if not rows:
            print("(no rows)")

        rows = await conn.fetch(
            """
            SELECT id, status, assigned_role, created_at, reviewed_at
            FROM admin_applications
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 5
            """,
            UID,
        )
        print("=== admin_applications (last 5) ===")
        for r in rows:
            print(dict(r))
        if not rows:
            print("(no rows)")

        rows = await conn.fetch(
            """
            SELECT id, left(token, 12) AS token_prefix, label, used_by, used_at, revoked_at
            FROM admin_invite_tokens
            WHERE used_by = $1 OR created_by = $1
            LIMIT 5
            """,
            UID,
        )
        print("=== admin_invite_tokens ===")
        for r in rows:
            print(dict(r))
        if not rows:
            print("(no rows)")

        for tbl, col in [
            ("staff_actions", "admin_user_id"),
            ("admin_activity", "admin_user_id"),
            ("admin_audit_log", "admin_user_id"),
            ("staff_strikes", "user_id"),
            ("staff_salaries", "user_id"),
        ]:
            c = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl} WHERE {col} = $1", UID)
            print(f"count {tbl}: {c}")

        u = await conn.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
            UID,
        )
        print("=== users (game profile — NOT admin panel) ===")
        print(dict(u) if u else "NOT FOUND")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
