# -*- coding: utf-8 -*-
"""Водные игры — все слова, кнопки и числа.

Как править
-----------
Сообщение целиком — в text= тройными кавычками.
Кнопка — b(text="Слово", go="splash", data="wg:splash").
Премиум-эмодзи на кнопке — emoji="5354820836442287981":
это icon_custom_emoji_id, подпись остаётся в text.
Ряд из двух кнопок — один список [кнопка, кнопка]. Новая строка — свой ряд.
data= не переписывают: по нему бот понимает нажатие.
Слово на кнопке и то же слово в тексте пиши одинаково.

Числа выстрела, потолков и сроков — в блоке «Правила» ниже.
Цены предметов в магазине создатель меняет во вкладке «Водные игры».
Стартовые цены здесь — только для первой записи в dex.

Чат показывает этот файл. После правки нужен перезапуск бота.
Все фразы, которые видит игрок — экраны ниже и словарь WORDS.
Кнопки «Увеличить», «Назад» и «Улучшить за N кут» — константы над экранами.
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime, timedelta, timezone


def t(text) -> str:
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join(line for line in (t(item) for item in text) if line)
    return textwrap.dedent(str(text)).strip("\n")


def public_group_name(raw: str) -> str:
    """Публичный адрес группы. Пустая строка — ссылку ставить нельзя."""
    text = str(raw or "").strip()
    text = text.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@")
    text = text.split("/")[0].split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{4,}", text):
        return ""
    return text


def emoji_id(value) -> str:
    """Цифровой id премиум-эмодзи. Пустая строка — обычная кнопка."""
    raw = str(value or "").strip()
    if raw.isdigit() and 5 <= len(raw) <= 32:
        return raw
    return ""


# В callback уже сидит хозяин: защита, продление, сложение срока.
_EMBEDDED_OWNER = {"more", "worn", "pick", "join"}
# Хозяин дописывается последним куском: выстрел, поиск, полотенце, навигация.
_SUFFIX_OWNER = {"leave", "pour", "towel", "find"}


def button_owner(data: str):
    """Чей это callback. None — кнопка без хозяина, её нажимать нельзя."""
    parts = str(data or "").split(":")
    if len(parts) < 3 or parts[0] != "wg":
        return None
    kind = parts[1]
    if kind in _EMBEDDED_OWNER:
        return int(parts[2]) if parts[2].isdigit() else None
    if kind in _SUFFIX_OWNER:
        if len(parts) >= 4 and parts[-1].isdigit():
            return int(parts[-1])
        return None
    if parts[-1].isdigit():
        return int(parts[-1])
    return None


def stamp_callback(data: str, user_id: int) -> str:
    """Помечает кнопку человеком, который её открыл. Чужой клик дальше не идёт."""
    if button_owner(data) is not None:
        return str(data)
    return f"{data}:{int(user_id)}"


def strip_callback_owner(data: str) -> str:
    """Снимает хвост с id, чтобы разбор кнопки остался прежним."""
    parts = str(data or "").split(":")
    if len(parts) < 3 or parts[0] != "wg" or parts[1] in _EMBEDDED_OWNER:
        return str(data or "")
    if button_owner(data) is None:
        return str(data or "")
    return ":".join(parts[:-1])


def b(*, text: str, go: str, data: str = "", color: str = "default", emoji: str = "") -> dict:
    button = {
        "text": t(text),
        "go": go,
        "data": data or ("wg:" + go),
        "style": color or "default",
    }
    icon = emoji_id(emoji)
    if icon:
        button["emoji"] = icon
    return button


def msg(*, text: str, buttons=None) -> dict:
    return {"text": t(text), "buttons": list(buttons or [])}


def iter_button_rows(buttons) -> list:
    out = []
    for row in buttons or []:
        if isinstance(row, dict):
            out.append([row])
        else:
            out.append(list(row))
    return out


SCREENS: dict = {}


def screen(name: str, text: str, buttons=None) -> dict:
    body = msg(text=text, buttons=buttons)
    SCREENS[name] = body
    return body


def button_rows(screen_name: str, **slots) -> list:
    out = []
    for row in iter_button_rows(SCREENS[screen_name]["buttons"]):
        built = []
        for button in row:
            text = str(button.get("text") or "")
            data = str(button.get("data") or "")
            if slots:
                text = text.format(**slots)
                data = data.format(**slots)
            built.append({
                "text": text,
                "data": data,
                "style": button.get("style") or "default",
                "emoji": emoji_id(button.get("emoji")),
            })
        if built:
            out.append(built)
    return out


def screen_text(screen_name: str, **slots) -> str:
    text = SCREENS[screen_name]["text"]
    return text.format(**slots) if slots else text


# ---------------------------------------------------------------------------
# Правила. Меняются здесь, не в десяти файлах.
# ---------------------------------------------------------------------------

# Ниже этого баланса выстрел не забирает кут и пишет шутку.
POOR_BALANCE = 50

# Сколько процентов баланса забирает один выстрел.
PERCENT_LOW = 4
PERCENT_HIGH = 8

# Потолок одного выстрела и потолок с одного человека за сутки.
# Максимальная ставка трейда в проекте — 1000 кут, поэтому один выстрел
# может быть больнее одной игры, но не может снять состояние за вечер.
SHOT_CAP = 1500
DAY_CAP = 4000

# Один стрелок по одной цели.
PAIR_GAP_SEC = 6 * 3600
PAIR_DAY_MAX = 2

# Полотенце: доля украденного, которую проект один раз отдаёт облитому.
TOWEL_PERCENT = 20
TOWEL_CAP = 400
TOWEL_HOURS = 3

# Сайт свежих анекдотов. Если он молчит, остаётся шутка из DRY_JOKES.
JOKE_SITE = "https://rzhunemogu.ru/RandJSON.aspx?CType=11"

# Цены по живому топу: второе место около 350 кут, третье 165, дальше около 60.
# Покупка без лимита склада. Повторное надевание, пока срок идёт, само
# предмет не тратит: сроки складываются отдельной платой EXTEND_FEE.
# Стрелять можно только под зонтиком. Дождевик, навес и сейф закрывают выстрел.
PRICES = {
    # Пистолетик уже стоит 100 в dex: это разовая покупка, предмет не тратится.
    # Патрон — уже существующая «Вода» (watercraft). Её цену и полку код не переписывает.
    "pistoletik": 100,
    "dryumbrella": 60,
    "drycoat": 180,
    "dryawning": 300,
    "drysafe": 10000,
}

EXTEND_FEE = 100
OLD_PRICES = {
    "dryumbrella": 8000,
    "drycoat": 28000,
    "dryawning": 90000,
    "drysafe": 750000,
}
BTN_EXTEND = "Увеличить"
BTN_BACK = "Назад"

# Короткие фразы: тосты, кнопки без экрана, строки истории кут.
# В Telegram-тосте теги не рисуются, поэтому здесь их нет.
WORDS = {
    "not_yours": "Это не ваша защита.",
    "not_your_button": "Это не ваша кнопка.",
    "button_old": "Кнопка устарела. Напишите «водные игры».",
    "no_such_item": "Такого предмета нет",
    "need_fee": "Нужно {fee} кут",
    "item_gone": "Предмета уже нет",
    "nothing_to_stack": "Складывать нечего",
    "worn_no_fee": "Защита надета без доплаты",
    "stack_failed": "Не удалось сложить срок",
    "stacked": "Срок увеличился",
    "looking": "Смотрю магазин и биржу",
    "open_buy": "Открыть покупку",
    "open_unlot": "Снять лот",
    "towel": "Полотенце",
    "towel_btn": "Полотенце +{amount}",
    "towel_lost": "Полотенце уже забрали.",
    "towel_not_yours": "Это полотенце для того, кого облили.",
    "towel_dry": "Время вышло. Полотенце больше не вернёт кут.",
    "towel_got": "+{amount} кут уже на балансе.",
    "shield_name": "защита",
    "where_market": "на бирже",
    "where_shop": "в магазине",
    "place_market": "биржа",
    "place_shop": "магазин",
    "leave": "Уйти",
    "pour": "Облить",
    "offer_gone": "Это уже решено",
    "missing_pistol": "Нужен Пистолетик.",
    "missing_water": "Нужна Вода: один выстрел списывает одну.",
    "water_held": "Вода не стреляет. Откройте Пистолетик.",
    "history_shot": "водные игры",
    "history_towel": "полотенце водных игр",
    "history_stack": "сложение защиты водных игр",
}


def word(name: str, **slots) -> str:
    text = WORDS[name]
    return text.format(**slots) if slots else text

SHIELDS = {
    "dryumbrella": {"hours": 3, "name": "Зонтик", "emoji": "☂️", "line": "Под зонтиком"},
    "drycoat": {"hours": 12, "name": "Дождевик", "emoji": "🧥", "line": "В дождевике"},
    "dryawning": {"hours": 72, "name": "Навес", "emoji": "🛖", "line": "Под навесом"},
    "drysafe": {"hours": None, "name": "Сухой сейф", "emoji": "💎", "line": "Сухой сейф"},
}

# Премиум-значок защиты. У навеса его нет: в тексте и в профиле остаётся 🛖.
SHIELD_PREMIUM = {
    "dryumbrella": "5224681716760715555",
    "drycoat": "5388820858414313315",
    "drysafe": "5471952986970267163",
}
SHOOT_EMOJI = "5317000922096769303"


def shield_mark(kind: str) -> str:
    """Значок защиты: премиум-эмодзи в тексте, у навеса обычный символ."""
    spec = SHIELDS.get(str(kind or "")) or {}
    plain = spec.get("emoji") or "💧"
    icon = SHIELD_PREMIUM.get(str(kind or ""))
    if not icon:
        return plain
    return f"<tg-emoji emoji-id='{icon}'>{plain}</tg-emoji>"

ITEMS = (
    {
        "name1": "pistoletik",
        "name": "Пистолетик",
        "emoji": "🔫",
        "match": ("пистолетик",),
        "price": PRICES["pistoletik"],
        "bio": "В группе ответьте на человека и напишите «Использовать 🔫». Один выстрел тратит одну Воду.",
    },
    {
        "name1": "watercraft",
        "name": "Вода",
        "emoji": "💧",
        "match": ("вода",),
    },
    {
        "name1": "dryumbrella",
        "name": "Зонтик",
        "emoji": "☂️",
        "match": ("зонтик",),
        "hours": 3,
        "price": PRICES["dryumbrella"],
        "bio": "3 часа вас не обливают. Под ним можно стрелять.",
    },
    {
        "name1": "drycoat",
        "name": "Дождевик",
        "emoji": "🧥",
        "match": ("дождевик",),
        "hours": 12,
        "price": PRICES["drycoat"],
        "bio": "12 часов вас не обливают. Пока надет, стрелять нельзя.",
    },
    {
        "name1": "dryawning",
        "name": "Навес",
        "emoji": "🛖",
        "match": ("навес",),
        "hours": 72,
        "price": PRICES["dryawning"],
        "bio": "3 дня вас не обливают. Пока надет, стрелять нельзя.",
    },
    {
        "name1": "drysafe",
        "name": "Сухой сейф",
        "emoji": "💎",
        "match": ("сухой сейф",),
        "hours": None,
        "price": PRICES["drysafe"],
        "bio": "Вас не обливают, пока сейф надет. Стрелять нельзя.",
    },
)


def item_by_key(name1: str) -> dict | None:
    key = str(name1 or "").strip()
    for item in ITEMS:
        if item["name1"] == key:
            return item
    return None


# ---------------------------------------------------------------------------
# Экраны
# ---------------------------------------------------------------------------

screen(
    "home",
    """
    <b><tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> Водные игры</b>
    <i>Обливаете человека и забираете часть его кут.</i>
    """,
    [
        [b(text="Выстрелить", go="aim", data="wg:aim", color="success", emoji=SHOOT_EMOJI)],
        [b(text="Защититься", go="shield", data="wg:shield", color="primary", emoji="5895483165182529286")],
        [b(text="Как это работает?", go="rules", data="wg:rules", color="default")],
    ],
)

screen(
    "rules",
    """
    <b>Как облить</b>
    Напишите «<code>Использовать 🔫</code>» в ответ на сообщение другого пользователя и вы получите от <u>{low}%</u> до <u>{high}%</u> от баланса того пользователя, которого вы облили водой.
    Не больше <code>{cap}</code> за раз и <code>{day}</code> за сутки.
    """,
    [
        [b(text="Выстрелить", go="aim", data="wg:aim", color="success", emoji=SHOOT_EMOJI)],
        [b(text="Защититься", go="shield", data="wg:shield", color="primary", emoji="5895483165182529286")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "splash_ready",
    """
    <b>Можно стрелять</b>
    <i>Нажмите «Выстрелить».</i>
    """,
    [
        [b(text="Выстрелить", go="aim", data="wg:aim", color="success", emoji=SHOOT_EMOJI)],
        [b(text="Защититься", go="shield", data="wg:shield", color="primary", emoji="5895483165182529286")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "aim",
    """
    <b>Дальше только Пистолетик</b>
    <i>В группе ответьте на сообщение человека и напишите «<code>Использовать 🔫</code>».</i>
    """,
    [
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "splash_need",
    """
    <b>Выстрел ещё не открыт</b>
    <i>{missing} Кнопка ниже откроет покупку.</i>
    """,
    [
        [b(text="🔫 Найти пистолетик", go="find-pistol", data="wg:find:pistoletik", color="success")],
        [b(text="💧 Найти воду", go="find-water", data="wg:find:watercraft", color="success")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "shield",
    f"""
    <b>Защита</b>
    <i>Наденьте предмет. Пока он на вас, вас не обливают.</i>

    {shield_mark("dryumbrella")} Зонтик — 3 часа. Под ним можно стрелять.
    {shield_mark("drycoat")} Дождевик — 12 часов. Стрелять нельзя.
    {shield_mark("dryawning")} Навес — 3 дня. Стрелять нельзя.
    {shield_mark("drysafe")} Сухой сейф — навсегда. Стрелять нельзя.
    """,
    [
        [b(text="Найти зонтик", go="find-umbrella", data="wg:find:dryumbrella", color="primary", emoji=SHIELD_PREMIUM["dryumbrella"])],
        [b(text="Найти дождевик", go="find-coat", data="wg:find:drycoat", color="primary", emoji=SHIELD_PREMIUM["drycoat"])],
        [b(text="🛖 Найти навес", go="find-awning", data="wg:find:dryawning", color="primary")],
        [b(text="Найти сухой сейф", go="find-safe", data="wg:find:drysafe", color="primary", emoji=SHIELD_PREMIUM["drysafe"])],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "found",
    """
    <b>{emoji} {name} есть {where}</b>
    <i>Кнопка откроет {place}.</i>
    """,
    [],
)

screen(
    "own_lot",
    """
    <b>{emoji} {name} уже на вашей бирже</b>
    <i>Снимите лот — предмет вернётся, и можно идти дальше.</i>
    """,
)

screen(
    "miss",
    """
    <b>{emoji} {name} сейчас не купить</b>
    <i>Нет ни в магазине, ни на бирже.</i>
    """,
    [
        [b(text="Проверить ещё раз", go="find", data="wg:find:{key}", color="primary")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

# Выстрел. {amount} {hours} {left} {emoji} {name} {title} подставляются сами.
screen(
    "shot_reply",
    """
    <b>Выстрел не пошёл</b>
    <i>Ответьте на человека и снова откройте Пистолетик.</i>
    """,
)

screen(
    "shot_self",
    """
    <b>Себя облить нельзя</b>
    <i>Ответьте на другого человека.</i>
    """,
)

screen(
    "shot_private",
    """
    <b>В личке выстрела нет</b>
    <i>Пистолетик и вода уже есть. Зайдите в группу по кнопке и откройте Пистолетик, ответив на человека.</i>
    """,
)

screen(
    "shot_locked",
    """
    <b>{emoji} {name} не даёт стрелять</b>
    <i>Снимите защиту или дождитесь конца срока. Вода не списана.</i>
    """,
)

screen(
    "shot_pair_day",
    """
    <b>Сегодня по этому пользователю уже два попадания</b>
    <i>Следующий раз — завтра. Вода не списана.</i>
    """,
)

screen(
    "shot_pair_wait",
    """
    <b>По нему ещё рано</b>
    <i>Следующий выстрел через {left}. Вода не списана.</i>
    """,
)

screen(
    "shot_bounce",
    """
    <b>Куты не перешли</b>
    <i>{title}: его не облить. Вода списана.</i>
    """,
)

screen(
    "shot_unknown",
    """
    <b>Этого человека нет в игре</b>
    <i>Он ещё не писал боту. Вода не списана.</i>
    """,
)

screen(
    "shot_day",
    """
    <b>С этого пользователя за сутки уже взяли максимальное количество кут</b>
    <i>До завтра куты не переходят. Вода при вас.</i>
    """,
)

screen(
    "shot_dry",
    """
    <b>С него сейчас нечего взять</b>
    <i>Куты не спишутся. Вода не списана.</i>
    """,
)

screen(
    "shot_broke",
    """
    <b>С него брать нечего</b>
    <i>Вода потрачена. Обливайте того, у кого кут больше. Напишите <code>топ</code>.</i>
    """,
)

screen(
    "shot_ask",
    """
    <b>При облитии вы заберете у пользователя {amount} кут</b>
    """,
)

screen(
    "shot_fee",
    """
    <i>Вам {payout}. Группе «{group}» — {fee}.</i>
    """,
)

screen(
    "shot_pistol_day",
    """
    <b>Пистолетик на сегодня закончился</b>
    <i>{used} из {limit}. Завтра снова можно.</i>
    """,
)

screen(
    "shot_guard",
    """
    <b>{mark} {name}</b>
    <i>Под защитой {span}. Облитие спишет воду, куты не будут заработаны</i>
    """,
)

screen(
    "shot_ask_broke",
    """
    <b>С него брать нечего</b>
    <i>Напишите <code>топ</code> для поиска более богатого пользователя </i>
    """,
)

screen(
    "shot_cancel",
    """
    <b>Выстрел отменён</b>
    <i>Вода при вас.</i>
    """,
)

screen(
    "shot_hit",
    """
    <b>Вы забрали {amount} кут</b>
    <i>Полотенце вернёт ему {towel} кут. Кнопка действует {hours}. Нажимает только он.</i>
    """,
)

screen(
    "shot_gift",
    """
    <b>Подарочные кут</b>
    <i>Их нельзя забрать. Вода при вас.</i>
    """,
)

screen(
    "towel_taken",
    """
    <b>Полотенце вернуло {amount} кут</b>
    <i>Они уже на балансе.</i>
    """,
)

screen(
    "shield_ended",
    """
    <b>Защита уже снялась</b>
    <i>Наденьте предмет снова. Доплаты не будет.</i>
    """,
)

screen(
    "wearing",
    """
    <b>{emoji} {name} уже надет</b>
    <i>Ещё {left}. «Увеличить» продлит за <u>{fee}</u> кут и один предмет.</i>
    """,
)

screen(
    "forever_worn",
    """
    <b>{emoji} {name} уже навсегда</b>
    <i>Продлевать некуда. Предмет остался у вас.</i>
    """,
)

screen(
    "hunt_open",
    """
    Стрелять можно.
    """,
)

screen(
    "hunt_closed",
    """
    Стрелять нельзя.
    """,
)

screen(
    "worn",
    """
    <b>{emoji} {name} на вас</b>
    <i>{term} вас не обливают. {hunt}</i>
    """,
)

screen(
    "extend_list",
    """
    <b>Чем продлить {name}</b>
    <i>{emoji} ещё {left}. Кут спишутся на следующем шаге.</i>
    """,
)

screen(
    "extend_empty",
    """
    <b>Продлевать нечем</b>
    <i>{emoji} {name} ещё {left}. Купите защиту и нажмите «Увеличить».</i>
    """,
)

screen(
    "extend_pick",
    """
    <b>Срок станет {next_left}</b>
    <i>Сейчас {now_left}. Кнопка спишет <u>{fee}</u> кут и один {name}.</i>{hunt}
    """,
)

screen(
    "extend_pick_hunt",
    """
    <i>После этого стрелять нельзя.</i>
    """,
)

screen(
    "stacked_forever",
    """
    {name} теперь не снимается.
    """,
)

screen(
    "stacked_time",
    """
    {name} теперь держится ещё {left}.
    """,
)

screen(
    "stacked",
    """
    <b>{emoji} Срок стал длиннее</b>
    <i>{tail} Списано <u>{fee}</u> кут и один {spent}.</i>{hunt}
    """,
)

screen(
    "fresh_instead",
    """
    <b>{emoji} {name} надет</b>
    <i>{term}. Доплаты нет. {hunt}</i>
    """,
)

screen(
    "poor_fee",
    """
    <b>На продление не хватает кут</b>
    <i>Нужно <u>{fee}</u>, у вас {balance}. Ничего не списано.</i>
    """,
)

screen(
    "missing_item",
    """
    <b>{name} уже нет в инвентаре</b>
    <i>Продление отменено. Кут на месте.</i>
    """,
)

screen(
    "choice_label",
    """
    {emoji} {name}: {count} шт, {plus}
    """,
)

screen(
    "bought_water_left",
    """
    <b>Отлично</b>
    <i>{emoji} {name} у вас. Осталась Вода - и можно обливать.</i>
    """,
)

screen(
    "bought_pistol_left",
    """
    <b>Отлично</b>
    <i>{emoji} {name} у вас. Остался Пистолетик - и можно обливать.</i>
    """,
)

screen(
    "bought_ready",
    """
    <b>Отлично</b>
    <i>Можно обливать. В группе ответьте на человека и напишите «<code>Использовать 🔫</code>».</i>
    """,
)

screen(
    "bought_shield",
    """
    <b>Отлично</b>
    <i>{emoji} {name} у вас. Откройте его в инвентаре.</i>
    """,
)


def find_button_rows() -> list:
    """Кнопки «Найти …» с экрана «Защититься». Пустой инвентарь берёт те же слова."""
    return [
        row for row in button_rows("shield")
        if any(str(button.get("data") or "").startswith("wg:find:") for button in row)
    ]


# ---------------------------------------------------------------------------
# Фразы, по которым бот открывает водные игры
# ---------------------------------------------------------------------------

_ASK_EXACT = {
    "водные игры",
    "водная игра",
    "водные",
    "что такое водные игры",
    "что такое водная игра",
    "что такое водные",
    "как играть в водные игры",
    "как играть в водные",
    "водные игры это",
    "водный пистолет",
    "как облить",
    "как облить человека",
    "как пользоваться пистолетиком",
    "пистолетик как пользоваться",
    "правила водных игр",
}

_ASK_PARTS = (
    ("водн", "игр"),
    ("водн", "пистолет"),
    ("что такое", "водн"),
    ("как", "обли"),
    ("как", "пистолет"),
    ("водн", "защит"),
)


def is_water_ask(text: str) -> bool:
    """Любая короткая фраза про водные игры, не команда «облить водой»."""
    raw = " ".join(str(text or "").lower().replace("ё", "е").split())
    raw = re.sub(r"[^a-zа-я0-9 ]", " ", raw)
    raw = " ".join(raw.split())
    if not raw or len(raw) > 80:
        return False
    if raw.startswith("облить водой") or raw == "облить водой":
        return False
    if raw in _ASK_EXACT:
        return True
    if len(raw.split()) > 8:
        return False
    return any(all(part in raw for part in pair) for pair in _ASK_PARTS)


def take_amount(balance: int, percent: int, *, cap: int, day_left: int, poor: int | None = None) -> int:
    floor = POOR_BALANCE if poor is None else int(poor)
    if int(balance) < floor:
        return 0
    raw = int(int(balance) * int(percent) / 100)
    if raw < 1:
        raw = 1
    room = min(int(cap), int(day_left), int(balance))
    if room < 1:
        return 0
    return min(raw, room)


# Технические группы, куда можно отправить комиссию обливания.
# Те же id, что у касс Ники: игры, фон, дом игр, копилка.
FEE_GROUPS = (
    {"id": "-1004324787050", "name": "Игры"},
    {"id": "-1004318525471", "name": "Фон"},
    {"id": "-1003855337972", "name": "Дом игр"},
    {"id": "-1004238101266", "name": "Копилка"},
)


def fee_groups() -> list:
    return [dict(item) for item in FEE_GROUPS]


def normalize_fee_chat(raw) -> str:
    text = str(raw or "").strip()
    allowed = {item["id"] for item in FEE_GROUPS}
    if text in allowed:
        return text
    return FEE_GROUPS[0]["id"]


def fee_group_name(raw) -> str:
    chosen = normalize_fee_chat(raw)
    for item in FEE_GROUPS:
        if item["id"] == chosen:
            return item["name"]
    return FEE_GROUPS[0]["name"]


def pistol_is_blocked(used: int, *, on: bool, limit: int) -> bool:
    """Лимит выключен — пистолетик можно брать сколько угодно раз."""
    if not on:
        return False
    cap = max(1, int(limit or 0))
    return int(used or 0) >= cap


def default_rules() -> dict:
    """То, с чего начинается выстрел, пока создатель не задал свои числа."""
    return {
        "percentLow": PERCENT_LOW,
        "percentHigh": PERCENT_HIGH,
        "shotCap": SHOT_CAP,
        "dayCap": DAY_CAP,
        "poorBalance": POOR_BALANCE,
        "commissionPercent": 10,
        "feeChatId": FEE_GROUPS[0]["id"],
        "pistolDayOn": False,
        "pistolDayMax": 10,
    }


def split_take(amount: int, commission: int) -> tuple[int, int]:
    """Сколько из снятой суммы остаётся облившему и сколько забирает проект.

    Комиссия — доля уже снятых кут, не второе списание с жертвы.
    """
    gross = max(0, int(amount))
    rate = max(0, min(100, int(commission)))
    fee = gross * rate // 100
    return gross - fee, fee


def pour_bounds(balance: int, low: int, high: int, *, cap: int, day_left: int, poor: int) -> tuple[int, int]:
    """Сколько кут заберёт выстрел на этом балансе: от меньшего процента до большего."""
    left = int(low)
    right = int(high)
    if left > right:
        left, right = right, left
    small = take_amount(balance, left, cap=cap, day_left=day_left, poor=poor)
    large = take_amount(balance, right, cap=cap, day_left=day_left, poor=poor)
    return min(small, large), max(small, large)


def btn_join(fee: int = EXTEND_FEE) -> str:
    return f"Улучшить за {int(fee)} кут"


def stock_is_open(name1: str = "", name: str = "") -> bool:
    """Остаток задаёт создатель во вкладке. Безлимита нет: ноль — предмета нет в продаже."""
    del name1, name
    return False


def can_shoot(kind: str) -> bool:
    """Стрелять можно только под зонтиком. Без защиты тоже можно: её просто нет."""
    return str(kind or "") == "dryumbrella"


def kept_kind(current_kind: str, added: str) -> str:
    """Зонтик поверх другой защиты не возвращает право стрелять."""
    current = str(current_kind or "")
    added = str(added or "")
    if added == "dryumbrella" and current and current != "dryumbrella":
        return current
    return added


def shop_can_take(remain: int, wanted: int, *, name1: str = "", name: str = "") -> int:
    wanted = int(wanted or 0)
    remain = int(remain or 0)
    if wanted < 1 or remain < 1:
        return 0
    if stock_is_open(name1, name):
        return wanted
    return min(wanted, remain)


def _ru_count(number: int, one: str, few: str, many: str) -> str:
    number = abs(int(number))
    if number % 10 == 1 and number % 100 != 11:
        word = one
    elif 2 <= number % 10 <= 4 and not (12 <= number % 100 <= 14):
        word = few
    else:
        word = many
    return f"{number} {word}"


def hours_phrase(hours) -> str:
    if hours is None:
        return "навсегда"
    hours = int(hours)
    if hours >= 24 and hours % 24 == 0:
        return _ru_count(hours // 24, "день", "дня", "дней")
    return _ru_count(hours, "час", "часа", "часов")


def left_phrase(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "меньше минуты"
    minutes_total = seconds // 60
    hours, minutes = divmod(minutes_total, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(_ru_count(days, "день", "дня", "дней"))
    if hours:
        parts.append(_ru_count(hours, "час", "часа", "часов"))
    if minutes and not days:
        parts.append(_ru_count(minutes, "минуту", "минуты", "минут"))
    return " ".join(parts) or "меньше минуты"


def joined_until(current_until, add_hours, now: datetime):
    """Складывает оставшийся срок с часами нового предмета. None — навсегда."""
    if add_hours is None or current_until is None:
        return None
    base = current_until
    moment = now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if base < moment:
        base = moment
    return base + timedelta(hours=int(add_hours))


def shields_in_bag(items: dict) -> list:
    bag = {}
    for key, value in (items or {}).items():
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            bag[str(key).strip().lower()] = count
    found = []
    for key, spec in SHIELDS.items():
        count = bag.get(str(spec["name"]).strip().lower(), 0)
        if count < 1:
            continue
        found.append({
            "name1": key,
            "name": spec["name"],
            "emoji": spec["emoji"],
            "hours": spec["hours"],
            "count": count,
        })
    return found


def take_one_item(items: dict, *names: str):
    bag = dict(items or {})
    wanted = [str(name) for name in names if str(name or "").strip()]
    for name in wanted:
        if int(bag.get(name, 0) or 0) > 0:
            bag[name] = int(bag[name]) - 1
            if bag[name] <= 0:
                bag.pop(name, None)
            return bag, True
    lowered = {str(key).lower(): key for key in bag}
    for name in wanted:
        key = lowered.get(name.lower())
        if key is None or int(bag.get(key, 0) or 0) < 1:
            continue
        bag[key] = int(bag[key]) - 1
        if bag[key] <= 0:
            bag.pop(key, None)
        return bag, True
    return bag, False


def guide_status(*, pistol: int, water: int, shield_line: str) -> str:
    """Справка «водные игры»: что уже есть и чего не хватает для выстрела."""
    def stock(count: int) -> str:
        count = int(count or 0)
        if count < 1:
            return "нет. Кнопка ниже откроет покупку"
        if count == 1:
            return "есть, 1 шт."
        return f"есть, {count} шт."

    lines = [
        f"🔫 <b>Пистолетик</b> — {stock(pistol)}",
        f"💧 <b>Вода</b> — {stock(water)}",
        shield_line,
    ]
    if int(pistol) > 0 and int(water) > 0:
        lines.append("Можно нажимать «Выстрелить».")
    return screen_text("home") + "\n\n" + "\n".join(lines)


def water_buy_kind(name1: str = "", name: str = "") -> str:
    """Ключ предмета водных игр. Пустая строка — покупка к этой системе не относится."""
    key = str(name1 or "").strip()
    if key in {"pistoletik", "watercraft"} or key in SHIELDS:
        return key
    title = str(name or "").strip().lower()
    if title == "вода":
        return "watercraft"
    if title == "пистолетик":
        return "pistoletik"
    for shield_key, spec in SHIELDS.items():
        if str(spec["name"]).strip().lower() == title:
            return shield_key
    return ""


def after_buy_text(*, kind: str, emoji: str, name: str, pistol: bool, water: bool) -> tuple[str, str]:
    """Следующий экран после покупки с кнопки водных игр: текст и один следующий шаг."""
    kind = water_buy_kind(kind, name)
    if not kind:
        return "", ""
    if kind in SHIELDS:
        return screen_text("bought_shield", emoji=emoji, name=name), "wear"
    if kind == "watercraft" and pistol:
        return screen_text("bought_ready"), "shoot"
    if kind == "watercraft":
        return screen_text("bought_pistol_left", emoji=emoji, name=name), "pistol"
    if kind == "pistoletik" and water:
        return screen_text("bought_ready"), "shoot"
    if kind == "pistoletik":
        return screen_text("bought_water_left", emoji=emoji, name=name), "water"
    return "", ""


def shield_profile_line(*, emoji: str, name: str, forever: bool, left: str, shoot: bool) -> str:
    """Строка под флагом в профиле, пока защита от обливания ещё действует."""
    span = "навсегда" if forever else f"ещё {left}"
    hunt = "Стрелять можно." if shoot else "Стрелять нельзя."
    return (
        f"{emoji} <b>Под защитой от ограблений</b> {span}\n"
        f"<i>{name}. {hunt}</i>"
    )


def wearing_text(*, emoji: str, name: str, left: str, fee: int) -> str:
    return screen_text("wearing", emoji=emoji, name=name, left=left, fee=int(fee))


def forever_worn_text(*, emoji: str, name: str) -> str:
    return screen_text("forever_worn", emoji=emoji, name=name)


def _hunt_line(shoot: bool) -> str:
    return screen_text("hunt_open" if shoot else "hunt_closed")


def worn_text(*, emoji: str, name: str, term: str, shoot: bool) -> str:
    return screen_text("worn", emoji=emoji, name=name, term=term, hunt=_hunt_line(shoot))


def extend_list_text(*, emoji: str, name: str, left: str) -> str:
    return screen_text("extend_list", emoji=emoji, name=name, left=left)


def extend_empty_text(*, emoji: str, name: str, left: str) -> str:
    return screen_text("extend_empty", emoji=emoji, name=name, left=left)


def extend_pick_text(*, emoji: str, name: str, add: str, now_left: str, next_left: str, fee: int, shoot: bool) -> str:
    hunt = "" if shoot else "\n" + screen_text("extend_pick_hunt")
    return screen_text(
        "extend_pick",
        emoji=emoji,
        name=name,
        add=add,
        now_left=now_left,
        next_left=next_left,
        fee=int(fee),
        hunt=hunt,
    )


def stacked_text(*, emoji: str, name: str, left: str, fee: int, shoot: bool, spent: str) -> str:
    if left == hours_phrase(None):
        tail = screen_text("stacked_forever", name=name)
    else:
        tail = screen_text("stacked_time", name=name, left=left)
    hunt = "" if shoot else "\n<i>" + _hunt_line(False) + "</i>"
    return screen_text("stacked", emoji=emoji, tail=tail, hunt=hunt, fee=int(fee), spent=spent)


def fresh_instead_text(*, emoji: str, name: str, term: str, shoot: bool) -> str:
    return screen_text(
        "fresh_instead",
        emoji=emoji,
        name=name,
        term=term,
        hunt=_hunt_line(shoot),
        fee=EXTEND_FEE,
    )


def poor_fee_text(*, fee: int, balance: int) -> str:
    have = f"{int(balance):,}".replace(",", " ")
    return screen_text("poor_fee", fee=int(fee), balance=have)


def missing_item_text(name: str) -> str:
    return screen_text("missing_item", name=name)


def choice_label(*, emoji: str, name: str, count: int, plus: str) -> str:
    text = screen_text("choice_label", emoji=emoji, name=name, count=count, plus=plus)
    return " ".join(text.split())


async def seed_water_dex(pool) -> None:
    """Кладёт в dex недостающие предметы водных игр. Уже стоящую цену не трогает."""
    for item in ITEMS:
        if "price" not in item:
            continue
        await pool.execute(
            """
            INSERT INTO dex (id, name, name1, emoji, price, dis, remains, sorting, bio, "use")
            SELECT
                (SELECT COALESCE(MAX(id), 0) + 1 FROM dex),
                $1, $2, $3, $4, 0, 1, '🔫', $5, 1
            WHERE NOT EXISTS (
                SELECT 1 FROM dex WHERE name1 = $2 OR lower(name) = lower($1)
            )
            """,
            item["name"],
            item["name1"],
            item["emoji"],
            int(item["price"]),
            item.get("bio") or "",
        )


async def settle_umbrella(pool) -> None:
    """Ставит выбранные цены вместо старых стартовых. Склад не обнуляется."""
    await seed_water_dex(pool)
    for item in ITEMS:
        if "price" not in item:
            continue
        old = OLD_PRICES.get(item["name1"])
        if old is not None:
            await pool.execute(
                """
                UPDATE dex
                SET price = $1
                WHERE (name1 = $2 OR lower(name) = lower($3))
                  AND price = $4
                """,
                int(item["price"]),
                item["name1"],
                item["name"],
                int(old),
            )
        await pool.execute(
            """
            UPDATE dex
            SET bio = $1,
                emoji = $2,
                sorting = '🔫',
                "use" = 1
            WHERE name1 = $3 OR lower(name) = lower($4)
            """,
            str(item.get("bio") or ""),
            item["emoji"],
            item["name1"],
            item["name"],
        )


def towel_amount(stolen: int) -> int:
    bonus = int(int(stolen) * TOWEL_PERCENT / 100)
    if bonus < 1:
        bonus = 1
    return min(bonus, TOWEL_CAP, int(stolen))


# Чёрный юмор про уже мокрого и пустые карманы. По кругу, без повтора подряд.
DRY_JOKES = (
    "С него уже капает на пол. Дальше вы просто моете лужу.",
    "Карманы выжаты. Ещё один выстрел — и вы стреляете по воспоминанию о кут.",
    "Он мокрый с утра, с обеда и, кажется, с позапрошлой среды. Брать нечего.",
    "Если отжать этого человека, получится вода. Кут там закончились раньше воды.",
    "Баланс смотрит на вас мокрыми глазами и просит хотя бы полотенце, не пистолет.",
    "Вы пришли грабить кассу, а там аквариум. Рыбок тоже нет.",
    "Он уже облит, высушен и снова облит. Экономика этого человека — сквозняк.",
    "С такого баланса даже капля стекает мимо. Касса пустая, шутка бесплатная.",
    "Пистолетик чихнул. В ответ прилетела сырость и ноль кут.",
    "Этот человек финансово водонепроницаемый: внутри ничего нет.",
    "Вы целились в сейф. Это была кружка. Пустая. И уже мокрая.",
    "Ещё чуть-чуть, и его можно будет выжимать в ведро. В ведре будут только шутки.",
    "Кут ушли раньше, чем вы достали воду. Осталась только репутация лужи.",
    "Обливать его дальше — благотворительность для пола.",
    "Баланс ниже дна стакана. Дно тоже мокрое.",
    "Он не прячет кут. Их нет. Это честная нищета под дождём.",
    "Выстрел прошёл навылет. За ним не было даже мелкой монеты.",
    "Сырость есть, добычи нет. Редкая и невыгодная комбинация.",
    "Пистолетик поработал, карманы даже не заметили. Они давно в отпуске.",
    "Если бедность можно довести до блеска, вы только что его натёрли.",
    "Он уже был облит жизнью. Ваша вода опоздала.",
    "Касса закрыта по причине сырости и пустоты. Вторым пунктом особенно.",
    "Вы украли бы кут, но они съехали и адрес не оставили.",
    "Мокрый, громкий и абсолютно нерентабельный. Классика.",
)


def broke_text(local: str, remote: str = "") -> str:
    extra = ""
    if remote:
        extra = f"\n\n<blockquote><i>{remote}</i></blockquote>"
    return (
        "<b>💧 Брать нечего</b>\n"
        f"<i>{local}</i>"
        f"{extra}\n\n"
        f"Баланс ниже <u>{POOR_BALANCE}</u> кут. Вода потрачена, кут остались при нём."
    )
