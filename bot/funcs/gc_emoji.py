# -*- coding: utf-8 -*-
"""Premium-эмодзи для системы игровых заданий (GC / челленджи).

Текст:  <tg-emoji emoji-id='…'>🌴</tg-emoji>
Кнопка: icon_custom_emoji_id=…, text без unicode-эмодзи.
Стиль кнопок — default (без primary).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardButton

# emoji → custom emoji id (из ТЗ)
GC_PREMIUM: Dict[str, str] = {
    "🐬": "5362063083311214432",
    "🦋": "5445096582238181549",
    "⚠️": "5213205860498549992",
    "⚠": "5213205860498549992",
    "💰": "5224257782013769471",
    "🏝": "5253567918741923731",
    "🏝️": "5253567918741923731",
    "🔙": "5255703720078879038",
    "❓": "5436113877181941026",
    "🍻": "5264737672684907396",
    "🎯": "5350460637182993292",
    "💦": "5460846081283740006",
    "💎": "5280922999241859582",
    "🥀": "5208923808169222461",
    "🏕": "5359636199155704118",
    "🏕️": "5359636199155704118",
    "🌴": "5449372007432985754",
    # доп. пак для системы заданий
    "🎮": "5386473766161238258",
    "📋": "6021435576513730578",
    "📍": "5321275372333979355",
    "🧾": "5444856076954520455",
    "🗓": "5413879192267805083",
    "📅": "5413879192267805083",
    "♻️": "5389044097929460525",
    "🔜": "5253767677670862169",
    # 🏜 в UI → premium 🍁
    "🏜": "5281026503658728615",
    "🏜️": "5281026503658728615",
    "🍁": "5281026503658728615",
    "✅": "5260463209562776385",
    "🕊": "5350682188775965398",
    "🕊️": "5350682188775965398",
    "⛵️": "5188322825735267247",
    "⛵": "5188322825735267247",
    "🍹": "5361684086807076580",
    # доп. пак #2
    "🔧": "5462921117423384478",
    "🛠": "5462921117423384478",
    "🛠️": "5462921117423384478",
    "❗": "5274099962655816924",
    "❗️": "5274099962655816924",
    "❕": "5274099962655816924",
    "📩": "5253742260054409879",
    "✉️": "5253742260054409879",
    "✉": "5253742260054409879",
    "☁️": "5006123161918374529",
    "☁": "5006123161918374529",
    "💼": "5208670581192411812",
    "🔥": "5420315771991497307",
    "📌": "5213260226194583825",
    "⭐️": "6005661956931850799",
    "⭐": "6005661956931850799",
    # 🔒 в UI → premium 🔓
    "🔒": "5429405838345265327",
    "🔓": "5429405838345265327",
    "📊": "5231200819986047254",
    "🏆": "5188344996356448758",
    "🎲": "5384474763827620477",
    "⛱": "5388885025225739902",
    "⛱️": "5388885025225739902",
    "↩️": "5895507195524550741",
}

# В <tg-emoji>…</tg-emoji> иногда нужен другой fallback-символ, чем в исходнике
GC_FACE_OVERRIDE: Dict[str, str] = {
    "🏜": "🍁",
    "🏜️": "🍁",
    "🔧": "🛠",
    "📩": "✉️",
    "✉": "✉️",
    "🔒": "🔓",
}

# Длинные ключи первыми (⚠ vs ⚠️, 🏝 vs 🏝️)
_GC_EMOJI_KEYS = sorted(GC_PREMIUM.keys(), key=len, reverse=True)


def gc_emoji_id(emoji: str) -> Optional[str]:
    e = str(emoji or "")
    if e in GC_PREMIUM:
        return GC_PREMIUM[e]
    e2 = e.replace("\ufe0f", "")
    return GC_PREMIUM.get(e2)


def gc_tg(emoji: str) -> str:
    """HTML premium emoji для текста сообщений."""
    eid = gc_emoji_id(emoji)
    raw = str(emoji or "")
    if not eid:
        return raw
    # В разметке оставляем «короткий» символ без VS16, если есть
    face = GC_FACE_OVERRIDE.get(raw) or GC_FACE_OVERRIDE.get(raw.replace("\ufe0f", ""))
    if not face:
        face = raw.replace("\ufe0f", "") or raw
    return f"<tg-emoji emoji-id='{eid}'>{face}</tg-emoji>"


def gc_split_leading(text: str) -> Tuple[Optional[str], str]:
    """Отделяет ведущий известный GC-эмодзи от подписи кнопки."""
    s = str(text or "").lstrip()
    for em in _GC_EMOJI_KEYS:
        if s.startswith(em):
            rest = s[len(em):].lstrip(" \u00a0·|-–—")
            return em, (rest or "\u200b")
    return None, str(text or "")


def gc_strip_known(text: str) -> Tuple[Optional[str], str]:
    """Первый известный эмодзи → icon; все известные unicode убираем из подписи.

    Нужно для кейсов вроде «⚠️ 🍻 100 → 500», где после warning остаётся
    второй premium-эмодзи в тексте кнопки.
    """
    s = str(text or "")
    first: Optional[str] = None
    out: List[str] = []
    i = 0
    n = len(s)
    while i < n:
        matched = False
        for em in _GC_EMOJI_KEYS:
            if s.startswith(em, i):
                if first is None:
                    first = em
                i += len(em)
                # схлопываем хвостик-разделители после вырезанного эмодзи
                while i < n and s[i] in " \u00a0·|-–—":
                    i += 1
                matched = True
                break
        if not matched:
            out.append(s[i])
            i += 1
    label = "".join(out).strip()
    return first, (label or "\u200b")


def gc_btn(
    text: str,
    *,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    style: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None,
) -> InlineKeyboardButton:
    """Кнопка GC: unicode-эмодзи → icon_custom_emoji_id; всегда style=default."""
    lead, label = gc_strip_known(text)
    eid = icon_custom_emoji_id or (gc_emoji_id(lead) if lead else None)
    # style-аргумент игнорируем: в системе заданий primary не используем
    _ = style

    kwargs: Dict[str, Any] = {
        "text": label if eid else str(text or "·"),
        "style": "default",
    }
    if eid:
        kwargs["icon_custom_emoji_id"] = eid
    if url:
        kwargs["url"] = url
    elif callback_data is not None:
        kwargs["callback_data"] = callback_data

    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        try:
            return InlineKeyboardButton(**kwargs)
        except TypeError:
            kwargs.pop("icon_custom_emoji_id", None)
            if eid and lead:
                kwargs["text"] = f"{lead} {label}".strip()
            return InlineKeyboardButton(**kwargs)


def gc_html_replace_known(text: str) -> str:
    """Заменяет известные unicode-эмодзи в HTML-тексте на <tg-emoji>…</tg-emoji>.

    Не трогает уже существующие <tg-emoji …>.
    """
    s = str(text or "")
    if not s:
        return s
    # Пропускаем уже обёрнутые: грубая защита — не трогаем emoji-id= участки
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s.startswith("<tg-emoji", i):
            j = s.find("</tg-emoji>", i)
            if j == -1:
                out.append(s[i:])
                break
            out.append(s[i:j + len("</tg-emoji>")])
            i = j + len("</tg-emoji>")
            continue
        matched = False
        for em in _GC_EMOJI_KEYS:
            if s.startswith(em, i):
                out.append(gc_tg(em))
                i += len(em)
                matched = True
                break
        if not matched:
            out.append(s[i])
            i += 1
    return "".join(out)
