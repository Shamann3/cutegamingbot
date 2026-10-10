# -*- coding: utf-8 -*-
"""Старт бота панели. Тексты и кнопки правятся здесь.

Как править
-----------
Сообщение — в text= тройными кавычками.
Кнопки — сразу под ним, каждая со своим icon=.
icon= — премиум-эмодзи только этой кнопки. Пустой icon= — кнопка без значка.
go= — какой экран открыть в боте. Его не переписывают.
webapp= — куда кнопка открывает панель:
    group-apply    заявка администратора группы
    group-enter    вход в панель администратора
    staff-register заявка сотрудника проекта
    staff-enter    вход в панель сотрудника
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
    "<i>«Подать заявку»</i> ниже всё равно откроет, кого мы берём.</blockquote>"
)

SCREENS = {
    "start": msg(
        text="""
        {wave} <b>{name}</b>
        <i>Вы из тех, кто замечает, когда в чате становится шумно, и не проходит мимо.</i>

        <b>Куда нажать</b>
        <b>Подать заявку</b> — хотите в команду. Дальше выберете, куда именно.
        <b>Панель администратора</b> — кабинет одной группы. Откроется сразу. Ключ придёт в этот чат, когда заявку примут.
        <b>Панель сотрудника</b> — кабинет всего проекта. Откроется сразу. Ключ выдаёт создатель.

        <blockquote>Внутри панели уже написано, что нажимать дальше.
        <b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Подать заявку",
                icon="""<tg-emoji emoji-id='5400289821253990206'>📝</tg-emoji>""",
                go="apply",
            )],
            [b(
                text="Панель администратора",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="group",
                webapp="group-enter",
            )],
            [b(
                text="Панель сотрудника",
                icon="""<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji>""",
                go="staff",
                webapp="staff-enter",
            )],
        ],
    ),
    # Личка бота панели. /start, если человек ещё не создатель. Кнопки под этим текстом.

    "start_known": msg(
        text="""
        {wave} <b>{name}</b>
        <i>Панель для вас уже открыта. Осталось нажать свой кабинет.</i>

        <b>Куда нажать</b>
        <b>Панель администратора</b> — кабинет группы.
        <b>Панель сотрудника</b> — кабинет проекта.
        <b>Подать заявку</b> — если нужна ещё одна роль.

        <blockquote><b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Подать заявку",
                icon="""<tg-emoji emoji-id='5400289821253990206'>📝</tg-emoji>""",
                go="apply",
            )],
            [b(
                text="Панель администратора",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="group",
                webapp="group-enter",
            )],
            [b(
                text="Панель сотрудника",
                icon="""<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji>""",
                go="staff",
                webapp="staff-enter",
            )],
        ],
    ),
    # Личка бота панели. /start создателя. Те же кнопки, текст короче: вход уже есть.

    "apply": msg(
        text="""
        <b>Вам здесь место, если вам не всё равно.</b>
        <i>Вам спокойнее, когда в чате есть правила, и вы готовы быть тем, кто их держит.</i>

        Мы берём тех, кто остаётся. За работой следит система: если активность пропадёт, должность снимут.
        <u>Администраторам и сотрудникам платят.</u> Пустые места нам не нужны.

        <b>Дальше одна кнопка. Она откроет панель.</b>
        <b>Заявка администратора группы</b> — одна группа. В панели выберете её, должность и напишете, чем полезны.
        <b>Заявка сотрудника проекта</b> — весь проект. В панели будет анкета.
        Текст заявки — <u>от 50 до 2000 символов</u>.

        <blockquote>Там уже написано каждое следующее нажатие.
        <b>Виво-Эпсилон!</b></blockquote>
        """,
        buttons=[
            [b(
                text="Заявка администратора группы",
                icon="""<tg-emoji emoji-id='5361948635317680832'>🛡</tg-emoji>""",
                go="group-apply",
                webapp="group-apply",
            )],
            [b(
                text="Заявка сотрудника проекта",
                icon="""<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji>""",
                go="staff-register",
                webapp="staff-register",
            )],
            [b(text="Назад", go="start")],
        ],
    ),
    # Личка, после «Подать заявку». Кнопки открывают нужную заявку в панели.
}
