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


def screen_intro(*, mult: int, kuty_lo: int, kuty_hi: int, items_on: bool, item_count: int = 1) -> str:
    mult_bit = f" · ×{int(mult)}" if int(mult or 1) > 1 else ""
    slots = max(1, int(item_count or 1))
    if items_on:
        if slots > 1:
            extra = f"\n{emoji(STAR, '⭐️')} Иногда рядом — до <b>{slots}</b> предметов."
        else:
            extra = f"\n{emoji(STAR, '⭐️')} Иногда рядом — ещё предмет."
    else:
        extra = ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>{mult_bit}\n"
        "<blockquote>"
        "<b>Это улучшенный бонус, с более крутыми подарками</b>\n"
        f"С клетки: <b>+{int(kuty_lo)}…{int(kuty_hi)}</b> кут."
        f"{extra}\n"
        "<i>Спасибо, что вы с нами.</i>"
        "</blockquote>\n"
        "<b>Нажмите на одну из кнопок.</b>"
    )


def button_open() -> str:
    return "Открыть Бонус +"


def button_later() -> str:
    return "Позже"


def screen_later() -> str:
    return (
        "<code>🎁</code> <b>Предмет остался у вас.</b>\n"
        "<i>Когда будете готовы — напишите</i> "
        "«<code>использовать 🎁</code>» <i>снова.</i>"
    )


def screen_board(*, mult: int, kuty_lo: int, kuty_hi: int) -> str:
    mult_bit = f"×{int(mult)} · " if int(mult or 1) > 1 else ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        f"<blockquote>{mult_bit}<b>+{int(kuty_lo)}…{int(kuty_hi)}</b> кут\n"
        "Нажмите клетку — награда сразу.\n"
        "Победа в игре не нужна.</blockquote>"
    )


def screen_need_cute(name: str) -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Добавьте в имя <code>Cute</code></b>\n"
        f"<blockquote>Сейчас: <b>{name}</b>\n"
        "Пример: <code>Имя Cute</code></blockquote>\n"
        "<i>🎁 остался у вас.</i>"
    )


def screen_off() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Бонус + сейчас недоступен</b>\n"
        "<i>Попробуйте позже — 🎁 остался у вас.</i>"
    )


def screen_fail() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Не удалось открыть</b>\n"
        "<i>Попробуйте ещё раз — 🎁 остался у вас.</i>"
    )


def screen_dry() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Сейчас наградить нечем</b>\n"
        "<blockquote>Куты и предметы берутся из запасов проекта.\n"
        "Попробуйте чуть позже.</blockquote>"
    )


def screen_result(
    *,
    board_kuty: int,
    extra_kuty: int = 0,
    project_kuty: int = 0,
    item_line: str = "",
    item_lines: list[str] | None = None,
) -> str:
    lines = [str(x) for x in (item_lines or []) if str(x).strip()]
    if item_line and item_line not in lines:
        lines.insert(0, item_line)
    paid_any = int(board_kuty or 0) > 0 or int(extra_kuty or 0) > 0 or int(project_kuty or 0) > 0 or bool(lines)
    if not paid_any:
        return screen_dry()
    parts = [f"{emoji(GIFT)} <b>Бонус + ваш</b>"]
    if int(board_kuty or 0) > 0:
        parts.append(
            f"<blockquote>{emoji(SPARK, '⚡️')} С клетки: <b>+{int(board_kuty)}</b> кут</blockquote>"
        )
    if int(extra_kuty or 0) > 0:
        parts.append(f"{emoji(STAR, '⭐️')} Ещё куты: <b>+{int(extra_kuty)}</b>")
    for line in lines:
        parts.append(f"{emoji(GIFT)} {line}")
    if int(project_kuty or 0) > 0:
        parts.append(
            f"{emoji(STAR, '⭐️')} <b>Дополнительные куты от проекта</b>: "
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


def help_block(*, mult: int, item_count: int = 1) -> str:
    mult_bit = f" Куты уже ×{int(mult)}." if int(mult or 1) > 1 else ""
    slots = max(1, int(item_count or 1))
    items = (
        f" Иногда — до <b>{slots}</b> предметов."
        if slots > 1
        else " Иногда — предмет."
    )
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        f"«использовать 🎁» — увеличенный бонус.{mult_bit}{items}\n"
        "Нужна приписка <code>Cute</code>. Победа не нужна."
    )


HISTORY_BOARD = "бонус +"
HISTORY_EXTRA = "бонус + ещё"
HISTORY_PROJECT = "бонус + от проекта"
HISTORY_BUY = "бонус + покупка"
