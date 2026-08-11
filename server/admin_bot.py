"""Telegram-бот админки — отдельный от игрового bot.py."""

from __future__ import annotations

import logging
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.types import MenuButtonWebApp, WebAppInfo

from config import ADMIN_BOT_TOKEN, ADMIN_ENABLED, ADMIN_WEBAPP_URL, admin_user_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cute-farm.admin-bot")


def _webapp_url_fresh(url: str) -> str:
    """Добавляет метку версии (?v=timestamp) к URL панели.

    Telegram WebView агрессивно кэширует мини-приложение по URL. Свежая метка
    заставляет клиент загрузить актуальный код при каждом открытии — иначе на
    телефоне могла жить старая версия панели, и правки не подхватывались."""
    try:
        parts = urlparse(url)
        query = dict(parse_qsl(parts.query))
        query["v"] = str(int(time.time()))
        return urlunparse(parts._replace(query=urlencode(query)))
    except Exception:
        return url


def _is_admin(user_id: int) -> bool:
    allowed = admin_user_ids()
    return bool(allowed) and user_id in allowed


async def run_admin_bot() -> None:
    if not ADMIN_ENABLED:
        logger.info("ADMIN_ENABLED=false — admin bot не запускается")
        return

    if not ADMIN_BOT_TOKEN:
        logger.warning("ADMIN_BOT_TOKEN не задан — admin bot пропущен")
        return

    from bot_polling import run_polling
    from aiogram.client.session.aiohttp import AiohttpSession

    # Локально на Windows часто ловим WinError 121 (таймаут семафора) —
    # короткий timeout aiohttp убивает старт. Держим запас.
    session = AiohttpSession(timeout=120.0)
    bot = Bot(token=ADMIN_BOT_TOKEN, session=session)
    try:
        me = await bot.get_me()
        logger.info("Admin bot: @%s (id=%s)", me.username, me.id)
    except TelegramUnauthorizedError:
        await bot.session.close()
        raise RuntimeError(
            "ADMIN_BOT_TOKEN отклонён Telegram. Создайте второго бота в @BotFather "
            "и вставьте его API Token в server/.env"
        ) from None

    dp = Dispatcher()

    # Мэджик: все inline-кнопки admin-бота
    try:
        from bot.magic import install_magic

        install_magic(dp, start_health=False)
    except Exception as _magic_err:
        logger.warning("Magic not attached to admin bot: %r", _magic_err)

    if ADMIN_WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🛡 Panel",
                web_app=WebAppInfo(url=_webapp_url_fresh(ADMIN_WEBAPP_URL)),
            )
        )
        logger.info("Admin Web App URL: %s", ADMIN_WEBAPP_URL)

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        user_id = message.from_user.id
        name = message.from_user.first_name or "admin"
        if _is_admin(user_id):
            text = f"<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Добро пожаловать, {name}.\nЭто бот модерации всей экосистемой Cute.</b>\n<blockquote><b>Виво-Эпсилон!</b></blockquote>"
        else:
            # Кандидаты/новый персонал: доступ внутри панели проверяется по ключу.
            text = (
                f"<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Добро пожаловать, {name}.\nЭто бот модерации всей экосистемой Cute.</b>\n<b>Откройте панель и пройдите регистрацию по выданному ключу.</b>\n<blockquote><b>Виво-Эпсилон!</b></blockquote>"
            )

        if ADMIN_WEBAPP_URL:
            await message.answer(
                text,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="Открыть панель",
                                web_app=WebAppInfo(url=_webapp_url_fresh(ADMIN_WEBAPP_URL)),
                                icon_custom_emoji_id="5361948635317680832",
                            )
                        ]
                    ]
                ),
                parse_mode="HTML",
            )
        else:
            #ошибка 512910 ADMIN_WEBAPP_URL не задан в .env
            await message.answer(
                text + "\n\n<b>Ошибка <code>#512910</code> ( обратитесь к сотрудникам эпсилона )</b> ",
                parse_mode="HTML",
            )

    await run_polling(dp, bot, label="admin-bot")


async def main() -> None:
    await run_admin_bot()

if __name__ == "__main__":
    asyncio.run(main())