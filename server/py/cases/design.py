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


def case_by_id(case_id: str) -> dict | None:
    for item in _DEFAULTS:
        if item["id"] == case_id:
            return dict(item)
    return None


def mark(emoji: str, premium: str) -> str:
    return f"<tg-emoji emoji-id=\"{premium}\">{emoji}</tg-emoji>"


def key_text() -> str:
    icon = mark(KEY["emoji"], KEY["premium"])
    return (
        f"{icon} <b>Ключ используется для открытия кейсов</b>\n"
        "<i>Кнопка откроет покупку кейса.</i>"
    )


def need_key_text(case_id: str) -> str:
    item = case_by_id(case_id) or _DEFAULTS[0]
    icon = mark(item["emoji"], item["premium"])
    return (
        f"{icon} <b>Чтобы открыть {item['name']}, купите <code>🔑</code> ключ</b>\n"
        "<i>Кнопка откроет покупку.</i>"
    )


def held_text(name: str, emoji: str, premium: str) -> str:
    return (
        f"{mark(emoji, premium)} <b>{name} уже у вас</b>\n"
        "<i>Используйте его.</i>"
    )


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
    if len(parts) < 4 or parts[0] != "cs" or parts[1] != "find":
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


def match_bought(name1: str, name: str) -> str:
    raw_name1 = str(name1 or "").strip()
    raw_name = str(name or "").strip().lower()
    for item in list(_DEFAULTS) + [KEY]:
        if raw_name1 == item["name1"] or raw_name == item["name"].lower():
            return item["id"]
    if raw_name1.lower() == "key":
        return "key"
    return ""
