# -*- coding: utf-8 -*-
"""Водные игры — все слова, кнопки и числа.

Как править
-----------
Сообщение целиком — в text= тройными кавычками.
Кнопка — b(text="Слово", go="splash", data="wg:splash").
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


def b(*, text: str, go: str, data: str = "", color: str = "default") -> dict:
    return {
        "text": t(text),
        "go": go,
        "data": data or ("wg:" + go),
        "style": color or "default",
    }


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
    "not_yours": "Эта кнопка открывает защиту того, кто её надел.",
    "no_such_item": "Такого предмета нет",
    "need_fee": "Нужно {fee} кут",
    "item_gone": "Предмета уже нет",
    "nothing_to_stack": "Складывать нечего",
    "worn_no_fee": "Защита надета без доплаты",
    "stack_failed": "Не удалось сложить срок",
    "stacked": "Срок увеличился",
    "looking": "Смотрю магазин и биржу",
    "open_buy": "Открыть покупку",
    "towel": "Полотенце",
    "towel_lost": "Полотенце уже не найти",
    "towel_not_yours": "Это полотенце не вам или его уже забрали",
    "towel_dry": "Полотенце высохло",
    "towel_got": "Полотенце: +{amount} кут",
    "shield_name": "защита",
    "where_market": "на бирже",
    "where_shop": "в магазине",
    "place_market": "биржа",
    "place_shop": "магазин",
    "missing_pistol": "Нужен Пистолетик.",
    "missing_water": "Нужна Вода.",
    "water_held": "Это Вода. Она не стреляет сама. Ответьте на сообщение в группе и используйте Пистолетик: одна Вода спишется.",
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

ITEMS = (
    {
        "name1": "pistoletik",
        "name": "Пистолетик",
        "emoji": "🔫",
        "match": ("пистолетик",),
        "price": PRICES["pistoletik"],
        "bio": (
            "Остаётся у вас навсегда. Один выстрел тратит одну воду. "
            "В группе ответьте на сообщение человека и используйте пистолетик. "
            "В личке выстрел не идёт. Можно купить сколько угодно."
        ),
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
        "bio": (
            "Три часа вас не обливают. Под зонтиком можно стрелять. Можно купить сколько угодно. "
            f"Если защита уже надета, кнопка «{BTN_EXTEND}» складывает срок "
            f"за {EXTEND_FEE} кут и один предмет."
        ),
    },
    {
        "name1": "drycoat",
        "name": "Дождевик",
        "emoji": "🧥",
        "match": ("дождевик",),
        "hours": 12,
        "price": PRICES["drycoat"],
        "bio": (
            "Двенадцать часов вас не обливают. Пока он надет, сами вы не стреляете. Можно купить сколько угодно. "
            "Когда срок кончится, первый выстрел снимает только половину. "
            f"Если защита уже надета, кнопка «{BTN_EXTEND}» складывает срок "
            f"за {EXTEND_FEE} кут и один предмет."
        ),
    },
    {
        "name1": "dryawning",
        "name": "Навес",
        "emoji": "🛖",
        "match": ("навес",),
        "hours": 72,
        "price": PRICES["dryawning"],
        "bio": (
            "Три дня вас не обливают. Пока он надет, сами вы не стреляете. Можно купить сколько угодно. "
            f"Если защита уже надета, кнопка «{BTN_EXTEND}» складывает срок "
            f"за {EXTEND_FEE} кут и один предмет."
        ),
    },
    {
        "name1": "drysafe",
        "name": "Сухой сейф",
        "emoji": "💎",
        "match": ("сухой сейф",),
        "hours": None,
        "price": PRICES["drysafe"],
        "bio": (
            "Навсегда вас не обливают. Пока сейф надет, сами вы не стреляете. "
            "Можно купить сколько угодно. Сложить его с другой защитой нельзя: "
            "срок и так не кончается."
        ),
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
    <b>🔫 Водные игры</b>
    <i>В группе можно забрать часть кут у человека.</i>

    <blockquote><b>🔫 Облить</b> — три шага, и вы уже стреляете.
    <b>☂️ Защититься</b> — если не хотите, чтобы обливали вас.</blockquote>

    <pre>1. Облить
2. Выстрелить
3. Ответить и открыть Пистолетик</pre>

    Выстрел забирает от <u>{low}%</u> до <u>{high}%</u> баланса.
    Не больше <code>{cap}</code> кут за раз и <code>{day}</code> кут с человека за сутки.
    Баланс ниже <code>{poor}</code> кут не уходит стрелку.
    Облить <s>себя</s> нельзя.

    <tg-spoiler>Если кут не перешли, вода всё равно тратится. Взамен приходит шутка.</tg-spoiler>

    <blockquote expandable>Пара отдыхает шесть часов и не чаще двух попаданий в сутки.
    Полотенце один раз отдаёт облитому часть кут от проекта, не из кармана стрелка.
    Под зонтиком стрелять можно. Под остальной защитой — нет.
    Фраза <code>водные игры</code> открывает справку и в <a href="https://t.me/CuteGamingBot">личке бота</a>.</blockquote>
    """,
    [
        [b(text="🔫 Облить", go="splash", data="wg:splash", color="primary")],
        [b(text="☂️ Защититься", go="shield", data="wg:shield", color="success")],
        [b(text="Как это работает", go="rules", data="wg:rules", color="default")],
    ],
)

screen(
    "rules",
    """
    <b>Как облить</b>
    <i>Три нажатия, если пистолетик и вода уже есть.</i>

    <pre>1. 🔫 Облить
2. 💥 Выстрелить
3. Ответить на сообщение и открыть Пистолетик</pre>

    <u>Пистолетик</u> остаётся у вас. <code>Вода</code> списывается одна за выстрел.

    <blockquote><b>Если предмета нет</b> — кнопка «Найти» смотрит магазин и биржу и открывает покупку.</blockquote>

    <tg-spoiler>Полотенце забирает облитый: часть кут от проекта, не у стрелка.</tg-spoiler>
    """,
    [
        [b(text="🔫 Облить", go="splash", data="wg:splash", color="primary")],
        [b(text="☂️ Защититься", go="shield", data="wg:shield", color="success")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "splash_ready",
    """
    <b>💥 Пистолетик заряжен</b>
    <i>Вода на месте. Это второй шаг.</i>

    Нажмите <u>💥 Выстрелить</u>.
    <blockquote>Следующий экран скажет, на чьё сообщение ответить и какой предмет открыть.</blockquote>
    """,
    [
        [b(text="💥 Выстрелить", go="aim", data="wg:aim", color="danger")],
        [b(text="☂️ Защититься", go="shield", data="wg:shield", color="success")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "aim",
    """
    <b>Третий шаг</b>
    <i>Найдите сообщение человека в группе.</i>

    <blockquote><b>Ответьте на него и используйте <u>Пистолетик</u>.</b>
    <code>личка</code> не считается: охота видна чату.</blockquote>

    Облить <s>себя</s> нельзя.
    """,
    [
        [b(text="Назад", go="splash", data="wg:splash", color="default")],
    ],
)

screen(
    "splash_need",
    """
    <b>Для выстрела не хватает предмета</b>
    <i>{missing}</i>

    <blockquote>Кнопка ниже прямо сейчас проверяет <u>магазин</u> и <u>биржу</u>.
    Если предмет лежит там, следующее нажатие откроет покупку.</blockquote>

    <code>Пистолетик</code> остаётся. <code>Вода</code> тратится.
    """,
    [
        [b(text="🔫 Найти пистолетик", go="find-pistol", data="wg:find:pistoletik", color="primary")],
        [b(text="💧 Найти воду", go="find-water", data="wg:find:watercraft", color="success")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "shield",
    """
    <b>☂️ Защититься от воды</b>
    <i>Эти предметы можно купить и надеть сколько угодно.</i>

    <b>☂️ Зонтик</b> — <u>3 часа</u>. Под ним можно стрелять.
    <b>🧥 Дождевик</b> — <u>12 часов</u>. Стрелять нельзя. Когда срок кончится, первый выстрел снимает только половину.
    <b>🛖 Навес</b> — <u>3 дня</u>. Стрелять нельзя.
    <b>💎 Сухой сейф</b> — <code>навсегда</code>. Стрелять нельзя.

    <blockquote>Первый раз предмет просто надевается.
    Если защита уже на вас, бот напишет её название и даст кнопку «Увеличить».
    «Улучшить за {fee} кут» списывает эти кут и один предмет, а часы складываются.</blockquote>

    <blockquote expandable>Пока идёт срок, новый предмет сам не пропадает. Его забирает только подтверждение.
    Зонтик поверх другой защиты не возвращает право стрелять.</blockquote>

    <tg-spoiler>Сейф нельзя сложить с другой защитой: срок и так не кончается.</tg-spoiler>
    """,
    [
        [b(text="☂️ Найти зонтик", go="find-umbrella", data="wg:find:dryumbrella", color="success")],
        [b(text="🧥 Найти дождевик", go="find-coat", data="wg:find:drycoat", color="primary")],
        [b(text="🛖 Найти навес", go="find-awning", data="wg:find:dryawning", color="default")],
        [b(text="💎 Найти сухой сейф", go="find-safe", data="wg:find:drysafe", color="danger")],
        [b(text="Назад", go="home", data="wg:home", color="default")],
    ],
)

screen(
    "found",
    """
    <b>{emoji} {name} нашёлся</b>
    <i>{where}</i>

    <blockquote>Дальше откроется <u>{place}</u>. Там уже карточка покупки.</blockquote>
    """,
    [],
)

screen(
    "miss",
    """
    <b>{emoji} {name} сейчас нигде не продаётся</b>
    <i>Ни в магазине, ни на бирже лота нет.</i>

    Загляните позже: кнопка каждый раз проверяет заново.
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
    ✖️ <b>Ответьте на сообщение того, кого обливаете.</b>
    """,
)

screen(
    "shot_self",
    """
    ✖️ <b>Себя обливать нельзя. Найдите кого-то в чате.</b>
    """,
)

screen(
    "shot_private",
    """
    ✖️ <b>В личке охота закрыта. Обливают в группе, чтобы это видел чат.</b>
    """,
)

screen(
    "shot_locked",
    """
    <b>{emoji} {name} надет</b>
    <i>Под этой защитой вы сами не стреляете. Стрелять можно только под зонтиком.</i>
    """,
)

screen(
    "shot_pair_day",
    """
    <b>На сегодня с этого человека хватит.</b>
    <i>Два попадания за сутки — и пара отдыхает.</i>
    """,
)

screen(
    "shot_pair_wait",
    """
    <b>Этот человек ещё не высох от вас.</b>
    <i>Следующий выстрел по нему — через {left}.</i>
    """,
)

screen(
    "shot_bounce",
    """
    <b>{emoji} Защита раскрылась</b>
    <i>{title}. Вода стекла, кут остались при нём.</i>
    """,
)

screen(
    "shot_unknown",
    """
    ✖️ <b>Этого человека ещё нет в базе. Обливать некого.</b>
    """,
)

screen(
    "shot_day",
    """
    <b>Он уже мокрый до нитки</b>
    <i>За сутки с него уже сняли потолок. До завтра кут не переходят. Вода при вас.</i>
    """,
)

screen(
    "shot_dry",
    """
    <b>С него сейчас нечего снять.</b>
    """,
)

screen(
    "shot_hit",
    """
    <b>🔫 Попадание</b>
    <i>Ушло <u>{amount}</u> кут. Они уже ваши.</i>

    <blockquote>Ему на {hours} оставили полотенце: кнопка под этим сообщением.</blockquote>
    """,
)

screen(
    "shield_ended",
    """
    <b>Защита уже кончилась</b>
    <i>Используйте предмет ещё раз: он наденется без доплаты.</i>
    """,
)

screen(
    "wearing",
    """
    <b>{emoji} Вы уже используете {name}</b>
    <i>До конца ещё {left}.</i>

    Предмет, который вы открыли, остался в инвентаре.

    <blockquote><b>Увеличить</b> складывает этот срок с предметом из инвентаря.
    Это стоит <u>{fee}</u> кут и один предмет.</blockquote>
    """,
)

screen(
    "forever_worn",
    """
    <b>{emoji} Вы уже используете {name}</b>
    <i>Срок не кончается. Складывать больше нечего.</i>

    Предмет, который вы открыли, остался в инвентаре.
    """,
)

screen(
    "hunt_open",
    """
    Под зонтиком можно стрелять.
    """,
)

screen(
    "hunt_closed",
    """
    Сами вы не стреляете, пока эта защита надета. Стрелять можно только под зонтиком.
    """,
)

screen(
    "worn",
    """
    <b>{emoji} {name} надет</b>
    <i>Вас не обливают {term}.</i>
    <i>{hunt}</i>

    <blockquote>Следующий такой предмет, пока этот надет, сам не тратится.
    Бот спросит и даст кнопку «Увеличить»: сроки сложатся за отдельную плату.</blockquote>
    """,
)

screen(
    "extend_list",
    """
    <b>Чем увеличить срок</b>
    <i>Сейчас надет {emoji} {name}, ещё {left}.</i>

    Нажмите предмет из инвентаря. Его время прибавится к текущему.
    Деньги и предмет спишутся только на следующем шаге.
    """,
)

screen(
    "extend_empty",
    """
    <b>Продлевать пока нечем</b>
    <i>Сейчас надет {emoji} {name}, ещё {left}.</i>

    В инвентаре нет предмета защиты.
    Купите ещё один и снова нажмите «Увеличить».
    """,
)

screen(
    "extend_pick",
    """
    <b>Сложить {emoji} {name} с текущей защитой</b>
    <i>Сейчас ещё {now_left}. Станет {next_left}.</i>

    <blockquote>Прибавится {add}.
    Списывается <u>{fee}</u> кут и один <u>{name}</u>.
    Кут уходят проекту. Предмет пропадает из инвентаря.</blockquote>{hunt}
    """,
)

screen(
    "extend_pick_hunt",
    """
    <i>После этого сами вы не стреляете. Стрелять можно только под зонтиком.</i>
    """,
)

screen(
    "stacked_forever",
    """
    {name} теперь навсегда.
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
    <b>{emoji} Срок увеличился</b>
    <i>{tail}</i>{hunt}

    Списано <u>{fee}</u> кут. Использован один {spent}.
    """,
)

screen(
    "fresh_instead",
    """
    <b>{emoji} {name} надет</b>
    <i>Прошлая защита уже кончилась, поэтому новый срок начался сейчас: {term}.</i>
    <i>{hunt}</i>

    Доплата <u>{fee}</u> кут не взята.
    """,
)

screen(
    "poor_fee",
    """
    <b>Не хватает кут</b>
    <i>Нужно <u>{fee}</u>, на балансе <u>{balance}</u>.</i>

    Предмет не потрачен. Срок не изменился.
    """,
)

screen(
    "missing_item",
    """
    <b>{name} уже нет в инвентаре</b>
    <i>Срок не изменился, кут не списаны.</i>
    """,
)

screen(
    "choice_label",
    """
    {emoji} {name} · {count} шт · {plus}
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


def take_amount(balance: int, percent: int, *, cap: int, day_left: int) -> int:
    if int(balance) < POOR_BALANCE:
        return 0
    raw = int(int(balance) * int(percent) / 100)
    if raw < 1:
        raw = 1
    room = min(int(cap), int(day_left), int(balance))
    if room < 1:
        return 0
    return min(raw, room)


def btn_join(fee: int = EXTEND_FEE) -> str:
    return f"Улучшить за {int(fee)} кут"


def stock_is_open(name1: str = "", name: str = "") -> bool:
    """Защита водных игр не кончается на складе."""
    key = str(name1 or "").strip().lower()
    title = str(name or "").strip().lower()
    return key in {
        "pistoletik",
        "dryumbrella",
        "drycoat",
        "dryawning",
        "drysafe",
    } or title in {
        "пистолетик",
        "зонтик",
        "дождевик",
        "навес",
        "сухой сейф",
    }


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
                "use" = 1,
                remains = CASE WHEN COALESCE(remains, 0) < 1 THEN 1 ELSE remains END
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
