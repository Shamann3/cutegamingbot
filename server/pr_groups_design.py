# -*- coding: utf-8 -*-
"""Пиар в группах — дизайн всех сообщений.

Как править
-----------
Сообщение целиком — в text= тройными кавычками.
Эмодзи сообщения — в emoji=.
Кнопки сразу под текстом: text="подпись" обычными кавычками, icon= у каждой.

Жирным станет каждая обычная строка.
Цитату пиши так: <blockquote><b><i>доп. информация</i></b></blockquote>
В тексте можно: <b>…</b>  <code>…</code>  {name} {link_hint}

Всё, что человек видит не большим сообщением
(статусы, списки, тосты, меню заданий, хелп) — ниже, в WORDS и рядом.
"""

from __future__ import annotations

import re
import textwrap


ACTIONS = frozenset({
    "owner", "reco", "earnings", "groups", "add_bot", "cant", "check",
    "public", "admin", "open_group", "wrote", "undo", "cancel", "more",
    "continue_photo", "yes", "no_confirm", "back_hub", "back_tasks",
    "back_how", "back_mine", "open_claim", "pick_group",
})
WHEN = frozenset({
    "always", "live", "mine", "not_live", "reco", "no_public", "no_admin",
    "have_photos", "has_username", "photos", "wait_confirm", "pending",
})
COLORS = frozenset({"default", "primary", "success", "danger"})


def t(text) -> str:
    """Срезает пустые края у тройных кавычек, внутренние строки оставляет."""
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join(line for line in (t(item) for item in text) if line)
    return textwrap.dedent(str(text)).strip("\n")


def say(key: str, **vals) -> str:
    tmpl = WORDS[key]
    return tmpl.format(**vals) if vals else tmpl


def name_or(value, key: str = "group") -> str:
    raw = str(value or "").strip()
    return raw if raw else say(key)


def b(*, text: str, icon: str = "", color: str = "default", go: str, when: str = "always") -> dict:
    item = {"text": t(text), "go": go, "show": when, "when": when, "style": color, "color": color}
    icon = t(icon)
    if icon:
        item["icon"] = icon
    return item


def items(kind: str, *, text: str, go: str) -> dict:
    return {"repeat": kind, "go": go, "text": t(text)}


def msg(*, emoji: str, text: str = "", buttons=None, extra_by=None, next_by=None, emoji_by=None, extra: str = "", next: str = "", next_empty: str = "", **more) -> dict:
    data = {
        "emoji": t(emoji),
        "text": t(text),
        "buttons": list(buttons or []),
        "extra": t(extra),
        "next": t(next),
        "next_empty": t(next_empty),
    }
    if emoji_by:
        data["emoji_by"] = {key: t(val) for key, val in emoji_by.items()}
    if extra_by:
        data["extra_by"] = {key: t(val) for key, val in extra_by.items()}
    if next_by:
        data["next_by"] = {key: t(val) for key, val in next_by.items()}
    for key, val in more.items():
        data[key] = t(val) if isinstance(val, (str, list, tuple)) else val
    return data


def iter_button_rows(buttons) -> list:
    out = []
    for row in buttons or []:
        if isinstance(row, dict) and row.get("repeat"):
            out.append(row)
        elif isinstance(row, dict):
            out.append([row])
        else:
            out.append(list(row))
    return out


LINK_HINT = t("""<code>@группа</code> · <code>t.me/группа</code> · <code>t.me/c/id</code> · id""")

PHOTO_STEPS = (
    {
        'what': t("""<b>Сделайте скриншот списка администраторов группы.</b>"""),
        'need': t("""<blockquote><b>На кадре должен быть <code>@CuteGamingBot</code>.</b></blockquote>"""),
    },
    {
        'what': t("""<b>Далее нужен скриншот сообщения от бота в этой группе.</b>"""),
        'need': t("""<blockquote><b>Нужно видеть, что бот там отвечает на сообщения.</b></blockquote>"""),
    },
    {
        'what': t("""<b>Покажите кто создатель группы.</b>"""),
        'need': t("""<blockquote><b>Сделайте скришот списка администраторов в котором будет видно создателя группы</b></blockquote>"""),
    },
)

NEED_PHOTO = {
    'video': {
        'title': t("""<b>Нужно фото, не видео.</b>"""),
        'extra': t("""<b>Видео или видео-кружок не принимаем.</b>"""),
        'next': t("""<b>Картинка из галереи - отправьте её сюда.</b>"""),
    },
    'file': {
        'title': t("""<b>Нужно фото, не файл.</b>"""),
        'extra': t("""<b>Документ без картинки не принимаем.</b>"""),
        'next': t("""<b>Картинка из галереи - отправьте её сюда.</b>"""),
    },
    'sticker': {
        'title': t("""<b>Нужно фото из группы.</b>"""),
        'extra': t("""<b>Стикер и эмодзи не считаются скрином группы.</b>"""),
        'next': t("""<b>Картинка из группы - отправьте её сюда.</b>"""),
    },
    'text': {
        'title': t("""<b>Нужно фото, не текст.</b>"""),
        'extra': t("""<b>Текст сюда не подходит - нужен кадр.</b>"""),
        'next': t("""<b>Картинка из галереи - отправьте её сюда.</b>"""),
    },
    'album': {
        'title': t("""<b>По одному фото.</b>"""),
        'extra': t("""<b>Альбом Telegram считает одним сообщением - кадры склеятся.</b>"""),
        'next': t("""<b>Следующий кадр - отдельно</b>"""),
    },
    'dup': {
        'title': t("""<b>Это фото уже есть.</b>"""),
        'extra': t("""<b>Этот кадр уже принят.</b>"""),
        'next': t("""<b>Пришлите другой кадр.</b>"""),
    },
    '': {
        'title': t("""<b>Нужно именно фото.</b>"""),
        'extra': t("""<b>Нужен скрин из самой группы.</b>"""),
        'next': t("""<b>Картинка из галереи - отправьте её сюда.</b>"""),
    },
}

# ===========================================================================
# Короткие тексты. Человек их тоже видит.
# Кнопки списков, статусы, тосты, меню заданий, хелп — правь здесь.
# ===========================================================================

WORDS = {
    "kut": "<b><u>{n} кут</u></b>",
    "group": "<b><u>группа</u></b>",
    "this_group": "<b><u>эта группа</u></b>",
    "group_acc": "<b><u>группу</u></b>",
    "of_group": "<b><u>группы</u></b>",
    "player": "<b><u>игрок</u></b>",
    "photo": "<b><u>фото</u></b>",
    "photo_have": "<b><u>Есть {have} из {total}.\n{what}</u></b>",
    "photo_hint_n": "<b><u>фото {n}</u></b>",
    "ellipsis": "<b><u>…</u></b>",
    "gifts_row": "<b><u>подарков : {n}</u></b>",
    "claim_btn": "<b><u> {title} · {short}</u></b>",
    "claim_btn_money": "<b><u>{title} · {short} · {money}</u></b>",
    "seen_line": "<b><u>«{names}» — {reason}.</u></b>",
    "seen_join": "», «",
    "seen_no_public": "<b><u>нет @адреса</u></b>",
    "seen_no_admin": "<b><u>Кут не администратор в группе</u></b>",
    "rejected": "<b><u>Не приняли.</u></b>",
    "reject_fallback": "<b><u>Заявку не приняли.</u></b>",
    "reject_join": "<b> · </b>",
    "toast_check": "<b><u>Смотрю группы…</u></b>",
    "history_gift": "<b><u>подарок новой группы</u></b>",
    "history_payout": "<b><u>рекомендации бота в группах</u></b>",
}

# Слова, которые человек пишет боту. Пусть совпадают с текстом сообщений.
CONFIRM_WORDS = frozenset({
    "подтверждение", "подтвердить", "подтверди", "confirm", "confirmation",
})
HELP_WORDS = frozenset({
    "хелп", "help", "помощь", "?",
})

STATUS = {
    "photos": "<b>нужны <u>3 фото</u></b>",
    "wait_confirm": "<b>ждём <u>Да</u> от создателя</b>",
    "confirm_retry": "<b><u>ещё один шанс подтверждения того что именно вы порекомендовали проект для создателя группы</u></b>",
    "pending": "<b><u>заявку проверяют сотрудники Эпсилона</u></b>",
    "accepting": "<b><u>заявку проверяют сотрудники Эпсилона</u></b>",
    "fulfilling": "<b><u>заявку проверяют сотрудники Эпсилона</u></b>",
    "live": "<b><u>идёт заработок</u></b>",
    "ended": "<b><u>срок задания на группу вышел</u></b>",
    "rejected": "<b><u>группу не приняли сотрудники Эпсилона</u></b>",
    "burned": "<b><u>Кут убрали из группы</u></b>",
    "expired": "<b><u>время вышло</u></b>",
    "cancelled": "<b><u>заявку сняли</u></b>",
}

STATUS_SHORT = {
    "photos": "<b>фото</b>",
    "wait_confirm": "<b>ждём Да</b>",
    "confirm_retry": "<b>ещё шанс</b>",
    "pending": "<b>смотрят</b>",
    "accepting": "<b>смотрят</b>",
    "fulfilling": "<b>смотрят</b>",
    "live": "<b>идёт</b>",
    "ended": "<b>срок</b>",
    "rejected": "<b>не приняли</b>",
    "burned": "<b>убрали</b>",
    "expired": "<b>время</b>",
    "cancelled": "<b>сняли</b>",
}

PAUSE = {
    "admin": "<b>пауза : <u>Куту нужна должность администратора в группе</u></b>",
    "public": "<b>пауза : <u>группа стала закрытой</u></b>",
}

PAUSE_HINT = {
    "admin": "<b>Верните Кут в список администраторов в группе и <u>зарплата снова начнёт капать.</u></b>",
    "public": "<b>Сделайте группу публичной и <u>зарплата снова начнёт капать.</u></b>",
}

PAUSE_SHORT = {
    "admin": "<b>пауза</b>",
    "public": "<b>закрыта</b>",
}

IDLE_HINT = {
    "hot": "<b>скорее нет</b>",
    "warn": "<b>осторожно</b>",
    "ok": "<b>можно смотреть</b>",
}

IDLE_LABEL = "<b>Уходил {n} дн. назад · {hint}</b>"

PHOTO_HINTS = (
    "<b>список админов</b>",
    "<b>сообщение от Кут</b>",
    "<b>создатель группы</b>",
)

REJECT_REASONS = [
    {"id": "already_was", "label": "Уже был Кут"},
    {"id": "not_admin", "label": "Бот не администратор"},
    {"id": "not_public", "label": "Нет открытого @username"},
    {"id": "too_small", "label": "Мало людей"},
    {"id": "farm", "label": "Пустышка / накрутка"},
    {"id": "dead", "label": "Мёртвая группа"},
    {"id": "bad_link", "label": "Неверная ссылка"},
    {"id": "adult", "label": "18+"},
    {"id": "insult", "label": "Оскорбление"},
]

TASKS_MENU = {
    "text": "<b>Рекомендация проекта в группах</b>",
    "icon": "<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji>",
}

HELP_TASKS = t("""
<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji> <b>Рекомендация проекта в группах</b>
<blockquote><b><i>Задания → Пиар в группах → кто вы. Потом ссылка, доказательства, проверка. Решение придёт в этот чат.</i></b></blockquote>
<blockquote><code>Задания</code></blockquote>
""")


# ===========================================================================
# Экраны. У каждого: целый текст, потом кнопки.
# ===========================================================================

SCREENS: dict[str, dict] = {

    'hub': msg(
        emoji="""<tg-emoji emoji-id='5452002597592382164'>📣</tg-emoji>""",
        text="""
        <b>Рекомендация бота в группах</b>
        <b>Заработок - до 35% комиссии с игр новых людей.</b>
        <blockquote><b><i>Длительность заработка - 14 дней · с той группы, в которую вы добавите нашего бота</i></b></blockquote>
        """,
        buttons=[
            b(
                text="Я владелец группы",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                color='default',
                go='owner',
            ),
            b(
                text="Я рекомендую бот в группах",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                color='default',
                go='reco',
            ),
            b(
                text="Заработки",
                icon="""<tg-emoji emoji-id='5444884960609590878'>💰</tg-emoji>""",
                color='default',
                go='earnings',
                when='live',
            ),
            b(
                text="Мои группы",
                icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""",
                go='groups',
                when='mine',
            ),
            b(
                text="Назад, в главное меню",
                icon="""<tg-emoji emoji-id='5348423147647414077'>↩️</tg-emoji>""",
                color='success',
                go='back_tasks',
            ),
        ],
    ),

    'choose': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>Кто вы?</b>
        """,
        buttons=[
            b(
                text="Я владелец группы",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                go='owner',
            ),
            b(
                text="Я рекомендую бот в группах",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ),
            b(
                text="Назад, в главное меню",
                icon="""<tg-emoji emoji-id='5345947485548326948'>😛</tg-emoji>""",
                color='success',
                go='back_hub',
            ),
        ],
    ),

    'how_owner': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>Ваша группа</b>
        <blockquote><b><i>Добавьте Кут в список администраторов в свою <u>публичную</u> группу.</i></b></blockquote>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            [
                b(
                    text="Нет @username",
                    icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""",
                    color='primary' ,
                    go='public',
                    when='no_public',
                ),
                b(
                    text="Кут не администратор",
                    icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""",
                    color='primary' ,
                    go='admin',
                    when='no_admin',
                ),
            ],
            b(
                text="Назад, в главное меню",
                icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""",
                color='success',
                go='back_hub',
            ),
        ],
    ),

    'how_reco': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>Чужой чат</b>
        <blockquote><b><i>Попросите создателя добавить @CuteGamingBot в список администраторов в новой группе</i></b></blockquote>
        <i>Когда Кут будет в админах - пришлите сюда ссылку на новую группу</i>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            [
                b(
                    text="Нет @username",
                    icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""",
                    color='primary' ,
                    go='public',
                    when='no_public',
                ),
                b(
                    text="Кут не администратор",
                    icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""",
                    color='primary' ,
                    go='admin',
                    when='no_admin',
                ),
            ],
            b(
                text="Назад, в главное меню",
                icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""",
                color='success',
                go='back_hub',
            ),
        ],
    ),

    'how_public': msg(
        emoji="""<tg-emoji emoji-id='5856976696019784799'>💙</tg-emoji>""",
        text="""
        <b>Нужна ссылка на группу</b>
        <pre><b>Название сверху → Управление → Тип группы → Публичная.</b></pre>
        <blockquote><b><i>Без открытого @адреса группу сдать на провеку нельзя.</i></b></blockquote>
        <b><i>Сделайте группу публичной. Потом пришлите сюда ссылку.</i></b>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5343909794149310690'>✅</tg-emoji>""",
                color='primary' ,
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'how_admin': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут должен быть админом</b>
        <blockquote><b><i>Без админки Кут не видит чат и мы не может принять заявку.</i></b></blockquote>
        <b><i>После добавления кута в список администраторов, пришлите ссылку на группу сюда.</i></b>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'how_admin_reco': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут должен быть админом</b>
        <blockquote><b><i>Без админки Кут не видит чат и не может принять заявку.</i></b></blockquote>
        <b><i>После добавления кута в список администраторов, пришлите ссылку на группу сюда.</i></b>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'need_public': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>У «{name}» нет @адреса</b>
        <blockquote><b><i>Закрытую группу сдать нельзя.</i></b></blockquote>
        <b><i>Сделайте группу публичной. Потом пришлите сюда ссылку.</i></b>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'need_admin': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>В «{name}» Кут не является администратором</b>
        <blockquote><b><i>Без админки заявку не примем.</i></b></blockquote>
        <b><i>После добавления кута в список администраторов, пришлите ссылку на группу сюда.</i></b>
        """,
        buttons=[
            b(
                text="Добавить Кут",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='add_bot',
            ),
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'need_admin_reco': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>В «{name}» Кут не является администратором</b>
        <b><i>Попросите создателя дать ему админку.<i></b>
        
        <blockquote><b><i>Без админки заявку не примем.</i></b></blockquote>
        
        <b><i>Когда Кут в админах - пришлите сюда ссылку.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) ,
            b(
                text="Не могу добавить",
                icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""",
                go='cant',
                when='reco',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'bot_joined': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>Кут зашёл в «{name}»</b>
        <blockquote><b><i>Дальше, нужно только указать кто вы</i></b></blockquote>
        """,
        buttons=[ b(
            text="Я владелец группы" , icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""" ,
            go='owner' , ) , b(
            text="Я рекомендую бот в группах" , icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""" ,
            go='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5345947485548326948'>😛</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'bot_joined_intent': msg(
        emoji="""<tg-emoji emoji-id='5857185830862329369'>💚</tg-emoji>""",
        text="""
        <b>Кут зашёл в «{name}»</b>
        <blockquote><b><i>Если он ещё не админ - сначала дайте админку.</i></b></blockquote>
        <b><i>Если кут уже является администратором - отправьте сюда ссылку на группу</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад" , icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""" , go='back_how' , ) ,
        ],
    ),

    'need_link': msg(
        emoji="""<tg-emoji emoji-id='5271929616896921139'>🪨</tg-emoji>""",
        text="""
        <b>Нужна ссылка на группу</b>
        <blockquote><b><i>Пришлите сюда ссылку текстом.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , go='add_bot' , ) ,
            b(
                text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
                when='reco' , ) , [ b(
                text="Нет @username" , icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""" ,
                color='primary' , go='public' , when='no_public' , ) , b(
                text="Кут не администратор" , icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""" ,
                color='primary' , go='admin' , when='no_admin' , ) , ] , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'forward_no_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Пересылка не подходит</b>
        <b><i>Не пересылайте сообщение с группы. Пришлите ссылку текстом.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , go='add_bot' , ) ,
            b(
                text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
                when='reco' , ) , [ b(
                text="Нет @username" , icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""" ,
                color='primary' , go='public' , when='no_public' , ) , b(
                text="Кут не администратор" , icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""" ,
                color='primary' , go='admin' , when='no_admin' , ) , ] , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'link_invite': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это закрытая ссылка</b>
        <b><i>Создайте публичную ссылку на группу и отправьте её сюда.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад" , icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""" , go='back_how' , ) ,
        ],
    ),

    'group_not_found': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Такую группу наша система не видит</b>
        <blockquote><b><i>Кут уже должен быть в чате, иначе группу не мы не сможем найти.</i></b></blockquote>
        
        <b><i>Проверьте ссылку. Кут должен быть в чате. Потом пришлите ссылку снова.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'bot_not_there': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут не в «{name}»</b>
        <blockquote><b><i>Сначала добавьте бота, потом снова отправьте ссылку сюда.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'bot_not_there_reco': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут не в «{name}»</b>
        <b><i>Попросите создателя добавить @CuteGamingBot в админы группы.</i></b>
        
        <blockquote><b><i>Пока Кут не в чате - ссылку проверять рано.</i></b></blockquote>
        <b><i>Когда Кут будет в чате - пришлите сюда ссылку снова.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'cant_add': msg(
        emoji="""<tg-emoji emoji-id='5445325005778866735'>😩</tg-emoji>""",
        text="""
        <b>Чужая группа</b>
        <b>Попросите создателя группы добавить кут в список администраторов</b>
        <b><i>Когда Кут будет в чате - пришлите сюда ссылку.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) ,
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_how',
            ),
        ],
    ),

    'not_in_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Вас нет в «{name}»</b>
        <blockquote><b><i>Сдавать можно только чат, в котором вы сами состоите.</i></b></blockquote>
        
        <b><i>Сначала вступите в группу. Потом вернитесь сюда и пришлите ссылку.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'not_a_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это не группа</b>
        <blockquote><b><i>Канал, бот и личка не подходят.</i></b></blockquote>
        
        <b><i>Нужен чат, не канал и не человек. Пришлите ссылку на группу.</i></b>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'pick_group': msg(
        emoji="""<tg-emoji emoji-id='5445325005778866735'>😩</tg-emoji>""",
        text="""
        <b>Какую группу сдаём?</b>
        <blockquote><b><i>Список - чаты, где Кут уже есть. Одна кнопка - одна группа.</i></b></blockquote>
        <b><i>Нажмите на нужную группу. Если список не тот - «Назад», в главное меню.</i></b>
        """,
        buttons=[
            items('groups', text="{title}", go='pick_group'), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'pick_role': msg(
        emoji="""<tg-emoji emoji-id='5444884960609590878'>🧐</tg-emoji>""",
        text="""
        <b>«{name}»</b>
        <b>Кто сдаёт эту группу?</b>
        <blockquote><b><i>Создатель потом нажмёт Да в группе, если вы не владелец.</i></b></blockquote>
        """,
        buttons=[
            b(
                text="Это моя группа",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                color='default',
                go='owner',
            ),
            b(
                text="Я рекомендую Кут в группах",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'owner_bridge': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>«{name}»</b>
        <b>Вы создатель. Дальше 3 фото - и заявка идёт на проверку.</b>
        <blockquote><b><i>Если ваш знакомый попросил вас добавить Кут - не забирайте заявку : пусть он пришлёт ссылку в бота.</i></b></blockquote>
        
        <b><i>Пришлите первое фото сюда.</i></b>
        """,
        buttons=[
            b(
                text="Другое фото",
                icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""",
                go='undo',
                when='have_photos',
            ),
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'reco_bridge': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>«{name}»</b>
        <b>Вы не создатель. Чтобы доля шла вам, создатель должен нажать на кнопку "да" когда вы вызовете команду "подтверждение" в той группе в которую вы попросили добавить кут</b>
        
        <b><i>Пришлите первое фото сюда.</i></b>
        """,
        buttons=[
            b(
                text="Другое фото",
                icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""",
                go='undo',
                when='have_photos',
            ),
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'not_owner_switch': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Вы не владелец «{name}»</b>
        <blockquote><b><i>Чужой чат сдаётся через рекомендацию, а не через владельца группы</i></b></blockquote>
        
        <b><i>Нажмите «Я рекомендую бот в группах».</i></b>
        """,
        buttons=[
            b(
                text="Я рекомендую бот в группах",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'are_owner_switch': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>«{name}» - ваша группа</b>
        <b><i>Нажмите «Я владелец группы».</i></b>
        """,
        buttons=[ b(
            text="Я владелец группы" , icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""" ,
            go='owner' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'wait_photo': msg(
        emoji="""<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
        text="""
        <b>{step} из {total}</b>
        <b>{body}</b>
        <blockquote><b><i>{need}</i></b></blockquote>
        {next}
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
        next_by={
            '0': """<b>Пришлите фото сюда</b>""",
            '1': """<b>Пришлите следующее фото сюда, одним кадром.</b>""",
            '2': """<b>Пришлите последнее фото сюда - и заявка уйдёт дальше.</b>""",
        },
    ),

    'need_photo': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>{title}</b>
        <blockquote><b><i>{extra}</i></b></blockquote>
        <b>{tail}</b>
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'photos_expired': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>24 часа вышли</b>
        <blockquote><b><i>Три фото нужно успеть отправить за сутки с первого кадра.</i></b></blockquote>
        
        <b><i>Нажмите «Сдать ещё группу» или «Назад» - и сдайте три фото заново.</i></b>
        """,
        buttons=[
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'after_proofs_owner': msg(
        emoji="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
        text="""
        <b>Доказательства приняты</b>
        <b><i>Новым людям проект даст куты - играть ими можно только у вас, в этой группе.</i></b>
        
        <blockquote><b><i>Теперь ваша группа уйдёт на проверку. Ответ придёт сюда.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'after_proofs_reco': msg(
        emoji="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
        text="""
        <b>Доказательства приняты</b>
        <b><i>14 дней вам будет капать доля с игр новых людей в этой группе.</i></b>
        
        <blockquote><b><i>Теперь эта группа уйдёт на проверку. Ответ придёт сюда.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'after_photos_reco': msg(
        emoji="""<tg-emoji emoji-id='5388670457249552219'>👯‍♀️</tg-emoji>""",
        text="""
        <b>Откройте «{name}» и отправьте слово <code>подтверждение</code>.</b>
        
        <blockquote><b><i>Владелец группы должен будет нажать на кнопку "да", в течении 24 часов.</i></b></blockquote>
        """,
        buttons=[
            b(
                text="Открыть группу",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""",
                go='open_group',
                when='has_username',
            ),
            b(
                text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
                when='mine' , ) , b(
                text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'wrote_confirm': msg(
        emoji="""<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
        text="""
        <b>Ждём подтверждения от создателя</b>
        <i>В сообщении с подтверждением в группе он должен нажать Да.</i>
        
        <blockquote><b><i>Без Да доля вам не пойдёт.</i></b></blockquote>
        <i>Если не нажал - откройте группу и напишите «подтверждение» ещё раз.</i>
        """,
        buttons=[ b(
            text="Открыть группу" , icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""" , go='open_group' ,
            when='has_username' , ) , b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'earnings': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Заработки</b>
        <b>Всего вам пришло : {total}</b>
        <b>Сегодня : {today}</b>
        <blockquote><b><i>{barnum}</i></b></blockquote>
        <b>{next}</b>
        """,
        buttons=[
            items('claims', text="{label}", go='open_claim'),
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
                when='live',
            ),
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                go='more',
                when='not_live',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
        extra_by={
            'empty': """Пока тихо. Сдайте группу - и здесь появятся цифры, которые захочется открывать.""",
            'live_paid': """Это уже ваши цифры. Откройте группу - будет видно, откуда капает.""",
            'live': """Группа уже в работе. Первые куты приходят, когда новые люди начинают играть.""",
            'today': """Сегодня уже есть движение. Откройте группу - там подробнее.""",
            'pending': """Вы уже сделали свою часть. Пока смотрим заявку - можно подождать здесь.""",
        },
        next_empty="""Нажмите «Сдать ещё группу» и выберите, кто вы.""",
        next="""Нажмите группу - откроется карточка. «Сдать ещё группу» - новое меню.""",
    ),

    'mine': msg(
        emoji="""<tg-emoji emoji-id='5452064260437859029'>🌐</tg-emoji>""",
        text="""
        <b>Мои группы</b>
        <b>Всего вам пришло : {total}</b>
        <b>Сегодня : {today}</b>
        <blockquote><b><i>{barnum}</i></b></blockquote>
        <b>{next}</b>
        """,
        buttons=[
            items('claims', text="{label}", go='open_claim'),
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
                when='live',
            ),
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                go='more',
                when='not_live',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
        extra_by={
            'empty': """Пока тихо. Сдайте группу — и здесь появятся цифры, которые захочется открывать.""",
            'live_paid': """Это уже ваши цифры. Откройте группу — будет видно, откуда капает.""",
            'live': """Группа уже в работе. Первые куты приходят, когда новые люди начинают играть.""",
            'today': """Сегодня уже есть движение. Откройте группу — там подробнее.""",
            'pending': """Вы уже сделали свою часть. Пока смотрим заявку — можно подождать здесь.""",
        },
        next_empty="""Нажмите «Сдать ещё группу» и выберите, кто вы.""",
        next="""Нажмите группу — откроется карточка. «Сдать ещё группу» — новое меню.""",
    ),

    'card': msg(
        emoji="""<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
        text="""
        <b>«{name}»</b>
        <b>{facts}</b>
        <blockquote><b><i>{extra}</i></b></blockquote>
        <b>{next}</b>
        """,
        buttons=[ b(
            text="Открыть группу" , icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""" , go='open_group' ,
            when='has_username' , ) ,
            b(
                text="Продолжить фото",
                icon="""<tg-emoji emoji-id='5253767677670862169'>▶️</tg-emoji>""",
                color='success',
                go='continue_photo',
                when='photos',
            ),
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='photos',
            ),
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='wait_confirm',
            ),
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='pending',
            ),
            b(
                text="Назад",
                icon="""<tg-emoji emoji-id='5226660202035554522'>↩️</tg-emoji>""",
                go='back_mine',
            ),
        ],
        emoji_by={
            'live_owner': """<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
            'live_reco': """<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
            'photos': """<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
            'error': """<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
            'wait': """<tg-emoji emoji-id='5391143319029968523'>🤙</tg-emoji>""",
        },
        extra_by={
            'pause': """Начисления стоят, пока это не исправить.""",
            'photos': """Три кадра нужны, чтобы заявка ушла дальше.""",
            'wait_confirm': """Да нажимает только владелец группы""",
            'pending': """Решение по вашей заявке придёт в этот чат.""",
            'live': """Пока Кут в админах и группа открытая - цифры обновляются сами.""",
            'ended': """Новые куты с этой группы больше не капают.""",
            'rejected': """{reason}""",
            'burned': """Если Кут вернуть в админы - это уже новая заявка.""",
        },
        next_by={
            'pause': """{hint} «Назад» - к списку групп.""",
            'photos': """Нажмите «Продолжить фото» и пришлите следующий кадр сюда.""",
            'wait_confirm': """Нажмите «Открыть группу», напишите «подтверждение», дождитесь Да.""",
            'pending': """Ждите. «Назад» - к списку.""",
            'live': """Ничего нажимать не нужно. «Назад» - к списку групп.""",
            'ended': """Срок вышел. «Назад» - к списку. Новую группу сдайте с главного меню.""",
            'rejected': """«Назад» - к списку.""",
            'burned': """Кут убрали из группы. «Назад» - к списку.""",
            'default': """«Назад» - к списку групп.""",
        },
        facts_owner="""
        <b>{status}</b>
        <b>Баланс группы : {balance}</b>
        <b>Подарков новым : {gifts}</b>
        <b>Новых людей : {newcomers}</b>
        """,
        facts_reco="""
        <b>{status}</b>
        <b>Вам уже пришло : {paid}</b>
        <b>Сегодня : {today}</b>
        <b>Осталось дней : {days}</b>
        <b>Новых людей : {newcomers}</b>
        """,
    ),

    'cancelled': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Заявку сняли</b>
        <blockquote><b><i>Эту группу можно сдать снова, если слот свободен.</i></b></blockquote>
        """,
        buttons=[
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
    ),

    'confirm': msg(
        emoji="""<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji>""",
        text="""
        <b>{who} действительно рекомендовал добавить Кут в эту группу?. Если это так - нажмите <u>Да.</u></b>
        <blockquote><i>Тогда задание этого пользователя будет выполнено</i></blockquote>
        """,
        buttons=[
            [
                b(
                    text="Да",
                    icon="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
                    color='success',
                    go='yes',
                ),
                b(
                    text="Нет",
                    icon="""<tg-emoji emoji-id='5391050667995460499'>🤨</tg-emoji>""",
                    color='danger',
                    go='no_confirm',
                ),
            ],
        ],
    ),

    'confirm_yes': msg(
        emoji="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
        text="""
        <b>Подтверждено. Заявка на проверке.</b>
        <blockquote><b><i>Решение придёт пригласившему бота в группу в личку.</i></b></blockquote>
        <i>Ничего больше нажимать не нужно.</i>
        """,
    ),

    'confirm_no_first': msg(
        emoji="""<tg-emoji emoji-id='5391050667995460499'>🤨</tg-emoji>""",
        text="""
        <b>Создатель группы не подтвердил рекомендацию бота</b>
        <blockquote><b><i>Остался один шанс в течение 24 часов.</i></b></blockquote>
        <i>Откройте группу и напишите <code>подтверждение</code> ещё раз.</i>
        """,
        buttons=[ b(
            text="Открыть группу" , icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""" , go='open_group' ,
            when='has_username' , ) , b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' ,
            when='wait_confirm' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'confirm_no_second': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Снова отказ от владельца группы в которой вы пытались рекомендовать наш проект</b>
        <blockquote><b><i>После двух отказов группу нельзя эту сдавать на задание 31 день.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'not_your_claim': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это не ваша заявка.</b>
        <blockquote><b><i>Подтверждение и снятие доступны только тому, кто сдавал группу.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'not_creator': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Подтверждает только создатель</b>
        <blockquote><b><i>Только владелец группы может подтвердить рекомендацию нашего проекта от какого-то пользователя</i></b></blockquote>
        """,
    ),

    'confirm_expired': msg(
        emoji="""<tg-emoji emoji-id='5447589583120257784'>😁</tg-emoji>""",
        text="""
        <b>Это подтверждение уже не действует.</b>
        <blockquote><b><i>Кнопки Да/Нет живут 24 часа с момента вызова функции «подтверждение».</i></b></blockquote>
        
        <i>Напишите в группе «подтверждение» снова.</i>
        """,
    ),

    'wrong_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Не та группа.</b>
        <blockquote><b><i>Функция «подтверждение» срабатывает только в сданном вами чате.</i></b></blockquote>
        
        <i>Откройте ту группу, куда вы добавляли Кут, и напишите «подтверждение» там.</i>
        """,
    ),

    'need_photos_first': msg(
        emoji="""<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
        text="""
        <b>Сначала отправьте 3 фото-доказательства в бот</b>
        <blockquote><b><i>Подтверждение в группе открывается только после трёх кадров.</i></b></blockquote>
        
        <i>Пришлите их сюда, в этот чат, по одному кадру.</i>
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'accepted': msg(
        emoji="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
        text="""
        <b>Группу приняли!</b>
        <b>{days} дней вам будет капать доля с игр новых пользователей в проекте</b>
        <blockquote><b><i>Капает только с людей, которых Кут ещё не знал.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'accepted_owner': msg(
        emoji="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
        text="""
        <b>Группу приняли!</b>
        <b>{days} дней · новые пользователи в проекте смогут играть у вас в группе на подарочные куты от проекта.</b>
        <blockquote><b><i>Подарки работают только в одиночных играх, и именно в той группе которую в которую вы добавили бот</i></b></blockquote>

        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'digest': msg(
        emoji="""<tg-emoji emoji-id='5444884960609590878'>🧐</tg-emoji>""",
        text="""
        <b>Сегодня с «{name}» : {newcomers} новых людей · вам {paid} кут.</b>
        <b>Осталось {days} дн.</b>
        <blockquote><b><i>{note}</i></b></blockquote>
        """,
        extra_by={
            'paid': """Это уже на вашем балансе.""",
            'empty': """Как появятся игры новых - цифра вырастет.""",
        },
    ),

    'gift': msg(
        emoji="""<tg-emoji emoji-id='5355193051193059834'>🎁</tg-emoji>""",
        text="""
        <b>{who}, На ваш баланс было выдано {amount} кут в подарок, для того чтобы научится играть в @CuteGamingBot</b>
        <blockquote><b><i>В случае каких либо непоняток, напишите "хелп"</i></b></blockquote>
        """,
    ),

    'gift_locked': msg(
        emoji="""<tg-emoji emoji-id='5271929616896921139'>🪨</tg-emoji>""",
        text="""
        <b>Подарочные куты можно поставить только в одиночных группах этой группы</b>
        <blockquote><b><i>Снять или перевести нельзя - ими учатся играть у вас в группе</i></b></blockquote>
        """,
    ),

    'term_end': msg(
        emoji="""<tg-emoji emoji-id='5445110875889360215'>🤐</tg-emoji>""",
        text="""
        <b>Срок по этой группе закончился. Новые куты с неё больше не капают.</b>
        <blockquote><b><i>Уже начисленные куты остаются у вас.</i></b></blockquote>
        
        <i>Откройте «Мои группы», чтобы увидеть статус. Новую группу можно сдать с главного меню.</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'kicked': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут убрали из группы. Начисления остановились.</b>
        <blockquote><b><i>Заявка по этой группе сгорает, если бот выгнали.</i></b></blockquote>
        
        <i>Верните Кут в админы, если хотите продолжить. Статус - в «Мои группы».</i>
        """,
    ),

    'rejected': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Не приняли.</b>
        <b><i>{reason}</i></b>
        <blockquote><b><i>Эту заявку уже не поправить.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'rejected_fix': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Не приняли.</b>
        <b><i>{reason}</i></b>
        <blockquote><b><i>Есть 48 часов, чтобы исправить и сдать снова.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Сдать ещё группу" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" ,
            color='success' , go='more' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'two_pending': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Максимум может быть 2 заявки</b>
        <blockquote><b><i>Одновременно смотрим не больше двух заявок на человека.</i></b></blockquote>
        
        <i>Нажмите «Мои группы» : дождитесь проверки или снимите одну.</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'two_live': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Максимум может быть 2 живых заявки</b>
        <blockquote><b><i>Живых групп на человеке не больше двух.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'banned_31': msg(
        emoji="""<tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji>""",
        text="""
        <b>Эту группу нельзя сдавать</b>
        <blockquote><b><i>После отказа создателя, слот на чат закрывается на месяц.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'freeze_admin': msg(
        emoji="""<tg-emoji emoji-id='5449913031578379785'>🛡</tg-emoji>""",
        text="""
        <b>Пауза : Куту нужно иметь права администратора</b>
        <i>Верните Кут в администраторы группы. Потом снова начнут приходить деньги</i>
        """,
    ),

    'freeze_public': msg(
        emoji="""<tg-emoji emoji-id='5447589583120257784'>😁</tg-emoji>""",
        text="""
        <b>Пауза : группа стала закрытой</b>
        <blockquote><b><i>Начисления стоят только в том случае если группа является публичной</i></b></blockquote>
        """,
    ),

    'group_busy': msg(
        emoji="""<tg-emoji emoji-id='5393451614843467174'>🔮</tg-emoji>""",
        text="""
        <b>Эту группу уже сдают</b>
        <blockquote><b><i>Одна группа - один человек. Первый, кто сдал доказательства, держит слот.</i></b></blockquote>
        
        <i>Нажмите «Назад» и возьмите другую.</i>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'group_busy_owner': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Эту группу уже сдаёт создатель</b>
        <blockquote><b><i>Одна группа - один человек. Первый, кто сдал доказательства, держит слот.</i></b></blockquote>
        
        <i>Нажмите «Назад» и возьмите другую.</i>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'confirm_timeout': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Создатель не нажал <u>Да</u> за 24 часа</b>
        <blockquote><b><i>Без подтверждения рекомендации, заявка не идёт на проверку.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Сдать ещё группу" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" ,
            color='success' , go='more' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'owner_no_confirm': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>Вам подтверждение не нужно</b>
        <blockquote><b><i>Создателю группы не нужно подтверждать рекомендацию бота в своей же группе</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
            color='success' , go='back_hub' , ) ,
        ],
    ),

    'resume': msg(
        emoji="""<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
        text="""
        <b>«{name}»</b>
        <b>{status}</b>
        <blockquote><b><i>Заявка не потерялась - продолжаем с того же шага.</i></b></blockquote>
        """,
        buttons=[b(
            text="Снять" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' ,
            when='photos' , ) ,
            b(
                text="Снять",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='wait_confirm',
            ),
            b(
                text="Мои группы",
                icon="""<tg-emoji emoji-id='5192951739623447936'>👥</tg-emoji>""",
                go='groups',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5460858729962421671'>✨</tg-emoji>""" ,
                color='success' , go='back_hub' , ) ,
        ],
        emoji_by={
            'live_owner': """<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
            'live_reco': """<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
            'photos': """<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
            'error': """<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
            'wait': """<tg-emoji emoji-id='5445110875889360215'>🤐</tg-emoji>""",
        },
    ),

}


# ===========================================================================
# Служебное. Ниже не текст экранов.
# ===========================================================================

PALETTE = {
    "hub": SCREENS["hub"]["emoji"],
    "owner": SCREENS["how_owner"]["emoji"],
    "reco": SCREENS["how_reco"]["emoji"],
    "photo": SCREENS["wait_photo"]["emoji"],
    "earn": SCREENS["earnings"]["emoji"],
    "groups": SCREENS["mine"]["emoji"],
    "public": SCREENS["how_public"]["emoji"],
    "admin": SCREENS["how_admin"]["emoji"],
    "ok": SCREENS["after_proofs_owner"]["emoji"],
    "wait": SCREENS["need_link"]["emoji"],
    "no": SCREENS["forward_no_group"]["emoji"],
    "gift": SCREENS["gift"]["emoji"],
    "confirm": SCREENS["confirm"]["emoji"],
}

HUB = SCREENS["hub"]["emoji"]

_EMOJI_RE = re.compile(r"<tg-emoji emoji-id=['\"](\d+)['\"]>(.*?)</tg-emoji>", re.I | re.S)
_NEVER_TOGETHER = {
    ("live", "not_live"),
    ("not_live", "live"),
    ("live", "mine"),
    ("mine", "live"),
    ("photos", "wait_confirm"),
    ("wait_confirm", "photos"),
    ("photos", "pending"),
    ("pending", "photos"),
    ("wait_confirm", "pending"),
    ("pending", "wait_confirm"),
}


def parse_emoji(tag: str) -> tuple[str, str]:
    raw = str(tag or "").strip()
    match = _EMOJI_RE.search(raw)
    if match:
        return match.group(1), match.group(2)
    if raw.isdigit():
        return raw, "🔹"
    return "", ""


def emoji_id(tag: str) -> str:
    return parse_emoji(tag)[0]


def emoji_html(tag: str) -> str:
    raw = str(tag or "").strip()
    if "<tg-emoji" in raw:
        return raw
    eid, face = parse_emoji(raw)
    if not eid:
        return ""
    return f"<tg-emoji emoji-id='{eid}'>{face}</tg-emoji>"


def _shows_together(one: str, two: str) -> bool:
    a = str(one or "always")
    b = str(two or "always")
    if a == "always" or b == "always":
        return True
    return (a, b) not in _NEVER_TOGETHER


def _button_icon(screen: str, go: str) -> str:
    spec = SCREENS[screen]
    for row in iter_button_rows(spec.get("buttons")):
        if isinstance(row, dict):
            continue
        for btn in row:
            if btn.get("go") == go and btn.get("icon"):
                return str(btn["icon"])
    return ""


_NEED_WORDS = (
    "kut", "group", "this_group", "group_acc", "of_group", "player",
    "photo", "photo_have", "photo_hint_n", "ellipsis",
    "gifts_row", "claim_btn", "claim_btn_money",
    "seen_line", "seen_join", "seen_no_public", "seen_no_admin",
    "rejected", "reject_fallback", "reject_join",
    "toast_check", "history_gift", "history_payout",
)


def design_errors() -> list[str]:
    errors: list[str] = []
    for key in _NEED_WORDS:
        if key not in WORDS or not str(WORDS[key]).strip():
            errors.append(f"WORDS: пустой «{key}»")
    if not str(TASKS_MENU.get("text") or "").strip():
        errors.append("TASKS_MENU: пустой text")
    if not emoji_id(TASKS_MENU.get("icon") or ""):
        errors.append("TASKS_MENU: нет прем-эмодзи в icon=")
    if not str(HELP_TASKS or "").strip():
        errors.append("HELP_TASKS: пустой текст хелпа")
    for name, spec in SCREENS.items():
        if not str(spec.get("text") or "").strip():
            errors.append(f"{name}: пустой text — вставь сообщение")
        found: list[tuple[str, str, str]] = []
        for row in iter_button_rows(spec.get("buttons")):
            if isinstance(row, dict):
                continue
            gos = []
            for btn in row:
                text = str(btn.get("text") or "?").strip() or "?"
                go = str(btn.get("go") or "")
                when = str(btn.get("show") or btn.get("when") or "always")
                color = str(btn.get("style") or btn.get("color") or "default")
                icon = str(btn.get("icon") or "")
                eid = emoji_id(icon)
                if not go or go not in ACTIONS:
                    errors.append(f"{name}: у «{text}» неизвестное действие go={go!r}")
                if when not in WHEN:
                    errors.append(f"{name}: у «{text}» неизвестное when={when!r}")
                if color not in COLORS:
                    errors.append(f"{name}: у «{text}» неизвестный color={color!r}")
                if not eid:
                    errors.append(f"{name}: у «{text}» нет прем-эмодзи — вставь icon=...")
                else:
                    found.append((text, eid, when))
                gos.append(go)
            if len(gos) != len(set(gos)):
                errors.append(f"{name}: в одном ряду два одинаковых go {gos}")
        for i, (text_a, id_a, when_a) in enumerate(found):
            for text_b, id_b, when_b in found[i + 1:]:
                if id_a == id_b and _shows_together(when_a, when_b):
                    errors.append(f"{name}: одинаковый эмодзи у кнопок «{text_a}» и «{text_b}» — смени icon")
    return errors


def assert_design() -> None:
    bad = design_errors()
    if bad:
        raise RuntimeError("Дизайн пиара — повтор эмодзи на кнопках:\n- " + "\n- ".join(bad))


EMOJI_HUB = emoji_id(SCREENS["hub"]["emoji"])
EMOJI_OWNER = emoji_id(SCREENS["how_owner"]["emoji"])
EMOJI_RECO = emoji_id(SCREENS["how_reco"]["emoji"])
EMOJI_PHOTO = emoji_id(SCREENS["wait_photo"]["emoji"])
EMOJI_EARN = emoji_id(SCREENS["earnings"]["emoji"])
EMOJI_GROUPS = emoji_id(SCREENS["mine"]["emoji"])
EMOJI_PUBLIC = emoji_id(SCREENS["how_public"]["emoji"])
EMOJI_ADMIN = emoji_id(SCREENS["how_admin"]["emoji"])
STATUS_EMOJI_OK = emoji_id(SCREENS["after_proofs_owner"]["emoji"])
STATUS_EMOJI_WAIT = emoji_id(SCREENS["need_link"]["emoji"])
STATUS_EMOJI_NO = emoji_id(SCREENS["forward_no_group"]["emoji"])
GIFT_EMOJI = emoji_id(SCREENS["gift"]["emoji"])
CONFIRM_EMOJI = emoji_id(SCREENS["confirm"]["emoji"])

ICON_GO = emoji_id(_button_icon("how_owner", "add_bot"))
ICON_NO = emoji_id(_button_icon("wait_photo", "cancel"))
ICON_BACK = emoji_id(_button_icon("how_public", "back_how"))
ICON_BACK_HUB = emoji_id(_button_icon("choose", "back_hub"))
ICON_OWNER = emoji_id(_button_icon("hub", "owner"))
ICON_RECO = emoji_id(_button_icon("hub", "reco"))
ICON_EARN = emoji_id(_button_icon("hub", "earnings"))
ICON_GROUPS = emoji_id(_button_icon("hub", "groups"))
ICON_CANT = emoji_id(_button_icon("how_reco", "cant"))
ICON_PUBLIC = emoji_id(_button_icon("how_owner", "public"))
ICON_ADMIN = emoji_id(_button_icon("how_owner", "admin"))
ICON_OPEN = emoji_id(_button_icon("after_photos_reco", "open_group"))
ICON_UNDO = emoji_id(_button_icon("wait_photo", "undo"))
ICON_MORE = emoji_id(_button_icon("photos_expired", "more"))
ICON_CONT = emoji_id(_button_icon("card", "continue_photo"))
ICON_CHECK = ICON_GO
ICON_WROTE = ICON_OPEN
ICON_OK = ICON_GO
TASKS_MENU_ICON_ID = emoji_id(TASKS_MENU["icon"])

assert_design()
