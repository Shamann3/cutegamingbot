# -*- coding: utf-8 -*-
"""После покупки с кнопки кейса меняет то же сообщение. Покупка здесь не считается."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger("cute-farm")

_py = str(Path(__file__).resolve().parent / "py")
if _py not in sys.path:
    sys.path.insert(0, _py)

from cases.design import face, held_text, match_bought, stamp_callback  # noqa: E402


def _button(target: str, user_id: int) -> dict:
    item = face(target) or {}
    fields = {
        "text": item.get("name") or "Предмет",
        "callback_data": stamp_callback(f"cs:find:{target}", int(user_id)),
        "style": "success",
    }
    premium = str(item.get("premium") or "")
    if premium.isdigit():
        fields["icon_custom_emoji_id"] = premium
    return fields


async def _edit(chat_id: int, message_id: int, text: str, rows: list) -> bool:
    try:
        import aiohttp
        from config import BOT_TOKEN
    except Exception:
        return False
    if not BOT_TOKEN:
        return False
    payload = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if rows:
        payload["reply_markup"] = {"inline_keyboard": rows}
    timeout = aiohttp.ClientTimeout(total=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
        return bool(isinstance(data, dict) and data.get("ok"))
    except Exception:
        log.warning("case prompt edit failed")
        return False


async def nudge_after_purchase(pool, user_id: int, item_id) -> None:
    raw_id = str(item_id or "").strip()
    if not raw_id.isdigit():
        return
    try:
        dex = await pool.fetchrow(
            "SELECT id, name, name1 FROM dex WHERE id = $1",
            int(raw_id),
        )
        if not dex:
            return
        bought = match_bought(dex["name1"], dex["name"])
        if not bought:
            return
        prompt = await pool.fetchrow(
            "SELECT chat_id, message_id, target FROM case_buy_prompts WHERE user_id = $1",
            int(user_id),
        )
        if not prompt:
            return
        wanted = str(prompt["target"] or "")
        if wanted == "cases":
            if bought == "key":
                return
        elif wanted != bought:
            return
        item = face(bought)
        if item is None:
            return
        text = held_text(item["name"], item["emoji"], item["premium"])
        rows = []
        if bought == "key":
            rows = [[_button(case_id, user_id)] for case_id in ("small", "mid", "large")]
            text += "\n<i>Дальше — кейс.</i>"
        else:
            rows = [[_button("key", user_id)]]
            text += "\n<i>Дальше — ключ, если его ещё нет.</i>"
        edited = await _edit(int(prompt["chat_id"]), int(prompt["message_id"]), text, rows)
        if edited:
            await pool.execute("DELETE FROM case_buy_prompts WHERE user_id = $1", int(user_id))
    except Exception:
        log.warning("case buy nudge skipped")
