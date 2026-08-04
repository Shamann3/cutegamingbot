"""
Переавторизация ОСНОВНОГО (текстового) юзербота — main_userbot_session.

Бот регистрирует MAIN первым; без него выводной тоже не поднимется.

    python reauth_main_userbot.py
    reauth-main.bat
"""

from __future__ import annotations

import argparse
import asyncio

from reauth_common import authorize_session

# Должны совпадать с main.py (run_bot MAIN_*)
MAIN_API_ID = 26543591
MAIN_API_HASH = "a8de6a89ea1236962103eac13cd45d95"
MAIN_SESSION_NEW = "main_userbot_session_new"
MAIN_SESSION_FINAL = "main_userbot_session"


async def main(force_fresh: bool = False) -> int:
    print("=" * 60)
    print("  REAUTH: основной юзербот (UA)")
    print("=" * 60)
    print()
    print("Совет: на телефоне Settings → Devices → Terminate other sessions,")
    print("чтобы код пришёл по SMS.")
    print()

    try:
        await authorize_session(
            MAIN_SESSION_NEW,
            MAIN_API_ID,
            MAIN_API_HASH,
            device_model="CuteGaming Main Userbot",
            phone=None,
            expected_user_id=None,
            expected_phone_digits=None,
            final_session_name=MAIN_SESSION_FINAL,
            force_fresh=force_fresh,
        )
        return 0
    except KeyboardInterrupt:
        print("\n[ERROR] Прервано пользователем.")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Логин не удался: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reauth main userbot session")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Не переиспользовать *_new.session, всегда свежий логин",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(force_fresh=args.fresh)))
