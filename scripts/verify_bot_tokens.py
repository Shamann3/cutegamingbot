#!/usr/bin/env python3
"""Проверка всех токенов ботов через Telegram getMe (без вывода полных секретов)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from config import (  # noqa: E402
    ADMIN_BOT_EXPECTED_ID,
    ADMIN_BOT_TOKEN,
    BOT_TOKEN,
    SUPPORT_BOT_TOKEN,
    describe_bot_tokens,
    token_bot_id,
    token_fingerprint,
    validate_bot_tokens,
    verify_bot_token_telegram,
)


async def main() -> int:
    print("=== Карта токенов (server/config.py + bot/config/config.py) ===\n")
    for entry in describe_bot_tokens():
        print(f"{entry['key']:20} [{entry['source']}]")
        print(f"  id:          {entry['bot_id']}")
        print(f"  fingerprint: {entry['fingerprint']}")
        print(f"  role:        {entry['role']}\n")

    print("=== validate_bot_tokens() ===")
    warnings = validate_bot_tokens()
    if warnings:
        for w in warnings:
            print(f"  WARN: {w}")
    else:
        print("  OK — предупреждений нет")

    print("\n=== Telegram getMe ===")
    checks = [
        ("ADMIN_BOT_TOKEN", ADMIN_BOT_TOKEN, ADMIN_BOT_EXPECTED_ID),
        ("BOT_TOKEN", BOT_TOKEN, ""),
        ("SUPPORT_BOT_TOKEN", SUPPORT_BOT_TOKEN, ""),
    ]
    exit_code = 0
    for label, token, expected_id in checks:
        if not token:
            print(f"  {label}: пропуск (пусто)")
            continue
        info = await verify_bot_token_telegram(token)
        fp = token_fingerprint(token)
        if info and info.get("ok"):
            bid = str(info.get("id", ""))
            uname = info.get("username") or "?"
            print(f"  {label}: OK @{uname} id={bid} fp={fp}")
            if expected_id and bid != expected_id:
                print(f"    ОШИБКА: ожидался bot id {expected_id}, получен {bid}")
                exit_code = 1
        else:
            err = (info or {}).get("error", "unknown")
            print(f"  {label}: FAIL — {err} fp={fp}")
            exit_code = 1

    if ADMIN_BOT_TOKEN:
        actual = token_bot_id(ADMIN_BOT_TOKEN)
        if ADMIN_BOT_EXPECTED_ID and actual == ADMIN_BOT_EXPECTED_ID:
            print(f"\nAdmin-бот: id {actual} совпадает с ADMIN_BOT_EXPECTED_ID.")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
