"""
Текстовый Telegram-бот фермы — тот же db.py и BOT_TOKEN.
Запуск: start-bot.ps1 или .venv/Scripts/python.exe game_bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo

from config import BOT_TOKEN, WEBAPP_URL
from db import db

logging.basicConfig(level=logging.INFO)

_CHAT_BALANCE_TRIGGERS = {
    "баланс чата", "баланс группы", "балик чата", "балик группы",
    "бг", "бч", "казна",
}


def _fmt(n: float) -> str:
    return "{:,.0f}".format(n).replace(",", ".")


async def main(*, manage_db: bool = True):
    if not BOT_TOKEN:
        raise RuntimeError("Задай BOT_TOKEN в server/.env")

    if manage_db:
        await db.connect()
    else:
        await db.ensure_connected()

    bot = Bot(token=BOT_TOKEN)
    try:
        try:
            me = await bot.get_me()
            logging.info("[FARM-BOTS] game bot: @%s", me.username)
        except TelegramUnauthorizedError:
            raise RuntimeError(
                "BOT_TOKEN отклонён Telegram. Открой @BotFather → бот → API Token, "
                "вставь в server/.env. Это НЕ ngrok authtoken!"
            ) from None

        await bot.delete_my_commands()

        dp = Dispatcher()

        @dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            name = message.from_user.first_name or "фермер"
            text = f"<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Добро пожаловать, {name}!</b>\n<b>Этот бот был создан для выращивания культур для проекта @CuteGamingbot</b>\n<blockquote><b>Этот бот является частью экосистемы Эпсилон</b></blockquote>"
            if WEBAPP_URL:
                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Открыть ферму", web_app=WebAppInfo(url=WEBAPP_URL))],
                    ]),icon_custom_emoji_id="5449850741667668411",
                    parse_mode="HTML",
                )
            else:
                await message.answer(text + "\n\n⚠️ WEBAPP_URL не задан в server/.env", parse_mode="HTML")

        if WEBAPP_URL:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🌿 Ферма",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
            logging.info("Кнопка Web App: %s", WEBAPP_URL)

        @dp.message(F.text.func(lambda t: t and t.strip().lower() in _CHAT_BALANCE_TRIGGERS))
        async def cmd_chat_balance(message: types.Message):
            if message.chat.type == "private":
                await message.reply(
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Баланс группы работает только в группах.</b>",
                    parse_mode="HTML",
                )
                return

            if not message.chat.username:
                await message.reply(
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Баланс группы доступен только в публичных группах (у группы должен быть @username).</b>",
                    parse_mode="HTML",
                )
                return

            chat_id = int(message.chat.id)
            try:
                chatbalance, dexbalance = await db.get_chat_balances(chat_id)
                total = chatbalance + dexbalance

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"{_fmt(total)} кут",
                        callback_data="group_balance_overview",
                    )],
                    [InlineKeyboardButton(
                        text="Подробнее",
                        callback_data=f"group_balance_details:{chatbalance}:{dexbalance}",
                    )],
                ])
                await message.reply("<tg-emoji emoji-id='5251344521546965676'>🏖</tg-emoji>", reply_markup=keyboard, parse_mode="HTML")

            except Exception as e:
                logging.warning("cmd_chat_balance error chat_id=%s: %s", chat_id, e)
                await message.reply(
                    "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Ошибка при получении баланса чата. Попробуйте позже.</b>",
                    parse_mode="HTML",
                )

        @dp.callback_query(F.data == "group_balance_overview")
        async def cb_balance_overview(callback: types.CallbackQuery):
            await callback.answer("Общий баланс чата (казна + биржа)")

        @dp.callback_query(F.data.startswith("group_balance_details:"))
        async def cb_balance_details(callback: types.CallbackQuery):
            try:
                _, chatbalance_str, dexbalance_str = callback.data.split(":", 2)
                chatbalance = float(chatbalance_str)
                dexbalance = float(dexbalance_str)
                total = chatbalance + dexbalance
                await callback.answer(
                    f"💰 Казна : {_fmt(chatbalance)} кут\n"
                    f"🧩 Биржа : {_fmt(dexbalance)} кут\n"
                    f"━━━━━━━━━━\n"
                    f"📖 Итого : {_fmt(total)} кут",
                    show_alert=True,
                )
            except Exception:
                await callback.answer("Ошибка при загрузке данных", show_alert=True)

        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if manage_db:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
