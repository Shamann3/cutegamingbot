# -*- coding: utf-8 -*-
"""Лёгкая групповая капча: один раз в группе навсегда, premium-эмодзи, HMAC."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger("group_captcha")

TG_EMOJI_RE = re.compile(
    r"<tg-emoji\s+[^>]*emoji-id=['\"](\d{5,32})['\"][^>]*>(.*?)</tg-emoji>",
    re.I | re.S,
)
EMOJI_ID_RE = re.compile(r"(\d{5,32})")
TOKEN_RE = re.compile(r"\{emoji:(\d{5,32})\}", re.I)
# В теге нужен настоящий fallback-символ: иначе Telegram не создаёт custom_emoji
# и клиент рисует обычный смайл (или пустоту). На кнопке unicode не ставим —
# премиум идёт только через icon_custom_emoji_id, как в gc_emoji / king_stats.
ICON_ONLY_TEXT = " "

CHALLENGE_TTL_SEC = 30 * 60
DISABLE_ICON = "<tg-emoji emoji-id='5462990652943904884'>✨</tg-emoji>"
DISABLE_ALERT = (
    "Капчу в группе может отключить только владелец чата.\n"
    "Если вам действительно мешает капча — попросите создателя группы отключить её"
)
PASS_ALERT = "Капча пройдена успешно!"
PASS_HTML = "<tg-emoji emoji-id='5348423147647414077'>🤩</tg-emoji> <b>Капча пройдена успешно!</b>"
PASS_EMOJI_ID = "5348423147647414077"
NEXT_ALERT = "Верно. Теперь нажмите вторую кнопку"
GATE_ALERT = (
    "Сначала пройдите капчу в этой группе. "
    "После этого игровые кнопки заработают"
)
CLICK_DB_TIMEOUT_SEC = 1.6

# --- Фоновая очистка просроченных карточек -------------------------------
CLEANUP_INTERVAL_SEC = 60     # как часто просыпается воркер
CLEANUP_BATCH = 200           # максимум карточек за одну итерацию
ORPHANS_BATCH = 200           # максимум осиротевших сообщений за итерацию

# Справка, закрытие карточек и ссылки наружу — не игра.
# Игровые callback'и (ставки, ходы, меню игр) остаются закрытыми до капчи.
_FREE_CALLBACK_EXACT = frozenset({
    "noop",
})
_FREE_CALLBACK_PREFIXES = (
    "gcA:",
    "gcX:",
    "help_",
    "9help_",
    "deletehelp",
    "twogreet_cut",
    "starthowtoplay",
    "9close_bonus",
    "about_start",
    "3412helpstarthelp",
    "store_close",
    "close_message",
)


def is_free_callback(data: str) -> bool:
    """True — кнопку можно нажать до прохождения капчи."""
    raw = str(data or "")
    if raw in _FREE_CALLBACK_EXACT:
        return True
    return raw.startswith(_FREE_CALLBACK_PREFIXES)


CAPTCHA_INTRO_LINE1 = "Это капча."
CAPTCHA_INTRO_LINE2 = "Чтобы писать в группе, пожалуйста, выполните задание ниже."
CAPTCHA_INTRO = f"{CAPTCHA_INTRO_LINE1}\n{CAPTCHA_INTRO_LINE2}"
INTRO_EYE_ID = "5389099803655305880"
INTRO_WARN_ID = "6025996269141364975"
INTRO_LINE1_CHUNKS = (
    {"kind": "text", "value": CAPTCHA_INTRO_LINE1},
)
INTRO_LINE2_CHUNKS = (
    {"kind": "text", "value": CAPTCHA_INTRO_LINE2},
)

VARIANT_LABELS = {
    1: "Найдите такое же",
    2: "Цвет",
    4: "Птица / картошка / чемодан",
    5: "Сторона",
}
ACTIVE_VARIANTS = (1, 2, 4, 5)

# Канон в кавычках подсказки. Алиасы — всё, что код принимает как этот ответ.
CHAT_OPTION = {
    "shield": ("щит", (
        "щит", "щитом", "щита", "щите", "щиту", "щиток", "щитком",
        "защита", "защиту", "защитой", "защите", "щитем", "shield",
    )),
    "fire": ("огонь", (
        "огонь", "огня", "огнем", "огнём", "огне", "пламя", "пламени", "пламенем",
        "костер", "костёр", "костра", "костре", "огонек", "огонёк", "fire",
    )),
    "diamond": ("алмаз", (
        "алмаз", "алмаза", "алмазом", "алмазу", "алмазе", "алмазик",
        "бриллиант", "бриллианта", "бриллиантом", "камень", "камня", "камнем", "diamond",
    )),
    "red": ("красный", (
        "красный", "красное", "красная", "красную", "красным", "красного",
        "красненький", "красненькое", "алый", "алое", "алая", "red",
    )),
    "green": ("зелёный", (
        "зеленый", "зелёный", "зеленое", "зелёное", "зеленая", "зелёная",
        "зеленую", "зелёную", "зеленым", "зелёным", "зеленого", "зелёного",
        "зелененький", "зелененькое", "green",
    )),
    "blue": ("синий", (
        "синий", "синее", "синяя", "синюю", "синим", "синего",
        "синенький", "синенькое", "голубой", "голубое", "голубая", "голубую", "blue",
    )),
    "living": ("птица", (
        "птица", "птицу", "птицы", "птицей", "птице", "птичка", "птичку", "птички",
        "голубь", "голубя", "голубок", "живое", "живого", "живой", "животное", "living",
    )),
    "food": ("картошка", (
        "картошка", "картошку", "картошки", "картошкой", "картошке", "картошечка",
        "картофель", "картофеля", "картоху", "фри", "еда", "еду", "едой", "еды", "food",
    )),
    "thing": ("чемодан", (
        "чемодан", "чемодана", "чемоданом", "чемодану", "чемодане", "чемоданчик",
        "багаж", "багажа", "вещь", "вещи", "вещью", "предмет", "предмета", "thing",
    )),
    "left": ("налево", (
        "налево", "на лево", "влево", "в лево", "лево", "левая", "левую", "левой",
        "левое", "слева", "левее", "left",
    )),
    "right": ("направо", (
        "направо", "на право", "вправо", "в право", "право", "правая", "правую", "правой",
        "правое", "справа", "правее", "right",
    )),
    "happy": ("весёлый", ("веселый", "весёлый", "веселое", "весёлое", "веселая", "весёлая", "радость", "радостный", "смех", "смеется", "смеётся", "happy")),
    "sad": ("грустный", ("грустный", "грустное", "грустная", "грусть", "печаль", "печальный", "грущу", "sad")),
    "angry": ("злой", ("злой", "злое", "злая", "злость", "злой", "сердитый", "сердитое", "злюсь", "angry")),
    "sun": ("солнце", ("солнце", "солнца", "солнцем", "солнышко", "солнцу", "sun")),
    "moon": ("луна", ("луна", "луну", "луны", "луной", "луне", "месяц", "месяца", "moon")),
    "earth": ("земля", ("земля", "землю", "земли", "землей", "землёй", "земле", "earth")),
}

_CHAT_FILLERS = frozenset({
    "на", "кнопку", "кнопка", "значок", "значком", "эмодзи", "смайл", "сначала",
    "потом", "затем", "после", "этого", "напишите", "напиши", "в", "чат", "или",
    "ответьте", "ответ", "нажмите", "нажать", "нужно", "надо", "пожалуйста",
    "это", "эта", "этот", "наверное", "думаю", "кажется", "будет", "вот",
    "точно", "может", "мне", "правильный", "вариант", "капча", "задание",
    "здесь", "тут", "отвечаю", "пишу", "значит", "типа", "как", "будто",
    "похоже", "скорее", "всего", "да", "ну", "же", "бы", "ли", "просто",
    "только", "кнопке", "кнопки", "значка", "цвет", "цвета", "цветом",
    "сторону", "сторона", "направление",
})
_CHAT_SPLIT = re.compile(
    r"(?:,|;|/|\s+(?:и затем|а затем|затем|а потом|и потом|потом|после этого|и)\s+)",
    re.I,
)
_CHAT_PREFIXES = (
    "или напишите в чат ",
    "напишите в чат ",
    "напиши в чат ",
    "или напиши ",
    "ответ ",
    "ответь ",
)

# Сырые теги — источник правды. Код сам достаёт id и fallback.
EMOJI = {
    "v1_prefix": "<tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji>",
    "shield": "<tg-emoji emoji-id='5449913031578379785'>🛡</tg-emoji>",
    "fire": "<tg-emoji emoji-id='5445110875889360215'>🔥</tg-emoji>",
    "diamond": "<tg-emoji emoji-id='5231463873848039753'>💎</tg-emoji>",
    "v2_prefix": "<tg-emoji emoji-id='5190806721286657692'>📊</tg-emoji>",
    "red": "<tg-emoji emoji-id='5296773795091094130'>🔴</tg-emoji>",
    "blue": "<tg-emoji emoji-id='5280922999241859582'>🔵</tg-emoji>",
    "green": "<tg-emoji emoji-id='5260300580626125837'>🟢</tg-emoji>",
    "gift": "<tg-emoji emoji-id='5379767475376270474'>🎁</tg-emoji>",
    "star": "<tg-emoji emoji-id='5363817495847279825'>⭐️</tg-emoji>",
    "dollar": "<tg-emoji emoji-id='5366356315440456875'>💲</tg-emoji>",
    "v4_prefix": "<tg-emoji emoji-id='5391209710634433397'>🎁</tg-emoji>",
    "living": "<tg-emoji emoji-id='5434121252874756456'>🕊</tg-emoji>",
    "food": "<tg-emoji emoji-id='5242583325134048374'>🍟</tg-emoji>",
    "thing": "<tg-emoji emoji-id='5839260716132995098'>🧳</tg-emoji>",
    "v5_prefix": "<tg-emoji emoji-id='5458669860009554206'>🚶</tg-emoji>",
    "left": "<tg-emoji emoji-id='5472370131373923279'>🫲</tg-emoji>",
    "right": "<tg-emoji emoji-id='5472348819746200625'>🫱</tg-emoji>",
    "v6_prefix": "<tg-emoji emoji-id='5170212941512837033'>🥰</tg-emoji>",
    "happy": "<tg-emoji emoji-id='5170244028486124162'>😂</tg-emoji>",
    "sad": "<tg-emoji emoji-id='5168219024420504223'>😔</tg-emoji>",
    "angry": "<tg-emoji emoji-id='5170607378424398392'>🤬</tg-emoji>",
    "v7_prefix": "<tg-emoji emoji-id='5283075860188898177'>🌤</tg-emoji>",
    "sun": "<tg-emoji emoji-id='5458770512568132268'>☀️</tg-emoji>",
    "moon": "<tg-emoji emoji-id='5195033767969839232'>🌙</tg-emoji>",
    "earth": "<tg-emoji emoji-id='6188045471118790922'>🌍</tg-emoji>",
    "v8_prefix": "<tg-emoji emoji-id='5461152608804689572'>⚖️</tg-emoji>",
    "berry": "<tg-emoji emoji-id='5406759193052995173'>🍒</tg-emoji>",
    "spark": "<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji>",
    "intro_eye": f"<tg-emoji emoji-id='{INTRO_EYE_ID}'>👁️</tg-emoji>",
    "intro_warn": f"<tg-emoji emoji-id='{INTRO_WARN_ID}'>👁</tg-emoji>",
    "disable": DISABLE_ICON,
}


@dataclass(frozen=True)
class PremiumEmoji:
    emoji_id: str
    face: str
    html: str

    def as_html(self) -> str:
        if not self.emoji_id:
            return ""
        return _premium_html(self.emoji_id, self.face)

    def as_plain(self) -> str:
        return self.face or ""


def _premium_html(eid: str, face: str = "") -> str:
    inner = (face or "").strip() or "•"
    return f"<tg-emoji emoji-id='{eid}'>{inner}</tg-emoji>"


def parse_premium_emoji(raw: Any, fallback_face: str = "•") -> PremiumEmoji:
    """Достаёт Telegram premium emoji-id из тега, {emoji:ID} или голого числа."""
    if isinstance(raw, PremiumEmoji):
        return raw
    s = str(raw or "").strip()
    if not s:
        return PremiumEmoji("", fallback_face, "")

    m = TG_EMOJI_RE.search(s)
    if m:
        face = re.sub(r"<[^>]+>", "", m.group(2) or "").strip() or fallback_face
        if face in {"\u2060", "\u200b", "•"}:
            face = fallback_face
        eid = m.group(1)
        return PremiumEmoji(eid, face, _premium_html(eid, face))

    m = TOKEN_RE.search(s)
    if m:
        eid = m.group(1)
        return PremiumEmoji(eid, fallback_face, _premium_html(eid, fallback_face))

    m = re.search(r"emoji-id\s*=\s*['\"](\d{5,32})['\"]", s, re.I)
    if m:
        eid = m.group(1)
        return PremiumEmoji(eid, fallback_face, _premium_html(eid, fallback_face))

    digits = EMOJI_ID_RE.fullmatch(s)
    if digits:
        eid = digits.group(1)
        return PremiumEmoji(eid, fallback_face, _premium_html(eid, fallback_face))

    return PremiumEmoji("", s[:8] or fallback_face, "")


def emoji(key: str) -> PremiumEmoji:
    return parse_premium_emoji(EMOJI[key], fallback_face=key)


def _secret() -> bytes:
    raw = (os.environ.get("CAPTCHA_HMAC_SECRET") or "").strip()
    if not raw:
        try:
            from bot.config.config import TOKEN
            raw = f"group-captcha-v1:{TOKEN}"
        except Exception:
            raw = "group-captcha-v1-dev"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def sign_parts(*parts: Any) -> str:
    msg = ":".join(str(p) for p in parts).encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:10]


def check_sign(mac: str, *parts: Any) -> bool:
    expected = sign_parts(*parts)
    return hmac.compare_digest(expected, str(mac or ""))


def _button_label(text: Optional[str]) -> str:
    """Telegram не принимает пустой text. Для иконки — ровно один пробел, без unicode-лица."""
    if text is None:
        return ICON_ONLY_TEXT
    label = str(text)
    return label if label else ICON_ONLY_TEXT


def premium_button(
    item: PremiumEmoji,
    callback_data: str,
    *,
    style: Optional[str] = None,
    text: Optional[str] = None,
    plain: bool = False,
):
    """Только премиум-иконка. Текст кнопки — пробел, если свой текст не задан."""
    _ = plain
    from aiogram.types import InlineKeyboardButton
    label = _button_label(text)
    kwargs = {"text": label, "callback_data": callback_data}
    eid = str(getattr(item, "emoji_id", "") or "")
    if not eid:
        return InlineKeyboardButton(**kwargs)
    try:
        return InlineKeyboardButton(
            **kwargs,
            style=style or "default",
            icon_custom_emoji_id=eid,
        )
    except TypeError:
        try:
            return InlineKeyboardButton(**kwargs, icon_custom_emoji_id=eid)
        except TypeError:
            return InlineKeyboardButton(**kwargs)


def mention_html(user: Any) -> str:
    uid = int(getattr(user, "id", 0) or 0)
    raw_name = (
        getattr(user, "full_name", None)
        or getattr(user, "first_name", None)
        or "друг"
    )
    name = html.escape(str(raw_name)[:40])
    if uid:
        return f'<a href="tg://user?id={uid}"><b>{name}</b></a>'
    return f"<b>{name}</b>"


def pick_variant(rng: Optional[random.Random] = None) -> int:
    return (rng or random).choice(list(ACTIVE_VARIANTS))


def _mark(answer: str) -> str:
    """Правильный ответ в задании — жирный и подчёркнутый."""
    return f"<u>{answer}</u>"


def _press_chunks(answer: str, *, prefix: str = "Нажмите ", suffix: str = "") -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = [
        {"kind": "text", "value": prefix},
        {"kind": "mark", "value": answer},
    ]
    if suffix:
        chunks.append({"kind": "text", "value": suffix})
    return chunks


def _press_same_icon_chunks() -> List[Dict[str, Any]]:
    return _press_chunks("таким же значком", prefix="Нажмите кнопку с ")


V4_WORDS = {"living": "птица", "food": "картошка", "thing": "чемодан"}
V6_WORDS = {"happy": "весёлый", "sad": "грустный", "angry": "злой"}
V7_ONTO = {"sun": "на солнце", "moon": "на луну", "earth": "на землю"}
_V7_ONTO_LEGACY = {"солнце": "на солнце", "луну": "на луну", "землю": "на землю"}


def _v4_chunks(word: str) -> List[Dict[str, Any]]:
    return _press_chunks(word, prefix="Нажмите на значок, который обозначает ")


def _v6_chunks(word: str) -> List[Dict[str, Any]]:
    return _press_chunks(word, prefix="Нажмите на ", suffix=" эмодзи")


def _v7_onto(key: str, names: Optional[Dict[str, Any]] = None) -> str:
    if key in V7_ONTO:
        return V7_ONTO[key]
    raw = str((names or {}).get(key) or key).strip()
    if raw.startswith("на "):
        return raw
    return _V7_ONTO_LEGACY.get(raw, f"на {raw}" if raw else raw)


def _v7_chunks(first: str, second: str, names: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return [
        {"kind": "text", "value": "Нажмите сначала "},
        {"kind": "mark", "value": _v7_onto(first, names)},
        {"kind": "text", "value": ", затем "},
        {"kind": "mark", "value": _v7_onto(second, names)},
    ]


def _shuffle(keys: Sequence[str], rng: random.Random) -> List[str]:
    out = list(keys)
    r = rng
    for _ in range(4):
        r.shuffle(out)
        if len(set(out)) <= 1:
            break
        # не оставляем исходный порядок, если есть из чего выбрать
        if out != list(keys):
            break
        r.shuffle(out)
    return out


def build_challenge(variant: Optional[int] = None, *, rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """Собирает карточку. Ответ, позиции и (где надо) задание всегда новые."""
    r = rng or random.Random()
    v = int(variant or pick_variant(r))
    if v not in VARIANT_LABELS:
        v = pick_variant(r)

    if v == 1:
        options = _shuffle(["shield", "fire", "diamond"], r)
        correct = r.choice(options)
        target = emoji(correct)
        prefix = emoji("v1_prefix")
        chunks = _press_same_icon_chunks()
        extras = [_emoji_ref(target)]
        return _pack(v, prefix, options, correct, chunks, extras=extras)

    if v == 2:
        colors = ["red", "green", "blue"]
        correct = r.choice(colors)
        options = _shuffle(colors, r)
        words = {"red": "красный", "green": "зелёный", "blue": "синий"}
        prefix = emoji("v2_prefix")
        chunks = _press_chunks(words[correct], suffix=" значок")
        return _pack(v, prefix, options, correct, chunks, extra={"color": words[correct]})

    if v == 4:
        keys = ["living", "food", "thing"]
        correct = r.choice(keys)
        options = _shuffle(keys, r)
        words = V4_WORDS
        prefix = emoji("v4_prefix")
        chunks = _v4_chunks(words[correct])
        return _pack(v, prefix, options, correct, chunks, extra={"ask": words[correct]})

    if v == 5:
        correct = r.choice(["left", "right"])
        options = ["left", "right"]  # места фиксированы
        words = {"left": "налево", "right": "направо"}
        prefix = emoji("v5_prefix")
        chunks = _press_chunks(words[correct], prefix="Нажмите кнопку ")
        return _pack(v, prefix, options, correct, chunks, extra={"side": words[correct]})

    if v == 6:
        keys = ["happy", "sad", "angry"]
        correct = r.choice(keys)
        options = _shuffle(keys, r)
        words = V6_WORDS
        prefix = emoji("v6_prefix")
        chunks = _v6_chunks(words[correct])
        return _pack(v, prefix, options, correct, chunks, extra={"mood": words[correct]})

    if v == 7:
        pool = ["sun", "moon", "earth"]
        first, second = r.sample(pool, 2)
        options = _shuffle(pool, r)
        names = dict(V7_ONTO)
        prefix = emoji("v7_prefix")
        chunks = _v7_chunks(first, second, names)
        return _pack(
            v, prefix, options, first, chunks,
            extra={"sequence": [first, second], "step": 0, "names": names},
        )

    return build_challenge(pick_variant(r), rng=r)


def _emoji_ref(item: PremiumEmoji) -> Dict[str, str]:
    return {"id": item.emoji_id, "face": item.face}


def _chunks_html(chunks: Sequence[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for ch in chunks:
        kind = ch.get("kind")
        if kind == "mark":
            parts.append(_mark(str(ch.get("value") or "")))
        elif kind == "emoji":
            parts.append(_premium_html(str(ch.get("id") or ""), str(ch.get("face") or "")))
        else:
            parts.append(str(ch.get("value") or ""))
    return "".join(parts)


def _pack(
    variant: int,
    prefix: PremiumEmoji,
    options: Sequence[str],
    correct: str,
    chunks: Sequence[Dict[str, Any]],
    *,
    extras: Optional[Sequence[Dict[str, str]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    extras = list(extras or [])
    tail = "".join(f" {_premium_html(e['id'], e['face'])}" for e in extras if e.get("id"))
    text = f"{prefix.as_html()} <b>{_chunks_html(chunks)}</b>{tail}"
    payload = {
        "variant": variant,
        "options": list(options),
        "correct": correct,
        "prefix_id": prefix.emoji_id,
        "prefix_face": prefix.face,
        "chunks": list(chunks),
        "extra_emoji": extras,
        "text": text,
        "step": 0,
        "sequence": [],
    }
    if extra:
        payload.update(extra)
    return payload


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _display_name(user: Any) -> str:
    raw = (
        getattr(user, "full_name", None)
        or getattr(user, "first_name", None)
        or "друг"
    )
    name = re.sub(r"[<>]", "", str(raw)[:40]).strip()
    return name or "друг"


def hydrate_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Достраивает старые карточки из БД, чтобы премиум и задание не терялись."""
    data = dict(payload or {})
    if not data.get("prefix_face") and data.get("prefix_id"):
        data["prefix_face"] = _face_by_id(str(data["prefix_id"]))
    variant = int(data.get("variant") or 0)
    if variant == 1 and not data.get("extra_emoji"):
        key = str(data.get("correct") or "")
        if key in EMOJI:
            data["extra_emoji"] = [_emoji_ref(emoji(key))]
    if data.get("chunks"):
        return data
    if variant == 7 and data.get("names") and data.get("sequence"):
        names = data.get("names") or {}
        seq = list(data.get("sequence") or [])
        first = seq[0] if seq else ""
        second = seq[1] if len(seq) > 1 else ""
        data["chunks"] = _v7_chunks(str(first), str(second), names)
        return data
    if variant in {1, 3}:
        data["chunks"] = _press_same_icon_chunks()
        return data
    if data.get("color"):
        data["chunks"] = _press_chunks(str(data["color"]), suffix=" значок")
        return data
    if data.get("ask"):
        data["chunks"] = _v4_chunks(str(data["ask"]))
        return data
    if data.get("side"):
        data["chunks"] = _press_chunks(str(data["side"]), prefix="Нажмите кнопку ")
        return data
    if data.get("mood"):
        mood = str(data["mood"])
        legacy_mood = {"весёлое": "весёлый", "грустное": "грустный", "злое": "злой"}
        data["chunks"] = _v6_chunks(legacy_mood.get(mood, mood))
        return data
    data["chunks"] = [{"kind": "text", "value": "Нажмите верную кнопку"}]
    return data


def card_plain_and_entities(payload: Dict[str, Any], user: Any):
    """Карточка через entities: custom_emoji уходит в Telegram напрямую, не как обычный смайл."""
    from aiogram.enums import MessageEntityType
    from aiogram.types import MessageEntity

    payload = hydrate_payload(payload)
    buf: List[str] = []
    ents: List[Any] = []

    def add(s: str) -> Tuple[int, int]:
        start = _utf16_len("".join(buf))
        buf.append(s)
        return start, _utf16_len(s)

    name = _display_name(user)
    start, ln = add(name)
    uid = int(getattr(user, "id", 0) or 0)
    if uid and ln:
        # text_link надёжнее text_mention: не зависит от полной сериализации User.
        ents.append(MessageEntity(
            type=MessageEntityType.TEXT_LINK,
            offset=start,
            length=ln,
            url=f"tg://user?id={uid}",
        ))
        ents.append(MessageEntity(type=MessageEntityType.BOLD, offset=start, length=ln))

    add("\n")
    _add_rich_line(add, ents, emoji("intro_eye"), INTRO_LINE1_CHUNKS)
    add("\n")
    _add_rich_line(add, ents, emoji("intro_warn"), INTRO_LINE2_CHUNKS)
    add("\n\n")

    prefix_id = str(payload.get("prefix_id") or "")
    prefix_face = str(payload.get("prefix_face") or "")
    prefix_icon = PremiumEmoji(prefix_id, prefix_face, "") if prefix_id and prefix_face else None
    _add_rich_line(add, ents, prefix_icon, payload.get("chunks") or [])

    for extra in payload.get("extra_emoji") or []:
        if not extra.get("id") or not extra.get("face"):
            continue
        add(" ")
        start, ln = add(str(extra["face"]))
        ents.append(MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=start,
            length=ln,
            custom_emoji_id=str(extra["id"]),
        ))

    hint = chat_hint_line(payload)
    if hint:
        add("\n")
        start, ln = add(hint)
        if ln:
            ents.append(MessageEntity(type=MessageEntityType.BOLD, offset=start, length=ln))
            block = getattr(MessageEntityType, "BLOCKQUOTE", None)
            if block is not None:
                ents.append(MessageEntity(type=block, offset=start, length=ln))

    return "".join(buf), ents


def _add_rich_line(
    add,
    ents,
    icon: Optional[PremiumEmoji],
    chunks: Sequence[Dict[str, Any]],
) -> None:
    from aiogram.enums import MessageEntityType
    from aiogram.types import MessageEntity

    if icon and icon.emoji_id and icon.face:
        start, ln = add(icon.face)
        ents.append(MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=start,
            length=ln,
            custom_emoji_id=icon.emoji_id,
        ))
        add(" ")

    bold_start, _ = add("")
    for ch in chunks:
        kind = ch.get("kind")
        if kind == "mark":
            start, ln = add(str(ch.get("value") or ""))
            if ln:
                ents.append(MessageEntity(type=MessageEntityType.UNDERLINE, offset=start, length=ln))
        elif kind == "emoji" and ch.get("id") and ch.get("face"):
            start, ln = add(str(ch["face"]))
            ents.append(MessageEntity(
                type=MessageEntityType.CUSTOM_EMOJI,
                offset=start,
                length=ln,
                custom_emoji_id=str(ch["id"]),
            ))
        else:
            add(str(ch.get("value") or ""))
    bold_end, _ = add("")
    bold_len = bold_end - bold_start
    if bold_len > 0:
        ents.append(MessageEntity(type=MessageEntityType.BOLD, offset=bold_start, length=bold_len))


def card_html(payload: Dict[str, Any], user: Any) -> str:
    # Не оборачиваем mention и tg-emoji в ещё один <b>: Telegram ломает вложенный bold.
    body = str(payload.get("text") or "<b>Нажмите верную кнопку</b>")
    who = mention_html(user)
    intro = (
        f"{emoji('intro_eye').as_html()} <b>{_chunks_html(INTRO_LINE1_CHUNKS)}</b>\n"
        f"{emoji('intro_warn').as_html()} <b>{_chunks_html(INTRO_LINE2_CHUNKS)}</b>"
    )
    hint = html.escape(chat_hint_line(payload), quote=False)
    quote = f"<blockquote><b>{hint}</b></blockquote>" if hint else ""
    return f"{who}\n{intro}\n\n{body}\n{quote}"


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def to_plain_text(raw: str) -> str:
    """Последний запасной вариант, если HTML Telegram отверг целиком."""
    s = html_to_faces(raw or "")
    s = _HTML_TAG_RE.sub("", s)
    return html.unescape(s).strip()


def answer_callback_data(challenge_id: int, pick: str) -> str:
    mac = sign_parts("a", int(challenge_id), pick)
    return f"gcA:{int(challenge_id)}:{pick}:{mac}"


def disable_callback_data(chat_id: int) -> str:
    mac = sign_parts("x", int(chat_id))
    return f"gcX:{int(chat_id)}:{mac}"


def parse_answer_callback(data: str) -> Optional[Tuple[int, str, str]]:
    parts = str(data or "").split(":")
    if len(parts) != 4 or parts[0] != "gcA":
        return None
    try:
        return int(parts[1]), parts[2], parts[3]
    except (TypeError, ValueError):
        return None


def parse_disable_callback(data: str) -> Optional[Tuple[int, str]]:
    parts = str(data or "").split(":")
    if len(parts) != 3 or parts[0] != "gcX":
        return None
    try:
        return int(parts[1]), parts[2]
    except (TypeError, ValueError):
        return None


def resolve_click_chat_id(row: Dict[str, Any], message_chat_id: Optional[int]) -> int:
    """Реальный чат клика важнее id из БД: новая группа часто мигрирует в супергруппу."""
    db_id = int(row.get("chat_id") or 0)
    if not message_chat_id:
        return db_id
    msg_id = int(message_chat_id)
    return msg_id or db_id


def build_markup(challenge_id: int, chat_id: int, payload: Dict[str, Any], *, plain: bool = False):
    from aiogram.types import InlineKeyboardMarkup
    rows: List[List[Any]] = []
    option_row: List[Any] = []
    for key in payload.get("options") or []:
        item = emoji(str(key))
        option_row.append(premium_button(
            item, answer_callback_data(challenge_id, str(key)), plain=plain,
        ))
    if option_row:
        rows.append(option_row)
    disable = emoji("disable")
    rows.append([
        premium_button(
            disable,
            disable_callback_data(chat_id),
            style="primary",
            text="Убрать капчу",
            plain=plain,
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def is_correct_pick(payload: Dict[str, Any], pick: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Возвращает ('pass' | 'fail' | 'next', новый payload или None).
    Для варианта 7 первый верный шаг даёт 'next'.
    """
    variant = int(payload.get("variant") or 0)
    pick = str(pick or "")
    if variant == 7:
        seq = list(payload.get("sequence") or [])
        step = int(payload.get("step") or 0)
        if step < 0 or step >= len(seq):
            return "fail", None
        if pick != str(seq[step]):
            return "fail", None
        nxt = dict(payload)
        nxt["step"] = step + 1
        if nxt["step"] >= len(seq):
            return "pass", nxt
        return "next", nxt
    if pick == str(payload.get("correct") or ""):
        return "pass", payload
    return "fail", None


def _fold_chat(text: str) -> str:
    s = str(text or "").replace("\u00a0", " ").strip().lower().replace("ё", "е")
    s = re.sub(r"[«»„“‟\"'`]+", "", s)
    s = re.sub(r"[.!?…]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" \t,;:-—")
    return s


def chat_hint_quoted(payload: Dict[str, Any]) -> str:
    """Строка в кавычках: Или напишите в чат \"…\"."""
    data = hydrate_payload(payload)
    variant = int(data.get("variant") or 0)
    if variant == 7:
        seq = [str(x) for x in (data.get("sequence") or []) if x]
        parts = [CHAT_OPTION.get(k, (k, ()))[0] for k in seq]
        return ", ".join(parts)
    key = str(data.get("correct") or "")
    if key in CHAT_OPTION:
        return CHAT_OPTION[key][0]
    for field in ("color", "ask", "side", "mood"):
        if data.get(field):
            return str(data[field])
    return key


def chat_hint_line(payload: Dict[str, Any]) -> str:
    quoted = chat_hint_quoted(payload)
    return f'Или напишите в чат "{quoted}"'


def option_aliases(key: str) -> set:
    key = str(key or "")
    names = {_fold_chat(key)}
    if key in CHAT_OPTION:
        hint, aliases = CHAT_OPTION[key]
        names.add(_fold_chat(hint))
        names.update(_fold_chat(a) for a in aliases)
    if key in EMOJI:
        face = _fold_chat(emoji(key).face)
        if face:
            names.add(face)
    names.discard("")
    return names


_RU_ENDINGS = (
    "ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими",
    "ый", "ий", "ая", "ое", "ее", "ые", "ие",
    "ом", "ем", "ам", "ям", "ах", "ях", "ов", "ев",
    "ую", "юю", "ой", "ей", "ью",
    "а", "я", "у", "ю", "е", "и", "ы", "о",
)


def _compact_chat(text: str) -> str:
    return _fold_chat(text).replace(" ", "")


def _stems(word: str) -> set:
    word = _compact_chat(word)
    out = {word}
    if len(word) < 4:
        return out
    for end in _RU_ENDINGS:
        if word.endswith(end):
            stem = word[:-len(end)]
            if len(stem) >= 3:
                out.add(stem)
    return out


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _score_token_alias(token: str, alias: str) -> float:
    token = _fold_chat(token)
    alias = _fold_chat(alias)
    if not token or not alias:
        return 0.0
    if token == alias:
        return 1.0
    compact_t = token.replace(" ", "")
    compact_a = alias.replace(" ", "")
    if compact_t == compact_a:
        return 0.99
    if _stems(compact_t) & _stems(compact_a):
        return 0.93
    shorter, longer = (compact_t, compact_a) if len(compact_t) <= len(compact_a) else (compact_a, compact_t)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return 0.86 + 0.08 * (len(shorter) / max(len(longer), 1))
    if len(shorter) >= 5 and shorter in longer:
        return 0.80
    n, m = len(compact_t), len(compact_a)
    if min(n, m) >= 3:
        dist = _levenshtein(compact_t, compact_a)
        if dist == 1 and max(n, m) >= 4:
            return 0.88
        if dist == 2 and min(n, m) >= 6:
            return 0.74
    return 0.0


def _bare_token(token: str) -> str:
    folded = _fold_chat(token)
    if folded.startswith("на ") and folded not in {"налево", "направо"}:
        folded = folded[3:].strip()
    return folded


def resolve_chat_token(token: str, options: Sequence[str]) -> Optional[str]:
    folded = _bare_token(token)
    if not folded:
        return None
    scores: Dict[str, float] = {}
    for key in options:
        best = 0.0
        for alias in option_aliases(str(key)):
            best = max(best, _score_token_alias(folded, alias), _score_token_alias(token, alias))
        scores[str(key)] = best
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    if not ranked or ranked[0][1] < 0.74:
        return None
    winner, top = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else 0.0
    if top < 0.99 and top - runner < 0.12:
        return None
    return winner


def _resolved_picks(tokens: Sequence[str], options: Sequence[str]) -> List[str]:
    found: List[str] = []
    for token in tokens:
        pick = resolve_chat_token(token, options)
        if pick is not None:
            found.append(pick)
    if not found and tokens:
        pick = resolve_chat_token(" ".join(tokens), options)
        if pick is not None:
            found.append(pick)
    return found


def _chat_tokens(text: str) -> List[str]:
    raw = _fold_chat(text)
    for prefix in _CHAT_PREFIXES:
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
            break
    quoted = re.findall(r"\"([^\"]+)\"", str(text or ""))
    if not quoted:
        quoted = re.findall(r"[«„“]([^»”]+)[»”]", str(text or ""))
    if quoted:
        raw = _fold_chat(quoted[-1])
    parts = [p.strip() for p in _CHAT_SPLIT.split(raw) if p and p.strip()]
    if len(parts) <= 1:
        words = [_fold_chat(w) for w in raw.split()]
        words = [w for w in words if w and w not in _CHAT_FILLERS]
        if words:
            parts = words
    cleaned: List[str] = []
    for part in parts:
        item = _bare_token(part)
        bits = [w for w in item.split() if w and w not in _CHAT_FILLERS]
        if not bits:
            continue
        cleaned.extend(bits)
    return cleaned


def match_chat_answer(payload: Dict[str, Any], text: str) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    """Разбор ответа из чата: pass | next | fail | miss."""
    data = hydrate_payload(payload)
    raw = str(text or "").strip()
    if not raw:
        return "miss", None, None
    options = [str(x) for x in (data.get("options") or [])]
    if not options:
        return "miss", None, None

    exact = _fold_chat(raw)
    for prefix in _CHAT_PREFIXES:
        if exact.startswith(prefix):
            exact = exact[len(prefix):].strip()
    hint = _fold_chat(chat_hint_quoted(data))
    tokens = _chat_tokens(raw)

    variant = int(data.get("variant") or 0)
    if variant == 7:
        seq = [str(x) for x in (data.get("sequence") or [])]
        step = int(data.get("step") or 0)
        need = seq[step:]
        resolved = _resolved_picks(tokens, options)
        if exact == hint or (resolved and resolved == seq) or (resolved and resolved == need):
            nxt = dict(data)
            nxt["step"] = len(seq)
            return "pass", (need[-1] if need else (seq[-1] if seq else None)), nxt
        if len(resolved) == 1:
            pick = resolved[0]
            status, nxt = is_correct_pick(data, pick)
            return status, pick, nxt
        if resolved:
            return "fail", resolved[0], None
        return "miss", None, None

    if exact == hint or _compact_chat(exact) == _compact_chat(hint):
        pick = str(data.get("correct") or "")
        status, nxt = is_correct_pick(data, pick)
        return status, pick, nxt

    resolved = _resolved_picks(tokens, options)
    unique = list(dict.fromkeys(resolved))
    if len(unique) == 1:
        pick = unique[0]
        status, nxt = is_correct_pick(data, pick)
        return status, pick, nxt
    if len(unique) > 1:
        return "fail", unique[0], None
    return "miss", None, None


SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS group_captcha_settings (
        chat_id BIGINT PRIMARY KEY,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        disabled_at TIMESTAMPTZ,
        disabled_by BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS group_captcha_passes (
        user_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        passed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        variant TEXT NOT NULL,
        attempts INT NOT NULL DEFAULT 1,
        duration_ms INT,
        trigger TEXT,
        PRIMARY KEY (user_id, chat_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_passes_chat_idx
        ON group_captcha_passes (chat_id, passed_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_passes_user_idx
        ON group_captcha_passes (user_id, passed_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS group_captcha_events (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        event TEXT NOT NULL,
        variant TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        meta JSONB
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_events_chat_idx
        ON group_captcha_events (chat_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_events_user_idx
        ON group_captcha_events (user_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_events_kind_idx
        ON group_captcha_events (event, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS group_captcha_challenges (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        message_id BIGINT,
        variant TEXT NOT NULL,
        payload JSONB NOT NULL,
        attempts INT NOT NULL DEFAULT 0,
        trigger TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS group_captcha_challenges_user_chat_idx
        ON group_captcha_challenges (chat_id, user_id)
    """,
    # Ускоряет фоновую чистку просроченных карточек.
    """
    CREATE INDEX IF NOT EXISTS group_captcha_challenges_expires_idx
        ON group_captcha_challenges (expires_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS group_captcha_resets (
        token TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    # Осиротевшие сообщения капчи: перевыпуск карточки в новом сообщении,
    # старое сообщение уже не в challenges, но должно быть удалено.
    """
    CREATE TABLE IF NOT EXISTS group_captcha_orphans (
        id BIGSERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        message_id BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS group_captcha_orphans_chat_idx
        ON group_captcha_orphans (chat_id)
    """,
)

# Один раз сбрасывает «уже прошёл», чтобы капча снова появилась у всех.
# Повторный запуск бота этот токен не повторит.
PASSES_RESET_TOKEN = "2026-09-14-reask-everyone"

_schema_ready = False
_passed_cache: Dict[Tuple[int, int], float] = {}
_not_passed_cache: Dict[Tuple[int, int], float] = {}
_disabled_cache: Dict[int, Tuple[bool, float]] = {}
_live_challenges: Dict[int, Dict[str, Any]] = {}
_live_by_user: Dict[Tuple[int, int], int] = {}
_CACHE_TTL = 90.0
_NOT_PASSED_TTL = 20.0
_seeded_chats: Dict[int, float] = {}
_SEED_TTL = 600.0

# Фоновая задача чистки.
_cleanup_task: Optional[asyncio.Task] = None
_cleanup_stop: Optional[asyncio.Event] = None


def _index_live(stored: Dict[str, Any]) -> None:
    cid = int(stored.get("chat_id") or 0)
    uid = int(stored.get("user_id") or 0)
    hid = int(stored.get("id") or 0)
    if cid and uid and hid:
        _live_by_user[(cid, uid)] = hid


def _drop_live_index(challenge_id: int, row: Optional[Dict[str, Any]] = None) -> None:
    hid = int(challenge_id)
    stored = row or _live_challenges.get(hid)
    if not stored:
        return
    cid = int(stored.get("chat_id") or 0)
    uid = int(stored.get("user_id") or 0)
    if cid and uid and _live_by_user.get((cid, uid)) == hid:
        _live_by_user.pop((cid, uid), None)


def remember_live(row: Optional[Dict[str, Any]]) -> None:
    if not row or not row.get("id"):
        return
    stored = dict(row)
    raw = stored.get("payload")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                stored["payload"] = parsed
        except Exception:
            pass
    hid = int(stored["id"])
    old = _live_challenges.get(hid)
    if old:
        _drop_live_index(hid, old)
    _live_challenges[hid] = stored
    _index_live(stored)


def peek_live(challenge_id: int) -> Optional[Dict[str, Any]]:
    row = _live_challenges.get(int(challenge_id))
    return dict(row) if row else None


def peek_live_user(chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    hid = _live_by_user.get((int(chat_id), int(user_id)))
    if not hid:
        return None
    return peek_live(hid)


def patch_live(challenge_id: int, **fields: Any) -> None:
    row = _live_challenges.get(int(challenge_id))
    if not row:
        return
    if "chat_id" in fields or "user_id" in fields:
        _drop_live_index(int(challenge_id), row)
    row.update(fields)
    _index_live(row)


def forget_live(challenge_id: int) -> None:
    hid = int(challenge_id)
    old = _live_challenges.pop(hid, None)
    if old:
        _drop_live_index(hid, old)


def forget_chat_live(chat_id: int) -> None:
    cid = int(chat_id)
    for key in [k for k, row in _live_challenges.items() if int(row.get("chat_id") or 0) == cid]:
        forget_live(key)


def note_passed(chat_id: int, user_id: int) -> None:
    _cache_pass(int(chat_id), int(user_id))


def strip_tg_emoji(raw: str) -> str:
    return TG_EMOJI_RE.sub(lambda m: (m.group(2) or "").strip(), raw or "")


def text_outside_tg_emoji(raw: str) -> str:
    """Текст карточки без premium-тегов — здесь обычных смайлов быть не должно."""
    return TG_EMOJI_RE.sub("", raw or "")


def _face_by_id(eid: str) -> str:
    for key in EMOJI:
        item = emoji(key)
        if item.emoji_id == str(eid):
            return item.face
    return ""


def html_to_faces(raw: str) -> str:
    """Не для отправки в чат. Нужен тестам и отладке."""
    return TG_EMOJI_RE.sub(lambda m: _face_by_id(m.group(1)), raw or "")


def _clear_pass_memory() -> None:
    _passed_cache.clear()
    _not_passed_cache.clear()
    _live_challenges.clear()
    _live_by_user.clear()
    _seeded_chats.clear()


async def _apply_passes_reset(conn) -> None:
    """Стирает прохождения один раз. История событий в админке остаётся."""
    already = await conn.fetchval(
        "SELECT 1 FROM group_captcha_resets WHERE token = $1",
        PASSES_RESET_TOKEN,
    )
    if already:
        return
    passes = await conn.execute("DELETE FROM group_captcha_passes")
    cards = await conn.execute("DELETE FROM group_captcha_challenges")
    await conn.execute(
        "INSERT INTO group_captcha_resets (token) VALUES ($1)",
        PASSES_RESET_TOKEN,
    )
    _clear_pass_memory()
    print(f"[CAPTCHA] one-shot reset {PASSES_RESET_TOKEN}: {passes} ; {cards}")
    log.warning("captcha one-shot reset applied token=%s passes=%s cards=%s", PASSES_RESET_TOKEN, passes, cards)


async def ensure_tables(pool) -> None:
    global _schema_ready
    if _schema_ready or pool is None:
        return
    async with pool.acquire() as conn:
        for stmt in SCHEMA_SQL:
            await conn.execute(stmt)
        await _apply_passes_reset(conn)
    _schema_ready = True


def _cache_pass(chat_id: int, user_id: int) -> None:
    key = (int(chat_id), int(user_id))
    _passed_cache[key] = time.monotonic()
    _not_passed_cache.pop(key, None)


def _cache_not_passed(chat_id: int, user_id: int) -> None:
    _not_passed_cache[(int(chat_id), int(user_id))] = time.monotonic()


def cached_passed(chat_id: int, user_id: int) -> Optional[bool]:
    key = (int(chat_id), int(user_id))
    ts = _passed_cache.get(key)
    if ts is not None:
        if time.monotonic() - ts <= 3600:
            return True
        _passed_cache.pop(key, None)
    miss = _not_passed_cache.get(key)
    if miss is not None:
        if time.monotonic() - miss <= _NOT_PASSED_TTL:
            return False
        _not_passed_cache.pop(key, None)
    return None


def cached_disabled(chat_id: int) -> Optional[bool]:
    hit = _disabled_cache.get(int(chat_id))
    if not hit:
        return None
    enabled, ts = hit
    if time.monotonic() - ts > _CACHE_TTL:
        _disabled_cache.pop(int(chat_id), None)
        return None
    return (not enabled)


async def is_chat_enabled(pool, chat_id: int) -> bool:
    cached = cached_disabled(chat_id)
    if cached is not None:
        return not cached
    await ensure_tables(pool)
    row = await pool.fetchrow(
        "SELECT enabled FROM group_captcha_settings WHERE chat_id = $1",
        int(chat_id),
    )
    enabled = True if row is None else bool(row["enabled"])
    _disabled_cache[int(chat_id)] = (enabled, time.monotonic())
    return enabled


async def has_passed(pool, chat_id: int, user_id: int) -> bool:
    hit = cached_passed(chat_id, user_id)
    if hit is not None:
        return hit
    await ensure_tables(pool)
    ok = await pool.fetchval(
        "SELECT 1 FROM group_captcha_passes WHERE chat_id = $1 AND user_id = $2",
        int(chat_id),
        int(user_id),
    )
    if ok:
        _cache_pass(chat_id, user_id)
        return True
    _cache_not_passed(chat_id, user_id)
    return False


async def user_needs_captcha(pool, chat_id: int, user_id: int) -> bool:
    """Один кэш/один SQL вместо пары запросов на каждое сообщение."""
    if pool is None:
        return False
    if cached_disabled(chat_id) is True:
        return False
    if cached_passed(chat_id, user_id) is True:
        return False
    if cached_disabled(chat_id) is False and cached_passed(chat_id, user_id) is False:
        return True
    await ensure_tables(pool)
    row = await pool.fetchrow(
        """
        SELECT COALESCE(
                   (SELECT s.enabled FROM group_captcha_settings s WHERE s.chat_id = $1),
                   TRUE
               ) AS enabled,
               EXISTS(
                   SELECT 1 FROM group_captcha_passes p
                    WHERE p.chat_id = $1 AND p.user_id = $2
               ) AS passed
        """,
        int(chat_id),
        int(user_id),
    )
    enabled = True if row is None else bool(row["enabled"])
    passed = False if row is None else bool(row["passed"])
    _disabled_cache[int(chat_id)] = (enabled, time.monotonic())
    if passed:
        _cache_pass(chat_id, user_id)
    else:
        _cache_not_passed(chat_id, user_id)
    return bool(enabled) and not passed


def _chat_title(chat: Any) -> str:
    return str(getattr(chat, "title", None) or "Группа")[:255]


def _chat_username(chat: Any) -> str:
    raw = getattr(chat, "username", None)
    return str(raw)[:64] if raw else "username отсутствует"


async def seed_new_group(pool, chat: Any = None, user: Any = None, *, chat_id: Optional[int] = None) -> None:
    """Заводит группу в captcha-настройках и в chat/memberchat без Telegram API."""
    if pool is None:
        return
    cid = int(getattr(chat, "id", 0) or chat_id or 0)
    if cid >= 0:
        return
    now = time.monotonic()
    ts = _seeded_chats.get(cid)
    if ts is not None and now - ts < _SEED_TTL:
        return
    _seeded_chats[cid] = now
    await ensure_tables(pool)
    try:
        await pool.execute(
            """
            INSERT INTO group_captcha_settings (chat_id, enabled)
            VALUES ($1, TRUE)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            cid,
        )
        if cached_disabled(cid) is None:
            _disabled_cache[cid] = (True, time.monotonic())
    except Exception:
        log.exception("captcha seed settings failed chat=%s", cid)
    title = _chat_title(chat) if chat is not None else "Группа"
    uname = _chat_username(chat) if chat is not None else "username отсутствует"
    try:
        await pool.execute(
            """
            INSERT INTO chat (
                chat_id, namechat, usernamechat, chatlink, description,
                creator_id, creator_name, creator_username, text, data
            )
            VALUES ($1, $2, $3, $4, $5, 0, $6, $7, 0, NOW())
            ON CONFLICT (chat_id) DO NOTHING
            """,
            cid,
            title,
            uname,
            "Приватная ссылка не найдена",
            "Описание отсутствует",
            "Неизвестно",
            "Неизвестно",
        )
    except Exception as e:
        log.warning("captcha seed chat row fallback chat=%s: %s", cid, e)
        try:
            await pool.execute(
                "INSERT INTO chat (chat_id) VALUES ($1) ON CONFLICT (chat_id) DO NOTHING",
                cid,
            )
        except Exception:
            log.exception("captcha seed chat row failed chat=%s", cid)
    uid = int(getattr(user, "id", 0) or 0)
    if uid <= 0:
        return
    name = str(
        getattr(user, "full_name", None) or getattr(user, "first_name", None) or "друг"
    )[:80]
    u_name = str(getattr(user, "username", None) or "")[:64]
    try:
        await pool.execute(
            """
            INSERT INTO memberchat (user_id, name, username, chat_id, chat_name, data)
            SELECT $1, $2, $3, $4, $5, NOW()
             WHERE NOT EXISTS (
                 SELECT 1 FROM memberchat WHERE user_id = $1 AND chat_id = $4
             )
            """,
            uid,
            name,
            u_name,
            cid,
            title,
        )
    except Exception:
        log.warning("captcha seed memberchat failed chat=%s user=%s", cid, uid)


async def remap_chat_id(pool, old_chat_id: int, new_chat_id: int) -> None:
    """Группа стала супергруппой: переносим капчу и строку chat на новый id."""
    old_id, new_id = int(old_chat_id), int(new_chat_id)
    if old_id == new_id or old_id >= 0 or new_id >= 0:
        return
    for hid, row in list(_live_challenges.items()):
        if int(row.get("chat_id") or 0) == old_id:
            patch_live(hid, chat_id=new_id)
    hit = _disabled_cache.pop(old_id, None)
    if hit:
        _disabled_cache[new_id] = hit
    for (cid, uid), ts in list(_passed_cache.items()):
        if cid == old_id:
            _passed_cache.pop((cid, uid), None)
            _passed_cache[(new_id, uid)] = ts
    for (cid, uid), ts in list(_not_passed_cache.items()):
        if cid == old_id:
            _not_passed_cache.pop((cid, uid), None)
            _not_passed_cache[(new_id, uid)] = ts
    _seeded_chats.pop(old_id, None)
    _seeded_chats[new_id] = time.monotonic()
    if pool is None:
        return
    await ensure_tables(pool)
    stmts = (
        """
        INSERT INTO group_captcha_settings (chat_id, enabled, disabled_at, disabled_by)
        SELECT $2, enabled, disabled_at, disabled_by
          FROM group_captcha_settings
         WHERE chat_id = $1
        ON CONFLICT (chat_id) DO NOTHING
        """,
        "UPDATE group_captcha_challenges SET chat_id = $2 WHERE chat_id = $1",
        "UPDATE group_captcha_orphans SET chat_id = $2 WHERE chat_id = $1",
        "UPDATE group_captcha_events SET chat_id = $2 WHERE chat_id = $1",
        """
        INSERT INTO group_captcha_passes
            (user_id, chat_id, passed_at, variant, attempts, duration_ms, trigger)
        SELECT user_id, $2, passed_at, variant, attempts, duration_ms, trigger
          FROM group_captcha_passes
         WHERE chat_id = $1
        ON CONFLICT (user_id, chat_id) DO NOTHING
        """,
    )
    for sql in stmts:
        try:
            await pool.execute(sql, old_id, new_id)
        except Exception:
            log.exception("captcha remap failed chat %s -> %s", old_id, new_id)
    try:
        await pool.execute(
            """
            INSERT INTO chat (
                chat_id, namechat, usernamechat, chatlink, description,
                creator_id, creator_name, creator_username, text, data
            )
            SELECT $2, namechat, usernamechat, chatlink, description,
                   creator_id, creator_name, creator_username, text, NOW()
              FROM chat
             WHERE chat_id = $1
            ON CONFLICT (chat_id) DO NOTHING
            """,
            old_id,
            new_id,
        )
    except Exception:
        try:
            await pool.execute(
                "INSERT INTO chat (chat_id) VALUES ($1) ON CONFLICT (chat_id) DO NOTHING",
                new_id,
            )
        except Exception:
            log.exception("captcha remap chat row failed %s -> %s", old_id, new_id)
    try:
        await pool.execute(
            """
            INSERT INTO memberchat (user_id, name, username, chat_id, chat_name, data)
            SELECT user_id, name, username, $2, chat_name, data
              FROM memberchat
             WHERE chat_id = $1
               AND NOT EXISTS (
                   SELECT 1 FROM memberchat m
                    WHERE m.user_id = memberchat.user_id AND m.chat_id = $2
               )
            """,
            old_id,
            new_id,
        )
    except Exception:
        log.warning("captcha remap memberchat failed %s -> %s", old_id, new_id)
    print(f"[CAPTCHA] remapped chat {old_id} -> {new_id}")


def event_meta(user: Any = None, chat: Any = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Снимок человека и чата — чтобы админка читала историю даже без JOIN."""
    meta: Dict[str, Any] = {}
    if user is not None:
        name = (
            getattr(user, "full_name", None)
            or getattr(user, "first_name", None)
        )
        if name:
            meta["name"] = str(name)[:80]
        uname = getattr(user, "username", None)
        if uname:
            meta["username"] = str(uname)[:64]
    if chat is not None:
        title = getattr(chat, "title", None)
        if title:
            meta["chat"] = str(title)[:80]
        cuser = getattr(chat, "username", None)
        if cuser:
            meta["chat_username"] = str(cuser)[:64]
    if extra:
        for key, value in extra.items():
            if value is not None and value != "":
                meta[key] = value
    return meta


async def log_event(
    pool,
    *,
    user_id: int,
    chat_id: int,
    event: str,
    variant: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    if pool is None:
        log.warning("captcha log_event skipped: no pool event=%s user=%s chat=%s", event, user_id, chat_id)
        return
    await ensure_tables(pool)
    try:
        await pool.execute(
            """
            INSERT INTO group_captcha_events (user_id, chat_id, event, variant, meta)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            int(user_id),
            int(chat_id),
            str(event),
            None if variant is None else str(variant),
            json.dumps(meta or {}, ensure_ascii=False),
        )
    except Exception:
        log.exception(
            "captcha log_event failed event=%s user=%s chat=%s variant=%s",
            event, user_id, chat_id, variant,
        )
        raise


async def disable_chat(pool, chat_id: int, by_user_id: int) -> None:
    await ensure_tables(pool)
    await pool.execute(
        """
        INSERT INTO group_captcha_settings (chat_id, enabled, disabled_at, disabled_by)
        VALUES ($1, FALSE, NOW(), $2)
        ON CONFLICT (chat_id) DO UPDATE
           SET enabled = FALSE,
               disabled_at = NOW(),
               disabled_by = EXCLUDED.disabled_by
        """,
        int(chat_id),
        int(by_user_id),
    )
    _disabled_cache[int(chat_id)] = (False, time.monotonic())
    forget_chat_live(chat_id)
    await pool.execute(
        "DELETE FROM group_captcha_challenges WHERE chat_id = $1",
        int(chat_id),
    )
    await log_event(pool, user_id=by_user_id, chat_id=chat_id, event="disable")


async def mark_passed(
    pool,
    *,
    user_id: int,
    chat_id: int,
    variant: Any,
    attempts: int,
    duration_ms: Optional[int],
    trigger: Optional[str],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    if pool is None:
        log.warning("captcha mark_passed skipped: no pool user=%s chat=%s", user_id, chat_id)
        return
    await ensure_tables(pool)
    packed = {
        "attempts": max(1, int(attempts or 1)),
        "duration_ms": duration_ms,
        "trigger": trigger,
    }
    if meta:
        packed.update(meta)
    try:
        await pool.execute(
            """
            INSERT INTO group_captcha_passes
                (user_id, chat_id, passed_at, variant, attempts, duration_ms, trigger)
            VALUES ($1, $2, NOW(), $3, $4, $5, $6)
            ON CONFLICT (user_id, chat_id) DO NOTHING
            """,
            int(user_id),
            int(chat_id),
            str(variant),
            packed["attempts"],
            duration_ms,
            trigger,
        )
    except Exception:
        log.exception("captcha mark_passed failed user=%s chat=%s", user_id, chat_id)
        raise
    _cache_pass(chat_id, user_id)
    await log_event(
        pool,
        user_id=user_id,
        chat_id=chat_id,
        event="pass",
        variant=variant,
        meta=packed,
    )


async def get_challenge(pool, challenge_id: int) -> Optional[Dict[str, Any]]:
    live = peek_live(challenge_id)
    if live:
        return live
    if pool is None:
        return None
    await ensure_tables(pool)
    try:
        row = await asyncio.wait_for(
            pool.fetchrow(
                "SELECT * FROM group_captcha_challenges WHERE id = $1",
                int(challenge_id),
            ),
            timeout=CLICK_DB_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        log.warning("captcha get_challenge timeout id=%s", challenge_id)
        return None
    if not row:
        return None
    data = dict(row)
    remember_live(data)
    return data


async def get_open_challenge(pool, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    live = peek_live_user(chat_id, user_id)
    if live:
        return live
    await ensure_tables(pool)
    row = await pool.fetchrow(
        """
        SELECT * FROM group_captcha_challenges
         WHERE chat_id = $1 AND user_id = $2
         ORDER BY id DESC
         LIMIT 1
        """,
        int(chat_id),
        int(user_id),
    )
    if not row:
        return None
    data = dict(row)
    remember_live(data)
    return data


async def save_challenge(
    pool,
    *,
    user_id: int,
    chat_id: int,
    payload: Dict[str, Any],
    trigger: str,
    message_id: Optional[int] = None,
    attempts: int = 0,
) -> Dict[str, Any]:
    await ensure_tables(pool)

    # Если у пользователя была карточка с ДРУГИМ message_id, старое сообщение
    # сейчас потеряется из БД — фиксируем его в orphans, чтобы фоновая чистка
    # его подобрала. Один SQL, без гонок.
    if message_id is not None:
        try:
            await pool.execute(
                """
                INSERT INTO group_captcha_orphans (chat_id, message_id)
                SELECT $1, c.message_id
                  FROM group_captcha_challenges c
                 WHERE c.chat_id = $1
                   AND c.user_id = $2
                   AND c.message_id IS NOT NULL
                   AND c.message_id <> $3
                """,
                int(chat_id),
                int(user_id),
                int(message_id),
            )
        except Exception:
            log.exception(
                "captcha save_challenge: orphan mark failed chat=%s user=%s",
                chat_id, user_id,
            )

    expires = datetime.now(timezone.utc).timestamp() + CHALLENGE_TTL_SEC
    expires_dt = datetime.fromtimestamp(expires, tz=timezone.utc)
    row = await pool.fetchrow(
        """
        INSERT INTO group_captcha_challenges
            (user_id, chat_id, message_id, variant, payload, attempts, trigger, expires_at)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
        ON CONFLICT (chat_id, user_id) DO UPDATE
           SET message_id = COALESCE(EXCLUDED.message_id, group_captcha_challenges.message_id),
               variant = EXCLUDED.variant,
               payload = EXCLUDED.payload,
               attempts = EXCLUDED.attempts,
               trigger = EXCLUDED.trigger,
               created_at = NOW(),
               expires_at = EXCLUDED.expires_at
        RETURNING *
        """,
        int(user_id),
        int(chat_id),
        message_id,
        str(payload.get("variant")),
        json.dumps(payload, ensure_ascii=False),
        int(attempts),
        trigger,
        expires_dt,
    )
    data = dict(row)
    remember_live(data)
    return data


async def update_challenge(
    pool,
    challenge_id: int,
    *,
    payload: Optional[Dict[str, Any]] = None,
    message_id: Optional[int] = None,
    attempts: Optional[int] = None,
) -> None:
    await ensure_tables(pool)
    sets = []
    args: List[Any] = []
    if payload is not None:
        args.append(json.dumps(payload, ensure_ascii=False))
        sets.append(f"payload = ${len(args)}::jsonb")
    if message_id is not None:
        args.append(int(message_id))
        sets.append(f"message_id = ${len(args)}")
    if attempts is not None:
        args.append(int(attempts))
        sets.append(f"attempts = ${len(args)}")
    if not sets:
        return
    args.append(int(challenge_id))
    await pool.execute(
        f"UPDATE group_captcha_challenges SET {', '.join(sets)} WHERE id = ${len(args)}",
        *args,
    )
    live_fields: Dict[str, Any] = {}
    if payload is not None:
        live_fields["payload"] = payload
    if message_id is not None:
        live_fields["message_id"] = int(message_id)
    if attempts is not None:
        live_fields["attempts"] = int(attempts)
    if live_fields:
        patch_live(challenge_id, **live_fields)


async def delete_challenge(pool, *, challenge_id: Optional[int] = None, chat_id: Optional[int] = None, user_id: Optional[int] = None) -> None:
    await ensure_tables(pool)
    if challenge_id is not None:
        forget_live(int(challenge_id))
        await pool.execute("DELETE FROM group_captcha_challenges WHERE id = $1", int(challenge_id))
        return
    if chat_id is not None and user_id is not None:
        dead = [
            cid for cid, row in _live_challenges.items()
            if int(row.get("chat_id") or 0) == int(chat_id) and int(row.get("user_id") or 0) == int(user_id)
        ]
        for cid in dead:
            forget_live(cid)
        await pool.execute(
            "DELETE FROM group_captcha_challenges WHERE chat_id = $1 AND user_id = $2",
            int(chat_id),
            int(user_id),
        )


def challenge_expired(row: Dict[str, Any]) -> bool:
    exp = row.get("expires_at")
    if not exp:
        return True
    if getattr(exp, "tzinfo", None) is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= exp


def duration_ms_of(row: Dict[str, Any]) -> Optional[int]:
    created = row.get("created_at")
    if not created:
        return None
    if getattr(created, "tzinfo", None) is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - created).total_seconds() * 1000))


# --------------------------------------------------------------------------
# Фоновая очистка просроченных карточек
# --------------------------------------------------------------------------

# Строки, которые Telegram отдаёт, когда удалять уже нечего или нельзя.
# Их молча пропускаем — это нормальные ситуации, не ошибка бота.
_DELETE_SOFT_ERRORS = (
    "message to delete not found",
    "message can't be deleted",
    "message identifier is not specified",
    "chat not found",
    "bot was kicked",
    "bot is not a member",
    "not enough rights",
    "have no rights",
)


async def _safe_delete_message(bot, chat_id: int, message_id: int) -> bool:
    """
    Пытается удалить сообщение. Возвращает True, если «удалено или уже нет».
    Никогда не бросает наружу — воркер должен жить даже при ошибках Telegram.
    """
    if bot is None or not chat_id or not message_id:
        return False
    try:
        from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
    except Exception:
        TelegramAPIError = TelegramBadRequest = TelegramForbiddenError = ()  # type: ignore

    try:
        await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
        return True
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if any(s in text for s in _DELETE_SOFT_ERRORS):
            log.debug(
                "captcha cleanup: message already gone chat=%s msg=%s (%s)",
                chat_id, message_id, exc,
            )
            return True
        log.warning(
            "captcha cleanup: delete failed chat=%s msg=%s: %s",
            chat_id, message_id, exc,
        )
        return False


async def _cleanup_expired_challenges(pool, bot, *, limit: int = CLEANUP_BATCH) -> int:
    rows = await pool.fetch(
        """
        SELECT id, chat_id, message_id
          FROM group_captcha_challenges
         WHERE expires_at <= NOW()
         ORDER BY expires_at ASC
         LIMIT $1
        """,
        int(limit),
    )
    if not rows:
        return 0

    ids: List[int] = []
    for r in rows:
        cid = int(r["id"])
        ids.append(cid)
        forget_live(cid)
        mid = r["message_id"]
        if mid:
            await _safe_delete_message(bot, int(r["chat_id"]), int(mid))

    # Запись из БД убираем в любом случае: даже если удалить сообщение не вышло
    # (нет прав и т.п.), карточка уже просрочена и жить в БД не должна.
    await pool.execute(
        "DELETE FROM group_captcha_challenges WHERE id = ANY($1::bigint[])",
        ids,
    )
    return len(ids)


async def _cleanup_orphans(pool, bot, *, limit: int = ORPHANS_BATCH) -> int:
    rows = await pool.fetch(
        """
        SELECT id, chat_id, message_id
          FROM group_captcha_orphans
         ORDER BY id ASC
         LIMIT $1
        """,
        int(limit),
    )
    if not rows:
        return 0
    ids: List[int] = []
    for r in rows:
        ids.append(int(r["id"]))
        await _safe_delete_message(bot, int(r["chat_id"]), int(r["message_id"]))
    await pool.execute(
        "DELETE FROM group_captcha_orphans WHERE id = ANY($1::bigint[])",
        ids,
    )
    return len(ids)


async def cleanup_expired(pool, bot, *, limit: int = CLEANUP_BATCH) -> int:
    """
    Один проход фоновой чистки: просроченные карточки + осиротевшие сообщения.
    Возвращает суммарное число обработанных записей.
    """
    if pool is None or bot is None:
        return 0
    await ensure_tables(pool)
    removed = 0
    try:
        removed += await _cleanup_expired_challenges(pool, bot, limit=limit)
    except Exception:
        log.exception("captcha cleanup: expired challenges pass failed")
    try:
        removed += await _cleanup_orphans(pool, bot, limit=limit)
    except Exception:
        log.exception("captcha cleanup: orphans pass failed")
    if removed:
        log.info("captcha cleanup: removed=%s", removed)
    return removed


async def expire_challenge_now(pool, bot, row: Optional[Dict[str, Any]]) -> None:
    """
    Мгновенно удаляет просроченную карточку.
    Удобно звать из обработчика клика, если challenge_expired(row) == True.
    """
    if not row or pool is None:
        return
    cid = int(row.get("id") or 0)
    chat_id = int(row.get("chat_id") or 0)
    mid = row.get("message_id")
    if cid:
        forget_live(cid)
        try:
            await pool.execute("DELETE FROM group_captcha_challenges WHERE id = $1", cid)
        except Exception:
            log.exception("captcha expire_challenge_now: DB delete failed id=%s", cid)
    if mid and bot is not None:
        await _safe_delete_message(bot, chat_id, int(mid))


async def _cleanup_worker(pool, bot, stop_event: asyncio.Event) -> None:
    log.info(
        "captcha cleanup worker started: interval=%ss batch=%s",
        CLEANUP_INTERVAL_SEC, CLEANUP_BATCH,
    )
    # Первый проход — сразу, чтобы подчистить хвосты после рестарта.
    while not stop_event.is_set():
        try:
            await cleanup_expired(pool, bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("captcha cleanup iteration crashed")

        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CLEANUP_INTERVAL_SEC)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
    log.info("captcha cleanup worker stopped")


def start_cleanup_task(pool, bot) -> Optional[asyncio.Task]:
    """
    Запускает фоновую чистку просроченных карточек.
    Вызывать один раз на старте бота, ПОСЛЕ создания pool и bot.
    Повторный вызов возвращает уже работающую задачу.
    """
    global _cleanup_task, _cleanup_stop
    if pool is None or bot is None:
        log.warning("captcha cleanup: not started (pool=%s bot=%s)", bool(pool), bool(bot))
        return None
    if _cleanup_task is not None and not _cleanup_task.done():
        return _cleanup_task

    _cleanup_stop = asyncio.Event()
    _cleanup_task = asyncio.create_task(
        _cleanup_worker(pool, bot, _cleanup_stop),
        name="group_captcha_cleanup",
    )
    return _cleanup_task


async def stop_cleanup_task() -> None:
    """Останавливает воркер. Безопасно вызывать, даже если он не запущен."""
    global _cleanup_task, _cleanup_stop
    task = _cleanup_task
    ev = _cleanup_stop
    _cleanup_task = None
    _cleanup_stop = None
    if ev is not None:
        ev.set()
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass