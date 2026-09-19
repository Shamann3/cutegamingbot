# -*- coding: utf-8 -*-
"""Пиар в группах: схема, заявки, посев, подарок, рента."""

from __future__ import annotations

import json
import logging
import sys
import asyncio
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

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
    ST_EXPIRED,
    ST_FULFILLING,
    ST_LIVE,
    ST_PENDING,
    ST_PHOTOS,
    ST_REJECTED,
    ST_WAIT_CONFIRM,
    WEEK_SEED_STATUSES,
    classify_player,
    is_broke,
    is_new_class,
    left_days_hint,
    looks_like_confirm,
    nika_step_amount,
    promoter_cut,
    recommend_seed,
    recommend_split,
    spendable_amount,
    weekly_seed_budget,
)

_GIFT_CLAW = ContextVar("pr_gift_claw", default=False)
_fulfill_lock = asyncio.Lock()

log = logging.getLogger("pr_groups")

PR_HUB = "prg:hub"
PR_START = "prg:go"
PR_PICK = "prg:g:"
PR_OWNER = "prg:own"
PR_RECO = "prg:rec"
PR_CANCEL = "prg:x"
PR_YES = "prgY:"
PR_NO = "prgN:"

ICON_GO = "5424616516018537963"
ICON_OK = "5339112148175959615"
ICON_NO = "5337017423906226569"


def _btn(text: str, data: str, icon: str, style: str = "default") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style, icon_custom_emoji_id=icon)


def entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Начать", PR_START, ICON_GO, "success")]])


def role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Это моя группа", PR_OWNER, ICON_OK)],
        [_btn("Я привёл Кут", PR_RECO, ICON_GO)],
        [_btn("Снять", PR_CANCEL, ICON_NO)],
    ])


def groups_keyboard(rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    kb = []
    for row in rows:
        title = (row.get("title") or str(row.get("chat_id")))[:32]
        kb.append([_btn(title, f"{PR_PICK}{row['chat_id']}", ICON_GO)])
    kb.append([_btn("Снять", PR_CANCEL, ICON_NO)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Снять", PR_CANCEL, ICON_NO)]])


def confirm_keyboard(claim_id: int, token: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Да", f"{PR_YES}{claim_id}:{int(token)}", ICON_OK, "success"),
        _btn("Нет", f"{PR_NO}{claim_id}:{int(token)}", ICON_NO, "danger"),
    ]])


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
            await p.execute(f"ALTER TABLE pr_claims ADD COLUMN IF NOT EXISTS {col} {spec}")
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
        CREATE TABLE IF NOT EXISTS pr_sessions (
            user_id BIGINT PRIMARY KEY,
            claim_id BIGINT,
            mode TEXT,
            extra JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


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


async def set_session(user_id: int, *, claim_id: Optional[int], mode: str, extra: Optional[dict] = None) -> None:
    p = await pool()
    await p.execute(
        """
        INSERT INTO pr_sessions (user_id, claim_id, mode, extra, updated_at)
        VALUES ($1, $2, $3, $4::jsonb, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            claim_id = $2, mode = $3, extra = $4::jsonb, updated_at = NOW()
        """,
        int(user_id), claim_id, mode, json.dumps(extra or {}, ensure_ascii=False),
    )


async def is_waiting_photos(user_id: int, chat_type: str = "") -> bool:
    if str(chat_type or "") != "private":
        return False
    session = await get_session(user_id)
    return bool(session and session.get("mode") == "photos")


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
    sets = []
    args: list[Any] = []
    i = 1
    for key, value in fields.items():
        if key == "photos" and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
            sets.append(f"{key} = ${i}::jsonb")
        else:
            sets.append(f"{key} = ${i}")
        args.append(value)
        i += 1
    args.append(int(claim_id))
    p = await pool()
    row = await p.fetchrow(
        f"UPDATE pr_claims SET {', '.join(sets)}, updated_at = NOW() WHERE id = ${i} RETURNING *",
        *args,
    )
    return _row(row)


async def add_photo(claim_id: int, file_id: str) -> dict[str, Any]:
    claim = await claim_by_id(claim_id)
    photos = list(claim.get("photos") or [])
    photos.append({"file_id": file_id, "n": len(photos) + 1})
    fields: dict[str, Any] = {"photos": photos}
    if len(photos) >= PHOTOS_REQUIRED:
        fields["photos_done_at"] = _now()
        if claim["role"] == ROLE_OWNER:
            fields["status"] = ST_PENDING
        else:
            fields["status"] = ST_WAIT_CONFIRM
    return await save_claim(claim_id, **fields)


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


async def money_view(member_count: int = 0) -> dict[str, Any]:
    ladder, items = await ladder_free()
    reserve = await nika_reserve()
    can = spendable_amount(ladder, reserve)
    rec_total = recommend_seed(member_count, can)
    split = recommend_split(rec_total, member_count)
    week_used = await week_seed_used()
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


async def week_seed_used() -> int:
    p = await pool()
    return _as_int(await p.fetchval(
        """
        SELECT COALESCE(SUM(seed_total), 0) FROM pr_claims
         WHERE status = ANY($1::text[])
           AND COALESCE(accepted_at, updated_at) >= NOW() - INTERVAL '7 days'
        """,
        list(WEEK_SEED_STATUSES),
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
    """Идемпотентно: стол снимается один раз, повтор тикера не списывает снова."""
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
        view = await money_view(members)
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
                raise ValueError("Техкасса не отдаёт стол")
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
    return await save_claim(
        claim_id,
        status=ST_LIVE,
        accepted_at=claim.get("accepted_at") or _now(),
        live_until=until,
        term_days=term_days,
        nika_on=bool(claim.get("nika_on")),
        freeze=None,
    )


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


async def maybe_grant_gift(bot, *, user_id: int, chat_id: int, name: str) -> Optional[int]:
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
    await _give_to_user(user_id, size, "подарок пиар-группы")
    p = await pool()
    await p.execute(
        """
        INSERT INTO pr_gifts (user_id, amount, chat_id, claim_id, granted_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO UPDATE SET amount = pr_gifts.amount + $2
        """,
        int(user_id), size, int(chat_id), int(claim["id"]),
    )
    await save_claim(int(claim["id"]), pool_left=int(claim["pool_left"]) - size)
    return size


async def consume_gift_bet(user_id: int, chat_id: int, bet: int) -> bool:
    """Списать подарок на соло-ставку. False — ставка лезет в подарок не там."""
    state = await gift_state(user_id)
    locked = int(state["amount"] or 0)
    if locked <= 0:
        return True
    if int(state.get("chat_id") or 0) != int(chat_id):
        return False
    take = min(locked, max(0, int(bet)))
    p = await pool()
    await p.execute(
        "UPDATE pr_gifts SET amount = $2, last_bet = $3 WHERE user_id = $1",
        int(user_id), locked - take, take,
    )
    return True


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
            await _give_to_user(int(claim["user_id"]), pay, "пиар в группах")
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
        await bot.send_message(
            int(claim["user_id"]),
            text_digest(
                newcomers=newcomers,
                commission=int(claim.get("commission_seen") or 0),
                paid=pay,
                days_left=left,
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        log.debug("digest send failed", exc_info=True)


async def end_claim(bot, claim: dict[str, Any], *, reason: str) -> None:
    from main import db
    status = ST_ENDED if reason != "kicked" else ST_BURNED
    chat_id = int(claim["chat_id"])
    lock = int(claim.get("seed_lock") or 0)
    nika_on = bool(claim.get("nika_on"))
    if reason == "kicked" or not nika_on:
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
        p = await pool()
        gifts = await p.fetch(
            "SELECT user_id, amount FROM pr_gifts WHERE claim_id = $1 AND amount > 0",
            int(claim["id"]),
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
    await save_claim(
        int(claim["id"]),
        status=status,
        ended_at=_now(),
        seed_lock=0 if reason == "kicked" or not nika_on else claim.get("seed_lock"),
        pool_left=0,
        pending_pay=0,
        freeze=None,
    )


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
    from pr_groups_logic import text_accepted, text_rejected
    p = await pool()
    rows = await p.fetch("SELECT * FROM pr_notices ORDER BY id ASC LIMIT 20")
    for row in rows:
        kind = row["kind"]
        payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"] or "{}")
        try:
            if kind == "accepted":
                await bot.send_message(int(row["user_id"]), text_accepted(int(payload.get("termDays") or 14)), parse_mode="HTML", disable_web_page_preview=True)
            elif kind == "rejected":
                await bot.send_message(int(row["user_id"]), text_rejected(str(payload.get("text") or ""), can_fix=bool(payload.get("canFix"))), parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            log.debug("notice fail", exc_info=True)
        await p.execute("DELETE FROM pr_notices WHERE id = $1", int(row["id"]))


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
                await push_notice(int(done["user_id"]), "accepted", {"termDays": done.get("term_days")})
        except Exception:
            log.exception("fulfill accept")
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
    lives = await list_live()
    for claim in lives:
        until = claim.get("live_until")
        if until and until <= _now():
            await end_claim(bot, claim, reason="term")
            continue
        last = claim.get("last_digest_at") or claim.get("accepted_at")
        if last and (_now() - last).total_seconds() >= 86400:
            await flush_digest(bot, claim)
        await try_quiet_nika(bot, claim)
