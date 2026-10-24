# -*- coding: utf-8 -*-
"""Бонус + — все тексты, которые видит человек.

Как править
-----------
Как в текстах брака и огонька: сообщение целиком в тройных кавычках.
Строка с # над ним — где человек его видит. Решётка в Telegram не уходит.
Слоты {name} {n} {mult} бот подставляет сам. Их не переименовывайте.
Кнопка, тост и строка истории — одна строка. Теги там не рисуются.
После правки перезапустите бота.

Числа, шансы и список предметов — вкладка «Огонёк → Бонус +».
"""
from __future__ import annotations

import re

EMOJI = "5438458242130806642"
SPARK = "5355274926154625762"
STAR = "5233479338791281256"
GIFT = "5438458242130806642"
NOTE = "5467519850576354798"


def emoji(eid: str, fallback: str = "🎁") -> str:
    return f"<tg-emoji emoji-id='{eid}'>{fallback}</tg-emoji>"


def _slots(template: str, **slots: str) -> str:
    def swap(match):
        return slots.get(match.group(1), match.group(0))

    return re.sub(r"\{([a-z_]+)\}", swap, str(template).strip("\n"))


# Где: первое сообщение после «использовать 🎁». {gift} значок, {mult} пусто или « · ×2».
INTRO = """
{gift} <b>Бонус +</b>{mult}
<blockquote><b>Это улучшенный бонус, с более крутыми подарками</b>
<i>Спасибо, что вы с нами.</i></blockquote>
<b>Нажмите на одну из кнопок.</b>
"""

BUTTON_OPEN = "Открыть Бонус +"  # Кнопка под первым сообщением. Тегов нет.
BUTTON_LATER = "Позже"  # Кнопка «не сейчас». Тегов нет.
BUTTON_WHAT = "Что можно получить?"  # Кнопка списка призов. Тегов нет.
BUTTON_BACK = "Назад"  # Кнопка возврата с списка призов. Тегов нет.

# Где: после «Позже». Предмет остаётся в инвентаре.
LATER = """
<code>🎁</code> <b>Предмет остался у вас.</b>
<i>Когда будете готовы — напишите</i> «<code>использовать 🎁</code>» <i>снова.</i>
"""

# Где: экран «Что можно получить?». {kuty} и {items} — списки из вкладки, могут быть пустыми.
POSSIBLE_HEAD = "{gift} <b>Что можно получить открыв бонус?</b>"
POSSIBLE_LEAD = "Это список до открытия. Точную клетку вы увидите только после того, как нажмёте её."
POSSIBLE_KUTY = "{spark} <b>Куты</b>"  # Заголовок блока кут в списке.
POSSIBLE_ONE = "Предмет · до <b>1шт</b> за раз"  # Заголовок, если за раз не больше одного предмета.
POSSIBLE_MANY = "Предметы · до <b>{n}шт</b> за раз"  # Заголовок, если предметов несколько. {n} — число.
POSSIBLE_HIDDEN = " · в списке не всё"  # Дописывается к заголовку, если часть предметов скрыта.
POSSIBLE_EMPTY = "<i>Список пока пуст.</i>"  # Если не отмечено ни кут, ни предметов.
POSSIBLE_PRESS = "<b>Нажмите на одну из кнопок.</b>"  # Низ экрана списка.
POSSIBLE_ROW = "· {line}"  # Одна строка списка. {line} уже готовая.

# Где: поле 3×3 после «Открыть Бонус +».
BOARD = """
{gift} <b>Бонус +</b>
<blockquote><b>Выберите одну клетку.</b>
Что внутри — узнаете сразу.
Откроется только нажатая клетка. Остальные в этот раз закрыты.</blockquote>
"""

# Где: в имени нет Cute. {name} текущее имя.
NEED_CUTE = """
{note} <b>Добавьте в имя <code>Cute</code></b>
<blockquote>Бонус + открывается только с этой припиской в имени.
Сейчас у вас: <b>{name}</b>
Пример: <code>Имя Cute</code></blockquote>
<i><code>🎁</code> Предмет остался у вас. После смены имени напишите «использовать 🎁» снова.</i>
"""

# Где: Бонус + выключен во вкладке.
OFF = """
{note} <b>Бонус + недоступен</b>
<blockquote>Сейчас его нельзя открыть: он выключен.</blockquote>
<i><code>🎁</code> Предмет остался у вас. Когда бонус снова включат, напишите «использовать 🎁».</i>
"""

# Где: поле не открылось.
FAIL = """
{note} <b>Не удалось открыть</b>
<blockquote>Поле с клетками не открылось. Попробуйте ещё раз.</blockquote>
<i><code>🎁</code> Предмет остался у вас. Напишите «использовать 🎁» снова.</i>
"""

# Где: клетка открыта, но выдать нечего.
DRY = """
{note} <b>Сейчас наградить нечем</b>
<blockquote>Клетка открыта, но выдать куты или предмет сейчас не получилось.
Попробуйте следующий 🎁 чуть позже.</blockquote>
"""

# Где: клетка открыта и приз есть. {lines} — строки внутри цитаты.
RESULT = """
{gift} <b>Бонус открыт</b>
<b><i>Вот что в нём было :</i></b>
<blockquote>{lines}</blockquote>

<i>Спасибо, что вы с нами</i>
"""

RESULT_KUTY = "{spark} <b>+ {n} кут</b>"  # Строка кут с клетки. {n} число.
RESULT_EXTRA = "{star} <b>+ {n} кут</b>"  # Строка дополнительных кут. {n} число.
RESULT_PROJECT = "{star} <b>Куты от проекта</b> : <b>+ {n}</b>"  # Строка кут от проекта. {n} число.
ITEM_GOT = "{face} + <b>{name}</b>"  # Предмет в результате. {face} эмодзи, {name} имя.
ITEM_PREVIEW = "<code>{face}</code> <b>{name}</b>"  # Предмет в списке «что можно получить».

ALERT_STRANGER = "Эта кнопка не ваша."  # Всплывашка: кнопку нажал не тот, кто открыл бонус.
ALERT_GONE = "Эта карточка уже не действует. Напишите «использовать 🎁» снова."  # Всплывашка: карточка устарела.

# Где: вкладка «хелп», блок про Бонус +. {mult} пусто или фраза про умножение.
HELP = """
{gift} <b>Бонус +</b>
Это отдельный подарок, не награда за день серии.{mult}
Напишите «использовать 🎁». Нажмите «Открыть Бонус +» и выберите одну клетку. Что внутри — узнаете после выбора.
Кнопка «Что можно получить?» показывает куты и предметы, которые могут выпасть.
Чтобы открыть, в имени должна быть приписка <code>Cute</code>. Если нажмёте «Позже», предмет останется у вас: напишите «использовать 🎁» снова.
"""

HELP_MULT = " Куты на клетке умножаются на <b>{n}</b>."  # Дописывается в справку, если множитель больше 1.

HISTORY_BOARD = "бонус +"  # История баланса: куты с клетки.
HISTORY_EXTRA = "бонус + ещё"  # История баланса: дополнительные куты.
HISTORY_PROJECT = "бонус + от проекта"  # История баланса: куты от проекта.
HISTORY_BUY = "бонус + покупка"  # История баланса: покупка предмета для бонуса.


def screen_intro(*, mult: int = 1) -> str:
    bit = f" · ×{int(mult)}" if int(mult or 1) > 1 else ""
    return _slots(INTRO, gift=emoji(GIFT), mult=bit)


def button_open() -> str:
    return BUTTON_OPEN


def button_later() -> str:
    return BUTTON_LATER


def button_what() -> str:
    return BUTTON_WHAT


def button_back() -> str:
    return BUTTON_BACK


def screen_later() -> str:
    return _slots(LATER)


def screen_possible(
    *,
    max_gifts: int,
    lines: list[str],
    kuty_lines: list[str] | None = None,
    hidden: bool = False,
) -> str:
    """Список до открытия. Слова — POSSIBLE_*."""
    slots = max(0, int(max_gifts or 0))
    kuty = [str(x) for x in (kuty_lines or []) if str(x).strip()]
    gifts = [str(x) for x in (lines or []) if str(x).strip()]
    parts = [
        _slots(POSSIBLE_HEAD, gift=emoji(GIFT)),
        POSSIBLE_LEAD,
    ]
    if kuty:
        parts.append(_slots(POSSIBLE_KUTY, spark=emoji(SPARK, "⚡️")))
        parts.extend(_slots(POSSIBLE_ROW, line=line) for line in kuty)
    if gifts:
        title = POSSIBLE_ONE if slots <= 1 else _slots(POSSIBLE_MANY, n=str(slots))
        if hidden:
            title += POSSIBLE_HIDDEN
        parts.append(f"{emoji(GIFT)} <b>{title}</b>")
        parts.extend(_slots(POSSIBLE_ROW, line=line) for line in gifts)
    elif not kuty:
        parts.append(POSSIBLE_EMPTY)
    parts.append(POSSIBLE_PRESS)
    return "\n".join(parts)


def screen_board(*, mult: int, kuty_lo: int, kuty_hi: int) -> str:
    _ = (mult, kuty_lo, kuty_hi)
    return _slots(BOARD, gift=emoji(GIFT))


def screen_need_cute(name: str) -> str:
    return _slots(NEED_CUTE, note=emoji(NOTE, "❕"), name=name)


def screen_off() -> str:
    return _slots(OFF, note=emoji(NOTE, "❕"))


def screen_fail() -> str:
    return _slots(FAIL, note=emoji(NOTE, "❕"))


def screen_dry() -> str:
    return _slots(DRY, note=emoji(NOTE, "❕"))


def screen_result(
    *,
    board_kuty: int,
    extra_kuty: int = 0,
    project_kuty: int = 0,
    item_line: str = "",
    item_lines: list[str] | None = None,
) -> str:
    """Результат клетки. Слова — RESULT и RESULT_*."""
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
    quote: list[str] = []
    if int(board_kuty or 0) > 0:
        quote.append(_slots(RESULT_KUTY, spark=emoji(SPARK, "⚡️"), n=str(int(board_kuty))))
    if int(extra_kuty or 0) > 0:
        quote.append(_slots(RESULT_EXTRA, star=emoji(STAR, "⭐️"), n=str(int(extra_kuty))))
    quote.extend(lines)
    if int(project_kuty or 0) > 0:
        quote.append(_slots(RESULT_PROJECT, star=emoji(STAR, "⭐️"), n=str(int(project_kuty))))
    return _slots(RESULT, gift=emoji(GIFT), lines="\n".join(quote))


def item_got(emoji_face: str, name: str) -> str:
    face = (emoji_face or "🎁").strip() or "🎁"
    return _slots(ITEM_GOT, face=face, name=name)


def preview_item_line(emoji_face: str, name: str) -> str:
    face = (emoji_face or "🎁").strip() or "🎁"
    return _slots(ITEM_PREVIEW, face=face, name=name)


def alert_stranger() -> str:
    return ALERT_STRANGER


def alert_gone() -> str:
    return ALERT_GONE


def help_block(*, mult: int, item_count: int = 1) -> str:
    _ = item_count
    bit = _slots(HELP_MULT, n=str(int(mult))) if int(mult or 1) > 1 else ""
    return _slots(HELP, gift=emoji(GIFT), mult=bit)
