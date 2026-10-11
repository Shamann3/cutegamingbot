# -*- coding: utf-8 -*-
"""После покупки с кнопки водных игр меняет то же сообщение на следующий шаг.

Сама покупка здесь не считается и не меняется. Если человек купил что-то другое
или кнопки не было — функция молча выходит.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger("cute-farm")

_TABLE_READY = False


def _load_design():
    py = str(Path(__file__).resolve().parent / "py")
    if py not in sys.path:
        sys.path.insert(0, py)
    from water_games import design as words
    return words


async def _ensure_table(pool) -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_buy_prompts (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            name1 TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _TABLE_READY = True


def _named_count(items: dict, *names: str) -> int:
    wanted = {str(name).strip().lower() for name in names if str(name).strip()}
    total = 0
    for key, value in (items or {}).items():
        if str(key).strip().lower() not in wanted:
            continue
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return total


def _callback(words, data: str) -> dict | None:
    for screen_name in ("splash_need", "home", "splash_ready"):
        for row in words.button_rows(screen_name):
            for button in row:
                if button.get("data") != data:
                    continue
                fields = {
                    "text": button["text"],
                    "callback_data": button["data"],
                    "style": button.get("style") or "default",
                }
                if button.get("emoji"):
                    fields["icon_custom_emoji_id"] = button["emoji"]
                return fields
    return None


async def _group_rows(pool, words) -> list:
    try:
        rows = await pool.fetch(
            """
            SELECT title, username
            FROM epsilon_official_groups
            WHERE is_official AND username <> ''
            ORDER BY title
            LIMIT 8
            """
        )
    except Exception:
        log.warning("water buy groups unavailable")
        return []
    buttons = []
    seen = set()
    for row in rows:
        username = words.public_group_name(row["username"])
        if not username or username.lower() in seen:
            continue
        seen.add(username.lower())
        title = " ".join(str(row["title"] or username).split())[:32] or username
        buttons.append([{"text": title, "url": f"https://t.me/{username}"}])
    return buttons


def _plain_buttons(rows: list) -> list:
    plain = []
    for row in rows:
        built = []
        for button in row:
            built.append({
                "text": button.get("text") or " ",
                **({"url": button["url"]} if button.get("url") else {"callback_data": button.get("callback_data") or "wg:home"}),
            })
        if built:
            plain.append(built)
    return plain


async def _edit_message(chat_id: int, message_id: int, text: str, rows: list) -> bool:
    try:
        import aiohttp
        from config import BOT_TOKEN
    except Exception:
        return False
    if not BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"

    async def send(markup_rows: list) -> bool:
        payload = {
            "chat_id": int(chat_id),
            "message_id": int(message_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": markup_rows},
        }
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
        return bool(isinstance(data, dict) and data.get("ok"))

    try:
        if await send(rows):
            return True
        return await send(_plain_buttons(rows))
    except Exception:
        log.warning("water prompt edit failed")
        return False


async def nudge_after_purchase(pool, user_id: int, item_id) -> None:
    """Меняет сообщение с кнопкой покупки, если куплен именно тот предмет."""
    raw_id = str(item_id or "").strip()
    if not raw_id.isdigit():
        return
    try:
        await _ensure_table(pool)
        words = _load_design()
        dex = await pool.fetchrow(
            "SELECT id, name, name1, emoji FROM dex WHERE id = $1",
            int(raw_id),
        )
        if not dex:
            return
        kind = words.water_buy_kind(dex["name1"], dex["name"])
        if not kind:
            return
        prompt = await pool.fetchrow(
            """
            SELECT chat_id, message_id, name1
            FROM water_buy_prompts
            WHERE user_id = $1
            """,
            int(user_id),
        )
        if not prompt or str(prompt["name1"] or "") != kind:
            return
        from user_items import count_item_in_storage, parse_items

        stored = parse_items(await pool.fetchval(
            "SELECT items FROM users WHERE user_id = $1",
            int(user_id),
        ))
        kit = await pool.fetch(
            """
            SELECT id, name1, name FROM dex
            WHERE name1 = ANY($1::text[]) OR lower(name) = ANY($2::text[])
            """,
            ["pistoletik", "watercraft"],
            ["пистолетик", "вода"],
        )
        pistol = kind == "pistoletik"
        water = kind == "watercraft"
        for row in kit:
            row_kind = words.water_buy_kind(row["name1"], row["name"])
            have = _named_count(stored, row["name"]) > 0
            try:
                have = have or count_item_in_storage(stored, str(row["id"])) > 0
            except Exception:
                pass
            if row_kind == "pistoletik" and have:
                pistol = True
            if row_kind == "watercraft" and have:
                water = True
        face_emoji = (dex["emoji"] or "").strip() or "💧"
        face_name = (dex["name"] or "").strip() or "Предмет"
        text, step = words.after_buy_text(
            kind=kind,
            emoji=face_emoji,
            name=face_name,
            pistol=pistol,
            water=water,
        )
        if not text:
            return
        rows = []
        if step == "water":
            button = _callback(words, "wg:find:watercraft")
            if button:
                rows.append([button])
        elif step == "pistol":
            button = _callback(words, "wg:find:pistoletik")
            if button:
                rows.append([button])
        elif step == "shoot" and int(prompt["chat_id"]) == int(user_id):
            rows = await _group_rows(pool, words)
            if not rows:
                text += "\n<i>Ссылки на группу нет.</i>"
        edited = await _edit_message(int(prompt["chat_id"]), int(prompt["message_id"]), text, rows)
        if edited:
            await pool.execute("DELETE FROM water_buy_prompts WHERE user_id = $1", int(user_id))
    except Exception:
        log.warning("water buy nudge skipped")
