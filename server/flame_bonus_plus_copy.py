# -*- coding: utf-8 -*-
"""Бонус + (предмет 🎁) — все тексты и подписи кнопок.

Как править
-----------
Этот файл — единственное место со словами Бонуса +.
Эмодзи телеграма держите в той же строке.
Числа, шансы и список предметов — вкладка «Огонёк → Бонус +».

После правки перезапустите бота.
"""
from __future__ import annotations

EMOJI = "5438458242130806642"
SPARK = "5321021153219732362"
STAR = "5233479338791281256"
GIFT = "5438458242130806642"
NOTE = "5467519850576354798"


def emoji(eid: str, fallback: str = "🎁") -> str:
    return f"<tg-emoji emoji-id='{eid}'>{fallback}</tg-emoji>"


def screen_intro(*, mult: int, kuty_lo: int, kuty_hi: int, items_on: bool) -> str:
    # Первый экран после «использовать 🎁».
    mult_bit = f" · уже ×{int(mult)}" if int(mult or 1) > 1 else ""
    extra = (
        f"\n{emoji(STAR, '⭐️')} Иногда рядом — ещё предмет от проекта."
        if items_on
        else ""
    )
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>{mult_bit}\n"
        "<blockquote>"
        "Это увеличенный бонус.\n"
        f"С клетки вы получите больше кут, чем в обычном бонусе: "
        f"<b>+{int(kuty_lo)}…{int(kuty_hi)}</b>."
        f"{extra}\n"
        "Спасибо, что играете с нами — это маленькая халява от проекта."
        "</blockquote>"
    )


def button_open() -> str:
    return "Открыть Бонус +"


def button_later() -> str:
    return "Позже"


def screen_later() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Бонус + отложен</b>\n"
        "<blockquote>Предмет 🎁 остался у вас.\n"
        "Когда будете готовы — снова «использовать 🎁».</blockquote>"
    )


def screen_board(*, mult: int, kuty_lo: int, kuty_hi: int) -> str:
    # Заголовок над клетками.
    mult_bit = f"×{int(mult)} · " if int(mult or 1) > 1 else ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        f"<blockquote>{mult_bit}<b>+{int(kuty_lo)}…{int(kuty_hi)}</b> кут\n"
        "Нажмите любую клетку — награда придёт сразу.\n"
        "Победа в игре не нужна.</blockquote>"
    )


def screen_need_cute(name: str) -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Чтобы открыть Бонус +, добавьте в имя <code>Cute</code></b>\n"
        f"<blockquote>Сейчас: <b>{name}</b>\n"
        "Пример: <code>Имя Cute</code></blockquote>\n"
        "<i>Предмет остался у вас.</i>"
    )


def screen_off() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Бонус + сейчас недоступен</b>\n"
        "<i>Попробуйте позже — предмет 🎁 остался у вас.</i>"
    )


def screen_fail() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Не удалось открыть Бонус +</b>\n"
        "<i>Попробуйте ещё раз — предмет остался у вас.</i>"
    )


def screen_result(
    *,
    board_kuty: int,
    extra_kuty: int = 0,
    project_kuty: int = 0,
    item_line: str = "",
) -> str:
    # Итог после клетки. project_kuty — запасной подарок без слова «процент».
    parts = [
        f"{emoji(GIFT)} <b>Бонус + ваш</b>",
        f"<blockquote>{emoji(SPARK, '⚡️')} С клетки: <b>+{int(board_kuty)}</b> кут</blockquote>",
    ]
    if int(extra_kuty or 0) > 0:
        parts.append(f"{emoji(STAR, '⭐️')} Ещё куты: <b>+{int(extra_kuty)}</b>")
    if item_line:
        parts.append(f"{emoji(GIFT)} {item_line}")
    if int(project_kuty or 0) > 0:
        parts.append(
            f"{emoji(STAR, '⭐️')} <b>+ дополнительные куты от самого проекта</b>: "
            f"<b>+{int(project_kuty)}</b>"
        )
    parts.append("<i>Спасибо, что вы с нами</i>")
    return "\n".join(parts)


def item_got(emoji_face: str, name: str) -> str:
    face = emoji_face or "🎁"
    return f"Вам: <code>{face}</code> <b>{name}</b>"


def alert_stranger() -> str:
    return "Эта кнопка не ваша."


def alert_gone() -> str:
    return "Открытие уже неактуально. Снова «использовать 🎁»."


def help_block(*, mult: int) -> str:
    mult_bit = f" Куты с доски уже ×{int(mult)}." if int(mult or 1) > 1 else ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        f"Напишите «использовать 🎁» — откроется увеличенный бонус.{mult_bit}\n"
        "Больше кут, чем в обычном бонусе, и иногда подарок-предмет от проекта.\n"
        "Нужна приписка <code>Cute</code> в имени. Победа в игре не нужна."
    )


HISTORY_BOARD = "бонус +"
HISTORY_EXTRA = "бонус + ещё"
HISTORY_PROJECT = "бонус + от проекта"
HISTORY_BUY = "бонус + покупка"
