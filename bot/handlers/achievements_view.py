# -*- coding: utf-8 -*-
"""Текстовые команды просмотра достижений.

«Мои достижения» — свой альбом с кнопками витрины и порядка.
«Достижения» ответом на сообщение / с id, @ником или именем — чужой альбом
только для чтения.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from aiogram.types import InlineKeyboardMarkup, Message

from bot.funcs import achievements as ach

_YO = str.maketrans({"ё": "е", "Ё": "е"})

# Остаток после «достижения …», который значит «мои», а не чужое имя.
_SELF_QUERY = frozenset({
    "мои", "мое", "моё", "моя", "мой",
    "свои", "свое", "своё", "своя", "свой",
    "меня", "себе", "я", "myself", "me", "mine", "my",
})

HELP_TRIGGERS = (
    "хелп достижения",
    "хелп ачивки",
    "хелп ачивка",
    "помощь достижения",
    "помощь ачивки",
    "как посмотреть достижения",
    "как смотреть достижения",
    "как открыть достижения",
    "достижения помощь",
    "ачивки помощь",
    "достижения хелп",
    "ачивки хелп",
    "help achievements",
    "achievements help",
)

# Свои — редактирование. Длинные первыми.
OWN_TRIGGERS = (
    "все мои достижения",
    "мои все достижения",
    "мои достижения профиля",
    "моя витрина достижений",
    "посмотреть мои достижения",
    "посмотри мои достижения",
    "показать мои достижения",
    "покажи мои достижения",
    "открыть мои достижения",
    "открой мои достижения",
    "мои достижения пожалуйста",
    "мои ачивки пожалуйста",
    "мои награды пожалуйста",
    "профиль моих достижений",
    "мои достижения",
    "мое достижение",
    "моё достижение",
    "мои достижение",
    "мое достижения",
    "моё достижения",
    "мои ачивки",
    "мои ачивы",
    "мои ачики",
    "мои ачивка",
    "мои ачи",
    "мои награды",
    "моя награда",
    "мое награждение",
    "моё награждение",
    "моя витрина",
    "мои витрина",
    "витрина моя",
    "достижения мои",
    "достижение мое",
    "достижение моё",
    "ачивки мои",
    "ачивы мои",
    "награды мои",
    "награда моя",
    "my achievements",
    "my achievement",
    "my awards",
)

# Чужие / общие. Длинные первыми, короткие — точное слово или слово + запрос.
VIEW_TRIGGERS = (
    "посмотреть достижения игрока",
    "посмотреть ачивки игрока",
    "посмотреть награды игрока",
    "показать достижения игрока",
    "показать ачивки игрока",
    "показать награды игрока",
    "открыть достижения игрока",
    "чьи достижения",
    "чьи ачивки",
    "чьи награды",
    "достижения игрока",
    "достижение игрока",
    "ачивки игрока",
    "ачивка игрока",
    "награды игрока",
    "награда игрока",
    "витрина игрока",
    "витрина достижений",
    "профиль достижений",
    "посмотреть достижения",
    "посмотри достижения",
    "посмотреть ачивки",
    "посмотри ачивки",
    "посмотреть награды",
    "посмотри награды",
    "показать достижения",
    "покажи достижения",
    "показать ачивки",
    "покажи ачивки",
    "показать награды",
    "покажи награды",
    "открыть достижения",
    "открой достижения",
    "открыть ачивки",
    "открой ачивки",
    "глянуть достижения",
    "глянь достижения",
    "глянуть ачивки",
    "глянь ачивки",
    "чекни достижения",
    "чекни ачивки",
    "чек достижения",
    "чек ачивки",
    "все достижения",
    "все ачивки",
    "все награды",
    "достежения",
    "достижния",
    "дастижения",
    "достижения",
    "достижение",
    "ачивки",
    "ачивка",
    "ачивы",
    "ачики",
    "ачивкы",
    "награды",
    "награда",
    "витрина",
    "ачи",
    "achievements",
    "achievement",
    "achivki",
    "achivky",
    "awards",
)

ADMIN_BLOCK_PREFIXES = (
    "наградить",
    "выдать достижение",
    "дать ачивку",
    "дать достижение",
    "снять достижение",
    "забрать ачивку",
    "забрать достижение",
    "снять ачивку",
    "достижения админ",
    "помощь наградить",
    "наградить помощь",
    "хелп наградить",
)

_TME_RE = re.compile(
    r"(?:https?://)?(?:t(?:elegram)?\.me|telegram\.dog)/([A-Za-z0-9_]{3,64})(?:\?.*)?",
    re.IGNORECASE,
)
_ID_TOKEN_RE = re.compile(r"^(?:id|айди)[\s:_-]*(\d{5,15})$", re.IGNORECASE)
_TG_USER_RE = re.compile(r"(?:tg://user\?id=|user_id[=: ]+)(\d{5,15})", re.IGNORECASE)
_DIGIT_RE = re.compile(r"^\d{5,15}$")
_UNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,64}$")
_BOT_CMD_RE = re.compile(r"^/([^\s@]+)(?:@\w+)?(?:\s+|$)")

_PICK_LIMIT = 8


def _norm(text: str) -> str:
    s = " ".join((text or "").replace("\u00a0", " ").split())
    return s.translate(_YO).lower().strip()


def _strip_command(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("/"):
        m = _BOT_CMD_RE.match(raw)
        if m:
            raw = (m.group(1) + " " + raw[m.end():]).strip()
    return raw


def _starts(n: str, prefix: str) -> bool:
    return n == prefix or n.startswith(prefix + " ")


def parse_achievements_intent(text: str) -> Optional[Tuple[str, str]]:
    """('own'|'view'|'help', query). None — не наша фраза."""
    raw = _strip_command(text)
    n = _norm(raw)
    if not n:
        return None

    for p in ADMIN_BLOCK_PREFIXES:
        if _starts(n, p):
            return None

    for p in HELP_TRIGGERS:
        if _starts(n, p):
            return "help", ""

    own = tuple(sorted(OWN_TRIGGERS, key=len, reverse=True))
    for p in own:
        if _starts(n, p):
            return "own", ""

    view = tuple(sorted(VIEW_TRIGGERS, key=len, reverse=True))
    for p in view:
        if n == p:
            return "view", ""
        if n.startswith(p + " "):
            rest = n[len(p):].strip()
            if rest in _SELF_QUERY:
                return "own", ""
            return "view", rest

    # «вася достижения», «@nick ачивки», «123456 награды»
    trail = (
        "достижения", "достижение", "ачивки", "ачивка", "ачивы", "ачики",
        "награды", "награда", "витрина", "ачи",
        "achievements", "achievement", "awards",
    )
    trail_block_left = frozenset({
        "царь", "king", "топ", "стата", "статистика", "хелп", "help",
        "магазин", "задания", "дать", "снять", "выдать", "забрать",
        "наградить", "админ", "админка",
    })
    for p in sorted(trail, key=len, reverse=True):
        if n.endswith(" " + p):
            rest = n[: -len(p)].strip()
            if rest in _SELF_QUERY or not rest:
                return "own", ""
            head = rest.split()[0] if rest else ""
            if rest in ADMIN_BLOCK_PREFIXES or head in trail_block_left:
                return None
            return "view", rest
    return None


def _entity_type(ent) -> str:
    t = getattr(ent, "type", None)
    if hasattr(t, "value"):
        return str(t.value)
    return str(t or "").lower()


def _mentions_from_message(message: Message) -> List[Tuple[Optional[int], str]]:
    """Явные упоминания в тексте: (user_id|None, @username|'')."""
    text = message.text or message.caption or ""
    ents = list(message.entities or message.caption_entities or [])
    out: List[Tuple[Optional[int], str]] = []
    for ent in ents:
        kind = _entity_type(ent)
        if kind == "text_mention":
            user = getattr(ent, "user", None)
            uid = int(getattr(user, "id", 0) or 0) if user else 0
            if uid and not bool(getattr(user, "is_bot", False)):
                out.append((uid, ""))
            continue
        if kind != "mention":
            continue
        try:
            off = int(getattr(ent, "offset", 0) or 0)
            length = int(getattr(ent, "length", 0) or 0)
            chunk = text.encode("utf-16-le")
            token = chunk[off * 2:(off + length) * 2].decode("utf-16-le")
        except Exception:
            token = ""
        uname = token[1:] if token.startswith("@") else token
        if _UNAME_RE.fullmatch(uname or ""):
            out.append((None, uname))
    return out


async def player_label_html(db, user_id: int) -> str:
    uid = int(user_id)
    name = "Игрок"
    uname = None
    try:
        name = (await db.get_firstname_by_user_id(uid)) or name
    except Exception:
        pass
    try:
        uname = await db.get_username_by_user_id(uid)
    except Exception:
        try:
            uname = await db.get_username_by_id(uid)
        except Exception:
            uname = None
    uname = (str(uname).lstrip("@") if uname else "") or None
    try:
        from bot.db_create.db import create_user_link
        link = await create_user_link(uid, str(name), uname)
    except Exception:
        link = html.escape(str(name))
    extra = f" · @{html.escape(uname)}" if uname else ""
    return f"{link}{extra} · <code>{uid}</code>"


async def _username_to_id(db, bot, username: str) -> Optional[int]:
    uname = (username or "").lstrip("@").strip()
    if not _UNAME_RE.fullmatch(uname):
        return None
    try:
        found = await db.get_user_id_by_username(uname)
        if found:
            return int(found)
    except Exception:
        pass
    if bot is None:
        return None
    try:
        chat = await bot.get_chat(f"@{uname}")
        cid = int(getattr(chat, "id", 0) or 0)
        if cid > 0:
            return cid
    except Exception:
        pass
    return None


async def _search_players(db, query: str) -> List[Dict[str, Any]]:
    q = " ".join((query or "").split()).strip(" ,.;:!\"'`()[]{}<>")
    if not q or len(q) > 64:
        return []
    safe = q.replace("%", "").replace("_", "").replace("\\", "")
    if not safe:
        return []
    if len(safe) < 2:
        pattern_exact = safe
        pattern_soft = safe
    else:
        pattern_exact = safe
        pattern_soft = f"%{safe}%"
    rows = []
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, first_name, username
                FROM users
                WHERE user_id > 0
                  AND (
                        first_name ILIKE $1
                     OR username ILIKE $1
                     OR first_name ILIKE $2
                     OR username ILIKE $2
                  )
                ORDER BY
                    CASE WHEN lower(first_name) = lower($3) THEN 0
                         WHEN lower(username) = lower($3) THEN 1
                         WHEN first_name ILIKE $1 THEN 2
                         ELSE 3 END,
                    user_id
                LIMIT 12
                """,
                pattern_exact,
                pattern_soft,
                safe,
            )
    except Exception as e:
        print(f"[ACH][VIEW] name search fail: {e!r}")
        return []
    out = []
    seen = set()
    for r in rows:
        uid = int(r["user_id"])
        if uid in seen:
            continue
        seen.add(uid)
        out.append({
            "user_id": uid,
            "first_name": r["first_name"] or "Игрок",
            "username": (r["username"] or "").lstrip("@") or "",
        })
    return out


async def resolve_view_target(
    message: Message,
    db,
    query: str,
) -> Tuple[Optional[int], List[Dict[str, Any]], str]:
    """(user_id, candidates, error). Один id / несколько имён / ошибка."""
    bot = message.bot
    q = (query or "").strip()

    if q:
        first = q.split()[0]
        m_id = _ID_TOKEN_RE.match(q) or _ID_TOKEN_RE.match(first) or _DIGIT_RE.match(first)
        if m_id:
            uid = int(m_id.group(1) if getattr(m_id, "lastindex", 0) else m_id.group(0))
            return uid, [], ""
        m_tg = _TG_USER_RE.search(q)
        if m_tg:
            return int(m_tg.group(1)), [], ""
        m_tme = _TME_RE.search(q)
        if m_tme:
            uid = await _username_to_id(db, bot, m_tme.group(1))
            if uid:
                return uid, [], ""
            return None, [], "Не нашёл игрока по этой ссылке."
        token = q.split()[0]
        uname = token[1:] if token.startswith("@") else token
        if token.startswith("@") or _UNAME_RE.fullmatch(uname):
            uid = await _username_to_id(db, bot, uname)
            if uid:
                return uid, [], ""
            if token.startswith("@"):
                return None, [], "Не нашёл игрока с таким @username."

        found = await _search_players(db, q)
        if len(found) == 1:
            return int(found[0]["user_id"]), [], ""
        if len(found) > 1:
            return None, found, ""
        # одно слово без @ — ещё раз как username, если имя не нашли
        if _UNAME_RE.fullmatch(uname):
            uid = await _username_to_id(db, bot, uname)
            if uid:
                return uid, [], ""
        return None, [], "Не нашёл игрока. Попробуйте id, @username или точное имя."

    mentions = _mentions_from_message(message)
    if mentions:
        uid, uname = mentions[0]
        if uid:
            return uid, [], ""
        if uname:
            found_id = await _username_to_id(db, bot, uname)
            if found_id:
                return found_id, [], ""
            return None, [], "Не нашёл игрока с таким @username."

    try:
        from bot.funcs.profile import _resolve_reply_target_user_id
        reply_id = _resolve_reply_target_user_id(message)
        if reply_id:
            return int(reply_id), [], ""
    except Exception:
        reply = message.reply_to_message
        if reply and reply.from_user and not reply.from_user.is_bot:
            return int(reply.from_user.id), [], ""

    return None, [], ""


def help_html() -> str:
    return (
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Как смотреть достижения</b>\n\n"
        f"<b>Свои</b> — с кнопками витрины и порядка:\n"
        f"<code>мои достижения</code>\n"
        f"<code>ачивки</code>\n"
        f"<code>достижения</code>\n\n"
        f"<b>Чужие</b> — только просмотр:\n"
        f"ответьте на сообщение игрока словом <code>достижения</code>\n"
        f"или напишите\n"
        f"<code>достижения @ник</code>\n"
        f"<code>достижения 123456789</code>\n"
        f"<code>достижения Иван</code>\n\n"
        f"<i>Подойдут и «ачивки», «награды», «витрина», «покажи достижения».</i>"
    )


def _picker_label(row: Dict[str, Any]) -> str:
    name = str(row.get("first_name") or "Игрок").replace("\n", " ").strip() or "Игрок"
    uname = str(row.get("username") or "").strip()
    uid = int(row["user_id"])
    if uname:
        label = f"{name} · @{uname}"
    else:
        label = f"{name} · {uid}"
    return label[:64]


async def _send_picker(message: Message, viewer_id: int, rows: Sequence[Dict[str, Any]]) -> None:
    from bot.handlers.achievements_admin import _btn

    shown = list(rows)[:_PICK_LIMIT]
    kb_rows = [[_btn(
        text=_picker_label(row),
        callback_data=f"achv_go:{int(viewer_id)}:{int(row['user_id'])}",
        style="primary",
    )] for row in shown]
    extra = ""
    if len(rows) > _PICK_LIMIT:
        extra = f"\n<i>Показаны первые {_PICK_LIMIT}. Уточните @username или id.</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.reply(
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Нашёл несколько игроков</b>\n"
        f"Выберите, чьи достижения открыть.{extra}",
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True,
    )


async def render_achievements_page(
    db,
    target_id: int,
    page: int,
    *,
    manage: bool,
) -> Tuple[dict, str]:
    doc = await ach.get_user_achievements_doc(db, int(target_id))
    owner_html = await player_label_html(db, int(target_id))
    text = ach.format_full_achievements_html(
        doc,
        page=page,
        mode="manage" if manage else "view",
        owner_html=owner_html,
    )
    return doc, text


async def send_achievements_album(
    message: Message,
    db,
    *,
    viewer_id: int,
    target_id: int,
    manage: bool,
) -> bool:
    from bot.handlers.achievements_admin import _build_manage_keyboard

    doc, text = await render_achievements_page(db, target_id, 0, manage=manage)
    kb = _build_manage_keyboard(
        int(viewer_id), int(target_id), doc, is_owner=manage, page=0,
    )
    bodies = (
        text,
        ach.fit_telegram_html(text, max_emojis=60, max_len=3600),
        ach.fit_telegram_html(text, max_emojis=24, max_len=2400),
        ach.strip_tg_emoji(text),
    )
    last_err = None
    for body in bodies:
        try:
            await message.reply(
                body,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            last_err = e
            low = str(e).lower()
            if "can't parse" in low or "document_invalid" in low or "too long" in low or "too many" in low:
                continue
            print(f"[ACH][VIEW] send fail: {e!r}")
            break
    if last_err:
        print(f"[ACH][VIEW] send give up: {last_err!r}")
    try:
        await message.reply("Не удалось открыть достижения. Попробуйте ещё раз.")
    except Exception:
        pass
    return False


async def handle_achievements_view_message(message: Message, db) -> bool:
    """True, если сообщение про просмотр достижений обработано."""
    if message.from_user is None or bool(getattr(message.from_user, "is_bot", False)):
        return False
    text = message.text or ""
    parsed = parse_achievements_intent(text)
    if not parsed:
        return False

    kind, query = parsed
    viewer_id = int(message.from_user.id)

    if kind == "help":
        await message.reply(help_html(), parse_mode="HTML", disable_web_page_preview=True)
        return True

    if kind == "own":
        return await send_achievements_album(
            message, db, viewer_id=viewer_id, target_id=viewer_id, manage=True,
        )

    target_id, candidates, err = await resolve_view_target(message, db, query)
    if candidates:
        await _send_picker(message, viewer_id, candidates)
        return True
    if err:
        await message.reply(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>{html.escape(err)}</b>\n\n"
            f"Ответьте на сообщение игрока или напишите id / @username / имя.",
            parse_mode="HTML",
        )
        return True

    if not target_id:
        # «достижения» без цели — свои, с редактированием
        return await send_achievements_album(
            message, db, viewer_id=viewer_id, target_id=viewer_id, manage=True,
        )

    manage = int(target_id) == viewer_id
    return await send_achievements_album(
        message, db, viewer_id=viewer_id, target_id=int(target_id), manage=manage,
    )


async def handle_achievements_view_callback(callback, db) -> bool:
    data = str(getattr(callback, "data", "") or "")
    if not data.startswith("achv_"):
        return False
    parts = data.split(":")
    action = parts[0]
    clicker = int(callback.from_user.id)

    async def _ack(text: str = "", *, alert: bool = False) -> None:
        try:
            if text:
                await callback.answer(text, show_alert=alert)
            else:
                await callback.answer()
        except Exception:
            pass

    if action == "achv_x":
        try:
            owner = int(parts[1])
            target = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            owner = 0
            target = 0
        if clicker != owner:
            await _ack("Это не ваше меню", alert=True)
            return True
        await _ack()
        mid = getattr(callback.message, "message_id", None)
        from_profile = False
        if mid is not None:
            try:
                from bot.funcs.profile import _profile_get_message_meta
                meta = _profile_get_message_meta(int(mid)) or {}
                from_profile = bool(meta.get("target_user_id") or meta.get("mode"))
            except Exception:
                from_profile = False
        if from_profile and target:
            from bot.handlers.achievements_admin import _return_achievements_to_profile
            await _return_achievements_to_profile(callback, db, owner, target)
            return True
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return True

    if action != "achv_go" or len(parts) < 3:
        await _ack("Ошибка", alert=True)
        return True

    try:
        viewer = int(parts[1])
        target = int(parts[2])
    except Exception:
        await _ack("Ошибка", alert=True)
        return True

    if clicker != viewer:
        await _ack("Это не ваше меню", alert=True)
        return True

    await _ack()
    from bot.handlers.achievements_admin import _achm_edit_now, _build_manage_keyboard

    manage = clicker == target
    doc, text = await render_achievements_page(db, target, 0, manage=manage)
    kb = _build_manage_keyboard(viewer, target, doc, is_owner=manage, page=0)
    ok = await _achm_edit_now(callback.message, text, kb)
    if not ok:
        await send_achievements_album(
            callback.message, db, viewer_id=viewer, target_id=target, manage=manage,
        )
    return True
