# -*- coding: utf-8 -*-
"""Кнопки «Принять» и «Отклонить» в личке создателя по заявке на снятие админки."""
from __future__ import annotations

import sys
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name="admin_drop")
_attached = False


def _realm():
    folder = str(Path(__file__).resolve().parents[2] / "server")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import group_realm
    return group_realm


@router.callback_query(F.data.startswith("admdrop:"))
async def decide_drop(call: CallbackQuery):
    parts = str(call.data or "").split(":")
    if len(parts) != 3 or parts[1] not in {"0", "1"}:
        await call.answer()
        return
    try:
        request_id = int(parts[2])
    except ValueError:
        await call.answer()
        return
    user = call.from_user
    if user is None:
        await call.answer()
        return
    try:
        result = await _realm().decide_admin_drop(request_id, int(user.id), parts[1] == "1")
    except Exception:
        await call.answer("Заявку сейчас не удалось решить", show_alert=True)
        return
    toast = str(result.get("toast") or "Готово")[:180]
    await call.answer(toast, show_alert=not result.get("ok"))
    text = str(result.get("text") or "")
    message = call.message
    if text and message is not None:
        try:
            await message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass


def attach_admin_drop(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(router)
    _attached = True
