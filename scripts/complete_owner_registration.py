#!/usr/bin/env python3
"""
Завершить регистрацию владельца вручную (если TOTP в WebApp не проходит).

Пример:
  python scripts/complete_owner_registration.py 6801702632
  python scripts/complete_owner_registration.py 6801702632 --code 123456
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Complete owner admin registration")
    parser.add_argument("user_id", type=int, help="Telegram user_id")
    parser.add_argument("--code", type=str, default="", help="6-digit TOTP to verify (optional)")
    parser.add_argument("--force", action="store_true", help="Skip TOTP verify (local fix only)")
    args = parser.parse_args()
    uid = args.user_id

    from admin_auth import normalize_totp_code, verify_totp
    from admin_db import (
        confirm_admin_registration,
        get_admin_account,
        get_pending_registration_by_token,
    )
    from db import db

    await db.connect()
    try:
        if await get_admin_account(uid):
            print(f"OK: admin_accounts already exists for user_id={uid}")
            return 0

        row = await db.pool.fetchrow(
            """
            SELECT setup_token, totp_secret, key_type, invite_token, expires_at
            FROM admin_register_pending
            WHERE user_id = $1
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            uid,
        )
        if not row:
            print(f"ERROR: no admin_register_pending for user_id={uid}")
            print("  Start registration in panel first (key + QR), then run this script.")
            return 1

        pending = dict(row)
        secret = pending["totp_secret"]
        print(f"pending setup_token={pending['setup_token'][:12]}…")
        print(f"totp_secret tail=…{secret[-4:] if secret else '????'}")
        print(f"expires_at={pending['expires_at']}")

        code = normalize_totp_code(args.code)
        if not args.force:
            if len(code) != 6:
                code = normalize_totp_code(input("Enter 6-digit code from Authenticator: "))
            if not verify_totp(secret, code, valid_window=12):
                print("ERROR: TOTP code does not match pending secret.")
                print("  Use the Authenticator entry for this secret tail, or re-register and retry.")
                return 1

        tg = await db.pool.fetchrow(
            "SELECT username, firstname FROM users WHERE user_id = $1",
            uid,
        )
        username = tg["username"] if tg else None
        first_name = tg["firstname"] if tg else None

        key_type = pending.get("key_type") or "owner"
        role = "owner" if key_type == "owner" else "applicant"
        status = "active" if key_type == "owner" else "pending"

        ok = await confirm_admin_registration(
            pending["setup_token"],
            uid,
            secret,
            username=username,
            first_name=first_name,
            role=role,
            status=status,
            invite_token=pending.get("invite_token"),
        )
        if not ok:
            print("ERROR: confirm_admin_registration failed (invite race?)")
            return 1

        print(f"OK: admin_accounts created user_id={uid} role={role} status={status}")
        print("  Login: tab «Вход» → key @CuteGamingBot3412... + code from Authenticator")
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
