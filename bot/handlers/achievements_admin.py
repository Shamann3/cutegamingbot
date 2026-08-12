# -*- coding: utf-8 -*-
"""Админ-команды выдачи/снятия достижений профиля."""

from __future__ import annotations

import html
import re
from typing import Any, Optional, Tuple

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.funcs import achievements as ach

# Pending official pick: admin_id -> target_user_id
_pending_official: dict[int, int] = {}
_pending_revoke: dict[int, int] = {}

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
            m = re.match(rf"(?is)^\s*{re.escape(p)}\s*(.*)$", text.strip())
            rest = (m.group(1) if m else "").strip()
            return p, rest
    return None


async def _resolve_target_user_id(message: Message, db, rest: str) -> Tuple[Optional[int], str]:
    """Returns (user_id, leftover_text_for_achievement)."""
    # Reply first
    if message.reply_to_message and message.reply_to_message.from_user:
        return int(message.reply_to_message.from_user.id), rest

    leftover = rest.strip()
    if not leftover:
        return None, ""

    parts = leftover.split(None, 1)
    token = parts[0]
    after = parts[1] if len(parts) > 1 else ""

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


async def _refresh_profile(db, user_id: int) -> None:
    try:
        from bot.funcs.profile import update_profile_after_data_change
        await update_profile_after_data_change(int(user_id), db=db)
    except Exception as e:
        print(f"[ACH] profile refresh skip: {e!r}")


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

    # «наградить» / «наградить официально» без текста → пикер
    if official_mode or not leftover:
        if can_off and (official_mode or not leftover):
            # если есть только право на офиц. или явно официально / пустое тело
            if official_mode or (not leftover and can_off and not can_free):
                return await _send_official_picker()
            if official_mode or not leftover:
                # пустой текст при наличии обоих прав → пикер официальных (удобнее)
                if not leftover:
                    return await _send_official_picker()

    # Free achievement
    if not leftover:
        await message.reply(
            "<b>Добавьте текст награды</b> после команды "
            "или напишите <code>наградить официально</code>.",
            parse_mode="HTML",
        )
        return True

    if not can_free:
        await message.reply("<b>Нет права выдавать свободные достижения.</b>", parse_mode="HTML")
        return True

    rest_text, ents = _slice_entities_for_rest(message, prefix, leftover)
    title_html, emoji_id, fallback = ach.sanitize_achievement_html(rest_text, ents)
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
    kb_rows = []
    for iid, it in rows[:25]:
        kind = "★" if it.get("kind") == "official" else "✧"
        title_plain = ach.strip_tg_emoji(it.get("title_html") or "")[:40]
        kb_rows.append([_btn(
            text=f"{kind} {title_plain}",
            callback_data=f"ach_rev:{target_id}:{iid}",
            style="danger",
        )])
    await message.reply(
        f"<tg-emoji emoji-id='{ach.ACHIEVEMENTS_HEADER_EMOJI}'>🎩</tg-emoji> "
        f"<b>Что снять?</b>\nИгрок <code>{target_id}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
    return True


async def handle_achievements_callback(callback: CallbackQuery, db) -> bool:
    data = str(callback.data or "")
    if not (data.startswith("ach_grant_off:") or data.startswith("ach_rev:") or data.startswith("achm_")):
        return False

    user_id = int(callback.from_user.id)

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
            )
        except Exception:
            pass
        await callback.answer("Готово")
        return True

    if data.startswith("ach_rev:"):
        parts = data.split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка", show_alert=True)
            return True
        target_id = int(parts[1])
        iid = parts[2]
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
        doc, ok = ach.admin_remove_item(doc, iid)
        if ok:
            await ach.save_user_achievements_doc(db, target_id, doc)
            await _refresh_profile(db, target_id)
        await callback.answer("Снято" if ok else "Не найдено", show_alert=not ok)
        try:
            await callback.message.edit_text(
                f"<b>{'Достижение снято' if ok else 'Не удалось снять'}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return True

    # Profile manage callbacks achm_
    return await _handle_profile_manage_cb(callback, db)


async def _handle_profile_manage_cb(callback: CallbackQuery, db) -> bool:
    from bot.funcs.profile import (
        user_message_mappingprofile,
        _profile_safe_edit_message,
    )

    data = str(callback.data or "")
    # achm_all:viewer:target
    # achm_up:viewer:target:iid
    # achm_dn:viewer:target:iid
    # achm_del:viewer:target:iid
    # achm_delok:viewer:target:iid
    # achm_back:viewer:target
    parts = data.split(":")
    if len(parts) < 3:
        return False
    action = parts[0]
    try:
        viewer = int(parts[1])
        target = int(parts[2])
    except Exception:
        await callback.answer("Ошибка", show_alert=True)
        return True

    clicker = int(callback.from_user.id)
    if clicker != viewer:
        await callback.answer("Это не ваше меню", show_alert=True)
        return True

    mid = callback.message.message_id if callback.message else None
    if mid and (viewer not in user_message_mappingprofile or user_message_mappingprofile[viewer] != mid):
        # still allow if mapped differently - soft check
        pass

    is_owner = clicker == target

    if action == "achm_all":
        doc = await ach.get_user_achievements_doc(db, target)
        name = callback.message.chat.first_name if False else ""
        try:
            # try get display name from caption — skip
            name = ""
        except Exception:
            name = ""
        text = ach.format_full_achievements_html(doc, owner_name=name)
        kb = _build_manage_keyboard(viewer, target, doc, is_owner=is_owner)
        try:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                if "DOCUMENT_INVALID" in str(e) or "can't parse" in str(e).lower():
                    plain = ach.strip_tg_emoji(text)
                    try:
                        await callback.message.edit_caption(caption=plain, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        await callback.message.edit_text(plain, parse_mode="HTML", reply_markup=kb)
                else:
                    await callback.answer("Не удалось открыть", show_alert=True)
                    return True
        await callback.answer()
        return True

    if action == "achm_back":
        try:
            from bot.funcs.profile import _profile_full_refresh_and_render
            await _profile_full_refresh_and_render(
                viewer_id=viewer,
                target_user_id=target,
                db=db,
                bot1=callback.bot,
                chat_id=int(callback.message.chat.id),
                message_obj=callback.message,
            )
        except Exception as e:
            print(f"[ACH] back to profile: {e!r}")
            await callback.answer("Обновите профиль", show_alert=True)
            return True
        await callback.answer()
        return True

    if not is_owner:
        await callback.answer("Только владелец профиля", show_alert=True)
        return True

    iid = parts[3] if len(parts) > 3 else ""
    doc = await ach.get_user_achievements_doc(db, target)

    if action == "achm_up":
        doc = ach.move_item(doc, iid, -1)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_dn":
        doc = ach.move_item(doc, iid, 1)
        await ach.save_user_achievements_doc(db, target, doc)
    elif action == "achm_del":
        it = doc.get("items", {}).get(iid)
        if not it or it.get("kind") != "free":
            await callback.answer("Можно удалять только свободные", show_alert=True)
            return True
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [_btn(text="Да, удалить", callback_data=f"achm_delok:{viewer}:{target}:{iid}", style="danger")],
            [_btn(text="Отмена", callback_data=f"achm_all:{viewer}:{target}", style="default")],
        ])
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer("Подтвердите удаление")
        return True
    elif action == "achm_delok":
        doc, ok = ach.remove_free_item(doc, iid)
        if ok:
            await ach.save_user_achievements_doc(db, target, doc)
            await callback.answer("Удалено")
        else:
            await callback.answer("Не удалось", show_alert=True)
    else:
        return False

    text = ach.format_full_achievements_html(doc)
    kb = _build_manage_keyboard(viewer, target, doc, is_owner=True)
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    await callback.answer()
    return True


def _build_manage_keyboard(viewer: int, target: int, doc: dict, *, is_owner: bool) -> InlineKeyboardMarkup:
    rows = []
    items = list(ach.showcase_items(doc, 99))  # use user order for manage
    # Actually manage should use full order
    doc_n = ach._normalize_doc(doc)
    ordered = [(iid, doc_n["items"][iid]) for iid in doc_n["order"] if iid in doc_n["items"]]
    if is_owner:
        for iid, it in ordered[:12]:
            title = ach.strip_tg_emoji(it.get("title_html") or "…")[:18]
            row = [
                _btn(text="↑", callback_data=f"achm_up:{viewer}:{target}:{iid}"),
                _btn(text="↓", callback_data=f"achm_dn:{viewer}:{target}:{iid}"),
            ]
            if it.get("kind") == "free":
                row.append(_btn(text="Удалить", callback_data=f"achm_del:{viewer}:{target}:{iid}", style="danger"))
            else:
                row.append(_btn(text=title, callback_data=f"achm_all:{viewer}:{target}"))
            rows.append(row)
    rows.append([_btn(
        text="К профилю",
        callback_data=f"achm_back:{viewer}:{target}",
        style="default",
        icon_custom_emoji_id="5226660202035554522",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_achievements_profile_button(viewer_id: int, target_user_id: int) -> InlineKeyboardButton:
    return _btn(
        text="Все достижения",
        callback_data=f"achm_all:{int(viewer_id)}:{int(target_user_id)}",
        style="primary",
        icon_custom_emoji_id=ach.ACHIEVEMENTS_HEADER_EMOJI,
    )
