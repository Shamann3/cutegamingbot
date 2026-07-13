"""
Текстовый Telegram-бот фермы — тот же db.py и BOT_TOKEN.
Запуск: start-bot.ps1 или .venv/Scripts/python.exe game_bot.py
"""

import asyncio
import logging
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from bot.config.config import TOKEN
from config import WEBAPP_URL
from db import db

logging.basicConfig(level=logging.INFO)


def _webapp_url_fresh(url: str) -> str:
    """Добавляет метку версии (?v=timestamp) к URL WebApp.

    Telegram WebView агрессивно кэширует мини-приложение по URL. Свежая метка
    заставляет клиент загрузить актуальный код при каждом открытии — иначе на
    телефоне могла жить старая версия игры, и правки (например, фиксы багов)
    не подхватывались бы после деплоя."""
    try:
        parts = urlparse(url)
        query = dict(parse_qsl(parts.query))
        query["v"] = str(int(time.time()))
        return urlunparse(parts._replace(query=urlencode(query)))
    except Exception:
        return url




def _fmt(n: float) -> str:
    return "{:,.0f}".format(n).replace(",", ".")


async def main(*, manage_db: bool = True):
    """if not BOT_TOKEN:
        raise RuntimeError("Задай BOT_TOKEN в server/.env")"""

    if manage_db:
        await db.connect()
    else:
        await db.ensure_connected()

    bot = Bot(token=TOKEN)
    try:
        try:
            me = await bot.get_me()
            logging.info("[FARM-BOTS] game bot: @%s", me.username)
        except TelegramUnauthorizedError:
            raise RuntimeError(
                "BOT_TOKEN отклонён Telegram. Открой @BotFather → бот → API Token, "
            ) from None

        await bot.delete_my_commands()

        dp = Dispatcher()

        """@dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            name = message.from_user.first_name or "фермер"
            text = f"<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Добро пожаловать, {name}!</b>\n<b>Этот бот был создан для выращивания культур для проекта @CuteGamingbot</b>\n<blockquote><b>Этот бот является частью экосистемы Эпсилон</b></blockquote>"
            if WEBAPP_URL:
                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Открыть ферму", web_app=WebAppInfo(url=_webapp_url_fresh(WEBAPP_URL)))],
                    ]),icon_custom_emoji_id="5449850741667668411",
                    parse_mode="HTML",
                )
            else:
                await message.answer(text + "\n\n⚠️ WEBAPP_URL не задан в server/.env", parse_mode="HTML")"""

        if WEBAPP_URL:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🌿 Ферма",
                    web_app=WebAppInfo(url=_webapp_url_fresh(WEBAPP_URL)),
                )
            )
            logging.info("Кнопка Web App: %s", WEBAPP_URL)



        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if manage_db:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
