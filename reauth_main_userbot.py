"""
Переавторизация ОСНОВНОГО (текстового) юзербота — main_userbot_session.

Аналог reauth_withdraw_userbot.py, но для основного украинского аккаунта,
которым бот шлёт прогревочные команды/контент. Именно этот юзербот бот
регистрирует ПЕРВЫМ на старте; пока он не авторизован, выводной юзербот
тоже не поднимается ("Технический юзербот для выводов не зарегистрирован").

Логинимся в НОВЫЙ файл main_userbot_session_new.session, чтобы не трогать
возможно-битый старый main_userbot_session.session.

Запуск ЛОКАЛЬНО, на машине с доступом к телефону украинского аккаунта:

    python reauth_main_userbot.py

Скрипт запросит номер телефона, код из Telegram (и пароль 2FA, если включён),
после чего создаст main_userbot_session_new.session в текущей папке.

ВАЖНО: как и с выводным — если аккаунт залогинен где-то ещё и читает код,
Telegram может заблокировать вход ("код сообщён"). Тогда на телефоне:
Настройки -> Устройства -> Завершить все другие сеансы, и код придёт по SMS.

После успешного логина reauth-main.bat сам заменит старый файл новым,
закоммитит и запушит (git add -f мимо .gitignore).
"""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path

from telethon import TelegramClient

# Параметры основного юзербота — совпадают с main.py (run_bot):
MAIN_API_ID = 26543591
MAIN_API_HASH = "a8de6a89ea1236962103eac13cd45d95"
MAIN_SESSION_NEW = "main_userbot_session_new"


def _session_path(name: str) -> Path:
    return Path(f"{name}.session")


async def _authorize(session_name: str, api_id: int, api_hash: str) -> None:
    """
    Логин без receive_updates: иначе Telethon 1.40.0 может упасть в
    update-loop (reset_deadline) сразу после успешного Signed in и
    отменить get_me() через CancelledError.
    """
    session_file = _session_path(session_name)
    journal = Path(f"{session_name}.session-journal")

    if session_file.exists() and session_file.stat().st_size == 0:
        session_file.unlink(missing_ok=True)
    if journal.exists():
        journal.unlink(missing_ok=True)

    warnings.filterwarnings(
        "ignore",
        message="Using async sessions support is an experimental feature",
        category=UserWarning,
    )

    client = TelegramClient(
        session_name,
        api_id,
        api_hash,
        receive_updates=False,
        device_model="CuteGaming Main Userbot",
        system_version="Windows",
        app_version="1.0",
        lang_code="ru",
        system_lang_code="ru",
    )

    me = None
    try:
        await client.start()

        if not await client.is_user_authorized():
            raise RuntimeError("Клиент не авторизован после start()")

        if hasattr(client.session, "save"):
            client.session.save()

        try:
            me = await client.get_me()
        except (asyncio.CancelledError, Exception) as exc:
            print(f"[warn] get_me() не удался ({type(exc).__name__}): {exc}")
            print("[warn] Сессия всё равно сохранена — проверяем файл…")

        if not session_file.exists() or session_file.stat().st_size < 64:
            raise RuntimeError(
                f"Файл сессии не создан или пуст: {session_file.resolve()}"
            )

        if me is not None:
            print(
                f"✅ Авторизован: id={me.id} username={me.username!r} "
                f"phone={me.phone!r}"
            )
        else:
            print("✅ Авторизован (профиль не прочитан, сессия на диске есть)")

        print(f"✅ Новая сессия сохранена в файл: {session_file.name}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main() -> int:
    try:
        await _authorize(MAIN_SESSION_NEW, MAIN_API_ID, MAIN_API_HASH)
        return 0
    except KeyboardInterrupt:
        print("\n[ERROR] Прервано пользователем.")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Логин не удался: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
