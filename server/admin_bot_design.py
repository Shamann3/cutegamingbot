# -*- coding: utf-8 -*-
"""Старт бота панели. Тексты и кнопки правятся здесь.

Как править
-----------
Сообщение — в text= тройными кавычками.
Кнопки — сразу под ним, каждая со своим icon=.
icon= — премиум-эмодзи только этой кнопки. Пустой icon= — кнопка без значка.
go= — какой экран открыть в боте. Его не переписывают.
webapp="panel" — кнопка открывает саму панель, без кабинета.
Человек уже внутри выбирает панель администратора или панель сотрудника.
Пустой webapp= — кнопка остаётся в боте и меняет это сообщение.

Под текстом строка с # : где его видит человек. Решётка в Telegram не уходит.
В тексте можно писать {name} — имя человека, и {wave} — знак приветствия.
Другие фигурные скобки в текст не ставьте.
После правки нужен перезапуск бота панели.
"""

from __future__ import annotations

import re
import textwrap

_EMOJI_RE = re.compile(r"<tg-emoji emoji-id=['\"](\d+)['\"]>", re.I)


def t(text) -> str:
    if text is None:
        return ""
    return textwrap.dedent(str(text)).strip("\n")


def emoji_id(tag: str) -> str:
    match = _EMOJI_RE.search(str(tag or ""))
    return match.group(1) if match else ""


def b(*, text: str, icon: str = "", go: str, webapp: str = "") -> dict:
    item = {"text": t(text), "go": go, "webapp": webapp}
    icon = t(icon)
    if icon:
        item["icon"] = icon
    return item


def msg(*, text: str, buttons=None) -> dict:
    return {"text": t(text), "buttons": list(buttons or [])}


def button_rows(name: str) -> list:
    out = []
    for row in SCREENS[name]["buttons"]:
        built = list(row) if isinstance(row, (list, tuple)) else [row]
        if built:
            out.append(built)
    return out


def screen_text(screen: str, **slots) -> str:
    return SCREENS[screen]["text"].format(**slots)


WAVE = "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji>"

# Если адреса панели нет даже у сайта, кнопки в кабинет не ставятся.
# Эта строка дописывается к тексту. В обычном /start её быть не должно.
ERROR_NO_PANEL = (
    "<blockquote><b>Панель сейчас не открывается.</b>\n"
    "Напишите сотрудникам Эпсилона и назовите номер <code>512910</code>.\n"
    "Кнопка <i>«Открыть панель»</i> появится, когда адрес панели будет задан.</blockquote>"
)

SCREENS = {
    "start": msg(
        text="""
        {wave} <b>{name}</b>
        <i>Вы из тех, кто замечает, когда в чате становится шумно, и не проходит мимо.</i>
        <blockquote><b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Открыть панель",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="panel",
                webapp="panel",
            )],
        ],
    ),
    # Личка бота панели. /start, если человек ещё не создатель. Кнопки под этим текстом.

    "start_known": msg(
        text="""
        {wave} <b>{name}</b>
        <i>Панель для вас уже открыта. Кнопка ниже ведёт в неё, без выбора кабинета заранее.</i>
        <blockquote><b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Открыть панель",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="panel",
                webapp="panel",
            )],
        ],
    ),
    # Личка бота панели. /start создателя. Те же кнопки, текст короче: вход уже есть.

    "apply": msg(
        text="""
<b>Вы нужны здесь.</b>
<i>Не потому что мы ищем кого-то.
А потому что вы уже здесь.</i>

<b>Вы видите беспорядок - и хотите его исправить.
Вы чувствуете хаос - и хотите тишину.
Вы знаете правила - и хотите их держать.</b>

<blockquote><b>Это не работа.
Это характер.</b></blockquote>

<b><u>Ваш труд заметят. Ваш труд оплатят.</u>
Пустых мест здесь нет.</b>

<blockquote><b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Открыть панель",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="panel",
                webapp="panel",
            )],
            [b(text="Назад", go="start")],
        ],
    ),
    # Запасной экран. С /start на него больше не ведёт кнопка: старт сразу открывает панель.
}
