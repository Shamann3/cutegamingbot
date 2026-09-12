# -*- coding: utf-8 -*-
"""Админ-команды выдачи/снятия достижений профиля."""

from __future__ import annotations

import asyncio
import html
import re
import time
from typing import Any, Optional, Tuple

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.funcs import achievements as ach

NAV_NEXT_EMOJI = "5434040112352607251"
NAV_PREV_EMOJI = "5440542387896070668"

# Меню достижений жмут часто. Telegram режет EditMessageText (flood).
# Действие применяем сразу, а перерисовку склеиваем: пользователь видит
# мгновенный ответ кнопки, экран догоняет одним спокойным кадром.
_ACHM_ABSORB_SEC = 0.26
_ACHM_MIN_GAP_SEC = 0.78
_ACHM_LAST_EDIT: dict[tuple, float] = {}
_ACHM_FLOOD_UNTIL: dict[tuple, float] = {}
_ACHM_PENDING: dict[tuple, tuple] = {}
_ACHM_TASKS: dict[tuple, asyncio.Task] = {}
_ACHM_GEN: dict[tuple, int] = {}
_ACHM_LAST_FP: dict[tuple, str] = {}

# Pending official pick: admin_id -> target_user_id
_pending_official: dict[int, int] = {}
_pending_revoke: dict[int, int] = {}
# Interactive free-award wizard: admin_id -> state
_pending_free: dict[int, dict] = {}

_CANCEL_WORDS = frozenset({"отмена", "cancel", "стоп", "stop"})

GRANT_TRIGGERS = (
    "наградить",
    "выдать достижение",
    "дать ачивку",
    "дать достижение",
)
REVOKE_TRIGGERS = (
    "снять достижение",
    "забрать ачивку",
    "забрать достижение",
    "снять ачивку",
)
HELP_TRIGGERS = (
    "достижения админ",
    "помощь наградить",
    "наградить помощь",
    "хелп наградить",
)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _match_prefix(text: str, prefixes: Tuple[str, ...]) -> Optional[Tuple[str, str]]:
    n = _norm(text)
    for p in sorted(prefixes, key=len, reverse=True):
        if n == p:
            return p, ""
        if n.startswith(p + " "):
            # preserve original casing/entities offset: use length of prefix in normalized space carefully
            # Fall back: strip from original with regex
            m = re.match(rf"(?is)^\s*{re.escape(p)}(?:\s+)(.*)$", text)
            rest = m.group(1) if m else ""
            return p, rest
    return None


async def _resolve_target_user_id(message: Message, db, rest: str) -> Tuple[Optional[int], str]:
    """Returns (user_id, leftover_text_for_achievement)."""
    # Reply first
    if message.reply_to_message and message.reply_to_message.from_user:
        return int(message.reply_to_message.from_user.id), rest

    leftover = rest or ""
    if not leftover.strip():
        return None, ""

    m = re.match(r"^(\S+)(?:[ \t]+|[ \t]*\n)(.*)$", leftover, flags=re.S)
    if m:
        token, after = m.group(1), m.group(2)
    else:
        token, after = leftover.strip(), ""

    # numeric id
    if token.isdigit():
        return int(token), after

    # @username or username
    uname = token[1:] if token.startswith("@") else token
    if re.fullmatch(r"[A-Za-z0-9_]{3,64}", uname):
        try:
            row = await db.pool.fetchrow(
                "SELECT user_id FROM users WHERE lower(username) = lower($1) LIMIT 1",
                uname,
            )
            if row:
                return int(row["user_id"]), after
        except Exception:
            pass
        # try get_chat
        try:
            chat = await message.bot.get_chat(f"@{uname}")
            if chat and getattr(chat, "id", None):
                return int(chat.id), after
        except Exception:
            pass

    return None, leftover


def _slice_entities_for_rest(message: Message, command_prefix: str, rest: str):
    """Shift entities to the rest substring after the command prefix."""
    text = message.text or message.caption or ""
    entities = list(message.entities or message.caption_entities or [])
    if not rest:
        return rest, []
    # Find rest start in original text
    idx = text.lower().rfind(rest.lower())
    if idx < 0:
        # try after prefix
        m = re.search(re.escape(command_prefix), text, flags=re.IGNORECASE)
        idx = (m.end() if m else 0)
        while idx < len(text) and text[idx].isspace():
            idx += 1
    # Convert idx to utf-16 offset
    prefix = text[:idx]
    utf16_off = len(prefix.encode("utf-16-le")) // 2
    shifted = []
    for ent in entities:
        off = int(getattr(ent, "offset", 0) or 0)
        length = int(getattr(ent, "length", 0) or 0)
        if off + length <= utf16_off:
            continue
        new_off = max(0, off - utf16_off)
        # clone-like shallow: mutate copy via type
        try:
            data = ent.model_dump() if hasattr(ent, "model_dump") else ent.dict()
            data["offset"] = new_off
            shifted.append(type(ent)(**data))
        except Exception:
            # fallback: keep original if can't clone
            shifted.append(ent)
    return rest, shifted


def _btn(**kwargs):
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs = dict(kwargs)
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


def _msg_key(message) -> Optional[tuple]:
    try:
        return (int(message.chat.id), int(message.message_id))
    except Exception:
        return None


def _prune_achm_maps() -> None:
    if len(_ACHM_LAST_EDIT) < 240:
        return
    now = time.monotonic()
    stale = [k for k, ts in _ACHM_LAST_EDIT.items() if now - ts > 1800]
    for k in stale:
        _ACHM_LAST_EDIT.pop(k, None)
        _ACHM_FLOOD_UNTIL.pop(k, None)
        _ACHM_LAST_FP.pop(k, None)
        _ACHM_GEN.pop(k, None)
        _ACHM_PENDING.pop(k, None)


def _render_fp(text: str, kb: InlineKeyboardMarkup) -> str:
    return f"{text}\0{repr(kb)}"


def _cancel_achm_render(message) -> None:
    """Сбросить отложенную перерисовку, чтобы «К профилю» / удаление не перетёрлись."""
    key = _msg_key(message)
    if not key:
        return
    _ACHM_PENDING.pop(key, None)
    _ACHM_GEN[key] = int(_ACHM_GEN.get(key, 0)) + 1


def _flood_wait_sec(exc: BaseException) -> float:
    raw = str(exc or "")
    low = raw.lower()
    if not any(x in low for x in ("retry after", "flood", "too many requests")):
        return 0.0
    ra = getattr(exc, "retry_after", None)
    try:
        if ra is not None:
            return max(0.2, float(ra))
    except Exception:
        pass
    m = re.search(r"retry after[^\d]*(\d+(?:\.\d+)?)", raw, flags=re.I)
    if m:
        try:
            return max(0.2, float(m.group(1)))
        except Exception:
            return 1.2
    return 1.2


def _nav_row(*, page_i: int, pages: int, prev_cb: str, next_cb: str):
    """Первая страница — только «Вперёд». Последняя — только «Назад». Середина — обе."""
    if pages <= 1:
        return None
    row = []
    if page_i > 0:
        row.append(_btn(
            text="Назад",
            callback_data=prev_cb,
            style="default",
            icon_custom_emoji_id=NAV_PREV_EMOJI,
        ))
    if page_i < pages - 1:
        row.append(_btn(
            text="Вперёд",
            callback_data=next_cb,
            style="default",
            icon_custom_emoji_id=NAV_NEXT_EMOJI,
        ))
    return row or None


async def _achm_edit_now(message, text: str, kb: InlineKeyboardMarkup) -> bool:
    """Один edit. При flood — ждём retry_after и пробуем ещё раз.
    Caption — только если в сообщении нет текста (фото), не как запас после flood.
    """
    if message is None:
        return False
    key = _msg_key(message)
    fp = _render_fp(text, kb)
    if key and _ACHM_LAST_FP.get(key) == fp:
        return True
    now = time.monotonic()
    if key:
        extra = _ACHM_FLOOD_UNTIL.get(key, 0) - now
        if extra > 0:
            await asyncio.sleep(extra)

    async def _send_text(body: str) -> None:
        await message.edit_text(
            body, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
        )

    async def _send_caption(body: str) -> None:
        await message.edit_caption(caption=body, parse_mode="HTML", reply_markup=kb)

    def _mark_ok() -> None:
        if key:
            _ACHM_LAST_EDIT[key] = time.monotonic()
            _ACHM_LAST_FP[key] = fp
            _prune_achm_maps()

    try:
        await _send_text(text)
        _mark_ok()
        return True
    except Exception as e:
        low = str(e).lower()
        if "not modified" in low:
            _mark_ok()
            return True
        wait = _flood_wait_sec(e)
        if wait:
            if key:
                _ACHM_FLOOD_UNTIL[key] = time.monotonic() + wait
            await asyncio.sleep(wait + 0.12)
            try:
                await _send_text(text)
                _mark_ok()
                return True
            except Exception as e2:
                if "not modified" in str(e2).lower():
                    _mark_ok()
                    return True
                print(f"[ACH] edit flood retry fail: {e2!r}")
                return False
        if "DOCUMENT_INVALID" in str(e) or "can't parse" in low:
            try:
                await _send_text(ach.strip_tg_emoji(text))
                _mark_ok()
                return True
            except Exception:
                return False
        if "there is no text" in low or "message can't be edited" in low:
            try:
                await _send_caption(text)
                _mark_ok()
                return True
            except Exception as e3:
                if "not modified" in str(e3).lower():
                    _mark_ok()
                    return True
                return False
        print(f"[ACH] edit fail: {e!r}")
        return False


def _schedule_achm_render(message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Склеивает частые клики в одну перерисовку — flood почти не случается."""
    if message is None:
        return
    key = _msg_key(message)
    if not key:
        return
    gen = int(_ACHM_GEN.get(key, 0))
    if _ACHM_LAST_FP.get(key) == _render_fp(text, kb) and key not in _ACHM_PENDING:
        return
    _ACHM_PENDING[key] = (text, kb, gen)
    task = _ACHM_TASKS.get(key)
    if task is not None and not task.done():
        return

    async def _pump() -> None:
        try:
            idle = time.monotonic() - _ACHM_LAST_EDIT.get(key, 0.0)
            await asyncio.sleep(0.12 if idle > 1.2 else _ACHM_ABSORB_SEC)
            while True:
                payload = _ACHM_PENDING.pop(key, None)
                if payload is None:
                    return
                body, markup, gen = payload
                if int(_ACHM_GEN.get(key, 0)) != gen:
                    return
                last = _ACHM_LAST_EDIT.get(key, 0.0)
                flood_left = _ACHM_FLOOD_UNTIL.get(key, 0.0) - time.monotonic()
                wait = max(_ACHM_MIN_GAP_SEC - (time.monotonic() - last), flood_left, 0.0)
                if wait > 0:
                    await asyncio.sleep(wait)
                    if int(_ACHM_GEN.get(key, 0)) != gen:
                        return
                    newer = _ACHM_PENDING.pop(key, None)
                    if newer is not None:
                        body, markup, gen = newer
                        if int(_ACHM_GEN.get(key, 0)) != gen:
                            return
                await _achm_edit_now(message, body, markup)
        except Exception as e:
            print(f"[ACH] render pump: {e!r}")
        finally:
            _ACHM_TASKS.pop(key, None)
            leftover = _ACHM_PENDING.get(key)
            if leftover is not None and int(leftover[2]) == int(_ACHM_GEN.get(key, 0)):
                _schedule_achm_render(message, leftover[0], leftover[1])

    _ACHM_TASKS[key] = asyncio.create_task(_pump())


async def _refresh_profile(db, user_id: int) -> None:
    try:
        from bot.funcs.profile import update_profile_after_data_change
        await update_profile_after_data_change(int(user_id), db=db)
    except Exception as e:
        print(f"[ACH] profile refresh skip: {e!r}")


def _wizard_clear(admin_id: int) -> None:
    _pending_free.pop(int(admin_id), None)


def _wizard_kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(text="Отмена", callback_data="achc_x", style="danger",
             icon_custom_emoji_id="5226660202035554522"),
    ]])


def _wizard_preview_html(state: dict) -> str:
    title_html = state.get("title_html") or html.escape(state.get("title_plain") or "…")
    ic = ach.icon_html(state.get("icon_emoji_id"), state.get("icon_fallback") or "⭐")
    eid = state.get("icon_emoji_id")
    eid_line = f"значок · <code>{html.escape(str(eid))}</code>" if eid else "значок · обычный emoji"
    body = title_html if ach.is_rich_title(title_html) else f"{ic} {title_html}"
    return (
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Свободная награда — превью</b>\n\n"
        f"{body}\n"
        f"<blockquote>{eid_line}</blockquote>\n"
        f"<i>Проверьте название и эмодзи, затем выдайте.</i>"
    )


def _wizard_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(text="Выдать", callback_data="achc_ok", style="success")],
        [
            _btn(text="Другой текст", callback_data="achc_retitle", style="default"),
            _btn(text="Emoji id", callback_data="achc_eid", style="default"),
        ],
        [
            _btn(text="В значок", callback_data="achc_put:icon", style="default"),
            _btn(text="В название", callback_data="achc_put:title", style="default"),
        ],
        [_btn(text="Отмена", callback_data="achc_x", style="danger",
              icon_custom_emoji_id="5226660202035554522")],
    ])


async def _wizard_start_free(message: Message, db, admin_id: int, target_id: int) -> None:
    _pending_official.pop(admin_id, None)
    _pending_free[admin_id] = {
        "target": int(target_id),
        "step": "title",
        "title_html": "",
        "title_plain": "",
        "icon_emoji_id": None,
        "icon_fallback": "⭐",
        "pending_eid": None,
        "ts": time.time(),
    }
    await message.reply(
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Свободная награда</b>\n"
        f"Игрок: <code>{int(target_id)}</code>\n\n"
        f"Следующим сообщением отправьте карточку награды.\n"
        f"Premium-эмодзи вставляйте прямо в текст — все сохранятся.\n"
        f"Переносы строк и пробелы в начале строк тоже сохранятся.\n"
        f"Или укажите numeric id кнопкой ниже и вставьте в значок / название.\n\n"
        f"Токен вручную: <code>{{emoji:5469967260380612012}}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn(text="Указать emoji id", callback_data="achc_eid", style="primary")],
            [_btn(text="Отмена", callback_data="achc_x", style="danger",
                  icon_custom_emoji_id="5226660202035554522")],
        ]),
    )


async def handle_achievements_pending_message(message: Message, db) -> bool:
    """Ловит следующий текст админа в мастере свободной награды."""
    if not message.from_user:
        return False
    admin_id = int(message.from_user.id)
    state = _pending_free.get(admin_id)
    if not state:
        return False
    if time.time() - float(state.get("ts") or 0) > 900:
        _wizard_clear(admin_id)
        return False
    raw_text = message.text or message.caption or ""
    if not raw_text.strip() and not (message.entities or message.caption_entities):
        return False
    text = raw_text
    n = _norm(text.strip())
    if n in _CANCEL_WORDS:
        _wizard_clear(admin_id)
        await message.reply("Создание награды отменено.", parse_mode="HTML")
        return True
    if (
        any(n == t or n.startswith(t + " ") for t in GRANT_TRIGGERS)
        or any(n == t or n.startswith(t + " ") for t in REVOKE_TRIGGERS)
        or any(n == t or n.startswith(t + " ") for t in HELP_TRIGGERS)
    ):
        _wizard_clear(admin_id)
        return False

    step = str(state.get("step") or "")
    if step == "title":
        ents = list(message.entities or message.caption_entities or [])
        try:
            title_html, emoji_id, fallback = ach.prepare_title_from_message(text, ents)
        except ValueError:
            await message.reply("<b>В тексте нельзя ссылки.</b> Отправьте название без URL.", parse_mode="HTML")
            return True
        if not (title_html or "").strip():
            await message.reply("<b>Пустой текст.</b> Напишите название награды.", parse_mode="HTML")
            return True
        state["title_html"] = title_html
        state["title_plain"] = ach.strip_tg_emoji(title_html) or text
        if emoji_id and not state.get("icon_emoji_id"):
            state["icon_emoji_id"] = emoji_id
        if fallback:
            state["icon_fallback"] = fallback
        state["step"] = "confirm"
        _pending_free[admin_id] = state
        await message.reply(
            _wizard_preview_html(state),
            parse_mode="HTML",
            reply_markup=_wizard_confirm_kb(),
            disable_web_page_preview=True,
        )
        return True

    if step == "emoji_id":
        eid = ach.parse_custom_emoji_id(text)
        if not eid:
            await message.reply(
                "<b>Не вижу id.</b> Пришлите число вида <code>5469967260380612012</code>.",
                parse_mode="HTML",
            )
            return True
        state["pending_eid"] = eid
        state["step"] = "confirm" if state.get("title_html") else "title"
        _pending_free[admin_id] = state
        if state["step"] == "confirm":
            await message.reply(
                f"Id принят: <code>{eid}</code>\nКуда поставить?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        _btn(text="В значок", callback_data="achc_put:icon", style="primary"),
                        _btn(text="В название", callback_data="achc_put:title", style="primary"),
                    ],
                    [_btn(text="И туда, и туда", callback_data="achc_put:both", style="success")],
                    [_btn(text="Отмена", callback_data="achc_x", style="danger")],
                ]),
            )
        else:
            await message.reply(
                f"Id сохранён: <code>{eid}</code>\nТеперь отправьте текст награды.",
                parse_mode="HTML",
                reply_markup=_wizard_kb_cancel(),
            )
        return True

    return False


async def handle_achievements_admin_message(message: Message, db) -> bool:
    """True если сообщение обработано как команда достижений."""
    text = (message.text or "").strip()
    if not text:
        return False
    lower = _norm(text)

    if lower in HELP_TRIGGERS or any(lower.startswith(t + " ") for t in HELP_TRIGGERS):
        await message.reply(ach.help_admin_html(), parse_mode="HTML")
        return True

    rev = _match_prefix(text, REVOKE_TRIGGERS)
    if rev:
        return await _handle_revoke(message, db, rev[1])

    gr = _match_prefix(text, GRANT_TRIGGERS)
    if gr:
        return await _handle_grant(message, db, gr[0], gr[1])

    return False


async def _handle_grant(message: Message, db, prefix: str, rest: str) -> bool:
    admin_id = int(message.from_user.id)
    can_free = await ach.admin_has_perm(db, admin_id, ach.PERM_GRANT_FREE)
    can_off = await ach.admin_has_perm(db, admin_id, ach.PERM_GRANT_OFFICIAL)
    if not can_free and not can_off:
        await message.reply(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Нет права выдавать достижения.</b>\n"
            f"Создатель выдаёт доступ во вкладке «Админ панель».",
            parse_mode="HTML",
        )
        return True

    rest_l = rest.lower().strip()
    official_mode = False
    body = rest
    if rest_l.startswith("официально"):
        official_mode = True
        body = rest[len("официально"):].strip() if rest.lower().startswith("официально") else rest
        # more robust:
        m = re.match(r"(?is)^официально\s*(.*)$", rest.strip())
        body = (m.group(1) if m else "").strip()
    elif rest_l.startswith("офиц"):
        m = re.match(r"(?is)^офиц(?:иально)?\s*(.*)$", rest.strip())
        official_mode = True
        body = (m.group(1) if m else "").strip()

    target_id, leftover = await _resolve_target_user_id(message, db, body)
    if not target_id:
        await message.reply(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Кому награда?</b>\n"
            f"Ответьте на сообщение игрока или укажите id / @username.\n\n"
            f"<i>Подсказка: напишите «помощь наградить»</i>",
            parse_mode="HTML",
        )
        return True

    granter_name = (
        message.from_user.full_name
        or message.from_user.first_name
        or message.from_user.username
        or "Администратор"
    )

    async def _send_official_picker() -> bool:
        if not can_off:
            await message.reply(
                "<b>Нет права выдавать официальные достижения.</b>",
                parse_mode="HTML",
            )
            return True
        _pending_official[admin_id] = int(target_id)
        items = await ach.list_official(db, enabled_only=True, limit=30)
        if not items:
            await message.reply(
                "<b>Каталог официальных пуст.</b> Создайте награды во вкладке «Достижения».",
                parse_mode="HTML",
            )
            return True
        clean_rows = []
        for it in items[:20]:
            kwargs = {
                "text": f"{it.get('icon_fallback') or '⭐'} {it.get('title')}",
                "callback_data": f"ach_grant_off:{target_id}:{it['id']}",
                "style": "primary",
            }
            eid = it.get("icon_emoji_id")
            if eid:
                kwargs["icon_custom_emoji_id"] = str(eid)
            clean_rows.append([_btn(**kwargs)])
        await message.reply(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Выберите официальное достижение</b>\n"
            f"Игрок: <code>{target_id}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=clean_rows),
        )
        return True

    # Официальное по коду/названию
    if official_mode and leftover:
        if not can_off:
            await message.reply("<b>Нет права выдавать официальные.</b>", parse_mode="HTML")
            return True
        official = await ach.find_official(db, leftover)
        if not official:
            await message.reply(
                f"<b>Не найдено:</b> <code>{html.escape(leftover)}</code>",
                parse_mode="HTML",
            )
            return True
        res = await ach.grant_official_to_user(
            db,
            target_user_id=int(target_id),
            official=official,
            granted_by=admin_id,
            granted_by_name=granter_name,
            source="admin",
        )
        await _refresh_profile(db, target_id)
        already = " (уже было)" if res.get("already") else ""
        await message.reply(
            f"<tg-emoji emoji-id='{ach.DEFAULT_ICON_EMOJI_ID}'>⭐</tg-emoji> "
            f"<b>Официальная награда выдана{already}</b>\n"
            f"{official.get('title_html') or html.escape(official.get('title') or '')}",
            parse_mode="HTML",
        )
        return True

    # «наградить» / «наградить официально» без текста → меню выбора
    if official_mode and not leftover:
        return await _send_official_picker()

    if not leftover:
        rows = []
        if can_off:
            rows.append([_btn(
                text="Официальное",
                callback_data=f"achc_kind:{int(target_id)}:off",
                style="primary",
                icon_custom_emoji_id=ach.ACHIEVEMENTS_HEADER_EMOJI,
            )])
        if can_free:
            rows.append([_btn(
                text="Свободное",
                callback_data=f"achc_kind:{int(target_id)}:free",
                style="success",
            )])
        rows.append([_btn(
            text="Отмена",
            callback_data="achc_x",
            style="danger",
            icon_custom_emoji_id="5226660202035554522",
        )])
        if not rows[:-1]:
            await message.reply("<b>Нет права выдавать достижения.</b>", parse_mode="HTML")
            return True
        await message.reply(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Какую награду выдать?</b>\n"
            f"Игрок: <code>{int(target_id)}</code>\n\n"
            f"<i>Свободное — своё название и premium-эмодзи.\n"
            f"Официальное — карточка из каталога.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        return True

    if not can_free:
        await message.reply("<b>Нет права выдавать свободные достижения.</b>", parse_mode="HTML")
        return True

    rest_text, ents = _slice_entities_for_rest(message, prefix, leftover)
    try:
        title_html, emoji_id, fallback = ach.prepare_title_from_message(rest_text, ents)
    except ValueError:
        await message.reply("<b>В тексте нельзя ссылки.</b>", parse_mode="HTML")
        return True
    if not title_html.strip():
        await message.reply("<b>Пустой текст награды.</b>", parse_mode="HTML")
        return True

    await ach.grant_free_to_user(
        db,
        target_user_id=int(target_id),
        title_html=title_html,
        icon_emoji_id=emoji_id,
        icon_fallback=fallback,
        granted_by=admin_id,
        granted_by_name=granter_name,
    )
    await _refresh_profile(db, target_id)
    await message.reply(
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Свободная награда выдана</b>\n{title_html}",
        parse_mode="HTML",
    )
    return True


async def _handle_revoke(message: Message, db, rest: str) -> bool:
    admin_id = int(message.from_user.id)
    if not await ach.admin_has_perm(db, admin_id, ach.PERM_GRANT_FREE):
        # allow official revoke with official perm too
        if not await ach.admin_has_perm(db, admin_id, ach.PERM_GRANT_OFFICIAL):
            await message.reply("<b>Нет права снимать достижения.</b>", parse_mode="HTML")
            return True

    target_id, _leftover = await _resolve_target_user_id(message, db, rest)
    if not target_id:
        await message.reply(
            "<b>Укажите игрока</b> реплаем или id/@username.",
            parse_mode="HTML",
        )
        return True

    doc = await ach.get_user_achievements_doc(db, int(target_id))
    rows = ach.sorted_items_for_display(doc)
    if not rows:
        await message.reply("<b>У игрока нет достижений.</b>", parse_mode="HTML")
        return True

    _pending_revoke[admin_id] = int(target_id)
    text, kb = _revoke_list_view(int(target_id), rows, page=0)
    await message.reply(text, parse_mode="HTML", reply_markup=kb)
    return True


def _revoke_list_view(target_id: int, rows, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    page_rows, page_i, pages, total = ach.paginate_items(rows, page, ach.PAGE_SIZE)
    pager = f"стр. {page_i + 1}/{pages} · {total}" if pages > 1 else f"{total} наград"
    kb_rows = []
    for iid, it in page_rows:
        kind = "★" if it.get("kind") == "official" else "✧"
        title_plain = ach.title_button_label(it, 36)
        kb_rows.append([_btn(
            text=f"{kind} {title_plain}"[:64],
            callback_data=f"ach_rev:{int(target_id)}:{iid}:{page_i}",
            style="danger",
        )])
    nav = _nav_row(
        page_i=page_i,
        pages=pages,
        prev_cb=f"ach_revp:{int(target_id)}:{page_i - 1}",
        next_cb=f"ach_revp:{int(target_id)}:{page_i + 1}",
    )
    if nav:
        kb_rows.append(nav)
    kb_rows.append([_btn(
        text="Закрыть",
        callback_data="achc_x",
        style="default",
        icon_custom_emoji_id="5226660202035554522",
    )])
    text = (
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Что снять?</b>\n"
        f"Игрок <code>{int(target_id)}</code>\n"
        f"<i>{pager} · сначала покажем карточку, потом подтверждение</i>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


async def _handle_wizard_cb(callback: CallbackQuery, db, user_id: int, data: str) -> bool:
    async def _ack(text: str = "", alert: bool = False) -> None:
        try:
            if text:
                await callback.answer(text, show_alert=alert)
            else:
                await callback.answer()
        except Exception:
            pass

    async def _show(text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
        try:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
            )
        except Exception:
            try:
                await callback.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass

    if data == "achc_x":
        _wizard_clear(user_id)
        _pending_official.pop(user_id, None)
        await _ack("Отменено")
        await _show("Отменено.")
        return True

    if data.startswith("achc_kind:"):
        parts = data.split(":")
        if len(parts) < 3:
            await _ack("Ошибка", True)
            return True
        target_id = int(parts[1])
        kind = parts[2]
        can_free = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_FREE)
        can_off = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_OFFICIAL)
        if kind == "off":
            if not can_off:
                await _ack("Нет права", True)
                return True
            await _ack()
            _pending_official[user_id] = target_id
            items = await ach.list_official(db, enabled_only=True, limit=30)
            if not items:
                await _show("<b>Каталог официальных пуст.</b>")
                return True
            clean_rows = []
            for it in items[:20]:
                kwargs = {
                    "text": f"{it.get('icon_fallback') or '⭐'} {it.get('title')}",
                    "callback_data": f"ach_grant_off:{target_id}:{it['id']}",
                    "style": "primary",
                }
                eid = it.get("icon_emoji_id")
                if eid:
                    kwargs["icon_custom_emoji_id"] = str(eid)
                clean_rows.append([_btn(**kwargs)])
            clean_rows.append([_btn(text="Отмена", callback_data="achc_x", style="danger")])
            await _show(
                f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
                f"<b>Выберите официальное достижение</b>\n"
                f"Игрок: <code>{target_id}</code>",
                InlineKeyboardMarkup(inline_keyboard=clean_rows),
            )
            return True
        if kind == "free":
            if not can_free:
                await _ack("Нет права", True)
                return True
            await _ack()
            _pending_official.pop(user_id, None)
            _pending_free[user_id] = {
                "target": int(target_id),
                "step": "title",
                "title_html": "",
                "title_plain": "",
                "icon_emoji_id": None,
                "icon_fallback": "⭐",
                "pending_eid": None,
                "ts": time.time(),
            }
            await _show(
                f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
                f"<b>Свободная награда</b>\n"
                f"Игрок: <code>{int(target_id)}</code>\n\n"
                f"Следующим сообщением отправьте карточку награды.\n"
                f"Premium-эмодзи, переносы и отступы сохранятся.\n"
                f"Токен: <code>{{emoji:5469967260380612012}}</code>",
                InlineKeyboardMarkup(inline_keyboard=[
                    [_btn(text="Указать emoji id", callback_data="achc_eid", style="primary")],
                    [_btn(text="Отмена", callback_data="achc_x", style="danger",
                          icon_custom_emoji_id="5226660202035554522")],
                ]),
            )
            return True
        await _ack("Ошибка", True)
        return True

    state = _pending_free.get(user_id)
    if data == "achc_eid":
        if not state:
            await _ack("Сначала выберите «Свободное»", True)
            return True
        state["step"] = "emoji_id"
        _pending_free[user_id] = state
        await _ack()
        await _show(
            "<b>Идентификатор premium-эмодзи</b>\n"
            "Отправьте следующим сообщением число, например\n"
            "<code>5469967260380612012</code>\n\n"
            "Его можно взять в @PremiumEmoji или из HTML <code>emoji-id</code>.",
            InlineKeyboardMarkup(inline_keyboard=[
                [_btn(text="Назад", callback_data="achc_back", style="default")],
                [_btn(text="Отмена", callback_data="achc_x", style="danger")],
            ]),
        )
        return True

    if data == "achc_back":
        if not state:
            await _ack("Уже закрыто")
            return True
        await _ack()
        if state.get("title_html"):
            state["step"] = "confirm"
            _pending_free[user_id] = state
            await _show(_wizard_preview_html(state), _wizard_confirm_kb())
        else:
            state["step"] = "title"
            _pending_free[user_id] = state
            await _show(
                f"<b>Отправьте текст награды</b> для <code>{state.get('target')}</code>.",
                _wizard_kb_cancel(),
            )
        return True

    if data == "achc_retitle":
        if not state:
            await _ack("Сначала откройте меню", True)
            return True
        state["step"] = "title"
        _pending_free[user_id] = state
        await _ack()
        await _show(
            "<b>Новый текст награды</b>\nОтправьте следующим сообщением.",
            _wizard_kb_cancel(),
        )
        return True

    if data.startswith("achc_put:"):
        if not state:
            await _ack("Сначала укажите emoji id", True)
            return True
        eid = state.get("pending_eid") or state.get("icon_emoji_id")
        if not eid:
            state["step"] = "emoji_id"
            _pending_free[user_id] = state
            await _ack("Сначала пришлите emoji id", True)
            return True
        where = data.split(":", 1)[1]
        fb = state.get("icon_fallback") or "⭐"
        if where in ("icon", "both"):
            state["icon_emoji_id"] = eid
        if where in ("title", "both"):
            token = "{emoji:" + str(eid) + "}"
            raw = ach.title_html_to_tokens(state.get("title_html") or "") or state.get("title_plain") or ""
            if token not in raw:
                sep = "" if not raw or raw.endswith(("\n", " ", "\u00A0")) else " "
                raw = raw + sep + token
            try:
                state["title_html"] = ach.compose_title_html(raw, fallback=fb)
                state["title_plain"] = ach.strip_tg_emoji(state["title_html"])
            except ValueError:
                await _ack("Нельзя ссылки", True)
                return True
        state["step"] = "confirm" if state.get("title_html") else "title"
        _pending_free[user_id] = state
        await _ack("Поставил")
        if state["step"] == "confirm":
            await _show(_wizard_preview_html(state), _wizard_confirm_kb())
        else:
            await _show("Id в значке. Теперь отправьте текст награды.", _wizard_kb_cancel())
        return True

    if data == "achc_ok":
        if not state or not state.get("title_html") or not state.get("target"):
            await _ack("Нет превью — отправьте текст", True)
            return True
        if not await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_FREE):
            await _ack("Нет права", True)
            return True
        name = callback.from_user.full_name or callback.from_user.first_name or "Админ"
        target_id = int(state["target"])
        await ach.grant_free_to_user(
            db,
            target_user_id=target_id,
            title_html=state["title_html"],
            icon_emoji_id=state.get("icon_emoji_id"),
            icon_fallback=state.get("icon_fallback") or "⭐",
            granted_by=user_id,
            granted_by_name=name,
        )
        await _refresh_profile(db, target_id)
        _wizard_clear(user_id)
        await _ack("Выдано")
        granted = state["title_html"]
        if not ach.is_rich_title(granted):
            granted = f"{ach.icon_html(state.get('icon_emoji_id'), state.get('icon_fallback') or '⭐')} {granted}"
        await _show(
            f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
            f"<b>Свободная награда выдана</b>\n{granted}"
        )
        return True

    await _ack("Неизвестная кнопка", True)
    return True


async def handle_achievements_callback(callback: CallbackQuery, db) -> bool:
    data = str(callback.data or "")
    if not (
        data.startswith("ach_grant_off:")
        or data.startswith("ach_rev")
        or data.startswith("achm_")
        or data.startswith("achc_")
    ):
        return False

    user_id = int(callback.from_user.id)

    if data.startswith("achc_"):
        return await _handle_wizard_cb(callback, db, user_id, data)

    if data.startswith("ach_grant_off:"):
        parts = data.split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка данных", show_alert=True)
            return True
        target_id = int(parts[1])
        oid = int(parts[2])
        if not await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_OFFICIAL):
            await callback.answer("Нет права", show_alert=True)
            return True
        official = await ach.get_official_by_id(db, oid)
        if not official or not official.get("enabled", True):
            await callback.answer("Не найдено", show_alert=True)
            return True
        name = callback.from_user.full_name or callback.from_user.first_name or "Админ"
        res = await ach.grant_official_to_user(
            db,
            target_user_id=target_id,
            official=official,
            granted_by=user_id,
            granted_by_name=name,
        )
        await _refresh_profile(db, target_id)
        already = " (уже было)" if res.get("already") else ""
        try:
            await callback.message.edit_text(
                f"<tg-emoji emoji-id='{ach.DEFAULT_ICON_EMOJI_ID}'>⭐</tg-emoji> "
                f"<b>Выдано{already}</b>\n"
                f"{official.get('title_html') or html.escape(official.get('title') or '')}",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await callback.answer("Готово")
        return True

    if data.startswith("ach_revp:"):
        parts = data.split(":")
        try:
            target_id = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            await callback.answer("Ошибка", show_alert=True)
            return True
        can_free = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_FREE)
        can_off = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_OFFICIAL)
        if not can_free and not can_off:
            await callback.answer("Нет права", show_alert=True)
            return True
        doc = await ach.get_user_achievements_doc(db, target_id)
        rows = ach.sorted_items_for_display(doc)
        text, kb = _revoke_list_view(target_id, rows, page=page)
        await callback.answer()
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        return True

    if data.startswith("ach_revok:"):
        parts = data.split(":")
        if len(parts) < 3:
            await callback.answer("Ошибка", show_alert=True)
            return True
        target_id = int(parts[1])
        iid = parts[2]
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        can_free = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_FREE)
        can_off = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_OFFICIAL)
        if not can_free and not can_off:
            await callback.answer("Нет права", show_alert=True)
            return True
        doc = await ach.get_user_achievements_doc(db, target_id)
        it = doc.get("items", {}).get(iid)
        if it and it.get("kind") == "official" and not can_off:
            await callback.answer("Нужно право на официальные", show_alert=True)
            return True
        if it and it.get("kind") == "free" and not can_free:
            await callback.answer("Нужно право на свободные", show_alert=True)
            return True
        title_line = ach.achievement_line_html(it, with_rarity=False) if it else "—"
        doc, ok = ach.admin_remove_item(doc, iid)
        if ok:
            await ach.save_user_achievements_doc(db, target_id, doc)
            await _refresh_profile(db, target_id)
        await callback.answer("Снято" if ok else "Не найдено", show_alert=not ok)
        if ok:
            rows = ach.sorted_items_for_display(doc)
            if rows:
                text, kb = _revoke_list_view(target_id, rows, page=page)
                head = f"<b>Снято</b>\n{title_line}\n\n"
                try:
                    await callback.message.edit_text(head + text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
                except Exception:
                    pass
            else:
                try:
                    await callback.message.edit_text(
                        f"<b>Снято</b>\n{title_line}\n\nУ игрока больше нет достижений.",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
        return True

    if data.startswith("ach_rev:"):
        parts = data.split(":")
        if len(parts) < 3:
            await callback.answer("Ошибка", show_alert=True)
            return True
        target_id = int(parts[1])
        iid = parts[2]
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        can_free = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_FREE)
        can_off = await ach.admin_has_perm(db, user_id, ach.PERM_GRANT_OFFICIAL)
        if not can_free and not can_off:
            await callback.answer("Нет права", show_alert=True)
            return True
        doc = await ach.get_user_achievements_doc(db, target_id)
        it = (doc.get("items") or {}).get(iid)
        if not it:
            await callback.answer("Уже снято", show_alert=True)
            return True
        if it.get("kind") == "official" and not can_off:
            await callback.answer("Нужно право на официальные", show_alert=True)
            return True
        if it.get("kind") == "free" and not can_free:
            await callback.answer("Нужно право на свободные", show_alert=True)
            return True
        await callback.answer()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [_btn(text="Да, снять", callback_data=f"ach_revok:{target_id}:{iid}:{page}", style="danger")],
            [_btn(text="Нет, оставить", callback_data=f"ach_revp:{target_id}:{page}", style="primary")],
        ])
        try:
            await callback.message.edit_text(
                ach.format_delete_confirm_html(it),
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=kb)
            except Exception:
                pass
        return True

    # Profile manage callbacks achm_
    return await _handle_profile_manage_cb(callback, db)


async def _return_achievements_to_profile(
    callback: CallbackQuery,
    db,
    viewer: int,
    target: int,
) -> bool:
    """Вернуть экран достижений обратно в живой профиль.

    `_profile_full_refresh_and_render` только собирает caption/markup и
    ничего не редактирует — поэтому «К профилю» раньше «отвечала» и
    оставляла список достижений на месте.
    """
    from bot.design.buttons import privates
    from bot.funcs.profile import (
        _build_profile_caption_for_target,
        _profile_build_own_profile_markup,
        _profile_build_who_markup,
        _profile_get_message_meta,
        _profile_store_message_meta,
        _profile_target_has_warns,
        user_message_mappingprofile,
    )

    message = callback.message
    if message is None:
        return False

    _cancel_achm_render(message)

    meta = _profile_get_message_meta(message.message_id)
    mode = str(meta.get("mode") or "")
    if mode not in ("own_profile", "who_are_you"):
        mode = "own_profile" if int(viewer) == int(target) else "who_are_you"

    try:
        caption = await _build_profile_caption_for_target(
            viewer_id=viewer,
            target_user_id=target,
            db=db,
            chat_id=int(message.chat.id),
        )
        has_warns = await _profile_target_has_warns(target)
    except Exception as e:
        print(f"[ACH] back render: {e!r}")
        return False

    if mode == "own_profile" and int(viewer) == int(target):
        markup = _profile_build_own_profile_markup(
            privates,
            viewer_id=viewer,
            has_warns=has_warns,
        )
    else:
        markup = _profile_build_who_markup(
            viewer_id=viewer,
            target_user_id=target,
            has_warns=has_warns,
        )

    ok_edit = await _achm_edit_now(message, caption, markup)
    if not ok_edit:
        ok_edit = await _achm_edit_now(message, ach.strip_tg_emoji(caption), markup)

    new_mid = message.message_id
    if not ok_edit:
        try:
            new_msg = await message.answer(
                text=caption,
                reply_markup=markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            new_mid = new_msg.message_id
        except Exception as e:
            print(f"[ACH] back fallback send: {e!r}")
            return False

    _profile_store_message_meta(
        new_mid,
        viewer_id=viewer,
        target_user_id=target,
        mode=mode,
        chat_id=int(message.chat.id),
        has_warns=has_warns,
    )
    try:
        user_message_mappingprofile[int(viewer)] = int(new_mid)
    except Exception:
        pass
    return True


async def _handle_profile_manage_cb(callback: CallbackQuery, db) -> bool:
    data = str(callback.data or "")
    # achm_all / achm_pg / achm_back / achm_up / achm_dn / achm_pin / achm_slot / achm_del / achm_delok
    parts = data.split(":")
    if len(parts) < 3:
        return False
    action = parts[0]
    try:
        viewer = int(parts[1])
        target = int(parts[2])
    except Exception:
        try:
            await callback.answer("Ошибка", show_alert=True)
        except Exception:
            pass
        return True

    clicker = int(callback.from_user.id)
    if clicker != viewer:
        try:
            await callback.answer("Это не ваше меню", show_alert=True)
        except Exception:
            pass
        return True

    def _page_at(idx: int, default: int = 0) -> int:
        try:
            return max(0, int(parts[idx]))
        except Exception:
            return default

    if action == "achm_pg":
        page = _page_at(3)
    elif action == "achm_slot":
        page = _page_at(5)
    elif action in ("achm_up", "achm_dn", "achm_pin", "achm_del", "achm_delok", "achm_all"):
        page = _page_at(3 if action == "achm_all" else 4)
    else:
        page = 0

    is_owner = clicker == target

    async def _ack(text: str = "", *, alert: bool = False) -> None:
        try:
            if text:
                await callback.answer(text, show_alert=alert)
            else:
                await callback.answer()
        except Exception:
            pass

    if action in ("achm_all", "achm_pg"):
        await _ack()
        doc = await ach.get_user_achievements_doc(db, target)
        rows = ach.sorted_items_for_display(doc)
        _, page, _, _ = ach.paginate_items(rows, page, ach.PAGE_SIZE)
        text = ach.format_full_achievements_html(doc, page=page)
        kb = _build_manage_keyboard(viewer, target, doc, is_owner=is_owner, page=page)
        _schedule_achm_render(callback.message, text, kb)
        return True

    if action == "achm_back":
        await _ack()
        ok = await _return_achievements_to_profile(callback, db, viewer, target)
        if not ok:
            print(f"[ACH] back to profile failed viewer={viewer} target={target}")
        return True

    if not is_owner:
        await _ack("Только владелец профиля", alert=True)
        return True

    iid = parts[3] if len(parts) > 3 else ""
    doc = await ach.get_user_achievements_doc(db, target)

    if action == "achm_up":
        await _ack("Выше")
        doc = ach.move_item(doc, iid, -1)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_dn":
        await _ack("Ниже")
        doc = ach.move_item(doc, iid, 1)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_pin":
        await _ack("На витрине · 1")
        doc = ach.pin_item_to_front(doc, iid)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_slot":
        try:
            slot = int(parts[4]) if len(parts) > 4 else 0
        except Exception:
            slot = 0
        await _ack(f"Витрина · {slot + 1}")
        doc = ach.pin_item_to_slot(doc, iid, slot)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_del":
        it = doc.get("items", {}).get(iid)
        if not it or it.get("kind") != "free":
            await _ack("Можно удалять только свободные", alert=True)
            return True
        await _ack()
        _cancel_achm_render(callback.message)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [_btn(
                text="Да, удалить",
                callback_data=f"achm_delok:{viewer}:{target}:{iid}:{page}",
                style="danger",
            )],
            [_btn(
                text="Нет, оставить",
                callback_data=f"achm_all:{viewer}:{target}:{page}",
                style="primary",
            )],
        ])
        await _achm_edit_now(callback.message, ach.format_delete_confirm_html(it), kb)
        return True
    elif action == "achm_delok":
        it = (doc.get("items") or {}).get(iid)
        doc, ok = ach.remove_free_item(doc, iid)
        if ok:
            await ach.save_user_achievements_doc(db, target, doc)
            await _ack("Удалено")
        else:
            await _ack("Не удалось", alert=True)
    else:
        return False

    rows = ach.sorted_items_for_display(doc)
    _, page, _, _ = ach.paginate_items(rows, page, ach.PAGE_SIZE)
    text = ach.format_full_achievements_html(doc, page=page)
    kb = _build_manage_keyboard(viewer, target, doc, is_owner=True, page=page)
    _schedule_achm_render(callback.message, text, kb)
    return True


def _profile_back_button(viewer: int, target: int) -> InlineKeyboardButton:
    return _btn(
        text="К профилю",
        callback_data=f"achm_back:{int(viewer)}:{int(target)}",
        style="primary",
        icon_custom_emoji_id="5226660202035554522",
    )


def _build_manage_keyboard(
    viewer: int,
    target: int,
    doc: dict,
    *,
    is_owner: bool,
    page: int = 0,
) -> InlineKeyboardMarkup:
    rows = []
    doc_n = ach._normalize_doc(doc)
    ordered = ach.sorted_items_for_display(doc_n)
    page_rows, page_i, pages, total = ach.paginate_items(ordered, page, ach.PAGE_SIZE)
    showcase_ids = [iid for iid, _ in ach.showcase_items(doc_n, ach.SHOWCASE_LIMIT)]

    rows.append([_profile_back_button(viewer, target)])

    if is_owner and ordered:
        rows.append([_btn(
            text=f"Витрина · {min(total, ach.SHOWCASE_LIMIT)}/{ach.SHOWCASE_LIMIT}",
            callback_data=f"achm_all:{viewer}:{target}:{page_i}",
        )])

    if is_owner:
        for iid, it in page_rows:
            title = ach.title_button_label(it, 18)
            on_v = iid in showcase_ids
            slot_n = 0
            if on_v:
                try:
                    slot_n = showcase_ids.index(iid) + 1
                except ValueError:
                    slot_n = 0
            pin_label = f"📌 {slot_n}·{title}" if slot_n else f"○ {title}"
            rows.append([
                _btn(
                    text=pin_label[:64],
                    callback_data=f"achm_pin:{viewer}:{target}:{iid}:{page_i}",
                    style="success" if on_v else "default",
                ),
                _btn(text="↑", callback_data=f"achm_up:{viewer}:{target}:{iid}:{page_i}"),
                _btn(text="↓", callback_data=f"achm_dn:{viewer}:{target}:{iid}:{page_i}"),
            ])
            slot_row = []
            for s in range(ach.SHOWCASE_LIMIT):
                selected = bool(slot_n and slot_n == s + 1)
                slot_row.append(_btn(
                    text=f"●{s + 1}" if selected else f"{s + 1}",
                    callback_data=f"achm_slot:{viewer}:{target}:{iid}:{s}:{page_i}",
                    style="success" if selected else "default",
                ))
            if it.get("kind") == "free":
                slot_row.append(_btn(
                    text="Удал.",
                    callback_data=f"achm_del:{viewer}:{target}:{iid}:{page_i}",
                    style="danger",
                ))
            rows.append(slot_row)

    nav = _nav_row(
        page_i=page_i,
        pages=pages,
        prev_cb=f"achm_pg:{viewer}:{target}:{page_i - 1}",
        next_cb=f"achm_pg:{viewer}:{target}:{page_i + 1}",
    )
    if nav:
        rows.append(nav)

    rows.append([_profile_back_button(viewer, target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_achievements_profile_button(viewer_id: int, target_user_id: int) -> InlineKeyboardButton:
    return _btn(
        text="Все достижения",
        callback_data=f"achm_all:{int(viewer_id)}:{int(target_user_id)}",
        style="primary",
        icon_custom_emoji_id=ach.ACHIEVEMENTS_HEADER_EMOJI,
    )
