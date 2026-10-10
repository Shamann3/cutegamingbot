"""Telegram-бот админки — отдельный от игрового bot.py."""

from __future__ import annotations

import asyncio
import html
import logging
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo

from admin_bot_design import ERROR_NO_PANEL, WAVE, button_rows, emoji_id, screen_text
from config import ADMIN_BOT_TOKEN, ADMIN_ENABLED, ADMIN_WEBAPP_URL, admin_user_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cute-farm.admin-bot")


def _webapp_url_fresh(url: str, door: str = "") -> str:
    """Добавляет метку версии (?v=timestamp) к URL панели.

    Telegram WebView агрессивно кэширует мини-приложение по URL. Свежая метка
    заставляет клиент загрузить актуальный код при каждом открытии — иначе на
    телефоне могла жить старая версия панели, и правки не подхватывались.
    door — пусто, если открывается сама панель, без кабинета."""
    try:
        parts = urlparse(url)
        query = dict(parse_qsl(parts.query))
        query["v"] = str(int(time.time()))
        if door:
            query["go"] = door
        return urlunparse(parts._replace(query=urlencode(query)))
    except Exception:
        return url


def _screen_name(user_id: int, asked: str) -> str:
    if asked == "start" and _is_admin(user_id):
        return "start_known"
    if asked == "start":
        return "start"
    return asked if asked in ("apply", "start_known") else "start"


def _markup(name: str) -> InlineKeyboardMarkup:
    rows = []
    for row in button_rows(name):
        built = []
        for btn in row:
            door = str(btn.get("webapp") or "")
            icon = emoji_id(btn.get("icon") or "")
            if door:
                if not ADMIN_WEBAPP_URL:
                    continue
                # panel — сама панель, дверь человек выбирает уже внутри.
                kwargs = {
                    "text": btn["text"],
                    "web_app": WebAppInfo(url=_webapp_url_fresh(
                        ADMIN_WEBAPP_URL,
                        "" if door == "panel" else door,
                    )),
                }
            else:
                kwargs = {"text": btn["text"], "callback_data": "eps:" + str(btn.get("go") or "start")}
            if icon:
                kwargs["icon_custom_emoji_id"] = icon
            built.append(InlineKeyboardButton(**kwargs))
        if built:
            rows.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _start_body(name: str, user_name: str) -> str:
    safe = html.escape(user_name or "admin").replace("{", "").replace("}", "")
    text = screen_text(name, wave=WAVE, name=safe)
    if not ADMIN_WEBAPP_URL:
        text += "\n\n" + ERROR_NO_PANEL
    return text


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
        screen = _screen_name(user_id, "start")
        await message.answer(
            _start_body(screen, name),
            reply_markup=_markup(screen),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("eps:"))
    async def on_screen(query: types.CallbackQuery):
        asked = (query.data or "").split(":", 1)[1]
        user = query.from_user
        name = (user.first_name if user else "") or "admin"
        screen = _screen_name(user.id if user else 0, "start" if asked == "start" else asked)
        await query.answer()
        try:
            await query.message.edit_text(
                _start_body(screen, name),
                reply_markup=_markup(screen),
                parse_mode="HTML",
            )
        except Exception:
            logger.debug("admin start screen edit skipped", exc_info=True)

    await run_polling(dp, bot, label="admin-bot")


async def main() -> None:
    await run_admin_bot()

if __name__ == "__main__":
    asyncio.run(main())