"""
Переавторизация юзербота для выводов (withdraw_userbot_session).

Зачем: Telegram убил старую сессию (AuthKeyDuplicatedError - файл сессии
использовался одновременно с двух разных IP, это триггерит защиту от
угона и необратимо инвалидирует ключ). Повторные попытки connect() с тем
же файлом сессии больше НИКОГДА не заработают - нужен новый логин.

ВАЖНО: логинимся в НОВЫЙ файл (withdraw_userbot_session_new.session),
а не в старый withdraw_userbot_session.session - тот уже существует
локально и содержит тот самый мёртвый ключ, Telethon просто загрузит
его и снова получит AuthKeyDuplicatedError вместо нового логина.

Запуск ЛОКАЛЬНО (не на сервере!), на машине с доступом к телефону/
Telegram-аккаунту выводного юзербота, чтобы получить код входа:

    python reauth_withdraw_userbot.py

Скрипт запросит номер телефона, код из Telegram (и пароль 2FA, если он
включён на аккаунте), после чего создаст withdraw_userbot_session_new.session
в текущей папке.

После успешного логина ПЕРЕИМЕНУЙ новый файл поверх старого и запушь:
    move /Y withdraw_userbot_session_new.session withdraw_userbot_session.session
    git add withdraw_userbot_session.session
    git commit -m "chore: reauth withdraw userbot session"
    git push origin main

ВАЖНО: после переименования и до пуша - НЕ запускай main.py локально
с этим же файлом сессии одновременно с продакшеном на DigitalOcean.
Именно одновременное использование одной сессии с разных IP убило
предыдущий ключ - если это повторится, придётся переавторизовываться
заново.
"""

import asyncio

from telethon import TelegramClient

WITHDRAW_API_ID = 20558168
WITHDRAW_API_HASH = "9abe2a15c04cf0e34024b04ca7653aa6"
WITHDRAW_SESSION_NEW = "withdraw_userbot_session_new"


async def main() -> None:
    client = TelegramClient(WITHDRAW_SESSION_NEW, WITHDRAW_API_ID, WITHDRAW_API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"✅ Авторизован: id={me.id} username={me.username!r} phone={me.phone!r}")
    print(f"✅ Новая сессия сохранена в файл: {WITHDRAW_SESSION_NEW}.session")
    print("")
    print("Теперь выполни (замени старый файл новым):")
    print(f"  move /Y {WITHDRAW_SESSION_NEW}.session withdraw_userbot_session.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
