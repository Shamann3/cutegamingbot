# -*- coding: utf-8 -*-
"""Пиар в группах: схема, заявки, посев, подарок, рента."""

from __future__ import annotations

import json
import logging
import re
import sys
import asyncio
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from pr_groups_logic import (  # noqa: E402
    BAN_DAYS,
    CLAIM_COLUMNS,
    CONFIRM_HOURS,
    DEFAULT_REJECT_REASONS,
    DEFAULT_TERM_DAYS,
    FIRST_NO_HOLD_HOURS,
    HOLD_GROUP_STATUSES,
    IN_PROGRESS_STATUSES,
    LIVE_STATUSES,
    MAX_LIVE_SEEDS,
    MAX_PENDING,
    PHOTO_HOURS,
    PHOTOS_REQUIRED,
    REJECT_HOLD_HOURS,
    ROLE_OWNER,
    ROLE_RECO,
    ST_ACCEPTING,
    ST_BURNED,
    ST_CANCELLED,
    ST_CONFIRM_RETRY,
    ST_ENDED,
    ST_ENDING,
    ST_EXPIRED,
    ST_FULFILLING,
    ST_LIVE,
    ST_PENDING,
    ST_PHOTOS,
    ST_REJECTED,
    ST_WAIT_CONFIRM,
    WEEK_SEED_STATUSES,
    CONFIRM_WAIT_STATUSES,
    MONEY_UNWIND_STATUSES,
    bet_fits_gift_lock,
    classify_player,
    gift_covers_this_play,
    is_broke,
    is_new_class,
    left_days_hint,
    LINK_MODES,
    looks_like_confirm,
    nika_step_amount,
    startgroup_url,
    promoter_cut,
    recommend_seed,
    recommend_split,
    spendable_amount,
    weekly_seed_budget,
    MINE_STATUSES,
    claim_button_label,
    claim_set_sql,
    alter_claim_column_sql,
    html_without_custom_emoji,
    moscow_day_start,
)

from pr_groups_design import (  # noqa: E402
    HELP_TASKS,
    ICON_ADMIN,
    ICON_BACK,
    ICON_BACK_HUB,
    ICON_CANT,
    ICON_CHECK,
    ICON_CONT,
    ICON_EARN,
    ICON_GO,
    ICON_GROUPS,
    ICON_MORE,
    ICON_NO,
    ICON_OPEN,
    ICON_OWNER,
    ICON_PUBLIC,
    ICON_RECO,
    ICON_UNDO,
    ICON_WROTE,
    SCREENS,
    TASKS_MENU,
    TASKS_MENU_ICON_ID,
    TASKS_MENU_TEXT,
    emoji_id as design_emoji_id,
    iter_button_rows,
    plain,
    say,
)

ICON_OK = ICON_CHECK

_GIFT_CLAW = ContextVar("pr_gift_claw", default=False)
_fulfill_lock = asyncio.Lock()
_gift_grant_locks: dict[int, asyncio.Lock] = {}

log = logging.getLogger("pr_groups")

PR_HUB = "prg:hub"
PR_TASKS = "questions_stars"
PR_START = "prg:go"
PR_CHECK = "prg:chk"
PR_HOW = "prg:how"
PR_PUBLIC = "prg:pub"
PR_ADMIN = "prg:adm"
PR_MINE = "prg:mine"
PR_BACK = "prg:back"
PR_WROTE = "prg:wrote"
PR_UNDO = "prg:undo"
PR_CANT = "prg:cant"
PR_OPEN = "prg:c:"
PR_PICK = "prg:g:"
PR_OWNER = "prg:own"
PR_RECO = "prg:rec"
PR_CANCEL = "prg:x"
PR_DROP_YES = "prg:z:"
PR_DROP_NO = "prg:zn"
PR_YES = "prgY:"
PR_NO = "prgN:"
PR_CONT = "prg:n:"


def _btn(text: str, data: str, icon: str | None = None, style: str = "default") -> InlineKeyboardButton:
    kwargs: dict[str, Any] = {"text": text, "callback_data": data, "style": style}
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


def _url(text: str, url: str, icon: str | None = None) -> InlineKeyboardButton:
    kwargs: dict[str, Any] = {"text": text, "url": url}
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


def markup_without_icons(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard:
        built: list[InlineKeyboardButton] = []
        for btn in row:
            kwargs: dict[str, Any] = {"text": str(btn.text or "·")}
            data = getattr(btn, "callback_data", None)
            url = getattr(btn, "url", None)
            if data:
                kwargs["callback_data"] = data
            elif url:
                kwargs["url"] = url
            else:
                continue
            style = getattr(btn, "style", None)
            if style:
                kwargs["style"] = style
            try:
                built.append(InlineKeyboardButton(**kwargs))
            except TypeError:
                kwargs.pop("style", None)
                built.append(InlineKeyboardButton(**kwargs))
        if built:
            rows.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def keyboard_icon_ids(markup: InlineKeyboardMarkup) -> list[str]:
    ids: list[str] = []
    for row in markup.inline_keyboard:
        for btn in row:
            icon = getattr(btn, "icon_custom_emoji_id", None) or ""
            if icon:
                ids.append(str(icon))
    return ids


def _btn_visible(show: str | None, ctx: dict[str, Any]) -> bool:
    flag = str(show or "always")
    if flag in {"", "always"}:
        return True
    live = bool(ctx.get("live"))
    mine = bool(ctx.get("mine"))
    intent = str(ctx.get("intent") or "")
    status = str(ctx.get("status") or "")
    if flag == "live":
        return live
    if flag == "not_live":
        return not live
    if flag == "mine":
        return mine and not live
    if flag == "reco":
        return intent == ROLE_RECO
    if flag == "no_public":
        return bool(ctx.get("no_public"))
    if flag == "no_admin":
        return bool(ctx.get("no_admin"))
    if flag == "have_photos":
        return int(ctx.get("have") or 0) > 0
    if flag == "has_username":
        return bool(str(ctx.get("username") or "").strip())
    if flag == "photos":
        return status == ST_PHOTOS
    if flag == "wait_confirm":
        return status in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}
    if flag == "pending":
        return status == ST_PENDING
    if flag == "open":
        return status in IN_PROGRESS_STATUSES
    return True


_HTML_TAG = re.compile(r"<[^>]+>")


def _fill_btn_text(text: str, values: dict[str, Any]) -> str:
    class Safe(dict):
        def __missing__(self, key: str) -> str:
            return ""
    filled = str(text or "").format_map(Safe(values))
    return " ".join(_HTML_TAG.sub("", filled).split())


def _resolve_go(go: str, ctx: dict[str, Any]) -> tuple[str, str]:
    """kind url|cb, payload."""
    username = str(ctx.get("username") or "").strip().lstrip("@")
    bot_username = str(ctx.get("bot_username") or "CuteGamingBot")
    cid = int(ctx.get("id") or ctx.get("claim_id") or 0)
    token = int(ctx.get("token") or 0)
    chat_id = ctx.get("chat_id")
    mapping = {
        "owner": ("cb", PR_OWNER),
        "reco": ("cb", PR_RECO),
        "earnings": ("cb", PR_MINE),
        "groups": ("cb", PR_MINE),
        "add_bot": ("url", startgroup_url(bot_username)),
        "cant": ("cb", PR_CANT),
        "check": ("cb", PR_CHECK),
        "public": ("cb", PR_PUBLIC),
        "admin": ("cb", PR_ADMIN),
        "open_group": ("url", f"https://t.me/{username}" if username else ""),
        "wrote": ("cb", PR_WROTE),
        "undo": ("cb", PR_UNDO),
        "cancel": ("cb", f"{PR_CANCEL}:{cid}" if cid else PR_CANCEL),
        "drop_yes": ("cb", f"{PR_DROP_YES}{cid}" if cid else ""),
        "drop_no": ("cb", PR_DROP_NO),
        "more": ("cb", PR_HUB),
        "continue_photo": ("cb", f"{PR_CONT}{cid}" if cid else ""),
        "yes": ("cb", f"{PR_YES}{cid}:{token}"),
        "no_confirm": ("cb", f"{PR_NO}{cid}:{token}"),
        "back_hub": ("cb", PR_HUB),
        "back_tasks": ("cb", PR_TASKS),
        "back_how": ("cb", PR_HOW),
        "back_mine": ("cb", PR_MINE),
        "open_claim": ("cb", f"{PR_OPEN}{cid}" if cid else ""),
        "pick_group": ("cb", f"{PR_PICK}{chat_id}" if chat_id is not None else ""),
    }
    return mapping.get(go, ("cb", ""))


def _design_button(item: dict[str, Any], ctx: dict[str, Any]) -> InlineKeyboardButton | None:
    kind, payload = _resolve_go(str(item.get("go") or ""), ctx)
    if not payload:
        return None
    text = _fill_btn_text(str(item.get("text") or ""), ctx)
    icon = design_emoji_id(str(item.get("icon") or ""))
    style = str(item.get("style") or item.get("color") or "default")
    if kind == "url":
        return _url(text, payload, icon or None)
    return _btn(text, payload, icon or None, style)


def _repeat_buttons(item: dict[str, Any], ctx: dict[str, Any]) -> list[list[InlineKeyboardButton]]:
    kind = str(item.get("repeat") or "")
    rows: list[list[InlineKeyboardButton]] = []
    if kind == "claims":
        for row in list(ctx.get("claims") or [])[:12]:
            local = dict(ctx)
            local["id"] = row.get("id")
            local["label"] = claim_button_label(row)
            btn = _design_button({**item, "icon": ""}, local)
            if btn:
                rows.append([btn])
    elif kind == "groups":
        for row in list(ctx.get("groups") or []):
            local = dict(ctx)
            local["chat_id"] = row.get("chat_id")
            local["title"] = (row.get("title") or str(row.get("chat_id")))[:32]
            btn = _design_button({**item, "icon": ""}, local)
            if btn:
                rows.append([btn])
    return rows


def keyboard_for(name: str, **ctx: Any) -> InlineKeyboardMarkup:
    spec = SCREENS[name]
    rows_out: list[list[InlineKeyboardButton]] = []
    for row in iter_button_rows(spec.get("buttons")):
        if isinstance(row, dict) and row.get("repeat"):
            rows_out.extend(_repeat_buttons(row, ctx))
            continue
        built: list[InlineKeyboardButton] = []
        for item in row:
            if not _btn_visible(item.get("show") or item.get("when"), ctx):
                continue
            btn = _design_button(item, ctx)
            if btn:
                built.append(btn)
        if built:
            rows_out.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows_out)


def entry_keyboard(*, mine: bool = False, live: bool = False) -> InlineKeyboardMarkup:
    return keyboard_for("hub", mine=mine, live=live)


def choose_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("choose")


def how_keyboard(
    *,
    intent: str = "",
    no_public: bool = False,
    no_admin: bool = False,
    bot_username: str = "CuteGamingBot",
) -> InlineKeyboardMarkup:
    name = "how_reco" if intent == ROLE_RECO else "how_owner"
    return keyboard_for(
        name,
        intent=intent,
        no_public=no_public,
        no_admin=no_admin,
        bot_username=bot_username,
    )


def how_public_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("how_public", intent=intent, bot_username=bot_username)


def how_admin_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    name = "how_admin_reco" if intent == ROLE_RECO else "how_admin"
    return keyboard_for(name, intent=intent, bot_username=bot_username)


def how_fix_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return how_admin_keyboard(bot_username, intent=intent)


def add_group_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    name = "bot_not_there_reco" if intent == ROLE_RECO else "bot_not_there"
    return keyboard_for(name, intent=intent, bot_username=bot_username)


def cant_add_keyboard(bot_username: str = "CuteGamingBot") -> InlineKeyboardMarkup:
    return keyboard_for("cant_add", bot_username=bot_username)


def switch_to_reco_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("not_owner_switch")


def switch_to_owner_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("are_owner_switch")


def role_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("pick_role")


def groups_keyboard(rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    return keyboard_for("pick_group", groups=rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return photo_keyboard(0)


def photo_keyboard(have: int = 0) -> InlineKeyboardMarkup:
    return keyboard_for("wait_photo", have=have)


def hub_only_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("not_your_claim")


def after_cancel_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("cancelled")


def after_owner_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("after_proofs_owner", mine=True)


def after_reco_keyboard(username: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("after_photos_reco", username=username, mine=True)


def joined_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("bot_joined")


def pending_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("two_pending", mine=True)


def mine_keyboard(rows: list[dict[str, Any]] | None = None, *, live: bool = False) -> InlineKeyboardMarkup:
    name = "earnings" if live else "mine"
    return keyboard_for(name, claims=list(rows or []), live=live)


def card_keyboard(claim: dict[str, Any] | None = None) -> InlineKeyboardMarkup:
    data = claim or {}
    return keyboard_for(
        "card",
        username=str(data.get("chat_username") or ""),
        status=str(data.get("status") or ""),
        id=int(data.get("id") or 0),
    )


def resume_keyboard(status: str, claim: dict[str, Any] | None = None) -> InlineKeyboardMarkup:
    data = claim or {}
    return keyboard_for(
        "resume",
        status=str(status or data.get("status") or ""),
        id=int(data.get("id") or 0),
    )


def confirm_keyboard(claim_id: int, token: int = 0) -> InlineKeyboardMarkup:
    return keyboard_for("confirm", claim_id=claim_id, id=claim_id, token=token)


def need_public_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("need_public", intent=intent, bot_username=bot_username)


def need_admin_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    name = "need_admin_reco" if intent == ROLE_RECO else "need_admin"
    return keyboard_for(name, intent=intent, bot_username=bot_username)


def need_link_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("need_link", intent=intent, bot_username=bot_username)


def forward_no_group_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("forward_no_group", intent=intent, bot_username=bot_username)


def link_invite_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("link_invite", intent=intent, bot_username=bot_username)


def group_not_found_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("group_not_found", intent=intent, bot_username=bot_username)


def not_in_group_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("not_in_group", intent=intent, bot_username=bot_username)


def not_a_group_keyboard(bot_username: str = "CuteGamingBot", *, intent: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("not_a_group", intent=intent, bot_username=bot_username)


def need_photo_keyboard(have: int = 0) -> InlineKeyboardMarkup:
    return keyboard_for("need_photo", have=have)


def photos_expired_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("photos_expired")


def two_live_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("two_live", mine=True)


def banned_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("banned_31")


def busy_keyboard(*, owner: bool = False) -> InlineKeyboardMarkup:
    return keyboard_for("group_busy_owner" if owner else "group_busy")


def wrote_keyboard(username: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("wrote_confirm", username=username, mine=True)


def confirm_no_first_keyboard(username: str = "") -> InlineKeyboardMarkup:
    return keyboard_for("confirm_no_first", username=username, mine=True, status=ST_CONFIRM_RETRY)


def confirm_no_second_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("confirm_no_second")


def need_photos_first_keyboard(have: int = 0) -> InlineKeyboardMarkup:
    return keyboard_for("need_photos_first", have=have)


def owner_no_confirm_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("owner_no_confirm", mine=True)


def drop_confirm_keyboard(claim: dict[str, Any]) -> InlineKeyboardMarkup:
    return keyboard_for("drop_confirm", id=int(claim.get("id") or 0))


def dropped_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("dropped", mine=True)


def admin_ended_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("admin_ended", mine=True)


def group_blocked_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("group_blocked", mine=True)


def wrong_group_keyboard(rows: list[dict[str, Any]] | None = None) -> InlineKeyboardMarkup | None:
    built: list[list[InlineKeyboardButton]] = []
    for row in list(rows or [])[:8]:
        uname = str(row.get("chat_username") or "").strip().lstrip("@")
        if not uname:
            continue
        title = str(row.get("chat_title") or uname)[:28]
        btn = _url(title, f"https://t.me/{uname}", ICON_OPEN or None)
        if btn:
            built.append([btn])
    return InlineKeyboardMarkup(inline_keyboard=built) if built else None


def accepted_keyboard(*, owner: bool = False) -> InlineKeyboardMarkup:
    return keyboard_for("accepted_owner" if owner else "accepted", mine=True)


def accepting_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("accepting", mine=True)


def digest_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("digest", mine=True)


def kicked_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("kicked", mine=True)


def freeze_admin_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("freeze_admin", mine=True)


def freeze_public_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("freeze_public", mine=True)


def term_end_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("term_end", mine=True)


def rejected_keyboard(*, can_fix: bool = False) -> InlineKeyboardMarkup:
    return keyboard_for("rejected_fix" if can_fix else "rejected")


def confirm_timeout_keyboard() -> InlineKeyboardMarkup:
    return keyboard_for("confirm_timeout")


_IMAGE_MIME = frozenset({
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/heic", "image/heif", "image/gif",
})
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif")


def image_file_id(message: Any) -> str:
    photos = getattr(message, "photo", None) or []
    if photos:
        return str(getattr(photos[-1], "file_id", "") or "")
    doc = getattr(message, "document", None)
    if not doc:
        return ""
    mime = str(getattr(doc, "mime_type", "") or "").lower()
    name = str(getattr(doc, "file_name", "") or "").lower()
    if mime in _IMAGE_MIME or name.endswith(_IMAGE_EXT):
        return str(getattr(doc, "file_id", "") or "")
    return ""


def photo_noise_kind(message: Any) -> str:
    if image_file_id(message):
        return ""
    if getattr(message, "video", None) or getattr(message, "video_note", None):
        return "video"
    if getattr(message, "sticker", None):
        return "sticker"
    if getattr(message, "animation", None):
        return "video"
    if getattr(message, "document", None):
        return "file"
    return "text"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def pool():
    from main import db
    return db.pool


async def ensure_schema() -> None:
    """По одному statement: asyncpg не принимает $1 в пачке CREATE."""
    p = await pool()
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute(
        "INSERT INTO pr_settings (id, reject_reasons) VALUES (1, $1::jsonb) ON CONFLICT (id) DO NOTHING",
        json.dumps(DEFAULT_REJECT_REASONS, ensure_ascii=False),
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_membership (
            chat_id BIGINT PRIMARY KEY,
            first_joined_at TIMESTAMPTZ,
            last_joined_at TIMESTAMPTZ,
            last_left_at TIMESTAMPTZ,
            last_added_by BIGINT,
            times_joined INTEGER NOT NULL DEFAULT 0,
            is_member BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_claims (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            photos JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    for col, spec in CLAIM_COLUMNS:
        try:
            await p.execute(alter_claim_column_sql(col, spec))
        except Exception:
            log.debug("pr alter %s", col, exc_info=True)
    await p.execute("CREATE INDEX IF NOT EXISTS pr_claims_user_idx ON pr_claims (user_id, status)")
    await p.execute("CREATE INDEX IF NOT EXISTS pr_claims_chat_idx ON pr_claims (chat_id, status)")
    await p.execute("CREATE INDEX IF NOT EXISTS pr_claims_status_idx ON pr_claims (status, created_at DESC)")
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_gifts (
            user_id BIGINT PRIMARY KEY,
            amount INTEGER NOT NULL DEFAULT 0,
            chat_id BIGINT,
            claim_id BIGINT,
            granted_at TIMESTAMPTZ,
            last_bet INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    try:
        await p.execute("ALTER TABLE pr_gifts ADD COLUMN IF NOT EXISTS last_bet INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_player_bind (
            user_id BIGINT PRIMARY KEY,
            claim_id BIGINT NOT NULL,
            bound_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_notices (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_chat_blocks (
            chat_id BIGINT PRIMARY KEY,
            until TIMESTAMPTZ NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_sessions (
            user_id BIGINT PRIMARY KEY,
            claim_id BIGINT,
            mode TEXT,
            extra JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_payouts (
            id BIGSERIAL PRIMARY KEY,
            claim_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            amount INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await p.execute("CREATE INDEX IF NOT EXISTS pr_payouts_user_idx ON pr_payouts (user_id, created_at DESC)")
    await p.execute("CREATE INDEX IF NOT EXISTS pr_payouts_claim_idx ON pr_payouts (claim_id, created_at DESC)")


def _row(row) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    photos = data.get("photos")
    if isinstance(photos, str):
        try:
            data["photos"] = json.loads(photos)
        except Exception:
            data["photos"] = []
    if data.get("photos") is None:
        data["photos"] = []
    return data


async def get_settings() -> dict[str, Any]:
    await ensure_schema()
    p = await pool()
    row = await p.fetchrow("SELECT * FROM pr_settings WHERE id = 1")
    reasons = DEFAULT_REJECT_REASONS
    if row and row["reject_reasons"]:
        raw = row["reject_reasons"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, list) and raw:
            reasons = raw
    return {"rejectReasons": reasons}


async def save_reject_reasons(reasons: list[dict[str, str]]) -> None:
    await ensure_schema()
    p = await pool()
    await p.execute(
        "UPDATE pr_settings SET reject_reasons = $1::jsonb, updated_at = NOW() WHERE id = 1",
        json.dumps(reasons, ensure_ascii=False),
    )


async def record_join(chat_id: int, added_by: Optional[int]) -> dict[str, Any]:
    await ensure_schema()
    p = await pool()
    row = await p.fetchrow(
        """
        INSERT INTO pr_membership (chat_id, first_joined_at, last_joined_at, last_added_by, times_joined, is_member)
        VALUES ($1, NOW(), NOW(), $2, 1, TRUE)
        ON CONFLICT (chat_id) DO UPDATE SET
            last_joined_at = NOW(),
            last_added_by = COALESCE($2, pr_membership.last_added_by),
            times_joined = pr_membership.times_joined + CASE WHEN pr_membership.is_member THEN 0 ELSE 1 END,
            is_member = TRUE
        RETURNING *
        """,
        int(chat_id), int(added_by) if added_by else None,
    )
    return dict(row)


async def record_leave(chat_id: int) -> Optional[dict[str, Any]]:
    await ensure_schema()
    p = await pool()
    row = await p.fetchrow(
        """
        UPDATE pr_membership
           SET is_member = FALSE, last_left_at = NOW()
         WHERE chat_id = $1
     RETURNING *
        """,
        int(chat_id),
    )
    return dict(row) if row else None


async def get_membership(chat_id: int) -> Optional[dict[str, Any]]:
    await ensure_schema()
    p = await pool()
    row = await p.fetchrow("SELECT * FROM pr_membership WHERE chat_id = $1", int(chat_id))
    return dict(row) if row else None


async def claim_by_id(claim_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    return _row(await p.fetchrow("SELECT * FROM pr_claims WHERE id = $1", int(claim_id)))


async def active_claim_for_user(user_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    return _row(await p.fetchrow(
        """
        SELECT * FROM pr_claims
         WHERE user_id = $1 AND status = ANY($2::text[])
         ORDER BY updated_at DESC
         LIMIT 1
        """,
        int(user_id), list(IN_PROGRESS_STATUSES),
    ))


async def live_claim_for_chat(chat_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    return _row(await p.fetchrow(
        "SELECT * FROM pr_claims WHERE chat_id = $1 AND status = $2 LIMIT 1",
        int(chat_id), ST_LIVE,
    ))


async def group_busy(chat_id: int, *, except_user: Optional[int] = None) -> Optional[dict[str, Any]]:
    p = await pool()
    row = await p.fetchrow(
        """
        SELECT * FROM pr_claims
         WHERE chat_id = $1 AND status = ANY($2::text[])
           AND ($3::bigint IS NULL OR user_id <> $3)
           AND (
                status <> $4
                OR reject_hold_until IS NULL
                OR reject_hold_until > NOW()
           )
         ORDER BY updated_at DESC
         LIMIT 1
        """,
        int(chat_id), list(HOLD_GROUP_STATUSES), except_user, ST_REJECTED,
    )
    return _row(row)


async def count_status(user_id: int, statuses: set[str]) -> int:
    p = await pool()
    return int(await p.fetchval(
        "SELECT COUNT(*) FROM pr_claims WHERE user_id = $1 AND status = ANY($2::text[])",
        int(user_id), list(statuses),
    ) or 0)


async def user_banned(user_id: int, chat_id: int) -> bool:
    p = await pool()
    until = await p.fetchval(
        """
        SELECT banned_until FROM pr_claims
         WHERE user_id = $1 AND chat_id = $2 AND banned_until > NOW()
         ORDER BY banned_until DESC LIMIT 1
        """,
        int(user_id), int(chat_id),
    )
    return until is not None


async def chat_block(chat_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    row = await p.fetchrow(
        "SELECT * FROM pr_chat_blocks WHERE chat_id = $1 AND until > NOW()",
        int(chat_id),
    )
    return dict(row) if row else None


async def chat_blocked(chat_id: int) -> bool:
    return await chat_block(chat_id) is not None


async def set_chat_block(chat_id: int, *, days: int, reason: str = "") -> None:
    days = max(1, int(days or 0))
    p = await pool()
    await p.execute(
        """
        INSERT INTO pr_chat_blocks (chat_id, until, reason, created_at)
        VALUES ($1, NOW() + ($2 || ' days')::interval, $3, NOW())
        ON CONFLICT (chat_id) DO UPDATE
           SET until = EXCLUDED.until, reason = EXCLUDED.reason, created_at = NOW()
        """,
        int(chat_id), str(days), str(reason or ""),
    )


async def clear_chat_block(chat_id: int) -> None:
    p = await pool()
    await p.execute("DELETE FROM pr_chat_blocks WHERE chat_id = $1", int(chat_id))


async def claims_waiting_confirm(user_id: int) -> list[dict[str, Any]]:
    p = await pool()
    rows = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE user_id = $1 AND status = ANY($2::text[])
         ORDER BY updated_at DESC
        """,
        int(user_id), list(CONFIRM_WAIT_STATUSES),
    )
    return [_row(r) for r in rows]


async def claim_for_user_chat(user_id: int, chat_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    return _row(await p.fetchrow(
        """
        SELECT * FROM pr_claims
         WHERE user_id = $1 AND chat_id = $2 AND status = ANY($3::text[])
         ORDER BY updated_at DESC
         LIMIT 1
        """,
        int(user_id), int(chat_id), list(IN_PROGRESS_STATUSES),
    ))


async def wait_confirm_for_chat(chat_id: int) -> Optional[dict[str, Any]]:
    p = await pool()
    return _row(await p.fetchrow(
        """
        SELECT * FROM pr_claims
         WHERE chat_id = $1 AND status = ANY($2::text[])
         ORDER BY updated_at DESC
         LIMIT 1
        """,
        int(chat_id), list(CONFIRM_WAIT_STATUSES),
    ))


def json_session_extra(extra: Optional[dict] = None) -> str:
    """Session extra is jsonb. Datetime/enum from chat inspect must not crash dumps."""
    return json.dumps(_json_safe(extra or {}), ensure_ascii=False)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


async def set_session(user_id: int, *, claim_id: Optional[int], mode: str, extra: Optional[dict] = None) -> None:
    p = await pool()
    await p.execute(
        """
        INSERT INTO pr_sessions (user_id, claim_id, mode, extra, updated_at)
        VALUES ($1, $2, $3, $4::jsonb, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            claim_id = $2, mode = $3, extra = $4::jsonb, updated_at = NOW()
        """,
        int(user_id), claim_id, mode, json_session_extra(extra),
    )


async def is_waiting_photos(user_id: int, chat_type: str = "") -> bool:
    if str(chat_type or "") != "private":
        return False
    session = await get_session(user_id)
    return bool(session and session.get("mode") == "photos")


async def is_waiting_link(user_id: int, chat_type: str = "") -> bool:
    if str(chat_type or "") != "private":
        return False
    session = await get_session(user_id)
    return bool(session and session.get("mode") in LINK_MODES)


async def get_session(user_id: int) -> Optional[dict[str, Any]]:
    try:
        p = await pool()
        row = await p.fetchrow("SELECT * FROM pr_sessions WHERE user_id = $1", int(user_id))
    except Exception:
        return None
    if not row:
        return None
    extra = row["extra"]
    if isinstance(extra, str):
        extra = json.loads(extra)
    return {"user_id": row["user_id"], "claim_id": row["claim_id"], "mode": row["mode"], "extra": extra or {}}


async def remember_ui(user_id: int, chat_id: int, message_id: int) -> None:
    session = await get_session(user_id) or {}
    extra = dict(session.get("extra") or {})
    extra["ui_chat"] = int(chat_id)
    extra["ui_msg"] = int(message_id)
    await set_session(
        int(user_id),
        claim_id=session.get("claim_id"),
        mode=str(session.get("mode") or "hub"),
        extra=extra,
    )


async def deliver_dm(bot, user_id: int, text: str, markup=None, *, fresh: bool = False) -> bool:
    """Одно живое сообщение в личке.

    По умолчанию правим текущий экран. fresh=True — всегда новое сообщение,
    старое бота удаляем только после успешной отправки. Сообщения игрока
    (фото) не трогаем: так промпт оказывается под только что присланным кадром.
    """
    session = await get_session(user_id) or {}
    extra = dict(session.get("extra") or {})
    chat_id = extra.get("ui_chat") or int(user_id)
    msg_id = extra.get("ui_msg")

    async def _edit_or_send(txt: str, mk) -> bool:
        if msg_id and not fresh:
            try:
                await bot.edit_message_text(
                    txt,
                    chat_id=int(chat_id),
                    message_id=int(msg_id),
                    reply_markup=mk,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return True
            except TelegramBadRequest as err:
                low = str(err).lower()
                if "not modified" in low:
                    if mk is not None:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=int(chat_id), message_id=int(msg_id), reply_markup=mk,
                            )
                        except Exception:
                            pass
                    return True
            except Exception:
                pass
        try:
            sent = await bot.send_message(
                int(user_id), txt, reply_markup=mk, parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception:
            try:
                sent = await bot.send_message(int(user_id), txt, reply_markup=mk)
            except Exception:
                return False
        extra["ui_chat"] = int(sent.chat.id)
        extra["ui_msg"] = int(sent.message_id)
        try:
            await set_session(
                int(user_id),
                claim_id=session.get("claim_id"),
                mode=str(session.get("mode") or "hub"),
                extra=extra,
            )
        except Exception:
            log.exception("pr remember ui after send")
        if msg_id and int(sent.message_id) != int(msg_id):
            try:
                await bot.delete_message(int(chat_id), int(msg_id))
            except Exception:
                pass
        return True

    if await _edit_or_send(text, markup):
        return True
    plain_mk = markup_without_icons(markup)
    if await _edit_or_send(html_without_custom_emoji(text), plain_mk):
        return True
    return await _edit_or_send(html_without_custom_emoji(text), None)


async def clear_session(user_id: int) -> None:
    p = await pool()
    await p.execute("DELETE FROM pr_sessions WHERE user_id = $1", int(user_id))


async def create_claim(
    *,
    user_id: int,
    chat_id: int,
    role: str,
    title: str,
    username: str,
    member_count: int,
    added_by: Optional[int],
    creator_id: Optional[int],
    joined_at: Optional[datetime],
) -> dict[str, Any]:
    p = await pool()
    row = await p.fetchrow(
        """
        INSERT INTO pr_claims (
            user_id, chat_id, role, status, photos_started_at,
            chat_title, chat_username, member_count, added_by, creator_id, joined_at
        ) VALUES ($1,$2,$3,$4,NOW(),$5,$6,$7,$8,$9,$10)
        RETURNING *
        """,
        int(user_id), int(chat_id), role, ST_PHOTOS,
        title, username, int(member_count or 0),
        int(added_by) if added_by else None,
        int(creator_id) if creator_id else None,
        joined_at or _now(),
    )
    return _row(row)


async def save_claim(claim_id: int, **fields: Any) -> Optional[dict[str, Any]]:
    if not fields:
        return await claim_by_id(claim_id)
    sql, args = claim_set_sql(fields, claim_id=int(claim_id))
    p = await pool()
    row = await p.fetchrow(sql, *args)
    return _row(row)


async def add_photo(claim_id: int, file_id: str) -> dict[str, Any]:
    claim = await claim_by_id(claim_id)
    photos = list(claim.get("photos") or [])
    if any(str(item.get("file_id") or "") == str(file_id) for item in photos):
        return claim
    photos.append({"file_id": file_id, "n": len(photos) + 1})
    fields: dict[str, Any] = {"photos": photos}
    if len(photos) >= PHOTOS_REQUIRED:
        fields["photos_done_at"] = _now()
        if claim["role"] == ROLE_OWNER:
            fields["status"] = ST_PENDING
        else:
            fields["status"] = ST_WAIT_CONFIRM
    return await save_claim(claim_id, **fields)


async def pop_photo(claim_id: int) -> Optional[dict[str, Any]]:
    claim = await claim_by_id(claim_id)
    if not claim:
        return None
    photos = list(claim.get("photos") or [])
    if photos:
        photos.pop()
    return await save_claim(int(claim_id), photos=photos, photos_done_at=None, status=ST_PHOTOS)


async def cancel_claim(claim_id: int) -> Optional[dict[str, Any]]:
    return await save_claim(claim_id, status=ST_CANCELLED)


async def expire_claim(claim_id: int) -> Optional[dict[str, Any]]:
    return await save_claim(claim_id, status=ST_EXPIRED)


async def recent_joins_for_user(user_id: int) -> list[dict[str, Any]]:
    """Группы, куда Кут зашёл за 14 дней. Кто видит список — решает хендлер (член группы)."""
    del user_id  # список общий, фильтр по членству в Telegram
    p = await pool()
    rows = await p.fetch(
        """
        SELECT m.chat_id, m.last_joined_at, m.last_added_by, m.last_left_at, m.times_joined
          FROM pr_membership m
         WHERE m.is_member = TRUE
           AND m.last_joined_at > NOW() - INTERVAL '14 days'
         ORDER BY m.last_joined_at DESC
         LIMIT 24
        """
    )
    return [dict(r) for r in rows]


async def nika_reserve() -> int:
    """Дыра Ники: цель минус текущий бч. Колонок sweep_keep в nika_group_settings нет."""
    p = await pool()
    try:
        return _as_int(await p.fetchval(
            """
            SELECT COALESCE(SUM(GREATEST(0,
                COALESCE(s.target_balance, 0) - COALESCE(c.chatbalance, 0)
            )), 0)::bigint
              FROM nika_group_settings s
              JOIN chat c ON c.chat_id = s.chat_id
             WHERE COALESCE(s.enabled, TRUE) = TRUE
            """
        ))
    except Exception:
        return 0


async def ladder_free() -> tuple[int, list[dict[str, Any]]]:
    from bot.config.config import (
        BACKGROUND_EARNINGS_CHAT_ID,
        GAME_COMMISSION_CHAT_ID,
        TECH_CHAT_ID,
    )
    ids = [GAME_COMMISSION_CHAT_ID, BACKGROUND_EARNINGS_CHAT_ID, TECH_CHAT_ID]
    p = await pool()
    rows = await p.fetch(
        "SELECT chat_id, COALESCE(chatbalance, 0)::bigint AS b FROM chat WHERE chat_id = ANY($1::bigint[])",
        ids,
    )
    by = {int(r["chat_id"]): _as_int(r["b"]) for r in rows}
    items = [{"chatId": cid, "balance": by.get(int(cid), 0)} for cid in ids]
    earmark = _as_int(await p.fetchval(
        "SELECT COALESCE(SUM(pool_left), 0) FROM pr_claims WHERE status = ANY($1::text[])",
        list(LIVE_STATUSES),
    ))
    total = sum(x["balance"] for x in items) - earmark
    return max(0, total), items


async def money_view(member_count: int = 0, *, except_claim_id: Optional[int] = None) -> dict[str, Any]:
    ladder, items = await ladder_free()
    reserve = await nika_reserve()
    can = spendable_amount(ladder, reserve)
    rec_total = recommend_seed(member_count, can)
    split = recommend_split(rec_total, member_count)
    week_used = await week_seed_used(except_claim_id=except_claim_id)
    week_cap = weekly_seed_budget(can)
    return {
        "ladder": items,
        "ladderFree": ladder,
        "nikaReserve": reserve,
        "spendable": can,
        "weeklyUsed": week_used,
        "weeklyCap": week_cap,
        "weeklyLeft": max(0, week_cap - week_used),
        "recommend": split,
    }


async def week_seed_used(*, except_claim_id: Optional[int] = None) -> int:
    p = await pool()
    return _as_int(await p.fetchval(
        """
        SELECT COALESCE(SUM(seed_total), 0) FROM pr_claims
         WHERE status = ANY($1::text[])
           AND COALESCE(accepted_at, updated_at) >= NOW() - INTERVAL '7 days'
           AND ($2::bigint IS NULL OR id <> $2)
        """,
        list(WEEK_SEED_STATUSES),
        int(except_claim_id) if except_claim_id else None,
    ))


async def _take_from_ladder(amount: int, bot=None) -> bool:
    from bot.config.config import (
        BACKGROUND_EARNINGS_CHAT_ID,
        GAME_COMMISSION_CHAT_ID,
        TECH_CHAT_ID,
    )
    from main import db
    need = int(amount)
    if need <= 0:
        return True
    taken: list[tuple[int, int]] = []
    for chat_id in (TECH_CHAT_ID, GAME_COMMISSION_CHAT_ID, BACKGROUND_EARNINGS_CHAT_ID):
        if need <= 0:
            break
        bal = _as_int(await db.pool.fetchval(
            "SELECT COALESCE(chatbalance, 0) FROM chat WHERE chat_id = $1", int(chat_id),
        ))
        take = min(bal, need)
        if take <= 0:
            continue
        snap = await db.update_chat_balance_minus(int(chat_id), take)
        if snap is None:
            continue
        taken.append((int(chat_id), take))
        need -= take
    if need > 0:
        for chat_id, amt in taken:
            try:
                if bot is not None:
                    await db.add_to_chatbalance(bot, chat_id, amt)
                else:
                    await db.pool.execute(
                        "UPDATE chat SET chatbalance = COALESCE(chatbalance, 0) + $2 WHERE chat_id = $1",
                        chat_id, amt,
                    )
            except Exception:
                log.exception("ladder refund fail chat=%s", chat_id)
        return False
    return True


async def _refund_to_ladder(amount: int, bot=None) -> None:
    if int(amount or 0) <= 0:
        return
    from bot.config.config import TECH_CHAT_ID
    from main import db
    try:
        if bot is not None:
            await db.add_to_chatbalance(bot, TECH_CHAT_ID, int(amount))
        else:
            await db.pool.execute(
                "UPDATE chat SET chatbalance = COALESCE(chatbalance, 0) + $2 WHERE chat_id = $1",
                TECH_CHAT_ID, int(amount),
            )
    except Exception:
        log.exception("ladder refund %s", amount)


async def _give_to_chat(bot, chat_id: int, amount: int) -> None:
    from main import db
    if amount <= 0:
        return
    await db.add_to_chatbalance(bot, int(chat_id), int(amount))


async def _give_to_user(user_id: int, amount: int, cause: str) -> None:
    from main import db
    if amount <= 0:
        return
    current = await db.get_user_balance(int(user_id))
    bal = int(current[0] if isinstance(current, tuple) else current or 0)
    await db.update_user_balance(int(user_id), bal + int(amount))
    try:
        await db.cutehistory_plus(int(user_id), int(amount), cause)
    except Exception:
        pass


async def fulfill_accept(claim_id: int, *, bot) -> dict[str, Any]:
    """Идемпотентно: куты на баланс чата списываются один раз, повтор тикера не списывает снова."""
    async with _fulfill_lock:
        return await _fulfill_accept_locked(claim_id, bot=bot)


async def _fulfill_accept_locked(claim_id: int, *, bot) -> dict[str, Any]:
    p = await pool()
    row = await p.fetchrow(
        """
        UPDATE pr_claims SET status = $2, updated_at = NOW()
         WHERE id = $1 AND status = ANY($3::text[])
     RETURNING *
        """,
        int(claim_id), ST_FULFILLING, [ST_ACCEPTING, ST_FULFILLING],
    )
    if not row:
        live = await claim_by_id(claim_id)
        if live and live["status"] == ST_LIVE:
            return live
        raise ValueError("Заявка не в очереди")
    claim = _row(row)
    total = int(claim.get("seed_total") or 0)
    term_days = int(claim.get("term_days") or DEFAULT_TERM_DAYS)
    members = int(claim.get("member_count") or 0)
    split = recommend_split(total, members)
    if not claim.get("seed_applied"):
        view = await money_view(members, except_claim_id=int(claim_id))
        if total > int(view["spendable"]):
            await save_claim(claim_id, status=ST_ACCEPTING)
            raise ValueError("Не хватает spendable")
        if total > int(view["weeklyLeft"]) and total > 0:
            await save_claim(claim_id, status=ST_ACCEPTING)
            raise ValueError("Недельный бюджет посева")
        live_now = await count_status(int(claim["user_id"]), {ST_LIVE})
        if live_now >= MAX_LIVE_SEEDS:
            await save_claim(claim_id, status=ST_ACCEPTING)
            raise ValueError("Уже 2 живые группы")
        if split["table"] > 0:
            if not await _take_from_ladder(split["table"], bot=bot):
                await save_claim(claim_id, status=ST_ACCEPTING)
                raise ValueError("Техкасса не отдаёт куты на баланс чата")
            await _give_to_chat(bot, int(claim["chat_id"]), split["table"])
        await save_claim(
            claim_id,
            seed_applied=True,
            table_amount=split["table"],
            pool_amount=split["pool"],
            pool_left=split["pool"],
            gift_size=split["gift"],
            seed_lock=split["table"],
        )
    until = claim.get("live_until") or (_now() + timedelta(days=term_days))
    done = await p.fetchrow(
        """
        UPDATE pr_claims
           SET status = $2,
               accepted_at = COALESCE(accepted_at, $3),
               live_until = $4,
               term_days = $5,
               nika_on = $6,
               freeze = NULL,
               updated_at = NOW()
         WHERE id = $1 AND status = $7
     RETURNING *
        """,
        int(claim_id),
        ST_LIVE,
        claim.get("accepted_at") or _now(),
        until,
        term_days,
        bool(claim.get("nika_on")),
        ST_FULFILLING,
    )
    if done:
        return _row(done)
    fresh = await claim_by_id(claim_id)
    if fresh and fresh.get("status") in {ST_LIVE, ST_ENDING}:
        return fresh
    raise ValueError("Заявка снята до посева")


async def accept_claim(
    claim_id: int,
    *,
    bot,
    seed_total: int,
    term_days: int,
    nika_on: bool,
) -> dict[str, Any]:
    claim = await claim_by_id(claim_id)
    if not claim or claim["status"] not in {ST_PENDING, ST_ACCEPTING, ST_FULFILLING}:
        raise ValueError("Заявка не в очереди")
    if claim["status"] == ST_PENDING:
        await save_claim(
            claim_id,
            status=ST_ACCEPTING,
            seed_total=int(seed_total),
            term_days=int(term_days or DEFAULT_TERM_DAYS),
            nika_on=bool(nika_on),
        )
    return await fulfill_accept(claim_id, bot=bot)


async def reject_claim(claim_id: int, text: str) -> dict[str, Any]:
    return await save_claim(
        claim_id,
        status=ST_REJECTED,
        reject_text=text,
        reject_hold_until=_now() + timedelta(hours=REJECT_HOLD_HOURS),
    )


async def seed_lock_for_chat(chat_id: int) -> int:
    claim = await live_claim_for_chat(chat_id)
    if not claim:
        return 0
    return _as_int(claim.get("seed_lock"))


async def gift_state(user_id: int) -> dict[str, Any]:
    p = await pool()
    row = await p.fetchrow("SELECT * FROM pr_gifts WHERE user_id = $1", int(user_id))
    if not row:
        return {"amount": 0, "chat_id": None, "claim_id": None, "last_bet": 0}
    return {
        "amount": _as_int(row["amount"]),
        "chat_id": row["chat_id"],
        "claim_id": row["claim_id"],
        "last_bet": _as_int(row["last_bet"]),
    }


async def ever_gifted(user_id: int) -> bool:
    p = await pool()
    return bool(await p.fetchval("SELECT 1 FROM pr_gifts WHERE user_id = $1", int(user_id)))


async def last_real_ts(user_id: int, *, before_ts: Optional[float] = None) -> Optional[float]:
    """Денежная активность. before_ts — только то, что было ДО входа Кута."""
    from main import db
    stamps: list[float] = []
    cutoff = datetime.fromtimestamp(before_ts, tz=timezone.utc) if before_ts else None
    try:
        raw = await db.get_game_last_activity(int(user_id))
        if raw:
            dt = datetime.strptime(str(raw), "%d.%m.%Y | %H:%M").replace(tzinfo=timezone.utc)
            if cutoff is None or dt < cutoff:
                stamps.append(dt.timestamp())
    except Exception:
        pass
    p = await pool()
    if cutoff:
        queries = (
            "SELECT EXTRACT(EPOCH FROM MAX(created_at)) FROM growth_fund_ledger WHERE user_id = $1 AND created_at < $2",
            "SELECT EXTRACT(EPOCH FROM MAX(created_at)) FROM p2p_transfers WHERE (sender_id = $1 OR receiver_id = $1) AND created_at < $2",
        )
        args: tuple[Any, ...] = (int(user_id), cutoff)
    else:
        queries = (
            "SELECT EXTRACT(EPOCH FROM MAX(created_at)) FROM growth_fund_ledger WHERE user_id = $1",
            "SELECT EXTRACT(EPOCH FROM MAX(created_at)) FROM p2p_transfers WHERE sender_id = $1 OR receiver_id = $1",
        )
        args = (int(user_id),)
    for sql in queries:
        try:
            val = await p.fetchval(sql, *args)
            if val:
                stamps.append(float(val))
        except Exception:
            continue
    return max(stamps) if stamps else None


async def first_seen_ts(user_id: int) -> Optional[float]:
    p = await pool()
    stamps: list[float] = []
    for sql in (
        "SELECT EXTRACT(EPOCH FROM MIN(timestamp)) FROM chatusers WHERE user_id = $1",
        "SELECT EXTRACT(EPOCH FROM MIN(created_at)) FROM users WHERE user_id = $1",
    ):
        try:
            val = await p.fetchval(sql, int(user_id))
            if val:
                stamps.append(float(val))
        except Exception:
            continue
    return min(stamps) if stamps else None


def _gift_user_lock(user_id: int) -> asyncio.Lock:
    uid = int(user_id)
    lock = _gift_grant_locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _gift_grant_locks[uid] = lock
    return lock


async def maybe_grant_gift(bot, *, user_id: int, chat_id: int, name: str) -> Optional[int]:
    """Один подарок за жизнь. Только живая группа, только новичок без своих кут."""
    del name
    uid = int(user_id)
    async with _gift_user_lock(uid):
        return await _maybe_grant_gift_locked(bot, user_id=uid, chat_id=int(chat_id))


async def _maybe_grant_gift_locked(bot, *, user_id: int, chat_id: int) -> Optional[int]:
    claim = await live_claim_for_chat(chat_id)
    if not claim or claim.get("freeze"):
        return None
    if int(claim.get("pool_left") or 0) <= 0:
        return None
    if await ever_gifted(user_id):
        return None
    if int(user_id) == int(claim["user_id"]):
        return None
    from main import db
    current = await db.get_user_balance(int(user_id))
    bal = int(current[0] if isinstance(current, tuple) else current or 0)
    gift = await gift_state(user_id)
    if not is_broke(bal, gift["amount"]):
        return None
    joined = claim.get("joined_at") or claim.get("accepted_at") or _now()
    if hasattr(joined, "timestamp"):
        t0 = joined.timestamp()
    else:
        t0 = _now().timestamp()
    kind = classify_player(
        last_real_ts=await last_real_ts(user_id, before_ts=t0),
        first_seen_ts=await first_seen_ts(user_id),
        joined_ts=t0,
    )
    if not is_new_class(kind):
        return None
    size = min(int(claim.get("gift_size") or 0), int(claim.get("pool_left") or 0))
    if size <= 0:
        return None
    if not await _take_from_ladder(size, bot=bot):
        return None
    p = await pool()
    ins = await p.fetchrow(
        """
        INSERT INTO pr_gifts (user_id, amount, chat_id, claim_id, granted_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO NOTHING
        RETURNING user_id
        """,
        int(user_id), size, int(chat_id), int(claim["id"]),
    )
    if not ins:
        await _refund_to_ladder(size, bot)
        return None
    try:
        await _give_to_user(user_id, size, plain(say("history_gift")))
    except Exception:
        log.exception("gift credit failed")
        await p.execute("DELETE FROM pr_gifts WHERE user_id = $1 AND amount = $2", int(user_id), size)
        await _refund_to_ladder(size, bot)
        return None
    took = await p.fetchrow(
        """
        UPDATE pr_claims
           SET pool_left = pool_left - $2, updated_at = NOW()
         WHERE id = $1
           AND status = $3
           AND COALESCE(pool_left, 0) >= $2
           AND (freeze IS NULL OR freeze = '')
     RETURNING pool_left
        """,
        int(claim["id"]), size, ST_LIVE,
    )
    if took:
        return size
    token = _GIFT_CLAW.set(True)
    try:
        current = await db.get_user_balance(int(user_id))
        bal = int(current[0] if isinstance(current, tuple) else current or 0)
        await p.execute("DELETE FROM pr_gifts WHERE user_id = $1", int(user_id))
        claw = min(size, bal)
        if claw > 0:
            await db.update_user_balance(int(user_id), bal - claw)
    except Exception:
        log.exception("gift claw after pool miss")
    finally:
        _GIFT_CLAW.reset(token)
    await _refund_to_ladder(size, bot)
    return None


async def consume_gift_bet(
    user_id: int,
    chat_id: int,
    bet: int,
    *,
    solo: bool = True,
    private: bool = False,
) -> bool:
    """Списать подарок на соло-ставку в своей группе. False — ставка лезет в подарок не там."""
    state = await gift_state(user_id)
    locked = int(state["amount"] or 0)
    if locked <= 0:
        return True
    from main import db
    current = await db.get_user_balance(int(user_id))
    bal = int(current[0] if isinstance(current, tuple) else current or 0)
    if not bet_fits_gift_lock(
        balance=bal,
        bet=bet,
        gift_amount=locked,
        gift_chat_id=state.get("chat_id"),
        play_chat_id=chat_id,
        solo=solo,
        private=private,
    ):
        return False
    if not gift_covers_this_play(
        gift_chat_id=state.get("chat_id"),
        play_chat_id=chat_id,
        solo=solo,
        private=private,
    ):
        return True
    take = min(locked, max(0, int(bet)))
    if take <= 0:
        return True
    p = await pool()
    row = await p.fetchrow(
        """
        UPDATE pr_gifts
           SET amount = amount - $2, last_bet = $2
         WHERE user_id = $1 AND amount >= $2 AND chat_id = $3
     RETURNING amount
        """,
        int(user_id), take, int(chat_id),
    )
    return row is not None


async def credit_gift_win(user_id: int, chat_id: int, net: int) -> None:
    state = await gift_state(user_id)
    if int(state.get("chat_id") or 0) != int(chat_id):
        return
    if int(state.get("amount") or 0) < 0:
        return
    last = 0
    p = await pool()
    row = await p.fetchrow("SELECT last_bet, amount FROM pr_gifts WHERE user_id = $1", int(user_id))
    if not row or int(row["last_bet"] or 0) <= 0:
        return
    await p.execute(
        "UPDATE pr_gifts SET amount = $2, last_bet = 0 WHERE user_id = $1",
        int(user_id), max(0, int(row["amount"] or 0) + max(0, int(net))),
    )


def gift_claw_active() -> bool:
    return bool(_GIFT_CLAW.get())


async def gift_blocks_other_spend(user_id: int, amount: int) -> bool:
    """True если перевод/PvP/чужой чат заденет подарок."""
    if gift_claw_active():
        return False
    from main import db
    state = await gift_state(user_id)
    if int(state["amount"] or 0) <= 0:
        return False
    current = await db.get_user_balance(int(user_id))
    bal = int(current[0] if isinstance(current, tuple) else current or 0)
    return bal - int(amount) < int(state["amount"])


async def adjust_gift(user_id: int, delta: int) -> int:
    state = await gift_state(user_id)
    nxt = max(0, int(state["amount"]) + int(delta))
    p = await pool()
    await p.execute(
        """
        INSERT INTO pr_gifts (user_id, amount) VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET amount = $2
        """,
        int(user_id), nxt,
    )
    return nxt


async def bind_player(user_id: int, claim_id: int) -> Optional[int]:
    p = await pool()
    try:
        await p.execute(
            "INSERT INTO pr_player_bind (user_id, claim_id) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
            int(user_id), int(claim_id),
        )
    except Exception:
        pass
    row = await p.fetchval("SELECT claim_id FROM pr_player_bind WHERE user_id = $1", int(user_id))
    return int(row) if row else None


async def note_commission(*, chat_id: int, user_id: int, commission: int, used_gift: bool) -> int:
    claim = await live_claim_for_chat(chat_id)
    if not claim or int(commission) <= 0:
        return 0
    if int(user_id) == int(claim["user_id"]):
        return 0
    bound = await bind_player(user_id, int(claim["id"]))
    if bound and bound != int(claim["id"]):
        return 0
    joined = claim.get("joined_at") or claim.get("accepted_at") or _now()
    t0 = joined.timestamp() if hasattr(joined, "timestamp") else _now().timestamp()
    kind = classify_player(
        last_real_ts=await last_real_ts(user_id, before_ts=t0),
        first_seen_ts=await first_seen_ts(user_id),
        joined_ts=t0,
    )
    if not is_new_class(kind) and not used_gift:
        return 0
    seen = int(claim.get("commission_seen") or 0) + int(commission)
    paid = int(claim.get("paid_kut") or 0)
    pending = int(claim.get("pending_pay") or 0)
    cut = promoter_cut(int(commission), paid + pending, seen)
    await save_claim(
        int(claim["id"]),
        commission_seen=seen,
        pending_pay=pending + cut,
    )
    return cut


async def flush_digest(bot, claim: dict[str, Any]) -> None:
    from pr_groups_logic import text_digest
    pay = int(claim.get("pending_pay") or 0)
    since = claim.get("last_digest_at") or claim.get("accepted_at") or _now()
    newcomers = 0
    try:
        p = await pool()
        newcomers = _as_int(await p.fetchval(
            "SELECT COUNT(*) FROM pr_player_bind WHERE claim_id = $1 AND bound_at >= $2",
            int(claim["id"]), since,
        ))
    except Exception:
        newcomers = 0
    if pay > 0:
        if await _take_from_ladder(pay, bot=bot):
            await _give_to_user(int(claim["user_id"]), pay, plain(say("history_payout")))
            await record_payout(int(claim["id"]), int(claim["user_id"]), pay)
            await save_claim(
                int(claim["id"]),
                paid_kut=int(claim.get("paid_kut") or 0) + pay,
                pending_pay=0,
                last_digest_at=_now(),
            )
        else:
            await save_claim(int(claim["id"]), last_digest_at=_now())
            return
    until = claim.get("live_until")
    left = 0
    if until:
        left = max(0, int((until - _now()).total_seconds() // 86400))
    try:
        await deliver_dm(
            bot,
            int(claim["user_id"]),
            text_digest(
                newcomers=newcomers,
                commission=int(claim.get("commission_seen") or 0),
                paid=pay,
                days_left=left,
                title=str(claim.get("chat_title") or ""),
            ),
            digest_keyboard(),
        )
    except Exception:
        log.debug("digest send failed", exc_info=True)


async def end_claim(bot, claim: dict[str, Any], *, reason: str) -> None:
    from main import db
    if reason == "kicked":
        new_status = ST_BURNED
    elif reason in {"drop", "admin", "user"}:
        new_status = ST_CANCELLED
    else:
        new_status = ST_ENDED
    cid = int(claim["id"])
    p = await pool()
    old = await p.fetchrow("SELECT * FROM pr_claims WHERE id = $1", cid)
    if not old or str(old.get("status") or "") not in MONEY_UNWIND_STATUSES:
        return
    lock = _as_int(old.get("seed_lock"))
    nika_on = bool(old.get("nika_on"))
    chat_id = int(old["chat_id"])
    moved = await p.fetchrow(
        """
        UPDATE pr_claims
           SET status = $2,
               ended_at = NOW(),
               seed_lock = 0,
               pool_left = 0,
               pending_pay = 0,
               freeze = NULL,
               updated_at = NOW()
         WHERE id = $1 AND status = $3
     RETURNING id
        """,
        cid, new_status, old["status"],
    )
    if not moved:
        return
    give_back = reason in {"kicked", "drop", "admin", "user"} or not nika_on
    if not give_back:
        return
    try:
        bal = _as_int(await db.pool.fetchval(
            "SELECT COALESCE(chatbalance, 0) FROM chat WHERE chat_id = $1", chat_id,
        ))
        take = min(lock, bal)
        if take > 0:
            await db.update_chat_balance_minus(chat_id, take)
            from bot.config.config import TECH_CHAT_ID
            await db.add_to_chatbalance(bot, TECH_CHAT_ID, take)
    except Exception:
        log.exception("return seed failed")
    gifts = await p.fetch(
        "SELECT user_id, amount FROM pr_gifts WHERE claim_id = $1 AND amount > 0",
        cid,
    )
    for g in gifts:
        amt = _as_int(g["amount"])
        uid = int(g["user_id"])
        token = _GIFT_CLAW.set(True)
        try:
            current = await db.get_user_balance(uid)
            bal = int(current[0] if isinstance(current, tuple) else current or 0)
            claw = min(amt, bal)
            await p.execute("UPDATE pr_gifts SET amount = 0, last_bet = 0 WHERE user_id = $1", uid)
            if claw > 0:
                await db.update_user_balance(uid, bal - claw)
                from bot.config.config import TECH_CHAT_ID
                await db.add_to_chatbalance(bot, TECH_CHAT_ID, claw)
        except Exception:
            log.debug("claw gift failed", exc_info=True)
        finally:
            _GIFT_CLAW.reset(token)


async def drop_claim(bot, claim: dict[str, Any], *, reason: str = "drop") -> Optional[dict[str, Any]]:
    """Снять заявку в любом открытом статусе. Посев и подарки не оставляем читить."""
    async with _fulfill_lock:
        fresh = await claim_by_id(int(claim["id"]))
        if not fresh or str(fresh.get("status") or "") not in IN_PROGRESS_STATUSES:
            return fresh
        if str(fresh.get("status") or "") in MONEY_UNWIND_STATUSES:
            await end_claim(bot, fresh, reason=reason)
        else:
            await cancel_claim(int(fresh["id"]))
        return await claim_by_id(int(claim["id"]))


async def try_quiet_nika(bot, claim: dict[str, Any]) -> int:
    if not claim.get("nika_on") or claim.get("status") != ST_LIVE or claim.get("freeze"):
        return 0
    last = claim.get("nika_last_at")
    if last and (_now() - last).total_seconds() < 12 * 3600:
        return 0
    p = await pool()
    fresh = _as_int(await p.fetchval(
        """
        SELECT COUNT(DISTINCT b.user_id)
          FROM pr_player_bind b
          JOIN growth_fund_ledger g ON g.user_id = b.user_id
         WHERE b.claim_id = $1
           AND g.chat_id = $2
           AND g.created_at >= NOW() - INTERVAL '24 hours'
        """,
        int(claim["id"]), int(claim["chat_id"]),
    ))
    if fresh < 3:
        return 0
    from main import db
    bal = _as_int(await db.pool.fetchval(
        "SELECT COALESCE(chatbalance, 0) FROM chat WHERE chat_id = $1", int(claim["chat_id"]),
    ))
    step = nika_step_amount(
        table_origin=int(claim.get("table_amount") or 0),
        chat_balance=bal,
        already_topped=int(claim.get("nika_topped") or 0),
    )
    if step <= 0:
        return 0
    view = await money_view()
    step = min(step, int(view["spendable"]))
    if step <= 0:
        return 0
    if not await _take_from_ladder(step, bot=bot):
        return 0
    await _give_to_chat(bot, int(claim["chat_id"]), step)
    await save_claim(
        int(claim["id"]),
        nika_topped=int(claim.get("nika_topped") or 0) + step,
        nika_last_at=_now(),
    )
    return step


async def list_user_claims(user_id: int) -> list[dict[str, Any]]:
    p = await pool()
    rows = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE user_id = $1 AND status = ANY($2::text[])
         ORDER BY
           CASE WHEN status = ANY($3::text[]) THEN 0 ELSE 1 END,
           updated_at DESC
         LIMIT 20
        """,
        int(user_id), list(MINE_STATUSES), list(IN_PROGRESS_STATUSES),
    )
    items = [_row(r) for r in rows]
    return await _decorate_claims(int(user_id), items)


async def _decorate_claims(user_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [int(row["id"]) for row in items if row and row.get("id")]
    if not ids:
        return items
    p = await pool()
    gifts = {
        int(r["claim_id"]): int(r["n"] or 0)
        for r in await p.fetch(
            "SELECT claim_id, COUNT(*) AS n FROM pr_gifts WHERE claim_id = ANY($1::bigint[]) AND amount > 0 GROUP BY claim_id",
            ids,
        )
        if r["claim_id"] is not None
    }
    since = moscow_day_start()
    today = {
        int(r["claim_id"]): int(r["n"] or 0)
        for r in await p.fetch(
            """
            SELECT claim_id, COALESCE(SUM(amount), 0) AS n
              FROM pr_payouts
             WHERE user_id = $1 AND created_at >= $2 AND claim_id = ANY($3::bigint[])
             GROUP BY claim_id
            """,
            int(user_id), since, ids,
        )
        if r["claim_id"] is not None
    }
    for row in items:
        cid = int(row.get("id") or 0)
        row["gifts"] = gifts.get(cid, 0)
        row["today_kut"] = today.get(cid, 0)
    return items


async def user_paid_total(user_id: int) -> int:
    p = await pool()
    return _as_int(await p.fetchval(
        "SELECT COALESCE(SUM(paid_kut), 0) FROM pr_claims WHERE user_id = $1",
        int(user_id),
    ))


async def payouts_today(user_id: int, claim_id: int | None = None) -> int:
    p = await pool()
    since = moscow_day_start()
    if claim_id:
        return _as_int(await p.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0) FROM pr_payouts
             WHERE user_id = $1 AND claim_id = $2 AND created_at >= $3
            """,
            int(user_id), int(claim_id), since,
        ))
    return _as_int(await p.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM pr_payouts WHERE user_id = $1 AND created_at >= $2",
        int(user_id), since,
    ))


async def record_payout(claim_id: int, user_id: int, amount: int) -> None:
    n = int(amount or 0)
    if n <= 0:
        return
    p = await pool()
    await p.execute(
        "INSERT INTO pr_payouts (claim_id, user_id, amount) VALUES ($1, $2, $3)",
        int(claim_id), int(user_id), n,
    )


async def gift_count(claim_id: int) -> int:
    p = await pool()
    return _as_int(await p.fetchval(
        "SELECT COUNT(*) FROM pr_gifts WHERE claim_id = $1 AND amount > 0",
        int(claim_id),
    ))


async def newcomer_count(claim_id: int) -> int:
    p = await pool()
    return _as_int(await p.fetchval(
        "SELECT COUNT(*) FROM pr_player_bind WHERE claim_id = $1",
        int(claim_id),
    ))


async def chat_balance_of(chat_id: int) -> int:
    from main import db
    try:
        return _as_int(await db.pool.fetchval(
            "SELECT COALESCE(chatbalance, 0) FROM chat WHERE chat_id = $1",
            int(chat_id),
        ))
    except Exception:
        return 0


async def claim_card_stats(claim: dict[str, Any]) -> dict[str, Any]:
    cid = int(claim.get("id") or 0)
    uid = int(claim.get("user_id") or 0)
    chat_id = int(claim.get("chat_id") or 0)
    today = await payouts_today(uid, cid) if uid and cid else 0
    newcomers = await newcomer_count(cid) if cid else 0
    gifts = await gift_count(cid) if cid else 0
    balance = await chat_balance_of(chat_id) if chat_id else 0
    return {
        "today": today,
        "newcomers": newcomers,
        "gifts": gifts,
        "chat_balance": balance,
    }


async def list_queue() -> list[dict[str, Any]]:
    p = await pool()
    rows = await p.fetch(
        "SELECT * FROM pr_claims WHERE status = $1 ORDER BY created_at ASC",
        ST_PENDING,
    )
    return [_row(r) for r in rows]


async def list_live() -> list[dict[str, Any]]:
    p = await pool()
    rows = await p.fetch(
        "SELECT * FROM pr_claims WHERE status = $1 ORDER BY accepted_at DESC",
        ST_LIVE,
    )
    return [_row(r) for r in rows]


async def has_open_fulfill() -> bool:
    p = await pool()
    return bool(await p.fetchval(
        "SELECT 1 FROM pr_claims WHERE status = ANY($1::text[]) LIMIT 1",
        [ST_ACCEPTING, ST_FULFILLING],
    ))


async def list_archive(limit: int = 40) -> list[dict[str, Any]]:
    p = await pool()
    rows = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE status = ANY($1::text[])
         ORDER BY updated_at DESC
         LIMIT $2
        """,
        [ST_REJECTED, ST_ENDED, ST_BURNED, ST_CANCELLED, ST_EXPIRED],
        int(limit),
    )
    return [_row(r) for r in rows]


async def push_notice(user_id: int, kind: str, payload: Optional[dict] = None) -> None:
    p = await pool()
    await p.execute(
        "INSERT INTO pr_notices (user_id, kind, payload) VALUES ($1, $2, $3::jsonb)",
        int(user_id), kind, json.dumps(payload or {}, ensure_ascii=False),
    )


async def drain_notices(bot) -> None:
    from pr_groups_logic import (
        text_accepted,
        text_accepting,
        text_admin_ended,
        text_confirm_timeout,
        text_dropped,
        text_photos_expired,
        text_rejected,
    )
    p = await pool()
    rows = await p.fetch("SELECT * FROM pr_notices ORDER BY created_at ASC, id ASC LIMIT 20")
    for row in rows:
        kind = row["kind"]
        payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"] or "{}")
        try:
            sent = False
            if kind == "accepting":
                claim = None
                claim_id = payload.get("claimId")
                if claim_id:
                    claim = await claim_by_id(int(claim_id))
                role = str((claim or {}).get("role") or payload.get("role") or "")
                days = int((claim or {}).get("term_days") or payload.get("termDays") or 14)
                if claim and claim.get("status") == ST_LIVE:
                    sent = await deliver_dm(
                        bot, int(row["user_id"]),
                        text_accepted(days, role=role),
                        accepted_keyboard(owner=role == ROLE_OWNER),
                        fresh=True,
                    )
                else:
                    sent = await deliver_dm(
                        bot, int(row["user_id"]), text_accepting(), accepting_keyboard(), fresh=True,
                    )
            elif kind == "accepted":
                sent = await deliver_dm(
                    bot, int(row["user_id"]),
                    text_accepted(int(payload.get("termDays") or 14), role=str(payload.get("role") or "")),
                    accepted_keyboard(owner=str(payload.get("role") or "") == ROLE_OWNER),
                    fresh=True,
                )
            elif kind == "rejected":
                can_fix = bool(payload.get("canFix"))
                sent = await deliver_dm(
                    bot, int(row["user_id"]),
                    text_rejected(str(payload.get("text") or ""), can_fix=can_fix),
                    rejected_keyboard(can_fix=can_fix),
                    fresh=True,
                )
            elif kind == "photos_expired":
                sent = await deliver_dm(bot, int(row["user_id"]), text_photos_expired(), photos_expired_keyboard(), fresh=True)
            elif kind == "confirm_expired":
                sent = await deliver_dm(bot, int(row["user_id"]), text_confirm_timeout(), confirm_timeout_keyboard(), fresh=True)
            elif kind == "admin_ended":
                sent = await deliver_dm(
                    bot, int(row["user_id"]),
                    text_admin_ended(str(payload.get("title") or ""), str(payload.get("reason") or "")),
                    admin_ended_keyboard(),
                    fresh=True,
                )
            elif kind == "dropped":
                sent = await deliver_dm(
                    bot, int(row["user_id"]), text_dropped(), dropped_keyboard(), fresh=True,
                )
            else:
                sent = True
            if sent:
                await p.execute("DELETE FROM pr_notices WHERE id = $1", int(row["id"]))
            else:
                raise RuntimeError("notice not delivered")
        except Exception:
            log.exception("notice fail id=%s kind=%s", row["id"], kind)
            try:
                await p.execute(
                    "UPDATE pr_notices SET created_at = NOW() + INTERVAL '5 minutes' WHERE id = $1",
                    int(row["id"]),
                )
            except Exception:
                pass


async def housekeep(bot) -> None:
    await ensure_schema()
    p = await pool()
    accepting = await p.fetch(
        "SELECT * FROM pr_claims WHERE status = ANY($1::text[])",
        [ST_ACCEPTING, ST_FULFILLING],
    )
    for row in accepting:
        try:
            done = await fulfill_accept(int(row["id"]), bot=bot)
            if done and done.get("status") == ST_LIVE:
                await push_notice(int(done["user_id"]), "accepted", {
                    "termDays": done.get("term_days"),
                    "role": done.get("role"),
                })
        except Exception:
            log.exception("fulfill accept")
    ending = await p.fetch("SELECT * FROM pr_claims WHERE status = $1", ST_ENDING)
    for row in ending:
        try:
            async with _fulfill_lock:
                await end_claim(bot, _row(row), reason="admin")
        except Exception:
            log.exception("end ending claim")
    await drain_notices(bot)
    photos = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE status = $1 AND photos_started_at < NOW() - ($2 || ' hours')::interval
        """,
        ST_PHOTOS, str(PHOTO_HOURS),
    )
    for row in photos:
        await expire_claim(int(row["id"]))
        await push_notice(int(row["user_id"]), "photos_expired")
    waits = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE status = $1
           AND photos_done_at IS NOT NULL
           AND photos_done_at < NOW() - ($2 || ' hours')::interval
           AND confirmed_at IS NULL
        """,
        ST_WAIT_CONFIRM, str(CONFIRM_HOURS),
    )
    for row in waits:
        await expire_claim(int(row["id"]))
        await push_notice(int(row["user_id"]), "confirm_expired")
    retries = await p.fetch(
        """
        SELECT * FROM pr_claims
         WHERE status = $1
           AND slot_hold_until IS NOT NULL
           AND slot_hold_until < NOW()
           AND confirmed_at IS NULL
        """,
        ST_CONFIRM_RETRY,
    )
    for row in retries:
        await expire_claim(int(row["id"]))
        await push_notice(int(row["user_id"]), "confirm_expired")
    lives = await list_live()
    for claim in lives:
        until = claim.get("live_until")
        if until and until <= _now():
            async with _fulfill_lock:
                await end_claim(bot, claim, reason="term")
            try:
                from pr_groups_logic import text_term_end
                await deliver_dm(bot, int(claim["user_id"]), text_term_end(), term_end_keyboard())
            except Exception:
                log.debug("term end notice", exc_info=True)
            continue
        last = claim.get("last_digest_at") or claim.get("accepted_at")
        if last and (_now() - last).total_seconds() >= 86400:
            await flush_digest(bot, claim)
        await try_quiet_nika(bot, claim)
