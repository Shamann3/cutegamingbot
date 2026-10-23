# -*- coding: utf-8 -*-
"""Бонус +: интро, открытие доски и выдача наград за техгруппы."""
from __future__ import annotations

import html
import sys
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from flame_bonus_plus import (  # noqa: E402
    acquire_bonus_item,
    board_range,
    gift_plus_defaults,
    pay_user_from_tech,
    roll_extra_bundle,
)
from flame_bonus_plus_copy import (  # noqa: E402
    HISTORY_BOARD,
    HISTORY_EXTRA,
    HISTORY_PROJECT,
    alert_gone,
    alert_stranger,
    button_later,
    button_open,
    screen_fail,
    screen_intro,
    screen_later,
    screen_need_cute,
    screen_off,
    screen_result,
)

_pending: dict[int, dict] = {}


def _pool(db):
    return getattr(db, "pool", None)


def remember_pending(user_id: int, *, item_name: str, conf: dict, chat_id: int) -> None:
    _pending[int(user_id)] = {
        "item_name": str(item_name or ""),
        "conf": dict(conf or {}),
        "chat_id": int(chat_id),
    }


def take_pending(user_id: int) -> dict | None:
    return _pending.pop(int(user_id), None)


def peek_pending(user_id: int) -> dict | None:
    return _pending.get(int(user_id))


def intro_markup(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=button_open()[:64],
            callback_data=f"bp:go:{int(user_id)}",
            style="success",
        )],
        [InlineKeyboardButton(
            text=button_later()[:64],
            callback_data=f"bp:no:{int(user_id)}",
            style="danger",
        )],
    ])


def intro_text(conf: dict) -> str:
    clean = gift_plus_defaults(conf)
    lo, hi = board_range(clean)
    items_on = bool(clean["item_on"] and any(
        str(row.get("kind")) == "item" and str(row.get("item_name") or row.get("itemName") or "").strip()
        for row in (clean.get("drops") or [])
    ))
    return screen_intro(mult=clean["mult"], kuty_lo=lo, kuty_hi=hi, items_on=items_on)


async def show_intro(message, db, *, item_name: str) -> bool:
    """Показать первый экран. False — предмет не списывать."""
    from bot.funcs.flame import load_gift

    conf = await load_gift(db)
    if not conf.get("enabled"):
        await message.reply(screen_off(), parse_mode="HTML")
        return False
    remember_pending(
        int(message.from_user.id),
        item_name=item_name,
        conf=conf,
        chat_id=int(message.chat.id),
    )
    await message.reply(
        intro_text(conf),
        parse_mode="HTML",
        reply_markup=intro_markup(int(message.from_user.id)),
        disable_web_page_preview=True,
    )
    return False


async def open_board_for(user, chat_id: int, reply_to, conf: dict) -> bool:
    from main import process_bonus_request
    return bool(await process_bonus_request(
        user=user,
        chat_id=int(chat_id),
        reply_to=reply_to,
        from_gift_item=True,
        gift_conf=conf,
    ))


async def apply_cell_rewards(db, user_id: int, board_amount: int, conf: dict) -> dict:
    """Начислить куты с клетки и независимые доп. награды. Деньги — с техгрупп."""
    pool = _pool(db)
    conf = gift_plus_defaults({**(conf or {}), "drops": (conf or {}).get("drops") or []})
    need = max(0, int(board_amount or 0))
    board_paid = 0
    if pool is not None and need > 0:
        board_paid = await pay_user_from_tech(pool, int(user_id), need)
    if board_paid < need and need > 0:
        # Техгруппы не покрыли клетку — всё равно отдадим сумму, чтобы 🎁 не пропал впустую.
        try:
            bal = await db.get_user_balance(int(user_id))
            await db.update_user_balance(int(user_id), int(bal or 0) + (need - board_paid))
            board_paid = need
        except Exception as exc:
            print(f"[BONUS+] board fallback {user_id}: {exc}")

    if board_paid > 0:
        try:
            await db.cutehistory_plus(int(user_id), board_paid, HISTORY_BOARD)
        except Exception:
            pass

    bundle = roll_extra_bundle(conf)
    extra_paid = 0
    if pool is not None and int(bundle.get("extra_kuty") or 0) > 0:
        extra_paid = await pay_user_from_tech(pool, int(user_id), int(bundle["extra_kuty"]))
        if extra_paid > 0:
            try:
                await db.cutehistory_plus(int(user_id), extra_paid, HISTORY_EXTRA)
            except Exception:
                pass

    item_line = ""
    project_kuty = 0
    if pool is not None and bundle.get("want_item") and bundle.get("item_names"):
        got = await acquire_bonus_item(
            pool,
            int(user_id),
            list(bundle["item_names"]),
            int(conf.get("fallback_pct") or 30),
        )
        if got.get("ok"):
            if got.get("source") == "project_kuty":
                project_kuty = int(got.get("project_kuty") or got.get("paid") or 0)
                if project_kuty > 0:
                    try:
                        await db.cutehistory_plus(int(user_id), project_kuty, HISTORY_PROJECT)
                    except Exception:
                        pass
            else:
                item_line = str(got.get("line") or "")
                try:
                    from bot.funcs.flame import note_gift_loot
                    await note_gift_loot(
                        db,
                        int(user_id),
                        "item",
                        1,
                        got.get("item_name") or "",
                        got.get("item_name") or "",
                    )
                except Exception:
                    pass

    try:
        from bot.funcs.flame import note_gift_loot
        if board_paid > 0:
            await note_gift_loot(db, int(user_id), "kuty", board_paid, "", f"{board_paid} кут")
        if extra_paid > 0:
            await note_gift_loot(db, int(user_id), "kuty", extra_paid, "", f"{extra_paid} кут")
    except Exception:
        pass

    return {
        "board_kuty": board_paid,
        "extra_kuty": extra_paid,
        "project_kuty": project_kuty,
        "item_line": item_line,
        "text": screen_result(
            board_kuty=board_paid or int(board_amount or 0),
            extra_kuty=extra_paid,
            project_kuty=project_kuty,
            item_line=item_line,
        ),
    }


async def bonus_plus_click(call) -> None:
    data = str(getattr(call, "data", "") or "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "bp":
        return
    action, owner = parts[1], parts[2]
    clicker = int(getattr(getattr(call, "from_user", None), "id", 0) or 0)
    if not owner.isdigit() or int(owner) != clicker:
        try:
            await call.answer(alert_stranger(), show_alert=True)
        except Exception:
            pass
        return

    from main import db

    if action == "no":
        take_pending(clicker)
        try:
            await call.message.edit_text(screen_later(), parse_mode="HTML")
        except Exception:
            try:
                await call.message.answer(screen_later(), parse_mode="HTML")
            except Exception:
                pass
        try:
            await call.answer()
        except Exception:
            pass
        return

    if action != "go":
        try:
            await call.answer()
        except Exception:
            pass
        return

    pending = take_pending(clicker)
    if not pending:
        try:
            await call.answer(alert_gone(), show_alert=True)
        except Exception:
            pass
        return

    conf = pending.get("conf") or {}
    item_name = str(pending.get("item_name") or "")
    chat_id = int(pending.get("chat_id") or call.message.chat.id)

    # Cute в имени
    user = call.from_user
    try:
        from main import _has_family_tag
        cute_ok = _has_family_tag(user)
    except Exception:
        cute_ok = "cute" in (user.first_name or "").lower()
    if not cute_ok:
        remember_pending(clicker, item_name=item_name, conf=conf, chat_id=chat_id)
        shown = html.escape((user.first_name or "имя").strip() or "имя")
        try:
            await call.message.edit_text(screen_need_cute(shown), parse_mode="HTML")
        except Exception:
            pass
        try:
            await call.answer()
        except Exception:
            pass
        return

    try:
        ok = await open_board_for(user, chat_id, call.message, conf)
    except Exception as exc:
        print(f"[BONUS+] open: {exc}")
        remember_pending(clicker, item_name=item_name, conf=conf, chat_id=chat_id)
        try:
            await call.message.edit_text(screen_fail(), parse_mode="HTML")
        except Exception:
            pass
        try:
            await call.answer()
        except Exception:
            pass
        return

    if ok and item_name:
        try:
            await db.delete_user_inventory1(clicker, item_name)
        except Exception as exc:
            print(f"[BONUS+] consume {clicker}: {exc}")
    elif not ok:
        remember_pending(clicker, item_name=item_name, conf=conf, chat_id=chat_id)
        try:
            await call.message.edit_text(screen_fail(), parse_mode="HTML")
        except Exception:
            pass
    try:
        await call.answer()
    except Exception:
        pass
