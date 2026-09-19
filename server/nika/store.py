# -*- coding: utf-8 -*-
"""Ника: чтение и запись состояния в Postgres.

Никаких денег здесь не двигается — только настройки, срезы, журнал и
атомарные claim'ы. Два экземпляра бота не сделают два тика подряд:
claim_tick / claim_group_action устроены как UPDATE ... WHERE ... RETURNING.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from nika.policy import (
    DEFAULT_SPEED_MODE,
    GroupPolicy,
    MAX_TICK_SEC,
    MIN_TICK_SEC,
    SOURCE_LADDER,
    SWEEP_DEST_CHAT_ID,
    normalize_speed_mode,
    normalize_sweep_speed,
    suggest_caps,
    sweep_speed_preset,
)

SAMPLE_KEEP_DAYS = 14
STALE_PENDING_SEC = 120


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def policy_from_row(row: Any) -> GroupPolicy:
    return GroupPolicy(
        chat_id=_as_int(row["chat_id"]),
        target_balance=_as_int(row["target_balance"]),
        speed_mode=normalize_speed_mode(row["speed_mode"]),
        dead_zone_pct=float(row["dead_zone_pct"] or 0.05),
        dead_zone_min=_as_int(row["dead_zone_min"], 100),
        max_transfer=_as_int(row["max_transfer"], 1000),
        max_daily_topup=_as_int(row["max_daily_topup"], 10000),
        max_daily_sweep=_as_int(row["max_daily_sweep"], 10000),
        sweep_share=float(row["sweep_share"] or 0.90),
        sweep_delay_sec=_as_int(row["sweep_delay_sec"], 45),
        sweep_cooldown_sec=_as_int(row["sweep_cooldown_sec"], 30),
    )


def forbidden_managed_ids() -> List[int]:
    ids = {int(cid) for cid, _ in SOURCE_LADDER}
    ids.add(int(SWEEP_DEST_CHAT_ID))
    return sorted(ids)


async def fetch_settings(conn) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow("SELECT * FROM nika_settings WHERE id = 1")
    return dict(row) if row else None


async def claim_tick(conn) -> Optional[Dict[str, Any]]:
    """Забрать право провести тик. None — рано или система выключена."""
    row = await conn.fetchrow(
        """
        UPDATE nika_settings
        SET last_tick_at = NOW(),
            updated_at = NOW()
        WHERE id = 1
          AND enabled = TRUE
          AND (
              last_tick_at IS NULL
              OR last_tick_at < NOW() - (GREATEST(tick_interval_sec, 8) * 0.8) * INTERVAL '1 second'
          )
        RETURNING *
        """
    )
    return dict(row) if row else None


async def record_tick_error(conn, error: str) -> None:
    await conn.execute(
        """
        UPDATE nika_settings
        SET last_error = $1,
            last_error_at = NOW(),
            heal_ok_streak = 0,
            updated_at = NOW()
        WHERE id = 1
        """,
        str(error)[:1000],
    )


async def record_tick_ok(conn) -> None:
    await conn.execute(
        """
        UPDATE nika_settings
        SET last_error = NULL,
            heal_ok_streak = COALESCE(heal_ok_streak, 0) + 1,
            updated_at = NOW()
        WHERE id = 1
        """
    )


async def fetch_enabled_groups(conn) -> List[Any]:
    return await conn.fetch(
        """
        SELECT *
        FROM nika_group_settings
        WHERE enabled = TRUE
        ORDER BY chat_id
        """
    )


async def claim_group_action(conn, chat_id: int, kind: str, cooldown_sec: int) -> bool:
    column = "last_topup_at" if kind == "topup" else "last_sweep_at"
    if column not in ("last_topup_at", "last_sweep_at"):
        return False
    wait = max(8, int(cooldown_sec or 8))
    row = await conn.fetchrow(
        f"""
        UPDATE nika_group_settings
        SET {column} = NOW(),
            updated_at = NOW()
        WHERE chat_id = $1
          AND enabled = TRUE
          AND (
              {column} IS NULL
              OR {column} < NOW() - $2 * INTERVAL '1 second'
          )
        RETURNING chat_id
        """,
        int(chat_id),
        wait,
    )
    return row is not None


async def force_touch_group_action(conn, chat_id: int, kind: str) -> None:
    """Пометить время действия без проверки кулдауна (ручная кнопка)."""
    column = "last_topup_at" if kind == "topup" else "last_sweep_at"
    if column not in ("last_topup_at", "last_sweep_at"):
        return
    await conn.execute(
        f"""
        UPDATE nika_group_settings
        SET {column} = NOW(),
            updated_at = NOW()
        WHERE chat_id = $1
        """,
        int(chat_id),
    )


async def insert_sample(conn, chat_id: int, balance: int, target_balance: int) -> None:
    await conn.execute(
        """
        INSERT INTO nika_balance_sample (chat_id, balance, target_balance)
        VALUES ($1, $2, $3)
        """,
        int(chat_id),
        int(balance),
        int(target_balance),
    )


async def prune_samples(conn, keep_days: int = SAMPLE_KEEP_DAYS) -> int:
    result = await conn.execute(
        """
        DELETE FROM nika_balance_sample
        WHERE created_at < NOW() - $1 * INTERVAL '1 day'
        """,
        int(max(1, keep_days)),
    )
    try:
        return int(str(result).split()[-1])
    except Exception:
        return 0


async def drain_per_hour(conn, chat_id: int, window_hours: int = 6) -> float:
    row = await conn.fetchrow(
        """
        SELECT
            (ARRAY_AGG(balance ORDER BY created_at ASC))[1] AS oldest,
            (ARRAY_AGG(balance ORDER BY created_at DESC))[1] AS newest,
            EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) AS span_sec
        FROM nika_balance_sample
        WHERE chat_id = $1
          AND created_at > NOW() - $2 * INTERVAL '1 hour'
        """,
        int(chat_id),
        int(max(1, window_hours)),
    )
    if not row or row["span_sec"] is None:
        return 0.0
    span = float(row["span_sec"] or 0)
    if span < 600:
        return 0.0
    oldest = _as_int(row["oldest"])
    newest = _as_int(row["newest"])
    return max(0.0, (oldest - newest) / (span / 3600.0))


async def sweep_window(conn, chat_id: int, delay_sec: int) -> Dict[str, Any]:
    wait = int(max(8, delay_sec))
    row = await conn.fetchrow(
        """
        SELECT
            MIN(balance)::bigint AS stable_balance,
            COUNT(*)::int AS n,
            (
                EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) >= $2
            ) AS covers
        FROM nika_balance_sample
        WHERE chat_id = $1
          AND created_at >= NOW() - $2 * INTERVAL '1 second'
        """,
        int(chat_id),
        wait,
    )
    if not row or _as_int(row["n"]) < 2:
        return {"stable_balance": None, "covers": False, "n": 0}
    return {
        "stable_balance": _as_int(row["stable_balance"]) if row["stable_balance"] is not None else None,
        "covers": bool(row["covers"]),
        "n": _as_int(row["n"]),
    }


async def daily_done_sum(conn, chat_id: int, kind: str) -> int:
    value = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0)::bigint
        FROM nika_transfer_log
        WHERE chat_id = $1
          AND kind = $2
          AND status = 'done'
          AND created_at > NOW() - INTERVAL '24 hours'
        """,
        int(chat_id),
        str(kind),
    )
    return _as_int(value)


async def ledger_events_24h(conn, chat_id: int) -> int:
    try:
        value = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM growth_fund_ledger
            WHERE chat_id = $1
              AND created_at > NOW() - INTERVAL '24 hours'
            """,
            int(chat_id),
        )
        return _as_int(value)
    except Exception:
        return 0


async def fetch_balances(conn, chat_ids: Sequence[int]) -> Dict[int, int]:
    ids = [int(cid) for cid in chat_ids]
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT chat_id, COALESCE(chatbalance, 0)::bigint AS balance
        FROM chat
        WHERE chat_id = ANY($1::bigint[])
        """,
        ids,
    )
    return {int(row["chat_id"]): _as_int(row["balance"]) for row in rows}


async def fetch_heal_rows(conn) -> List[Any]:
    return await conn.fetch(
        """
        SELECT *
        FROM nika_transfer_log
        WHERE (
                status = 'refund_failed'
             )
           OR (
                status = 'pending'
                AND created_at < NOW() - $1 * INTERVAL '1 second'
             )
           OR (
                revert_requested_at IS NOT NULL
                AND reverted_at IS NULL
                AND status = 'done'
             )
        ORDER BY created_at ASC
        LIMIT 50
        """,
        int(STALE_PENDING_SEC),
    )


async def try_owner_alert(conn, cooldown_sec: int) -> Optional[int]:
    row = await conn.fetchrow(
        """
        UPDATE nika_settings
        SET last_owner_alert_at = NOW(),
            updated_at = NOW()
        WHERE id = 1
          AND owner_alert_user_id IS NOT NULL
          AND (
              last_owner_alert_at IS NULL
              OR last_owner_alert_at < NOW() - GREATEST($1, 600) * INTERVAL '1 second'
          )
        RETURNING owner_alert_user_id
        """,
        int(cooldown_sec or 21600),
    )
    if not row:
        return None
    return _as_int(row["owner_alert_user_id"]) or None


async def disable_system(db) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE nika_settings SET enabled = FALSE, updated_at = NOW() WHERE id = 1"
        )


async def enable_system(db) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE nika_settings SET enabled = TRUE, updated_at = NOW() WHERE id = 1"
        )


async def disable_group(db, chat_id: int) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nika_group_settings
            SET enabled = FALSE, updated_at = NOW()
            WHERE chat_id = $1
            """,
            int(chat_id),
        )


async def enable_group(db, chat_id: int) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nika_group_settings
            SET enabled = TRUE, updated_at = NOW()
            WHERE chat_id = $1
            """,
            int(chat_id),
        )


async def fetch_group_row(conn, chat_id: int) -> Optional[Any]:
    return await conn.fetchrow(
        "SELECT * FROM nika_group_settings WHERE chat_id = $1",
        int(chat_id),
    )


async def claim_commands(conn, limit: int = 8) -> List[Any]:
    return await conn.fetch(
        """
        UPDATE nika_operator_commands
        SET status = 'running',
            started_at = NOW()
        WHERE id IN (
            SELECT id
            FROM nika_operator_commands
            WHERE status = 'queued'
            ORDER BY CASE WHEN kind = 'now_sweep' THEN 0 ELSE 1 END, created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT $1
        )
        RETURNING *
        """,
        int(max(1, min(20, limit))),
    )


async def maybe_sample_universe(db) -> None:
    """Один срез «все балансы», не чаще чем раз в 90 секунд."""
    from nika.policy import SOURCE_LADDER, SWEEP_DEST_CHAT_ID

    ladder = [int(cid) for cid, _ in SOURCE_LADDER]
    vault = int(SWEEP_DEST_CHAT_ID)
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO nika_universe_sample (
                users_balance, chats_balance, live_chats_balance,
                managed_balance, ladder_balance, vault_balance
            )
            SELECT
                (SELECT COALESCE(SUM(balance), 0)::bigint FROM users),
                (SELECT COALESCE(SUM(chatbalance), 0)::bigint FROM chat),
                (
                    SELECT COALESCE(SUM(chatbalance), 0)::bigint
                    FROM chat
                    WHERE COALESCE(is_technical, FALSE) = FALSE
                ),
                (
                    SELECT COALESCE(SUM(c.chatbalance), 0)::bigint
                    FROM nika_group_settings s
                    JOIN chat c ON c.chat_id = s.chat_id
                ),
                (
                    SELECT COALESCE(SUM(chatbalance), 0)::bigint
                    FROM chat
                    WHERE chat_id = ANY($1::bigint[])
                ),
                (
                    SELECT COALESCE(chatbalance, 0)::bigint
                    FROM chat
                    WHERE chat_id = $2
                )
            WHERE NOT EXISTS (
                SELECT 1
                FROM nika_universe_sample
                WHERE created_at > NOW() - INTERVAL '90 seconds'
            )
            """,
            ladder,
            vault,
        )


async def prune_universe(conn, keep_days: int = 60) -> None:
    await conn.execute(
        """
        DELETE FROM nika_universe_sample
        WHERE created_at < NOW() - $1 * INTERVAL '1 day'
        """,
        int(max(7, keep_days)),
    )


async def finish_command(conn, command_id: int, *, ok: bool, error: str = "", result: Optional[Dict[str, Any]] = None) -> None:
    await conn.execute(
        """
        UPDATE nika_operator_commands
        SET status = $2,
            error = $3,
            result = $4::jsonb,
            finished_at = NOW()
        WHERE id = $1
        """,
        int(command_id),
        "done" if ok else "failed",
        (error or "")[:1000],
        json.dumps(result or {}, ensure_ascii=False),
    )


async def queued_command_stats(conn) -> Dict[str, int]:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'queued')::int AS queued,
            COUNT(*) FILTER (
                WHERE status = 'queued' AND created_at < NOW() - INTERVAL '2 minutes'
            )::int AS stale,
            COUNT(*) FILTER (WHERE status = 'running')::int AS running
        FROM nika_operator_commands
        WHERE status IN ('queued', 'running')
        """
    )
    if not row:
        return {"queued": 0, "stale": 0, "running": 0}
    return {
        "queued": _as_int(row["queued"]),
        "stale": _as_int(row["stale"]),
        "running": _as_int(row["running"]),
    }


async def upsert_group(
    db,
    chat_id: int,
    target_balance: int,
    *,
    speed_mode: str = DEFAULT_SPEED_MODE,
    enabled: bool = True,
    updated_by: Optional[int] = None,
    note: Optional[str] = None,
) -> bool:
    cid = int(chat_id)
    if cid in set(forbidden_managed_ids()):
        return False
    caps = suggest_caps(int(target_balance))
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO nika_group_settings (
                chat_id, enabled, target_balance, speed_mode,
                max_transfer, max_daily_topup, max_daily_sweep,
                dead_zone_min, note, updated_by, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, NOW())
            ON CONFLICT (chat_id) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                target_balance = EXCLUDED.target_balance,
                speed_mode = EXCLUDED.speed_mode,
                note = COALESCE(EXCLUDED.note, nika_group_settings.note),
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            """,
            cid,
            bool(enabled),
            int(target_balance),
            normalize_speed_mode(speed_mode),
            int(caps["max_transfer"]),
            int(caps["max_daily_topup"]),
            int(caps["dead_zone_min"]),
            note,
            updated_by,
        )
    return True


async def remove_group(db, chat_id: int) -> bool:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM nika_group_settings WHERE chat_id = $1 RETURNING chat_id",
            int(chat_id),
        )
    return row is not None


async def update_global_settings(
    db,
    *,
    enabled: Optional[bool] = None,
    dry_run: Optional[bool] = None,
    tick_interval_sec: Optional[int] = None,
    sweep_speed: Optional[str] = None,
) -> None:
    sets = ["updated_at = NOW()"]
    args: list = []
    if enabled is not None:
        args.append(bool(enabled))
        sets.append(f"enabled = ${len(args)}")
    if dry_run is not None:
        args.append(bool(dry_run))
        sets.append(f"dry_run = ${len(args)}")
    if sweep_speed is not None:
        speed_key = normalize_sweep_speed(sweep_speed)
        args.append(speed_key)
        sets.append(f"sweep_speed = ${len(args)}")
        if tick_interval_sec is None:
            tick_interval_sec = int(sweep_speed_preset(speed_key)["tickSec"])
    if tick_interval_sec is not None:
        tick = int(tick_interval_sec)
        if tick < MIN_TICK_SEC:
            tick = MIN_TICK_SEC
        if tick > MAX_TICK_SEC:
            tick = MAX_TICK_SEC
        args.append(tick)
        sets.append(f"tick_interval_sec = ${len(args)}")
    if len(args) == 0:
        return
    async with db.pool.acquire() as conn:
        await conn.execute(
            f"UPDATE nika_settings SET {', '.join(sets)} WHERE id = 1",
            *args,
        )


async def list_supervised_groups(db) -> List[Dict[str, Any]]:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.*, COALESCE(c.chatbalance, 0)::bigint AS balance,
                   c.namechat
            FROM nika_group_settings s
            LEFT JOIN chat c ON c.chat_id = s.chat_id
            ORDER BY s.enabled DESC, s.chat_id
            """
        )
    return [dict(row) for row in rows]


async def list_recent_transfers(db, *, chat_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    limit = int(max(1, min(200, limit)))
    async with db.pool.acquire() as conn:
        if chat_id is None:
            rows = await conn.fetch(
                """
                SELECT * FROM nika_transfer_log
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM nika_transfer_log
                WHERE chat_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                int(chat_id),
                limit,
            )
    return [dict(row) for row in rows]


async def request_revert(db, transfer_id: int, requested_by: int) -> bool:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE nika_transfer_log
            SET revert_requested_at = NOW(),
                revert_requested_by = $2
            WHERE id = $1
              AND status = 'done'
              AND reverted_at IS NULL
              AND revert_requested_at IS NULL
            RETURNING id
            """,
            int(transfer_id),
            int(requested_by),
        )
    return row is not None
