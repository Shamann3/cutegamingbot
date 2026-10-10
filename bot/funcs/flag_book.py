"""Имя страны по флагу в профиле.

Флаг в Telegram — это два символа региона. Рядом с ними иногда прилипает
невидимый знак варианта, и точное сравнение со словарём тогда не находит
страну. Здесь флаг сначала очищается, потом имя берётся из предмета в магазине,
из словаря и только потом из кода страны.
"""

from __future__ import annotations

import unicodedata

_SKIP = frozenset("\ufe0e\ufe0f\u200d\u200b\u2060\ufeff")


def normalize_flag(value) -> str:
    """Оставить сам флаг: без пробелов и невидимых знаков."""
    text = unicodedata.normalize("NFC", str(value or ""))
    chars = [ch for ch in text if ch not in _SKIP and unicodedata.category(ch) != "Cf"]
    flags = [ch for ch in chars if 0x1F1E6 <= ord(ch) <= 0x1F1FF]
    if len(flags) >= 2:
        return flags[0] + flags[1]
    return "".join(chars).strip()


def iso_code(emoji: str) -> str:
    pair = normalize_flag(emoji)
    letters = [ch for ch in pair if 0x1F1E6 <= ord(ch) <= 0x1F1FF]
    if len(letters) < 2:
        return ""
    return "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in letters[:2])


def _titles():
    from bot.config.config import country_dict

    by_flag = {}
    by_iso = {}
    for emoji, title in country_dict.items():
        key = normalize_flag(emoji)
        name = str(title or "").strip()
        if not key or not name:
            continue
        by_flag.setdefault(key, name)
        code = iso_code(key)
        if code:
            by_iso.setdefault(code, name)
    return by_flag, by_iso


def country_title(emoji, shop_name: str = "") -> str:
    """Как подписать флаг в профиле. Пустая строка, если флага нет."""
    shop = str(shop_name or "").strip()
    if shop:
        return shop
    key = normalize_flag(emoji)
    if not key:
        return ""
    by_flag, by_iso = _titles()
    if key in by_flag:
        return by_flag[key]
    code = iso_code(key)
    if code and code in by_iso:
        return by_iso[code]
    if code:
        return f"Флаг {code}"
    return "Неизвестная страна"
