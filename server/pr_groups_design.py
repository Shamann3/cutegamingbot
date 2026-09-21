# -*- coding: utf-8 -*-
"""Пиар в группах - дизайн всех сообщений.

Как править
-----------
Сообщение целиком - в text= тройными кавычками.
Эмодзи сообщения - в emoji=.
Кнопки сразу под текстом: text="подпись" обычными кавычками, icon= у каждой.

Типографика
-----------
<b>жирный</b> - то, на чём нужно сосредоточиться.
<i>курсив</i> - доп. текст, в основном навигация: что нажать, куда отправить.
<u>подчёркнутый</u> - только самое важное: 35%, 14 дней, подтверждение, 3 фото, суммы, @бот.
Доп. информация - в <blockquote><b><i>…</i></b></blockquote>
Много текста - тоже в цитате, блоки разделяй пустой строкой.

WORDS для кнопок, тостов и истории - без тегов: Telegram их там не рисует.
В тексте можно: <b> <i> <u> <code> {name} {link_hint} {progress}
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


_TAG_RE = re.compile(r"<[^>]+>")


def plain(text) -> str:
    """Текст для кнопки, тоста и истории: без тегов, Telegram их там не рисует."""
    return " ".join(_TAG_RE.sub("", str(text or "")).split())


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
        'what': t("""<b>Скриншот списка администраторов.</b>"""),
        'need': t("""<blockquote><b><i>Так видно, что <u>@CuteGamingBot</u> админ.</i></b></blockquote>"""),
    },
    {
        'what': t("""<b>Скриншот сообщения от Кут в этой группе.</b>"""),
        'need': t("""<blockquote><b><i>Так видно, что бот в чате отвечает.</i></b></blockquote>"""),
    },
    {
        'what': t("""<b>Скриншот, где видно создателя.</b>"""),
        'need': t("""<blockquote><b><i>Так понятно, кто владелец группы.</i></b></blockquote>"""),
    },
)

NEED_PHOTO = {
    'video': {
        'title': t("""Нужно фото, не видео."""),
        'extra': t("""Видео и кружок не принимаем."""),
        'next': t("""Картинка из галереи - сюда."""),
    },
    'file': {
        'title': t("""Нужно фото, не файл."""),
        'extra': t("""Документ без картинки не принимаем."""),
        'next': t("""Картинка из галереи - сюда."""),
    },
    'sticker': {
        'title': t("""Нужно фото из группы."""),
        'extra': t("""Стикер и эмодзи - это не скрин."""),
        'next': t("""Картинка из группы - сюда."""),
    },
    'text': {
        'title': t("""Нужно фото, не текст."""),
        'extra': t("""Текст сюда не подходит - нужен кадр."""),
        'next': t("""Картинка из галереи - сюда."""),
    },
    'album': {
        'title': t("""По одному фото."""),
        'extra': t("""Альбом склеит кадры в одно сообщение."""),
        'next': t("""Следующий кадр - отдельно."""),
    },
    'dup': {
        'title': t("""Это фото уже есть."""),
        'extra': t("""Этот кадр уже принят."""),
        'next': t("""Пришлите другой кадр."""),
    },
    '': {
        'title': t("""Нужно именно фото."""),
        'extra': t("""Нужен скрин из самой группы."""),
        'next': t("""Картинка из галереи - сюда."""),
    },
}

# ===========================================================================
# Короткие тексты. Человек их тоже видит.
# Кнопки списков, статусы, тосты, меню заданий, хелп - правь здесь.
# ===========================================================================

WORDS = {
    "kut": "{n} кут",
    "group": "группа",
    "this_group": "эта группа",
    "group_acc": "группу",
    "of_group": "группы",
    "player": "игрок",
    "photo": "фото",
    "photo_have": "<b>Есть <u>{have} из {total}</u>.</b>\n\n{what}",
    "photo_hint_n": "фото {n}",
    "ellipsis": "…",
    "gifts_row": "подарков: {n}",
    "claim_btn": "{title} · {short}",
    "claim_btn_money": "{title} · {short} · {money}",
    "seen_line": "«{names}» - {reason}.",
    "seen_join": "», «",
    "seen_no_public": "нет @адреса",
    "seen_no_admin": "Кут не администратор",
    "rejected": "Не приняли.",
    "reject_fallback": "Заявку не приняли.",
    "reject_join": " · ",
    "toast_check": "Смотрю группы…",
    "history_gift": "подарок новой группы",
    "history_payout": "рекомендации бота в группах",
    "progress": "<i>Шаг {n} из {total}: {what}</i>",
}

PATH_OWNER = (
    "откройте группу и добавьте Кут",
    "пришлите ссылку сюда",
    "отправьте 3 фото",
    "ждём проверку",
)
PATH_RECO = (
    "создатель добавит Кут в админы",
    "пришлите ссылку сюда",
    "отправьте 3 фото",
    "нужно подтверждение рекомендации",
    "ждём проверку",
)


def progress(*, intent: str = "", n: int = 1) -> str:
    reco = str(intent or "") == "reco"
    labels = PATH_RECO if reco else PATH_OWNER
    total = len(labels)
    step = max(1, min(int(n or 1), total))
    return say("progress", n=step, total=total, what=labels[step - 1])

# Слова, которые человек пишет боту. Пусть совпадают с текстом сообщений.
CONFIRM_WORDS = frozenset({
    "подтверждение", "подтвердить", "подтверди", "confirm", "confirmation",
})
HELP_WORDS = frozenset({
    "хелп", "help", "помощь", "?",
})

STATUS = {
    "photos": "нужны <u>3 фото</u>",
    "wait_confirm": "ждём <u>подтверждение</u>",
    "confirm_retry": "ещё один шанс",
    "pending": "заявку смотрят",
    "accepting": "заявку смотрят",
    "fulfilling": "заявку смотрят",
    "live": "идёт заработок",
    "ended": "срок вышел",
    "rejected": "не приняли",
    "burned": "Кут убрали",
    "expired": "время вышло",
    "cancelled": "заявку сняли",
}

STATUS_SHORT = {
    "photos": "фото",
    "wait_confirm": "ждём подтверждение",
    "confirm_retry": "ещё шанс",
    "pending": "смотрят",
    "accepting": "смотрят",
    "fulfilling": "смотрят",
    "live": "идёт",
    "ended": "срок",
    "rejected": "не приняли",
    "burned": "убрали",
    "expired": "время",
    "cancelled": "сняли",
}

PAUSE = {
    "admin": "пауза: Куту нужна админка",
    "public": "пауза: группа закрыта",
}

PAUSE_HINT = {
    "admin": "Верните Кут в администраторы - зарплата снова начнёт капать.",
    "public": "Сделайте группу публичной - зарплата снова начнёт капать.",
}

PAUSE_SHORT = {
    "admin": "пауза",
    "public": "закрыта",
}

IDLE_HINT = {
    "hot": "скорее нет",
    "warn": "осторожно",
    "ok": "можно смотреть",
}

IDLE_LABEL = "Уходил {n} дн. назад · {hint}"

PHOTO_HINTS = (
    "список админов",
    "сообщение от Кут",
    "создатель группы",
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
    "text": "Заработок в группах",
    "icon": "<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>",
}

HELP_TASKS = t("""
<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji> <b>Заработок в группах</b>

<blockquote><b><i>Кут - игры прямо в Telegram. Новым пользователям проект выдаёт подарочные куты, чтобы начать играть. Вам - до 35% комиссии с их игр, 14 дней. Откройте задание.</i></b></blockquote>

<blockquote><code>Задания</code></blockquote>
""")


# ===========================================================================
# Экраны. У каждого: целый текст, потом кнопки.
# ===========================================================================

SCREENS: dict[str, dict] = {

    'hub': msg(
        emoji="""<tg-emoji emoji-id='5452002597592382164'>📣</tg-emoji>""",
        text="""
        <b>В чате сидят люди. Они не играют - вам с этого ноль.</b>

        <b>Кут - игры в Telegram. Новым пользователям проект выдаёт подарочные куты, чтобы начать. Вам - до 35% комиссии с их игр, 14 дней.</b>

        <blockquote><b><i>Своя группа или чужая. Нажмите, кто вы - дальше только ваш путь, без лишнего.</i></b></blockquote>

        <i>Нажмите, кто вы.</i>
        """,
        buttons=[
            b(
                text="Я владелец группы",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                color='default',
                go='owner',
            ),
            b(
                text="Это чужая группа",
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
                icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""",
                color='primary',
                go='back_tasks',
            ),
        ],
    ),

    'choose': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>Кто вы?</b>

        <b>Кут ставят в группу. Люди играют в чате. Вам капает.</b>

        <blockquote><b><i>Своя группа - играют у вас.
Чужая - до 35% комиссии вам, 14 дней.
Новым пользователям проект выдаёт подарочные куты.</i></b></blockquote>

        <i>Нажмите кнопку.</i>
        """,
        buttons=[
            b(
                text="Я владелец группы",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                go='owner',
            ),
            b(
                text="Это чужая группа",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ),
            b(
                text="Назад, в главное меню",
                icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""",
                color='primary',
                go='back_hub',
            ),
        ],
    ),

    'how_owner': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>Сдать свою группу</b>

        {progress}

        <b>Люди играют в вашем чате. Не уходят в чужой.</b>

        <blockquote><b><i>Кут - игры в Telegram.
Новым пользователям проект выдаёт подарочные куты.
Играть ими можно только у вас, в одиночных играх.
Снять или перевести нельзя.
Вам не 35% на карман - вам игроки и баланс группы.
14 дней. Только те, кого Кут ещё не знал.</i></b></blockquote>

        <blockquote><b><i>Когда вернётесь - пришлите ссылку сюда. Подойдёт {link_hint}</i></b></blockquote>

        <blockquote><b><i>{seen}</i></b></blockquote>

        <i>Нажмите «Добавить Кут». Это игровой бот - ему нужна админка.</i>
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
                    text="Группа закрытая",
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
                icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""",
                color='primary',
                go='back_hub',
            ),
        ],
    ),

    'how_reco': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>Рекомендовать бота в группе</b>

        {progress}

        <b>Кут - игры в Telegram. Чужая группа может платить вам до 35% комиссии, 14 дней.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Играть - в чужой группе.
Когда они играют, с комиссии их игр вам капает до 35%.
Только новые - кого Кут ещё не знал.
Нужно подтверждение, что вы порекомендовали добавить <u>@CuteGamingBot</u>.</i></b></blockquote>

        <blockquote><b><i>Сначала создатель добавляет Кут в админы. Следующий шаг бот откроет сам.</i></b></blockquote>

        <blockquote><b><i>{seen}</i></b></blockquote>

        <i>Когда Кут в админах - пришлите ссылку сюда.</i>
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
                    text="Группа закрытая",
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
                icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""",
                color='primary',
                go='back_hub',
            ),
        ],
    ),

    'how_public': msg(
        emoji="""<tg-emoji emoji-id='5856976696019784799'>💙</tg-emoji>""",
        text="""
        <b>Закрытая группа деньги не принесёт</b>

        {progress}

        <blockquote><b><i>Название сверху → Управление → Тип группы → <u>Публичная</u></i></b></blockquote>

        <blockquote><b><i>Без открытого @адреса заработок не запустим. Новым пользователям проект выдаёт подарочные куты.</i></b></blockquote>

        <i>Сделайте публичной и пришлите ссылку сюда.</i>
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
        <b>Без админки куты не капают</b>

        {progress}

        <b>Кут должен видеть чат. Иначе куты не капают.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Без прав администратора заявку не примем.</i></b></blockquote>

        <i>Добавьте Кут в администраторы и пришлите ссылку сюда.</i>
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
        <b>Без админки куты не капают</b>

        {progress}

        <b>Попросите создателя дать Куту права администратора.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Без админки заработок не стартует.</i></b></blockquote>

        <i>Когда Кут в админах - пришлите ссылку сюда.</i>
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

        {progress}

        <b>Закрытую группу сдать нельзя.</b>

        <blockquote><b><i>Нужен открытый @адрес.</i></b></blockquote>

        <i>Сделайте публичной и пришлите ссылку сюда.</i>
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
        <b>В «{name}» Кут не администратор</b>

        {progress}

        <b>Без админки заявку не примем.</b>

        <blockquote><b><i>Кут должен видеть чат.</i></b></blockquote>

        <i>Добавьте Кут в администраторы и пришлите ссылку сюда.</i>
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
        <b>В «{name}» Кут не администратор</b>

        {progress}

        <b>Попросите создателя дать ему админку.</b>

        <blockquote><b><i>Без админки заявку не примем.</i></b></blockquote>

        <i>Когда Кут в админах - пришлите ссылку сюда.</i>
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
        <b>Кут уже в «{name}». Осталось забрать результат.</b>

        <b>Нажмите, кто вы. Дальше только ваш путь.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Своя группа - играют у вас. Чужая - доля вам.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Я владелец группы" , icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""" ,
            go='owner' , ) , b(
            text="Это чужая группа" , icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""" ,
            go='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'bot_joined_intent': msg(
        emoji="""<tg-emoji emoji-id='5857185830862329369'>💚</tg-emoji>""",
        text="""
        <b>Кут уже в «{name}». Не отпустите этот слот.</b>

        {progress}

        <b>Если он ещё не админ - дайте админку. Иначе куты не капнут.</b>

        <blockquote><b><i>Потом ссылка сюда. Без ссылки дальше не пойдём. Новым пользователям проект выдаёт подарочные куты.</i></b></blockquote>

        <i>Если Кут уже админ - отправьте ссылку сюда.</i>
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

        {progress}

        <b>Пришлите её сюда текстом - из шапки группы.</b>

        <blockquote><b><i>Подойдёт {link_hint}</i></b></blockquote>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Без ссылки куты не начнут капать.</i></b></blockquote>

        <i>Копировать ссылку - из шапки группы.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , go='add_bot' , ) ,
            b(
                text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
                when='reco' , ) , [ b(
                text="Группа закрытая" , icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""" ,
                color='primary' , go='public' , when='no_public' , ) , b(
                text="Кут не администратор" , icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""" ,
                color='primary' , go='admin' , when='no_admin' , ) , ] , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'forward_no_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Пересылка не подходит</b>

        {progress}

        <b>Пришлите ссылку текстом, не сообщением из группы.</b>

        <blockquote><b><i>Подойдёт {link_hint}</i></b></blockquote>

        <i>Скопируйте ссылку из шапки и отправьте сюда.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , go='add_bot' , ) ,
            b(
                text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
                when='reco' , ) , [ b(
                text="Группа закрытая" , icon="""<tg-emoji emoji-id='5271604874419647061'>🔗</tg-emoji>""" ,
                color='primary' , go='public' , when='no_public' , ) , b(
                text="Кут не администратор" , icon="""<tg-emoji emoji-id='5251203410396458957'>🛡</tg-emoji>""" ,
                color='primary' , go='admin' , when='no_admin' , ) , ] , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'link_invite': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это закрытая ссылка</b>

        {progress}

        <b>Нужна <u>публичная</u> ссылка на группу.</b>

        <blockquote><b><i>Приглашение t.me/+ не подойдёт.</i></b></blockquote>

        <i>Создайте публичную ссылку и отправьте её сюда.</i>
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
        <b>Такую группу система не видит</b>

        {progress}

        <b>Кут уже должен быть в чате.</b>

        <blockquote><b><i>Без Кута в чате ссылку не проверим.</i></b></blockquote>

        <i>Проверьте ссылку и пришлите её снова.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'bot_not_there': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут не в «{name}»</b>

        {progress}

        <b>Сначала добавьте бота в чат.</b>

        <blockquote><b><i>Пока Кут не в группе - ссылку проверять рано.</i></b></blockquote>

        <i>Добавьте Кут и отправьте ссылку сюда снова.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'bot_not_there_reco': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут не в «{name}»</b>

        {progress}

        <b>Попросите создателя добавить <u>@CuteGamingBot</u> в админы.</b>

        <blockquote><b><i>Пока Кут не в чате - ссылку проверять рано.</i></b></blockquote>

        <i>Когда Кут в чате - пришлите ссылку снова.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'cant_add': msg(
        emoji="""<tg-emoji emoji-id='5445325005778866735'>😩</tg-emoji>""",
        text="""
        <b>Чужая группа. Куты всё равно могут быть вашими.</b>

        {progress}

        <b>Попросите создателя добавить <u>@CuteGamingBot</u> в администраторы.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Подойдёт {link_hint}</i></b></blockquote>

        <i>Когда Кут в чате - пришлите ссылку сюда, из шапки группы.</i>
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

        {progress}

        <b>Сдавать можно только чат, где вы сами состоите.</b>

        <blockquote><b><i>Чужой чат со стороны не принимаем.</i></b></blockquote>

        <i>Сначала вступите. Потом пришлите ссылку сюда.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'not_a_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это не группа</b>

        {progress}

        <b>Канал, бот и личка не подходят.</b>

        <blockquote><b><i>Нужен чат - там пишут и играют.</i></b></blockquote>

        <i>Пришлите ссылку на группу.</i>
        """,
        buttons=[ b(
            text="Добавить Кут" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" , color='success' ,
            go='add_bot' , ) , b(
            text="Не могу добавить" , icon="""<tg-emoji emoji-id='5463426192692500499'>🤞</tg-emoji>""" , go='cant' ,
            when='reco' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'pick_group': msg(
        emoji="""<tg-emoji emoji-id='5445325005778866735'>😩</tg-emoji>""",
        text="""
        <b>Какую группу сдаём?</b>

        <blockquote><b><i>Список - чаты, где Кут уже есть.</i></b></blockquote>

        <i>Нажмите нужную. Если список не тот - «Назад».</i>
        """,
        buttons=[
            items('groups', text="{title}", go='pick_group'), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'pick_role': msg(
        emoji="""<tg-emoji emoji-id='5444884960609590878'>🧐</tg-emoji>""",
        text="""
        <b>«{name}»</b>

        <b>Кто забирает результат с этой группы?</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты.
Своя - новички играют только у вас.
Чужая - доля вам с их игр, нужно подтверждение рекомендации.</i></b></blockquote>

        <i>Нажмите, кто вы.</i>
        """,
        buttons=[
            b(
                text="Это моя группа",
                icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
                color='default',
                go='owner',
            ),
            b(
                text="Это чужая группа",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'owner_bridge': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>«{name}»</b>

        {progress}

        <b>Дальше <u>3 фото</u> - по ним проверим, что Кут в чате.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Играть только у вас. Если знакомый просил добавить Кут - пусть сам пришлёт ссылку в бота.</i></b></blockquote>

        <i>Пришлите первое фото сюда.</i>
        """,
        buttons=[
            b(
                text="Другое фото",
                icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""",
                go='undo',
                when='have_photos',
            ),
            b(
                text="Снять заявку",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'reco_bridge': msg(
        emoji="""<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji>""",
        text="""
        <b>«{name}»</b>

        {progress}

        <b>Чтобы доля шла вам, нужно подтверждение рекомендации.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Сначала 3 фото. Потом в группе напишите «подтверждение» - что вы порекомендовали добавить бота.</i></b></blockquote>

        <i>Пришлите первое фото сюда.</i>
        """,
        buttons=[
            b(
                text="Другое фото",
                icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""",
                go='undo',
                when='have_photos',
            ),
            b(
                text="Снять заявку",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'not_owner_switch': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Вы не владелец «{name}»</b>

        <b>Чужой чат сдаётся через рекомендацию.</b>

        <blockquote><b><i>Иначе доля уйдёт не тому.</i></b></blockquote>

        <i>Нажмите «Это чужая группа».</i>
        """,
        buttons=[
            b(
                text="Это чужая группа",
                icon="""<tg-emoji emoji-id='5388583647370565067'>🔥</tg-emoji>""",
                go='reco',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'are_owner_switch': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>«{name}» - ваша группа</b>

        <blockquote><b><i>Создателю подтверждение не нужно.</i></b></blockquote>

        <i>Нажмите «Я владелец группы».</i>
        """,
        buttons=[ b(
            text="Я владелец группы" , icon="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""" ,
            go='owner' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'wait_photo': msg(
        emoji="""<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
        text="""
        <b>{step} из {total}</b>

        {progress}

        {body}

        {need}

        {next}
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
        next_by={
            '0': """<i>Пришлите фото сюда.</i>""",
            '1': """<i>Пришлите следующее фото сюда, одним кадром.</i>""",
            '2': """<i>Пришлите последнее фото сюда.</i>""",
        },
    ),

    'need_photo': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>{title}</b>

        {progress}

        <blockquote><b><i>{extra}</i></b></blockquote>

        <i>{tail}</i>
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'photos_expired': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b><u>24 часа</u> вышли</b>

        <blockquote><b><i>Три фото нужно успеть за сутки с первого кадра.</i></b></blockquote>

        <i>Нажмите «Сдать ещё группу» и сдайте фото заново.</i>
        """,
        buttons=[
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'after_proofs_owner': msg(
        emoji="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
        text="""
        <b>Доказательства приняты</b>

        {progress}

        <b>Ещё не финал. Слот уже ваш - пока заявку смотрят.</b>

        <blockquote><b><i>Если примут
Новым пользователям проект выдаёт подарочные куты.
Играть только у вас, в этой группе.
Вам игроки и баланс группы, не 35% на карман.</i></b></blockquote>

        <blockquote><b><i>Ждём проверку. Ответ придёт сюда.</i></b></blockquote>

        <i>Ничего нажимать не нужно. Статус - в «Мои группы».</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'after_proofs_reco': msg(
        emoji="""<tg-emoji emoji-id='5474515587797360318'>💋</tg-emoji>""",
        text="""
        <b>Доказательства приняты</b>

        {progress}

        <b>Ещё не финал. 14 дней заработка уже рядом.</b>

        <blockquote><b><i>Если примут
Новым пользователям проект выдаёт подарочные куты.
14 дней вам капает доля с их игр.
Только те, кого Кут ещё не знал.
Куты приходят вам на баланс сами.</i></b></blockquote>

        <blockquote><b><i>Ждём проверку. Ответ придёт сюда.</i></b></blockquote>

        <i>Ничего нажимать не нужно. Статус - в «Мои группы».</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'after_photos_reco': msg(
        emoji="""<tg-emoji emoji-id='5388670457249552219'>👯‍♀️</tg-emoji>""",
        text="""
        <b>Последний шаг. Без него 35% не откроются.</b>

        {progress}

        <b>Откройте «{name}» и напишите <code>подтверждение</code>.</b>

        <b>Создатель должен подтвердить рекомендацию за <u>24 часа</u>. Потом окно закроется.</b>

        <blockquote><b><i>Он нажмёт <u>Да</u>. Новым пользователям проект выдаёт подарочные куты.</i></b></blockquote>

        <i>Нажмите «Открыть группу», если есть кнопка.</i>
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
                text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'wrote_confirm': msg(
        emoji="""<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
        text="""
        <b>Ждём подтверждение. Пока окно открыто - заработок ещё может стать вашим.</b>

        {progress}

        <blockquote><b><i>Создатель должен подтвердить, что вы порекомендовали добавить бота. Без этого доля вам не пойдёт. Новым пользователям проект выдаёт подарочные куты.</i></b></blockquote>

        <i>Если не подтвердил - напишите «подтверждение» ещё раз.</i>
        """,
        buttons=[ b(
            text="Открыть группу" , icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""" , go='open_group' ,
            when='has_username' , ) , b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'earnings': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Заработки</b>

        <blockquote><b><i>Всего вам пришло: <u>{total}</u>
Сегодня: <u>{today}</u></i></b></blockquote>

        <blockquote><b><i>{barnum}</i></b></blockquote>

        <i>{next}</i>
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
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
        extra_by={
            'empty': """Пока тихо. Новым пользователям проект выдаёт подарочные куты. Сдайте группу - здесь появятся цифры.""",
            'live_paid': """Это уже ваши цифры. Новым пользователям проект выдаёт подарочные куты.""",
            'live': """Новым пользователям проект выдаёт подарочные куты. Вам капает, когда они играют.""",
            'today': """Сегодня уже есть движение. Новым пользователям проект выдаёт подарочные куты.""",
            'pending': """Свою часть вы сделали. Ждём проверку.""",
        },
        next_empty="""Нажмите «Сдать ещё группу» и выберите, кто вы.""",
        next="""Нажмите группу - откроется карточка.""",
    ),

    'mine': msg(
        emoji="""<tg-emoji emoji-id='5452064260437859029'>🌐</tg-emoji>""",
        text="""
        <b>Мои группы</b>

        <blockquote><b><i>Всего вам пришло: <u>{total}</u>
Сегодня: <u>{today}</u></i></b></blockquote>

        <blockquote><b><i>{barnum}</i></b></blockquote>

        <i>{next}</i>
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
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
        extra_by={
            'empty': """Пока тихо. Новым пользователям проект выдаёт подарочные куты. Сдайте группу - здесь появятся цифры.""",
            'live_paid': """Это уже ваши цифры. Новым пользователям проект выдаёт подарочные куты.""",
            'live': """Новым пользователям проект выдаёт подарочные куты. Вам капает, когда они играют.""",
            'today': """Сегодня уже есть движение. Новым пользователям проект выдаёт подарочные куты.""",
            'pending': """Свою часть вы сделали. Ждём проверку.""",
        },
        next_empty="""Нажмите «Сдать ещё группу» и выберите, кто вы.""",
        next="""Нажмите группу - откроется карточка.""",
    ),

    'card': msg(
        emoji="""<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>""",
        text="""
        <b>«{name}»</b>

        <blockquote><b><i>{facts}</i></b></blockquote>

        <blockquote><b><i>{extra}</i></b></blockquote>

        <i>{next}</i>
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
                text="Снять заявку",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='photos',
            ),
            b(
                text="Снять заявку",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='wait_confirm',
            ),
            b(
                text="Снять заявку",
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
            'photos': """Нужны три кадра - иначе заявка не уйдёт.""",
            'wait_confirm': """Подтвердить рекомендацию может только владелец группы.""",
            'pending': """Решение придёт в этот чат.""",
            'live': """Новым пользователям проект выдаёт подарочные куты. Пока Кут админ и группа открытая - цифры обновляются сами.""",
            'ended': """Новые куты с этой группы больше не капают.""",
            'rejected': """{reason}""",
            'burned': """Вернуть Кут в админы - уже новая заявка.""",
        },
        next_by={
            'pause': """{hint}""",
            'photos': """Нажмите «Продолжить фото» и пришлите кадр сюда.""",
            'wait_confirm': """Откройте группу, напишите «подтверждение» и дождитесь ответа владельца.""",
            'pending': """Ждите. «Назад» - к списку.""",
            'live': """Ничего нажимать не нужно.""",
            'ended': """Срок вышел. Новую группу сдайте с главного меню.""",
            'rejected': """«Назад» - к списку.""",
            'burned': """Кут убрали. «Назад» - к списку.""",
            'default': """«Назад» - к списку.""",
        },
        facts_owner="""
        <b>{status}</b>
        <b>Баланс группы: <u>{balance}</u></b>
        <b>Подарков новым: <u>{gifts}</u></b>
        <b>Новых людей: <u>{newcomers}</u></b>
        """,
        facts_reco="""
        <b>{status}</b>
        <b>Вам уже пришло: <u>{paid}</u></b>
        <b>Сегодня: <u>{today}</u></b>
        <b>Осталось дней: <u>{days}</u></b>
        <b>Новых людей: <u>{newcomers}</u></b>
        """,
    ),

    'cancelled': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Заявку сняли</b>

        <blockquote><b><i>Эту группу можно сдать снова, если слот свободен.</i></b></blockquote>

        <i>Нажмите «Сдать ещё группу», если хотите заново.</i>
        """,
        buttons=[
            b(
                text="Сдать ещё группу",
                icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
                color='success',
                go='more',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
        ],
    ),

    'confirm': msg(
        emoji="""<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji>""",
        text="""
        <b>{who} порекомендовал добавить нашего бота в эту группу?</b>

        <b>Если да - нажмите <u>Да</u>.</b>

        <blockquote><b><i>Так вы подтвердите его рекомендацию. Новым пользователям проект выдаёт подарочные куты. Тогда задание будет выполнено.</i></b></blockquote>
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

        <blockquote><b><i>Решение придёт тому, кто привёл Кут, в личку.</i></b></blockquote>
        """,
    ),

    'confirm_no_first': msg(
        emoji="""<tg-emoji emoji-id='5391050667995460499'>🤨</tg-emoji>""",
        text="""
        <b>Создатель не подтвердил рекомендацию</b>

        <b>Остался <u>один шанс</u> за <u>24 часа</u>.</b>

        <blockquote><b><i>Второй отказ закроет группу на месяц.</i></b></blockquote>

        <i>Напишите <code>подтверждение</code> ещё раз.</i>
        """,
        buttons=[ b(
            text="Открыть группу" , icon="""<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji>""" , go='open_group' ,
            when='has_username' , ) , b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' ,
            when='wait_confirm' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'confirm_no_second': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Снова отказ от владельца</b>

        <b>Эту группу нельзя сдавать <u>31 день</u>.</b>

        <blockquote><b><i>После двух отказов слот закрывается на месяц.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'not_your_claim': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Это не ваша заявка</b>

        <blockquote><b><i>Подтверждение и снятие - только тому, кто сдавал группу.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'not_creator': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Подтверждает только создатель</b>

        <blockquote><b><i>Рекомендацию подтверждает владелец группы - больше никто.</i></b></blockquote>
        """,
    ),

    'confirm_expired': msg(
        emoji="""<tg-emoji emoji-id='5447589583120257784'>😁</tg-emoji>""",
        text="""
        <b>Это подтверждение уже не действует</b>

        <blockquote><b><i>Кнопки Да / Нет живут <u>24 часа</u>.</i></b></blockquote>

        <i>Напишите в группе «подтверждение» снова.</i>
        """,
    ),

    'wrong_group': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Не та группа</b>

        <blockquote><b><i>«Подтверждение» работает только в сданном чате.</i></b></blockquote>

        <i>Напишите его в той группе, куда добавляли Кут.</i>
        """,
    ),

    'need_photos_first': msg(
        emoji="""<tg-emoji emoji-id='5388625626380916939'>📖</tg-emoji>""",
        text="""
        <b>Сначала отправьте <u>3 фото</u> сюда</b>

        {progress}

        <blockquote><b><i>Подтверждение откроется только после трёх кадров.</i></b></blockquote>

        <i>Пришлите их сюда, по одному кадру.</i>
        """,
        buttons=[ b(
            text="Другое фото" , icon="""<tg-emoji emoji-id='5231137194340540199'>🤙</tg-emoji>""" , go='undo' ,
            when='have_photos' , ) , b(
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'accepted': msg(
        emoji="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
        text="""
        <b>Группу приняли. Куты уже могут капать.</b>

        <b><u>{days} дней</u> вам капает доля с игр новых людей. Сами.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты.
До 35% с их игр - на ваш баланс.
Только те, кого Кут ещё не знал.
Ничего нажимать не нужно - куты капают сами.</i></b></blockquote>

        <i>Статус - в «Мои группы».</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'accepted_owner': msg(
        emoji="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""",
        text="""
        <b>Группу приняли. Куты уже могут капать.</b>

        <b><u>{days} дней</u> новые люди играют у вас на подарок проекта.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты.
Играть только у вас, в одиночных играх.
Снять или перевести нельзя. Это подарок новичкам, не ваши деньги.
Ничего нажимать не нужно - куты капают сами.</i></b></blockquote>

        <i>Статус и баланс группы - в «Мои группы».</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'digest': msg(
        emoji="""<tg-emoji emoji-id='5444884960609590878'>🧐</tg-emoji>""",
        text="""
        <b>Сегодня с «{name}»: <u>{newcomers}</u> новых · вам <u>{paid}</u>.</b>

        <b>Осталось <u>{days}</u> дн.</b>

        <blockquote><b><i>{note}</i></b></blockquote>
        """,
        extra_by={
            'paid': """Это уже на вашем балансе. Новым пользователям проект выдаёт подарочные куты.""",
            'empty': """Новым пользователям проект выдаёт подарочные куты. Как появятся их игры - цифра вырастет.""",
        },
    ),

    'gift': msg(
        emoji="""<tg-emoji emoji-id='5355193051193059834'>🎁</tg-emoji>""",
        text="""
        <b>{who}, вам <u>{amount} кут</u> в подарок - чтобы научится играть в Кут.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Играть ими можно только в этой группе, в одиночных играх.</i></b></blockquote>

        <i>Если что-то непонятно - напишите «хелп».</i>
        """,
    ),

    'gift_locked': msg(
        emoji="""<tg-emoji emoji-id='5271929616896921139'>🪨</tg-emoji>""",
        text="""
        <b>Подарочные куты - только в <u>одиночной игре</u> этой группы.</b>

        <blockquote><b><i>Новым пользователям проект выдаёт подарочные куты. Снять или перевести нельзя - ими учатся играть в этой группе.</i></b></blockquote>
        """,
    ),

    'term_end': msg(
        emoji="""<tg-emoji emoji-id='5445110875889360215'>🤐</tg-emoji>""",
        text="""
        <b>Срок по этой группе закончился</b>

        <b>Новые куты с неё больше не капают.</b>

        <blockquote><b><i>Уже начисленные куты остаются у вас.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'kicked': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Кут убрали из группы</b>

        <b>Начисления остановились.</b>

        <blockquote><b><i>Если бота выгнали - заявка сгорает.</i></b></blockquote>
        """,
    ),

    'rejected': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Не приняли</b>

        <b>{reason}</b>

        <blockquote><b><i>Эту заявку уже не поправить.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'rejected_fix': msg(
        emoji="""<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji>""",
        text="""
        <b>Не приняли</b>

        <b>{reason}</b>

        <blockquote><b><i>Есть <u>48 часов</u>, чтобы исправить и сдать снова.</i></b></blockquote>

        <i>Нажмите «Сдать ещё группу».</i>
        """,
        buttons=[ b(
            text="Сдать ещё группу" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" ,
            color='success' , go='more' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'two_pending': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Максимум <u>2 заявки</u> на проверке</b>

        <blockquote><b><i>Одновременно смотрим не больше двух.</i></b></blockquote>

        <i>Нажмите «Мои группы»: ждите или снимите одну.</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'two_live': msg(
        emoji="""<tg-emoji emoji-id='5231463873848039753'>😳</tg-emoji>""",
        text="""
        <b>Максимум <u>2 живых</u> группы</b>

        <blockquote><b><i>Живых групп на человеке не больше двух.</i></b></blockquote>

        <i>Нажмите «Мои группы» - там видно, что уже идёт.</i>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'banned_31': msg(
        emoji="""<tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji>""",
        text="""
        <b>Эту группу нельзя сдавать</b>

        <blockquote><b><i>После отказа создателя слот закрыт на <u>31 день</u>.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'freeze_admin': msg(
        emoji="""<tg-emoji emoji-id='5449913031578379785'>🛡</tg-emoji>""",
        text="""
        <b>Пауза: Куту нужна админка</b>

        <blockquote><b><i>Пока Кут не администратор - начисления стоят.</i></b></blockquote>

        <i>Верните Кут в администраторы. Потом зарплата снова начнёт капать.</i>
        """,
    ),

    'freeze_public': msg(
        emoji="""<tg-emoji emoji-id='5447589583120257784'>😁</tg-emoji>""",
        text="""
        <b>Пауза: группа стала закрытой</b>

        <blockquote><b><i>Начисления идут только пока группа <u>публичная</u>.</i></b></blockquote>

        <i>Сделайте группу публичной - зарплата снова начнёт капать.</i>
        """,
    ),

    'group_busy': msg(
        emoji="""<tg-emoji emoji-id='5393451614843467174'>🔮</tg-emoji>""",
        text="""
        <b>Эту группу уже сдают</b>

        <blockquote><b><i>Одна группа - один человек. Первый, кто сдал доказательства, держит слот.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'group_busy_owner': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Эту группу уже сдаёт создатель</b>

        <blockquote><b><i>Одна группа - один человек. Первый, кто сдал доказательства, держит слот.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'confirm_timeout': msg(
        emoji="""<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji>""",
        text="""
        <b>Рекомендацию не подтвердили за <u>24 часа</u></b>

        <blockquote><b><i>Без подтверждения, что бота порекомендовали в группу, заявка не идёт на проверку.</i></b></blockquote>

        <i>Нажмите «Сдать ещё группу», если хотите заново.</i>
        """,
        buttons=[ b(
            text="Сдать ещё группу" , icon="""<tg-emoji emoji-id='5461055585493470291'>🔥</tg-emoji>""" ,
            color='success' , go='more' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
        ],
    ),

    'owner_no_confirm': msg(
        emoji="""<tg-emoji emoji-id='5442949339108366200'>🌟</tg-emoji>""",
        text="""
        <b>Вам подтверждение не нужно</b>

        <blockquote><b><i>Создателю не нужно подтверждать рекомендацию в своей группе.</i></b></blockquote>
        """,
        buttons=[ b(
            text="Мои группы" , icon="""<tg-emoji emoji-id='5458561205926908268'>👁</tg-emoji>""" , go='groups' ,
            when='mine' , ) , b(
            text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
            color='primary' , go='back_hub' , ) ,
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
            text="Снять заявку" , icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""" , go='cancel' ,
            when='photos' , ) ,
            b(
                text="Снять заявку",
                icon="""<tg-emoji emoji-id='5388711744770171046'>👋</tg-emoji>""",
                go='cancel',
                when='wait_confirm',
            ),
            b(
                text="Мои группы",
                icon="""<tg-emoji emoji-id='5192951739623447936'>👥</tg-emoji>""",
                go='groups',
            ), b(
                text="Назад, в главное меню" , icon="""<tg-emoji emoji-id='5375364347918827433'>👋</tg-emoji>""" ,
                color='primary' , go='back_hub' , ) ,
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
    "toast_check", "history_gift", "history_payout", "progress",
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
            errors.append(f"{name}: пустой text - вставь сообщение")
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
                    errors.append(f"{name}: у «{text}» нет прем-эмодзи - вставь icon=...")
                else:
                    found.append((text, eid, when))
                gos.append(go)
            if len(gos) != len(set(gos)):
                errors.append(f"{name}: в одном ряду два одинаковых go {gos}")
        for i, (text_a, id_a, when_a) in enumerate(found):
            for text_b, id_b, when_b in found[i + 1:]:
                if id_a == id_b and _shows_together(when_a, when_b):
                    errors.append(f"{name}: одинаковый эмодзи у кнопок «{text_a}» и «{text_b}» - смени icon")
    return errors


def assert_design() -> None:
    bad = design_errors()
    if bad:
        raise RuntimeError("Дизайн пиара - повтор эмодзи на кнопках:\n- " + "\n- ".join(bad))


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
TASKS_MENU_TEXT = plain(TASKS_MENU["text"])

assert_design()
