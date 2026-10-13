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

from cases.design import (  # noqa: E402
    KEY,
    buy_label,
    case_by_id,
    face,
    key_text,
    match_bought,
    need_key_text,
    owns,
    ready_open_text,
    stamp_callback,
    use_lines,
)
from json_db_codec import decode_json_payload  # noqa: E402


def _button(target: str, user_id: int) -> dict:
    item = face(target) or {}
    fields = {
        "text": buy_label(item.get("name") or "предмет"),
        "callback_data": stamp_callback(f"cs:find:{target}:home", int(user_id)),
    }
    premium = str(item.get("premium") or "")
    if premium.isdigit():
        fields["icon_custom_emoji_id"] = premium
    return fields


def _back_button(user_id: int) -> dict:
    return {
        "text": "Назад",
        "callback_data": stamp_callback("cs:guide:home", int(user_id)),
    }


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
    payload["reply_markup"] = {"inline_keyboard": rows or []}
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
        key_finishes_case = bought == "key" and wanted in ("small", "mid", "large")
        if wanted == "cases":
            if bought == "key":
                return
        elif wanted != bought and not key_finishes_case:
            return
        item = face(bought)
        if item is None:
            return
        bag_row = await pool.fetchrow("SELECT items FROM users WHERE user_id = $1", int(user_id))
        bag = decode_json_payload(bag_row["items"]) if bag_row else {}
        catalog = [face(code) for code in ("key", "small", "mid", "large")]
        dex_rows = await pool.fetch(
            """
            SELECT id, name, name1 FROM dex
            WHERE name1 = ANY($1::text[]) OR lower(name) = ANY($2::text[])
            """,
            [row["name1"] for row in catalog if row],
            [row["name"].lower() for row in catalog if row],
        )
        dex_ids = {}
        for row in dex_rows:
            for known in catalog:
                if not known:
                    continue
                if str(row["name1"] or "") == known["name1"] or str(row["name"] or "").lower() == known["name"].lower():
                    dex_ids[known["id"]] = row["id"]
        held_cases = [
            case for case in catalog
            if case and case["id"] != "key" and owns(bag, case, dex_ids.get(case["id"]))
        ]
        has_key = owns(bag, KEY, dex_ids.get("key"))
        if bought != "key" and item and not any(case["id"] == item["id"] for case in held_cases):
            held_cases.append(item)
        opened = face(wanted) if key_finishes_case else None
        if opened and owns(bag, opened, dex_ids.get(opened["id"])):
            if not any(case["id"] == opened["id"] for case in held_cases):
                held_cases.append(opened)
        try:
            saved = await pool.fetch("SELECT case_id, max_cute FROM case_rules")
        except Exception:
            saved = []
        ceilings = {str(row["case_id"]): int(row["max_cute"]) for row in saved}
        for case in held_cases:
            if not case:
                continue
            base = case_by_id(case["id"])
            case["max"] = ceilings.get(case["id"], int(base["max"]) if base else 0)
        rows = []
        if held_cases and has_key:
            text = ready_open_text(held_cases, fresh=True)
        elif held_cases:
            text = (
                f"{need_key_text(held_cases[0]['id'])}\n"
                "<i>Потом напишите сообщение ниже.</i>\n"
                f"{use_lines(held_cases)}"
            )
            rows = [[_button("key", user_id)]]
        elif bought == "key":
            text = key_text()
            rows = [[_button(case_id, user_id)] for case_id in ("small", "mid", "large")]
        else:
            text = need_key_text(bought)
            rows = [[_button("key", user_id)]]
        rows.append([_back_button(user_id)])
        edited = await _edit(int(prompt["chat_id"]), int(prompt["message_id"]), text, rows)
        if edited:
            await pool.execute("DELETE FROM case_buy_prompts WHERE user_id = $1", int(user_id))
    except Exception:
        log.exception("case buy nudge skipped")
