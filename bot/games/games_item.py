# -*- coding: utf-8 -*-
"""Предметные мини-игры (слоты / боулинг / дартс / футбол / баскетбол).

Ставка = цена предмета из dex. Предмет списывается только после успешного броска
(это делает shop.py по коду возврата).
"""
from __future__ import annotations

import asyncio
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db_create.db import db
from bot.funcs.tg_dice import (
    is_basket_hit,
    is_bowling_strike,
    is_darts_bullseye,
    is_soccer_goal,
    read_dice_value,
)

# Анимация Telegram-dice ~4–5 с. Без паузы value часто пустой.
DICE_WAIT = 4.5

# Коды результата для вызывающего кода (useitems / shop).
OK_PLAYED = "played"       # бросок состоялся, предмет можно списать
SKIP_COOLDOWN = "cooldown"  # не играли
SKIP_BAD_BET = "bad_bet"
SKIP_UNREAD = "unread"      # бросок не прочитался — предмет не списывать


def _money(amount: int | float) -> str:
    return f"{round(amount):,.0f}".replace(",", ".")


def _result_kb(text: str, win: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=text[:64],
                callback_data="money_won" if win else "money_lost",
            )
        ]]
    )


async def _attach_result(dice_message, text: str, win: bool) -> None:
    try:
        await dice_message.edit_reply_markup(reply_markup=_result_kb(text, win))
    except Exception:
        try:
            await dice_message.reply(f"<b>{text}</b>", parse_mode="HTML")
        except Exception:
            pass


def get_combo_text(dice_value: int):
    values = ["BAR", "виноград", "лимон", "семь"]
    dice_value -= 1
    result = []
    for _ in range(3):
        result.append(values[dice_value % 4])
        dice_value //= 4
    return result


class Slots:
    MAX_BET = 500000

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = int(bet or 0)
        self.user_id = user_id
        self.balance = balance
        self.message = message

    async def main(self):
        """Возвращает (код, выигрыш). Баланс здесь не трогаем — только useitems."""
        if self.bet <= 0 or self.bet > self.MAX_BET:
            await self.message.answer(
                "Максимальная ставка <b>500.000 кут</b>" if self.bet > self.MAX_BET else "⚠️ Цена предмета не найдена",
                parse_mode="HTML",
            )
            return SKIP_BAD_BET, 0

        first_slots = await self.message.reply_dice(emoji="🎰")
        await asyncio.sleep(DICE_WAIT)
        value = read_dice_value(first_slots)
        if value is None:
            await _attach_result(first_slots, "Бросок не прочитался", False)
            return SKIP_UNREAD, 0

        combo = get_combo_text(value)
        multiplier_dict = {
            ("семь", "семь", "семь"): 2.7,
            ("виноград", "виноград", "виноград"): 1.9,
            ("лимон", "лимон", "лимон"): 2.5,
            ("BAR", "BAR", "BAR"): 2.3,
            ("семь", "BAR", "BAR"): 1.6,
            ("виноград", "BAR", "BAR"): 1.6,
            ("лимон", "BAR", "BAR"): 1.6,
            ("BAR", "BAR", "семь"): 1.6,
            ("BAR", "BAR", "виноград"): 1.6,
            ("BAR", "BAR", "лимон"): 1.6,
            ("лимон", "лимон", "семь"): 1.6,
            ("лимон", "лимон", "виноград"): 1.6,
            ("лимон", "лимон", "BAR"): 1.6,
            ("семь", "лимон", "лимон"): 1.6,
            ("виноград", "лимон", "лимон"): 1.6,
            ("BAR", "лимон", "лимон"): 1.6,
            ("виноград", "виноград", "BAR"): 1.6,
            ("виноград", "виноград", "лимон"): 1.6,
            ("виноград", "виноград", "семь"): 1.6,
            ("BAR", "виноград", "виноград"): 1.6,
            ("лимон", "виноград", "виноград"): 1.6,
            ("семь", "виноград", "виноград"): 1.6,
            ("семь", "семь", "BAR"): 1.6,
            ("семь", "семь", "лимон"): 1.6,
            ("семь", "семь", "виноград"): 1.6,
            ("BAR", "семь", "семь"): 1.6,
            ("лимон", "семь", "семь"): 1.6,
            ("виноград", "семь", "семь"): 1.6,
        }
        win_multiplier = multiplier_dict.get(tuple(combo), 0)
        if win_multiplier <= 0:
            await _attach_result(first_slots, "🔥 Ничего не выиграно", False)
            return OK_PLAYED, 0

        win_amount = round(self.bet * win_multiplier)
        await _attach_result(
            first_slots,
            f"🎰 Победа: {_money(win_amount)} | {win_multiplier:.1f}x",
            True,
        )
        try:
            await db.add_xp_to_games(self.user_id)
        except Exception:
            pass
        return OK_PLAYED, win_amount


class Bowling:
    MAX_BET = 500000
    MULT = 2.7

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = int(bet or 0)
        self.user_id = user_id
        self.balance = balance
        self.message = message

    async def main(self):
        if self.bet <= 0 or self.bet > self.MAX_BET:
            await self.message.answer(
                "Максимальная ставка <b>500.000 кут</b>" if self.bet > self.MAX_BET else "⚠️ Цена предмета не найдена",
                parse_mode="HTML",
            )
            return SKIP_BAD_BET, 0

        user_dice = await self.message.reply_dice(emoji="🎳")
        await asyncio.sleep(DICE_WAIT)
        value = read_dice_value(user_dice)
        if value is None:
            await _attach_result(user_dice, "Бросок не прочитался", False)
            return SKIP_UNREAD, 0

        if is_bowling_strike(value):
            win = round(self.bet * self.MULT)
            await _attach_result(user_dice, f"💸 Страйк! {_money(win)} кут", True)
            return OK_PLAYED, win

        await _attach_result(user_dice, "🔥 Вы не сбили все кегли", False)
        return OK_PLAYED, 0


class Dart:
    MAX_BET = 500000
    MULT = 2.6

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = int(bet or 0)
        self.user_id = user_id
        self.balance = balance
        self.message = message

    async def main(self):
        if self.bet <= 0 or self.bet > self.MAX_BET:
            await self.message.answer(
                "Максимальная ставка <b>500.000 кут</b>" if self.bet > self.MAX_BET else "⚠️ Цена предмета не найдена",
                parse_mode="HTML",
            )
            return SKIP_BAD_BET, 0

        user_dart = await self.message.reply_dice(emoji="🎯")
        await asyncio.sleep(DICE_WAIT)
        value = read_dice_value(user_dart)
        if value is None:
            await _attach_result(user_dart, "Бросок не прочитался", False)
            return SKIP_UNREAD, 0

        if is_darts_bullseye(value):
            win = round(self.bet * self.MULT)
            await _attach_result(user_dart, f"💸 В яблочко! {_money(win)} кут", True)
            return OK_PLAYED, win

        await _attach_result(user_dart, "🔥 Промах", False)
        return OK_PLAYED, 0


class FootGame:
    """Предмет ⚽️ / ⚽. Гол — значения 3, 4, 5 (мяч в сетке), как в живом футболе."""

    MAX_BET = 500000
    MULT = 2.4
    # Telegram принимает оба варианта эмодзи.
    EMOJIS = ("⚽", "⚽️")

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = int(bet or 0)
        self.user_id = user_id
        self.balance = balance
        self.message = message

    async def main(self):
        if self.bet <= 0 or self.bet > self.MAX_BET:
            await self.message.answer(
                "Максимальная ставка <b>500.000 кут</b>" if self.bet > self.MAX_BET else "⚠️ Цена предмета не найдена",
                parse_mode="HTML",
            )
            return SKIP_BAD_BET, 0

        user_dice = await self.message.reply_dice(emoji="⚽")
        await asyncio.sleep(DICE_WAIT)
        value = read_dice_value(user_dice)
        if value is None:
            await _attach_result(user_dice, "Бросок не прочитался", False)
            return SKIP_UNREAD, 0

        if is_soccer_goal(value):
            win = round(self.bet * self.MULT)
            await _attach_result(user_dice, f"💸 Гол! {_money(win)} кут", True)
            return OK_PLAYED, win

        await _attach_result(user_dice, "🔥 Мимо", False)
        return OK_PLAYED, 0


class Basketball:
    MAX_BET = 500000
    MULT = 2.4

    def __init__(self, bet: int, user_id, balance, bot, dp, message):
        self.bet = int(bet or 0)
        self.user_id = user_id
        self.balance = balance
        self.message = message

    async def main(self):
        if self.bet <= 0 or self.bet > self.MAX_BET:
            await self.message.answer(
                "Максимальная ставка <b>500.000 кут</b>" if self.bet > self.MAX_BET else "⚠️ Цена предмета не найдена",
                parse_mode="HTML",
            )
            return SKIP_BAD_BET, 0

        user_dice = await self.message.reply_dice(emoji="🏀")
        await asyncio.sleep(DICE_WAIT)
        value = read_dice_value(user_dice)
        if value is None:
            await _attach_result(user_dice, "Бросок не прочитался", False)
            return SKIP_UNREAD, 0

        if is_basket_hit(value):
            win = round(self.bet * self.MULT)
            await _attach_result(user_dice, f"💸 Попадание! {_money(win)} кут", True)
            return OK_PLAYED, win

        await _attach_result(user_dice, "🔥 Мимо", False)
        return OK_PLAYED, 0
