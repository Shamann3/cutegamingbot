#!/usr/bin/env python3
"""Создаёт/восстанавливает аккаунты владельцев в admin_accounts.

Запуск (из корня проекта):
  server\\.venv\\Scripts\\python.exe scripts\\ensure_owner_admin.py

Требует ADMIN_TOTP_SECRET в корневом .env — этот секрет нужно добавить
в Google Authenticator (CuteFarming Panel).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from admin_auth import build_otpauth_uri, normalize_totp_secret, totp_qr_data_url
from admin_db import bootstrap_owner_accounts, get_admin_account
from config import ADMIN_TOTP_SECRET, owner_user_ids, ACTIVE_DB_PROFILE, DB_LOCATION, DB_HOST, DB_PORT, DB_NAME
from db import db


async def main() -> int:
    secret = normalize_totp_secret(ADMIN_TOTP_SECRET)
    print(f"DB target: {ACTIVE_DB_PROFILE}/{DB_LOCATION} -> {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Owners: {sorted(owner_user_ids())}")
    if not secret:
        print("ERROR: задайте ADMIN_TOTP_SECRET в корневом .env (base32, латиница/цифры 2-7).")
        return 1

    await db.connect()
    try:
        changed = await bootstrap_owner_accounts()
        print(f"bootstrap_owner_accounts: changed={changed}")
        for uid in sorted(owner_user_ids()):
            acc = await get_admin_account(uid)
            print(f"  user {uid}: role={acc and acc.get('role')} status={acc and acc.get('status')}")
        uri = build_otpauth_uri(secret, account_name="CuteFarming Owner")
        qr_path = ROOT / "panel" / "owner-totp-setup.html"
        html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Owner TOTP</title></head>
<body style="font-family:sans-serif;background:#111;color:#eee;padding:2rem">
<h1>CuteFarming Panel — TOTP владельца</h1>
<p>Отсканируйте QR в Google Authenticator / Authy. Удалите старые записи «CuteFarming Panel».</p>
<p><img src="{totp_qr_data_url(uri)}" alt="QR" style="background:#fff;padding:12px;border-radius:12px"/></p>
<p>Ручной ключ: <code>{secret}</code></p>
<p>Вход: admin-бот → панель → ключ <code>@CuteGamingBot3412...</code> + 6 цифр из приложения.</p>
</body></html>"""
        qr_path.write_text(html, encoding="utf-8")
        print(f"QR-страница: {qr_path}")
        print(f"OTPAuth URI: {uri}")
    finally:
        await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
