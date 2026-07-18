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

import asyncio

from telethon import TelegramClient

# Параметры основного юзербота — совпадают с main.py (run_bot):
MAIN_API_ID = 26543591
MAIN_API_HASH = "a8de6a89ea1236962103eac13cd45d95"
MAIN_SESSION_NEW = "main_userbot_session_new"


async def main() -> None:
    client = TelegramClient(
        MAIN_SESSION_NEW,
        MAIN_API_ID,
        MAIN_API_HASH,
        device_model="CuteGaming Main Userbot",
        system_version="Windows",
        app_version="1.0",
        lang_code="ru",
        system_lang_code="ru",
    )
    await client.start()
    me = await client.get_me()
    print(f"✅ Авторизован: id={me.id} username={me.username!r} phone={me.phone!r}")
    print(f"✅ Новая сессия сохранена в файл: {MAIN_SESSION_NEW}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
