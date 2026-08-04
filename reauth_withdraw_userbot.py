"""
Переавторизация юзербота для выводов (withdraw_userbot_session).

Запуск ЛОКАЛЬНО (не на сервере), с доступом к телефону аккаунта +4796751305:

    python reauth_withdraw_userbot.py
    reauth-withdraw.bat

Логинимся в withdraw_userbot_session_new.session, bat сам заменит
файл и (по подтверждению) запушит на GitHub → DigitalOcean deploy.

НЕ запускай main.py локально с этой же сессией, пока она крутится
на проде — два IP = AuthKeyDuplicatedError.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from reauth_common import authorize_session

# Должны совпадать с main.py (TECH_* / WITHDRAW_*)
WITHDRAW_API_ID = 20558168
WITHDRAW_API_HASH = "9abe2a15c04cf0e34024b04ca7653aa6"
WITHDRAW_SESSION_NEW = "withdraw_userbot_session_new"
WITHDRAW_SESSION_FINAL = "withdraw_userbot_session"
WITHDRAW_PHONE = "+4796751305"
EXPECTED_USER_ID = 6801702632
EXPECTED_PHONE_DIGITS = "4796751305"


async def main(force_fresh: bool = False) -> int:
    print("=" * 60)
    print("  REAUTH: выводной юзербот (NO)")
    print(f"  телефон: {WITHDRAW_PHONE}")
    print(f"  ожид. id: {EXPECTED_USER_ID}")
    print("=" * 60)
    print()
    print("Совет: на телефоне Settings → Devices → Terminate other sessions,")
    print("чтобы код пришёл по SMS, а не «код уже сообщён».")
    print()

    try:
        await authorize_session(
            WITHDRAW_SESSION_NEW,
            WITHDRAW_API_ID,
            WITHDRAW_API_HASH,
            device_model="CuteGaming Withdraw Userbot",
            phone=WITHDRAW_PHONE,
            expected_user_id=EXPECTED_USER_ID,
            expected_phone_digits=EXPECTED_PHONE_DIGITS,
            final_session_name=WITHDRAW_SESSION_FINAL,
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
    parser = argparse.ArgumentParser(description="Reauth withdraw userbot session")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Не переиспользовать *_new.session, всегда свежий логин",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(force_fresh=args.fresh)))
