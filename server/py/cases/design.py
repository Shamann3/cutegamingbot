# -*- coding: utf-8 -*-
"""Кейсы: короткие тексты, шансы и потолок. Комиссии нет — край сидит в шансах."""
from __future__ import annotations

import random

KEY_PREMIUM = "5278573677900752088"
CASE_PREMIUM = {
    "small": "5379808153011502648",
    "mid": "5375106250449100282",
    "large": "5927197049077372412",
}

# Чаще середина, потолок редкий и настоящий. Среднее ниже потолка.
_DEFAULTS = (
    {
        "id": "small",
        "name1": "case5000_15000",
        "name": "Маленький кейс",
        "emoji": "📦",
        "premium": CASE_PREMIUM["small"],
        "max": 50,
        "bands": (
            {"chance": 62, "amount": 12},
            {"chance": 25, "amount": 24},
            {"chance": 10, "amount": 36},
            {"chance": 3, "amount": 50},
        ),
    },
    {
        "id": "mid",
        "name1": "case20000_40000",
        "name": "Средний кейс",
        "emoji": "🧳",
        "premium": CASE_PREMIUM["mid"],
        "max": 70,
        "bands": (
            {"chance": 60, "amount": 32},
            {"chance": 27, "amount": 48},
            {"chance": 10, "amount": 60},
            {"chance": 3, "amount": 70},
        ),
    },
    {
        "id": "large",
        "name1": "case50000_100000",
        "name": "Большой кейс",
        "emoji": "\U0001fa8e",
        "premium": CASE_PREMIUM["large"],
        "max": 170,
        "bands": (
            {"chance": 64, "amount": 60},
            {"chance": 24, "amount": 100},
            {"chance": 9, "amount": 140},
            {"chance": 3, "amount": 170},
        ),
    },
)

KEY = {
    "id": "key",
    "name1": "key",
    "name": "Ключ",
    "emoji": "🔑",
    "premium": KEY_PREMIUM,
}

HISTORY = {
    "small": "открытие маленького кейса",
    "mid": "открытие среднего кейса",
    "large": "открытие большого кейса",
}

MAX_CUTE = 1_000_000
MIN_BANDS = 2
MAX_BANDS = 6


def cases() -> list[dict]:
    return [dict(item) for item in _DEFAULTS]


def shop_items() -> list[dict]:
    """Ключ и три кейса в том порядке, в каком их видит создатель."""
    return [dict(KEY), *cases()]


def case_by_id(case_id: str) -> dict | None:
    for item in _DEFAULTS:
        if item["id"] == case_id:
            return dict(item)
    return None


def mark(emoji: str, premium: str) -> str:
    return f"<tg-emoji emoji-id=\"{premium}\">{emoji}</tg-emoji>"


def key_text() -> str:
    icon = mark(KEY["emoji"], KEY["premium"])
    return f"{icon} <b>Нужен кейс</b>\n<i>Кнопка откроет покупку.</i>"


def need_key_text(case_id: str) -> str:
    item = case_by_id(case_id) or _DEFAULTS[0]
    icon = mark(item["emoji"], item["premium"])
    return f"{icon} <b>Нужен ключ</b>\n<i>Купите <code>🔑</code>. Кнопка откроет покупку.</i>"


def held_text(name: str, emoji: str, premium: str) -> str:
    return (
        f"{mark(emoji, premium)} <b>{name} уже у вас</b>\n"
        "<i>Используйте его.</i>"
    )


def ready_open_text(items: list[dict]) -> str:
    """Ключ и кейс уже есть. Одна команда — и кнопка «Открыть»."""
    blocks = []
    for item in items:
        emoji = str(item.get("emoji") or "")
        blocks.append(
            f"{mark(emoji, str(item.get('premium') or ''))} <b>Можно открыть</b>\n"
            f"<code>использовать {emoji}</code>"
        )
    return "\n\n".join(blocks)


def closed_text() -> str:
    return (
        f"{mark(KEY['emoji'], KEY['premium'])} <b>Кейсы временно недоступны</b>\n"
        "<i>Нужно немного подождать.</i>"
    )


# Те же технические кассы, что платят комиссии игр. Имена короткие, для вкладки.
FUND_CHATS = (
    {"id": "-1004324787050", "name": "Игры"},
    {"id": "-1004318525471", "name": "Фон"},
    {"id": "-1003855337972", "name": "Дом игр"},
    {"id": "-1004238101266", "name": "Копилка"},
)


def fund_ids() -> list[int]:
    return [int(item["id"]) for item in FUND_CHATS]


def fund_label(chat_id, namechat: str = "") -> str:
    key = str(chat_id)
    for item in FUND_CHATS:
        if item["id"] == key:
            return item["name"]
    text = str(namechat or "").strip()
    return text or "Техгруппа"


def take_plan(groups, amount: int):
    """С каких технических групп списать приз. None — кассы не хватает."""
    need = int(amount)
    if need < 1:
        return []
    ordered = sorted(
        groups or [],
        key=lambda row: (-int(row.get("balance") or 0), int(row.get("id") or 0)),
    )
    plan = []
    for row in ordered:
        if need <= 0:
            break
        have = int(row.get("balance") or 0)
        if have <= 0:
            continue
        piece = min(have, need)
        plan.append({"id": int(row["id"]), "take": piece})
        need -= piece
    if need > 0:
        return None
    return plan


def owns(items: dict, item: dict, dex_id=None) -> bool:
    wanted = {str(item.get("name") or "").strip().lower()}
    if dex_id is not None and str(dex_id).strip():
        wanted.add(str(dex_id).strip().lower())
    wanted.discard("")
    for key, value in (items or {}).items():
        if str(key).strip().lower() not in wanted:
            continue
        try:
            if int(value or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def found_text(name: str, emoji: str, premium: str, where: str, place: str) -> str:
    return (
        f"<b>{mark(emoji, premium)} {name} есть {where}</b>\n"
        f"<i>Кнопка откроет {place}.</i>"
    )


def own_lot_text(name: str, emoji: str, premium: str) -> str:
    return (
        f"<b>{mark(emoji, premium)} {name} уже на вашей бирже</b>\n"
        "<i>Снимите лот — предмет вернётся.</i>"
    )


def miss_text(name: str, emoji: str, premium: str) -> str:
    return (
        f"<b>{mark(emoji, premium)} {name} сейчас не продаётся</b>\n"
        "<i>Ни в магазине, ни на бирже.</i>"
    )


def opened_text(case_id: str, amount: int, ceiling: int) -> str:
    item = case_by_id(case_id) or _DEFAULTS[0]
    icon = mark(item["emoji"], item["premium"])
    shown = f"{int(amount):,}".replace(",", ".")
    if int(amount) >= int(ceiling):
        return f"{icon} <b>Потолок</b>\n<i>{item['name']} отдал {shown} кут.</i>"
    return f"{icon} <b>{item['name']} открыт</b>\n<i>+{shown} кут</i>"


def button_owner(data: str):
    parts = str(data or "").split(":")
    if len(parts) < 3 or parts[0] != "cs":
        return None
    if parts[1] in {"guide", "open"}:
        if len(parts) >= 4 and parts[-1].isdigit():
            return int(parts[-1])
        return None
    if len(parts) < 4 or parts[1] != "find":
        return None
    if parts[-1].isdigit():
        return int(parts[-1])
    return None


def stamp_callback(data: str, user_id: int) -> str:
    if button_owner(data) is not None:
        return str(data)
    return f"{data}:{int(user_id)}"


def find_target(data: str) -> str:
    parts = str(data or "").split(":")
    if len(parts) < 3 or parts[0] != "cs" or parts[1] != "find":
        return ""
    return parts[2]


def _clean_bands(raw) -> list[dict]:
    bands = []
    for row in raw or []:
        if not isinstance(row, dict):
            raise ValueError("band")
        chance = int(row.get("chance"))
        amount = int(row.get("amount"))
        bands.append({"chance": chance, "amount": amount})
    return bands


def check_rules(case_id: str, max_cute: int, bands) -> dict:
    """Потолок достижим. Шансы складываются в 100. Комиссии в правилах нет."""
    if case_by_id(case_id) is None:
        raise ValueError("case")
    ceiling = int(max_cute)
    if ceiling < 1 or ceiling > MAX_CUTE:
        raise ValueError("max")
    cleaned = _clean_bands(bands)
    if not (MIN_BANDS <= len(cleaned) <= MAX_BANDS):
        raise ValueError("count")
    if sum(row["chance"] for row in cleaned) != 100:
        raise ValueError("sum")
    for row in cleaned:
        if row["chance"] < 1 or row["chance"] > 100:
            raise ValueError("chance")
        if row["amount"] < 1 or row["amount"] > ceiling:
            raise ValueError("amount")
    if max(row["amount"] for row in cleaned) != ceiling:
        raise ValueError("ceiling")
    return {"id": case_id, "max": ceiling, "bands": cleaned}


def average(bands) -> float:
    total = sum(int(row["chance"]) * int(row["amount"]) for row in bands)
    return total / 100


def roll_amount(bands, rng=None) -> int:
    picker = rng or random
    weights = [int(row["chance"]) for row in bands]
    amounts = [int(row["amount"]) for row in bands]
    return int(picker.choices(amounts, weights=weights, k=1)[0])


def public_case(stored: dict | None, case_id: str) -> dict:
    base = case_by_id(case_id)
    if base is None:
        raise KeyError(case_id)
    bands = [dict(row) for row in base["bands"]]
    ceiling = int(base["max"])
    if stored:
        try:
            checked = check_rules(case_id, stored.get("max"), stored.get("bands"))
        except (TypeError, ValueError):
            checked = None
        if checked:
            ceiling = checked["max"]
            bands = checked["bands"]
    return {
        "id": case_id,
        "name1": base["name1"],
        "name": base["name"],
        "emoji": base["emoji"],
        "premium": base["premium"],
        "max": ceiling,
        "bands": bands,
        "average": average(bands),
    }


def face(target: str) -> dict | None:
    if target == "key":
        return dict(KEY)
    found = case_by_id(target)
    return dict(found) if found else None


def _dots(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def guide_home(*, has_key: bool, held: list[dict], open_now: bool = True) -> str:
    """Первый экран: открыть, купить недостающее или подождать кассу."""
    title = f"{mark(KEY['emoji'], KEY['premium'])} <b>Кейсы</b>"
    if not open_now:
        return f"{title}\n<i>Временно недоступны. Нужно немного подождать.</i>"
    if has_key and held:
        lines = [title, "<i>Можно открыть.</i>"]
        for item in held:
            lines.append(f"<code>использовать {item.get('emoji') or ''}</code>")
        return "\n".join(lines)
    if has_key:
        return f"{title}\n<i>Нужен кейс.</i>"
    if held:
        return f"{title}\n<i>Нужен ключ.</i>"
    return f"{title}\n<i>Нужны ключ и кейс.</i>"


def guide_how(ceilings: list[int]) -> str:
    """Команды и потолки. Шансы здесь не пишем."""
    order = ("small", "mid", "large")
    items = [case_by_id(case_id) for case_id in order]
    caps = list(ceilings or [])
    while len(caps) < 3:
        caps.append(int(items[len(caps)]["max"]))
    short = {"small": "Маленький", "mid": "Средний", "large": "Большой"}
    lines = [
        f"{mark(KEY['emoji'], KEY['premium'])} <b>Как открыть</b>",
        "<i>Ключ и кейс. Затем «Открыть» или команда.</i>",
    ]
    for item in items:
        lines.append(f"<code>использовать {item['emoji']}</code>")
    lines.append(" · ".join(
        f"{short[item['id']]} до <b>{_dots(cap)}</b>"
        for item, cap in zip(items, caps)
    ))
    lines.append("<i>Ключ и кейс сгорают. Приходит выпавшее число.</i>")
    return "\n".join(lines)


# Настоящая команда предмета. «использовать кейс» — это вопрос, не расход.
_USE_NAMES = {
    "ключ",
    "key",
    "маленький кейс",
    "средний кейс",
    "большой кейс",
    "case5000_15000",
    "case20000_40000",
    "case50000_100000",
}

# Слова, которые не меняют смысл короткой фразы.
_FILLERS = {
    "а", "и", "ну", "вот", "же", "бы", "ли", "то", "эт", "это", "этот", "эта", "эти",
    "в", "на", "по", "за", "для", "с", "со", "к", "ко", "о", "об", "про", "из", "от", "до", "у",
    "не", "ни", "ты", "вы", "мне", "меня", "мной", "нам", "мой", "моя", "мои", "моем", "моём",
    "свой", "свою", "свои", "тут", "здесь", "уже", "еще", "ещё", "пожалуйста", "пж", "плиз", "плз",
    "бот", "кут", "куты", "кутик",
}

# Намерение: открыть, спросить, купить, найти. Короткое сообщение без такого слова
# и без одного только «кейсы» справку не открывает.
_INTENT_STEMS = (
    "откры", "откро", "вскро", "раскро",
    "как", "че", "что", "чо", "зачем", "почему",
    "хелп", "help", "помощ", "подскаж", "объясн", "расскаж", "научи", "покаж",
    "инструк", "правил", "гайд", "guide", "тутор", "мануал",
    "где", "куда",
    "хочу", "хотел", "хотим", "можно", "надо",
    "куп", "покуп",
    "получ", "взят", "доста",
    "использ", "польз", "юза", "заюза",
    "работ", "устро",
    "open", "how", "what", "where",
)


def _words(text: str) -> str:
    raw = " ".join(str(text or "").replace("ё", "е").split()).casefold()
    raw = "".join(ch if ch.isalnum() or ch == " " else " " for ch in raw)
    return " ".join(raw.split())


def _case_word(token: str) -> bool:
    return token in {"case", "cases"} or token == "кейс" or token.startswith("кейс")


def _intent_word(token: str) -> bool:
    return any(token.startswith(stem) for stem in _INTENT_STEMS)


def _real_item_use(raw: str) -> bool:
    """«использовать 📦» и «использовать маленький кейс» открывают предмет, не справку."""
    if not raw.startswith("использовать"):
        return False
    rest = raw[len("использовать"):].strip()
    return rest == "" or rest in _USE_NAMES


def is_case_ask(text: str) -> bool:
    """Короткая фраза про кейсы: «открыть кейс», «как открыть», «открой», «где кейсы».

    Длинный разговор, где слово просто встретилось, и команда расхода предмета
    сюда не входят.
    """
    raw = _words(text)
    if not raw or len(raw) > 80 or _real_item_use(raw):
        return False
    tokens = raw.split()
    if len(tokens) > 10:
        return False
    if not any(_case_word(token) for token in tokens):
        return False
    if all(_case_word(token) or token in _FILLERS for token in tokens):
        return True
    return any(_intent_word(token) for token in tokens)


def match_bought(name1: str, name: str) -> str:
    raw_name1 = str(name1 or "").strip()
    raw_name = str(name or "").strip().lower()
    for item in list(_DEFAULTS) + [KEY]:
        if raw_name1 == item["name1"] or raw_name == item["name"].lower():
            return item["id"]
    if raw_name1.lower() == "key":
        return "key"
    return ""
