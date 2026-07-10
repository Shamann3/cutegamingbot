"""Check the latest pending admin-registration TOTP code for one Telegram user."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from admin_auth import normalize_totp_code, verify_totp  # noqa: E402
from db import db  # noqa: E402
import pyotp  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", type=int)
    parser.add_argument("code")
    args = parser.parse_args()

    code = normalize_totp_code(args.code)
    if len(code) != 6:
        print("ERROR: code must contain 6 digits")
        return 2

    await db.connect()
    try:
        row = await db.pool.fetchrow(
            """
            SELECT setup_token, totp_secret, expires_at, key_type
            FROM admin_register_pending
            WHERE user_id = $1
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            args.user_id,
        )

        if not row:
            print("NO PENDING: press Back -> Continue to create a new QR first")
            return 1

        secret = (row["totp_secret"] or "").replace(" ", "").upper()
        print("pending token:", row["setup_token"][:8] + "...")
        print("key type:", row["key_type"])
        print("expires at:", row["expires_at"])
        print("secret tail in DB:", secret[-4:] if secret else "EMPTY")
        print("entered code:", code)
        print("server unix time:", int(time.time()))
        if secret:
            totp = pyotp.TOTP(secret, digits=6, interval=30)
            print("SERVER EXPECTED CODE NOW:", totp.now())
            print("seconds left:", 30 - (int(time.time()) % 30))
        print("MATCH narrow window:", verify_totp(secret, code, valid_window=1))
        print("MATCH wide window:", verify_totp(secret, code, valid_window=30))
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
