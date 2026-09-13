# -*- coding: utf-8 -*-
"""Лёгкая групповая капча: один раз в группе навсегда, premium-эмодзи, HMAC."""

from __future__ import annotations

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
VARIANT_7_CHANCE = 0.11
DISABLE_ICON = "<tg-emoji emoji-id='5462990652943904884'>✨</tg-emoji>"
DISABLE_ALERT = (
    "Капчу в группе может отключить только владелец чата.\n"
    "Если вам действительно мешает капча — попросите создателя группы отключить её"
)
PASS_ALERT = "Капча пройдена. Теперь вы можете писать в группе"
CAPTCHA_INTRO_LINE1 = "Это капча."
CAPTCHA_INTRO_LINE2 = "Пожалуйста, пройдите её, чтобы писать в группе."
CAPTCHA_INTRO = f"{CAPTCHA_INTRO_LINE1}\n{CAPTCHA_INTRO_LINE2}"
INTRO_EYE_ID = "5389099803655305880"
INTRO_WARN_ID = "5213205860498549992"

VARIANT_LABELS = {
    1: "Найдите такое же",
    2: "Цвет",
    3: "Как на карточке",
    4: "Живое / еда / вещь",
    5: "Сторона",
    6: "Настроение",
    7: "Два по порядку",
}

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
    "intro_warn": f"<tg-emoji emoji-id='{INTRO_WARN_ID}'>⚠️</tg-emoji>",
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


def premium_button(
    item: PremiumEmoji,
    callback_data: str,
    *,
    style: Optional[str] = None,
    text: Optional[str] = None,
    plain: bool = False,
):
    """Как в проводах: text=' ', премиум только через icon_custom_emoji_id."""
    _ = plain
    from aiogram.types import InlineKeyboardButton
    return InlineKeyboardButton(
        text=ICON_ONLY_TEXT if text is None else text,
        callback_data=callback_data,
        style=style or "default",
        icon_custom_emoji_id=str(item.emoji_id),
    )


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
    r = rng or random
    if r.random() < VARIANT_7_CHANCE:
        return 7
    return r.choice([1, 2, 3, 4, 5, 6])


def _mark(answer: str) -> str:
    """Правильный ответ в задании — жирный и подчёркнутый."""
    return f"<u>{answer}</u>"


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
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": "такое же"}]
        extras = [_emoji_ref(target)]
        return _pack(v, prefix, options, correct, chunks, extras=extras)

    if v == 2:
        colors = ["red", "green", "blue"]
        correct = r.choice(colors)
        options = _shuffle(colors, r)
        words = {"red": "красный", "green": "зелёный", "blue": "синий"}
        prefix = emoji("v2_prefix")
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": words[correct]}]
        return _pack(v, prefix, options, correct, chunks, extra={"color": words[correct]})

    if v == 3:
        pool = ["gift", "star", "dollar"]
        correct = r.choice(pool)
        options = _shuffle(pool, r)
        prefix = emoji(correct)
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": "такое же"}]
        return _pack(v, prefix, options, correct, chunks)

    if v == 4:
        keys = ["living", "food", "thing"]
        correct = r.choice(keys)
        options = _shuffle(keys, r)
        words = {"living": "живое", "food": "еду", "thing": "вещь"}
        prefix = emoji("v4_prefix")
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": words[correct]}]
        return _pack(v, prefix, options, correct, chunks, extra={"ask": words[correct]})

    if v == 5:
        correct = r.choice(["left", "right"])
        options = ["left", "right"]  # места фиксированы
        words = {"left": "налево", "right": "направо"}
        prefix = emoji("v5_prefix")
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": words[correct]}]
        return _pack(v, prefix, options, correct, chunks, extra={"side": words[correct]})

    if v == 6:
        keys = ["happy", "sad", "angry"]
        correct = r.choice(keys)
        options = _shuffle(keys, r)
        words = {"happy": "весёлое", "sad": "грустное", "angry": "злое"}
        prefix = emoji("v6_prefix")
        chunks = [{"kind": "text", "value": "Нажмите "}, {"kind": "mark", "value": words[correct]}]
        return _pack(v, prefix, options, correct, chunks, extra={"mood": words[correct]})

    if v == 7:
        pool = ["sun", "moon", "earth"]
        first, second = r.sample(pool, 2)
        options = _shuffle(pool, r)
        names = {"sun": "солнце", "moon": "луну", "earth": "землю"}
        prefix = emoji("v7_prefix")
        chunks = [
            {"kind": "text", "value": "Сначала нажмите "},
            {"kind": "mark", "value": names[first]},
            {"kind": "text", "value": ", затем "},
            {"kind": "mark", "value": names[second]},
        ]
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
        data["chunks"] = [
            {"kind": "text", "value": "Сначала нажмите "},
            {"kind": "mark", "value": str(names.get(first) or first)},
            {"kind": "text", "value": ", затем "},
            {"kind": "mark", "value": str(names.get(second) or second)},
        ]
        return data
    if variant == 1:
        data["chunks"] = [
            {"kind": "text", "value": "Нажмите "},
            {"kind": "mark", "value": "такое же"},
        ]
        return data
    mark = data.get("color") or data.get("ask") or data.get("side") or data.get("mood")
    if mark:
        data["chunks"] = [
            {"kind": "text", "value": "Нажмите "},
            {"kind": "mark", "value": str(mark)},
        ]
        return data
    data["chunks"] = [{"kind": "text", "value": "Нажмите нужную кнопку"}]
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
    _add_intro_line(add, ents, emoji("intro_eye"), CAPTCHA_INTRO_LINE1)
    add("\n")
    _add_intro_line(add, ents, emoji("intro_warn"), CAPTCHA_INTRO_LINE2)
    add("\n\n")

    prefix_id = str(payload.get("prefix_id") or "")
    prefix_face = str(payload.get("prefix_face") or "")
    if prefix_id and prefix_face:
        start, ln = add(prefix_face)
        ents.append(MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=start,
            length=ln,
            custom_emoji_id=prefix_id,
        ))
        add(" ")

    bold_start = _utf16_len("".join(buf))
    for ch in payload.get("chunks") or []:
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
    bold_len = _utf16_len("".join(buf)) - bold_start
    if bold_len > 0:
        ents.append(MessageEntity(type=MessageEntityType.BOLD, offset=bold_start, length=bold_len))

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

    return "".join(buf), ents


def _add_intro_line(add, ents, icon: PremiumEmoji, text: str) -> None:
    from aiogram.enums import MessageEntityType
    from aiogram.types import MessageEntity

    if icon.emoji_id and icon.face:
        start, ln = add(icon.face)
        ents.append(MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=start,
            length=ln,
            custom_emoji_id=icon.emoji_id,
        ))
        add(" ")
    start, ln = add(text)
    if ln:
        ents.append(MessageEntity(type=MessageEntityType.BOLD, offset=start, length=ln))


def card_html(payload: Dict[str, Any], user: Any) -> str:
    # Не оборачиваем mention и tg-emoji в ещё один <b>: Telegram ломает вложенный bold.
    body = str(payload.get("text") or "<b>Нажмите нужную кнопку</b>")
    who = mention_html(user)
    intro = (
        f"{emoji('intro_eye').as_html()} <b>{CAPTCHA_INTRO_LINE1}</b>\n"
        f"{emoji('intro_warn').as_html()} <b>{CAPTCHA_INTRO_LINE2}</b>"
    )
    return f"{who}\n{intro}\n\n{body}"


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
)

_schema_ready = False
_passed_cache: Dict[Tuple[int, int], float] = {}
_not_passed_cache: Dict[Tuple[int, int], float] = {}
_disabled_cache: Dict[int, Tuple[bool, float]] = {}
_live_challenges: Dict[int, Dict[str, Any]] = {}
_CACHE_TTL = 90.0
_NOT_PASSED_TTL = 20.0


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
    _live_challenges[int(stored["id"])] = stored


def peek_live(challenge_id: int) -> Optional[Dict[str, Any]]:
    row = _live_challenges.get(int(challenge_id))
    return dict(row) if row else None


def patch_live(challenge_id: int, **fields: Any) -> None:
    row = _live_challenges.get(int(challenge_id))
    if not row:
        return
    row.update(fields)


def forget_live(challenge_id: int) -> None:
    _live_challenges.pop(int(challenge_id), None)


def forget_chat_live(chat_id: int) -> None:
    cid = int(chat_id)
    for key in [k for k, row in _live_challenges.items() if int(row.get("chat_id") or 0) == cid]:
        _live_challenges.pop(key, None)


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


async def ensure_tables(pool) -> None:
    global _schema_ready
    if _schema_ready or pool is None:
        return
    async with pool.acquire() as conn:
        for stmt in SCHEMA_SQL:
            await conn.execute(stmt)
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


async def log_event(
    pool,
    *,
    user_id: int,
    chat_id: int,
    event: str,
    variant: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    await ensure_tables(pool)
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
) -> None:
    await ensure_tables(pool)
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
        max(1, int(attempts or 1)),
        duration_ms,
        trigger,
    )
    _cache_pass(chat_id, user_id)
    await log_event(
        pool,
        user_id=user_id,
        chat_id=chat_id,
        event="pass",
        variant=variant,
        meta={"attempts": attempts, "duration_ms": duration_ms, "trigger": trigger},
    )


async def get_challenge(pool, challenge_id: int) -> Optional[Dict[str, Any]]:
    live = peek_live(challenge_id)
    if live:
        return live
    await ensure_tables(pool)
    row = await pool.fetchrow(
        "SELECT * FROM group_captcha_challenges WHERE id = $1",
        int(challenge_id),
    )
    if not row:
        return None
    data = dict(row)
    remember_live(data)
    return data


async def get_open_challenge(pool, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
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
    return dict(row) if row else None


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
