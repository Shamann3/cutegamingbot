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


def screen_intro(*, mult: int = 1) -> str:
    mult_bit = f" · ×{int(mult)}" if int(mult or 1) > 1 else ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>{mult_bit}\n"
        "<blockquote>"
        "<b>Это улучшенный бонус, с более крутыми подарками</b>\n"
        "<i>Спасибо, что вы с нами.</i>"
        "</blockquote>\n"
    )


def button_open() -> str:
    return "Открыть Бонус +"


def button_later() -> str:
    return "Позже"


def button_what() -> str:
    return "Что можно получить?"


def button_back() -> str:
    return "Назад"


def screen_later() -> str:
    return (
        "<code>🎁</code> <b>Предмет остался у вас.</b>\n"
        "<i>Когда будете готовы — напишите</i> "
        "«<code>использовать 🎁</code>» <i>снова.</i>"
    )


def screen_possible(
    *,
    max_gifts: int,
    lines: list[str],
    kuty_lines: list[str] | None = None,
    hidden: bool = False,
) -> str:
    """Экран кнопки. Куты и отмеченные предметы — из вкладки «Огонёк → Бонус +»."""
    slots = max(0, int(max_gifts or 0))
    kuty = [str(x) for x in (kuty_lines or []) if str(x).strip()]
    gifts = [str(x) for x in (lines or []) if str(x).strip()]
    parts = [
        f"{emoji(GIFT)} <b>Что можно получить открыв бонус?</b>",
    ]
    if kuty:
        parts.append(f"{emoji(SPARK, '⚡️')} <b>Куты</b>")
        parts.extend(f"· {line}" for line in kuty)
    if gifts:
        if slots <= 1:
            title = "Предмет · до <b>1шт</b> за раз"
        else:
            title = f"Предметы · до <b>{slots}шт</b> за раз"
        if hidden:
            title += " · в списке не всё"
        parts.append(f"{emoji(GIFT)} <b>{title}</b>")
        parts.extend(f"· {line}" for line in gifts)
    elif not kuty:
        parts.append("<i>Список пока пуст.</i>")
    parts.append("<b>Нажмите на одну из кнопок.</b>")
    return "\n".join(parts)


def screen_board(*, mult: int, kuty_lo: int, kuty_hi: int) -> str:
    _ = (mult, kuty_lo, kuty_hi)
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        "<blockquote><b>Нажмите на одну из кнопок.</b></blockquote>"
    )


def screen_need_cute(name: str) -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Добавьте в имя <code>Cute</code></b>\n"
        f"<blockquote>Сейчас: <b>{name}</b>\n"
        "Пример: <code>Имя Cute</code></blockquote>\n"
        "<i><code>🎁</code> Предмет остался у вас.</i>"
    )


def screen_off() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Бонус + недоступен</b>\n"
        "<i>Позже — <code>🎁</code> предмет остался у вас.</i>"
    )


def screen_fail() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Не удалось открыть</b>\n"
        "<i>Ещё раз — <code>🎁</code> предмет остался у вас.</i>"
    )


def screen_dry() -> str:
    return (
        f"{emoji(NOTE, '❕')} <b>Сейчас наградить нечем</b>\n"
        "<blockquote>Попробуйте чуть позже.</blockquote>"
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
    paid_any = (
        int(board_kuty or 0) > 0
        or int(extra_kuty or 0) > 0
        or int(project_kuty or 0) > 0
        or bool(lines)
    )
    if not paid_any:
        return screen_dry()
    parts = [f"{emoji(GIFT)} <b>Бонус + ваш</b>"]
    if int(board_kuty or 0) > 0:
        parts.append(
            f"<blockquote>{emoji(SPARK, '⚡️')} С клетки : <b>+{int(board_kuty)}</b> кут</blockquote>"
        )
    if int(extra_kuty or 0) > 0:
        parts.append(f"{emoji(STAR, '⭐️')} Ещё : <b>+{int(extra_kuty)}</b> кут")
    for line in lines:
        parts.append(f"{emoji(GIFT)} {line}")
    if int(project_kuty or 0) > 0:
        parts.append(
            f"{emoji(STAR, '⭐️')} <b>Куты от проекта</b> : <b>+{int(project_kuty)}</b>"
        )
    parts.append("<i>Спасибо, что вы с нами</i>")
    return "\n".join(parts)


def item_got(emoji_face: str, name: str) -> str:
    face = emoji_face or "🎁"
    return f"Вам: <code>{face}</code> <b>{name}</b>"


def preview_item_line(emoji_face: str, name: str) -> str:
    face = (emoji_face or "🎁").strip() or "🎁"
    return f"<code>{face}</code> <b>{name}</b>"


def alert_stranger() -> str:
    return "Эта кнопка не ваша."


def alert_gone() -> str:
    return "Уже неактуально. Снова «использовать 🎁»."


def help_block(*, mult: int, item_count: int = 1) -> str:
    _ = item_count
    mult_bit = f" ×{int(mult)}." if int(mult or 1) > 1 else ""
    return (
        f"{emoji(GIFT)} <b>Бонус +</b>\n"
        f"«использовать 🎁» — улучшенный бонус.{mult_bit}\n"
        "Кнопка «Что можно получить?» — куты и предметы из настройки.\n"
        "Нужна приписка <code>Cute</code>."
    )


HISTORY_BOARD = "бонус +"
HISTORY_EXTRA = "бонус + ещё"
HISTORY_PROJECT = "бонус + от проекта"
HISTORY_BUY = "бонус + покупка"
