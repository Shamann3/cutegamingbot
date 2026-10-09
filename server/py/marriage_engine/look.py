# -*- coding: utf-8 -*-
"""Сборка фраз брака. Слова, кнопки и экраны правятся в marriage_design.py.

Правила (цены, искра, эффекты) живут в других файлах. Этот файл их не считает.
Что видит человек, берётся из marriage_design.py и больше нигде не переписывается.
"""
from marriage_engine.marriage_design import *  # noqa: F401,F403


def _plain(text):
    return plain(text)


def item_name(row):
    name = _plain((row or {}).get("name") or "")
    if name.startswith(SEED_PREFIX):
        tail = name[len(SEED_PREFIX):]
        name = SEED_FRUIT.get(tail, tail)
    if name.endswith(NAME_TAIL):
        name = name[: -len(NAME_TAIL)]
    if name.endswith(PAIR_TAIL):
        name = name[: -len(PAIR_TAIL)]
    return name or ITEM_WORD


MOON_FROM, MOON_TO = 21, 6
DAWN_FROM, DAWN_TO = 6, 10
_FOOD_IDS = ("juice", "soup", "salad")


def _hour_box(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    if number < 0 or number > 23:
        return int(default)
    return number


def clocks(cfg=None):
    """Часы луны и рассвета. Берутся из панели, иначе 21:00–06:00 и 06:00–10:00."""
    cfg = cfg if isinstance(cfg, dict) else {}
    moon_from = _hour_box(cfg.get("moonFrom"), MOON_FROM)
    moon_to = _hour_box(cfg.get("moonTo"), MOON_TO)
    dawn_from = _hour_box(cfg.get("dawnFrom"), DAWN_FROM)
    dawn_to = _hour_box(cfg.get("dawnTo"), DAWN_TO)
    return {
        "moon_from": f"{moon_from:02d}:00",
        "moon_to": f"{moon_to:02d}:00",
        "dawn_from": f"{dawn_from:02d}:00",
        "dawn_to": f"{dawn_to:02d}:00",
        "moon_from_h": moon_from,
        "moon_to_h": moon_to,
        "dawn_from_h": dawn_from,
        "dawn_to_h": dawn_to,
    }


def hour_hits(hour, start, end):
    if hour is None:
        return False
    start, end = int(start), int(end)
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _form(count, words):
    number = abs(int(count or 0))
    if number % 10 == 1 and number % 100 != 11:
        return words[0]
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return words[1]
    return words[2]


def spark_acc(count):
    """Винительный: на 1 искру, на 3 искры, на 8 искр."""
    return _form(count, SPARK_ACC)


def spark_nom(count):
    """Именительный: 1 искра, 3 искры, 8 искр."""
    return _form(count, SPARK_NOM)


def _care_n(row):
    try:
        return max(0, int((row or {}).get("care") or 0))
    except (TypeError, ValueError):
        return 0


def _food_bounds(rows):
    found = []
    for row in rows or []:
        if str((row or {}).get("id") or "") in _FOOD_IDS:
            found.append(_care_n(row))
    if not found:
        found = [8, 12, 15]
    return min(found), max(found)


def old_bios():
    found = []
    for pack in OLD_ABOUT.values():
        found.extend(pack)
    return found


def item_about(row, rows=None, cfg=None):
    """Описание предмета. Число искр и часы подставляются из панели."""
    row = row or {}
    if row.get("from_dex"):
        written = _plain(row.get("line") or "")
        if written:
            return written
    ident = str(row.get("id") or "")
    template = ABOUT.get(ident) or ""
    if not template:
        return _plain(row.get("line") or "")
    number = _care_n(row)
    low, high = _food_bounds(rows)
    if ident in _FOOD_IDS and low == high:
        template = FOOD_SAME
    times = clocks(cfg)
    return template.format(
        n=number,
        acc=spark_acc(number),
        nom=spark_nom(number),
        moon_from=times["moon_from"],
        moon_to=times["moon_to"],
        dawn_from=times["dawn_from"],
        dawn_to=times["dawn_to"],
        food_from=low,
        food_to=high,
        food_word=spark_nom(high),
    )


def alert_text(reason, cfg=None):
    text = GIFT_ALERT.get(reason) or GIFT_ALERT["bad"]
    times = clocks(cfg)
    for key in ("moon_from", "moon_to", "dawn_from", "dawn_to"):
        text = text.replace("{" + key + "}", times[key])
    return text


def feast_screen(name, day, prizes):
    """Экран праздника. Заголовок, день и выбор дара — из marriage_design."""
    try:
        number = int(day or 0)
    except (TypeError, ValueError):
        number = 0
    aura = FEAST_AURA.get(number) or FEAST_REACHED
    lines = [
        HEART + " <b>" + FEAST_TITLE + "</b>",
        "<b>" + _plain(name or FEAST_DAY) + "</b>",
        "<i>" + aura + " " + FEAST_PICK + "</i>",
    ]
    for row in prizes or []:
        lines.append(
            str((row or {}).get("emoji") or "")
            + " <b>" + _plain((row or {}).get("name") or FEAST_GIFT) + "</b>\n<i>"
            + _plain((row or {}).get("blurb") or "") + "</i>"
        )
    return "\n".join(lines)


def care_word(count):
    return _form(count, (CARE_ONE, CARE_FEW, CARE_MANY))


def care_got(who, count, each=False):
    """«Вам добавилось 3 заботы.» Слова — CARE_GOT в дизайне."""
    number = int(count or 0)
    template = CARE_GOT_EACH if each else CARE_GOT
    return template.format(who=who, n=number, word=care_word(number))


def use_card(emoji, title, line):
    """Ответ на использование: как у остальных предметов Кута. Знак, имя, короткая цитата."""
    mark = str(emoji or "").strip()
    head = ((mark + " ") if mark else "") + "<b>" + _plain(title or ITEM_WORD) + "</b>"
    quote = _plain(line)
    if not quote:
        return head
    return head + "\n<blockquote><b>" + quote + "</b></blockquote>"
