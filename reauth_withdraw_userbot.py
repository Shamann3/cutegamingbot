"""
Переавторизация юзербота для выводов (withdraw_userbot_session).

Зачем: Telegram убил старую сессию (AuthKeyDuplicatedError — файл сессии
использовался одновременно с двух разных IP, это триггерит защиту от
угона и необратимо инвалидирует ключ). Повторные попытки connect() с тем
же файлом сессии больше НИКОГДА не заработают — нужен новый логин.

ВАЖНО: логинимся в НОВЫЙ файл (withdraw_userbot_session_new.session),
а не в старый withdraw_userbot_session.session — тот уже существует
локально и содержит тот самый мёртвый ключ, Telethon просто загрузит
его и снова получит AuthKeyDuplicatedError вместо нового логина.

Запуск ЛОКАЛЬНО (не на сервере!), на машине с доступом к телефону/
Telegram-аккаунту выводного юзербота, чтобы получить код входа:

    python reauth_withdraw_userbot.py

Скрипт запросит номер телефона, код из Telegram (и пароль 2FA, если он
включён на аккаунте), после чего создаст withdraw_userbot_session_new.session
в текущей папке.

После успешного логина ПЕРЕИМЕНУЙ новый файл поверх старого и запушь
(или используй reauth-withdraw.bat):

    move /Y withdraw_userbot_session_new.session withdraw_userbot_session.session
    git add -f withdraw_userbot_session.session
    git commit -m "chore: reauth withdraw userbot session"
    git push origin main

ВАЖНО: после переименования и до пуша — НЕ запускай main.py локально
с этим же файлом сессии одновременно с продакшеном на DigitalOcean.
Именно одновременное использование одной сессии с разных IP убило
предыдущий ключ — если это повторится, придётся переавторизовываться
заново.
"""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path

from telethon import TelegramClient

WITHDRAW_API_ID = 20558168
WITHDRAW_API_HASH = "9abe2a15c04cf0e34024b04ca7653aa6"
WITHDRAW_SESSION_NEW = "withdraw_userbot_session_new"


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

    # Не продолжаем поверх полубитого файла от прошлого падения
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
        device_model="CuteGaming Withdraw Userbot",
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

        # Сессию важно сохранить на диск до любых сетевых вызовов,
        # которые могут быть отменены багом Telethon.
        if hasattr(client.session, "save"):
            client.session.save()

        try:
            me = await client.get_me()
        except (asyncio.CancelledError, Exception) as exc:
            # Авторизация уже есть на диске — get_me не критичен
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
        print("")
        print("Теперь выполни (замени старый файл новым) или запусти bat:")
        print(f"  move /Y {session_file.name} withdraw_userbot_session.session")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main() -> int:
    try:
        await _authorize(WITHDRAW_SESSION_NEW, WITHDRAW_API_ID, WITHDRAW_API_HASH)
        return 0
    except KeyboardInterrupt:
        print("\n[ERROR] Прервано пользователем.")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Логин не удался: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
