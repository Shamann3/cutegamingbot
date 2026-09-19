# -*- coding: utf-8 -*-
"""Админка Ники: чтение, инциденты, очередь команд.

Деньги здесь не двигаются. FastAPI не пишет chat.chatbalance — иначе
fastlane-кэш бота останется со старым балансом и игры выплатят не то.
Кнопки «долить / собрать / вернуть» кладут команду, её исполняет процесс бота.
Пауза и настройки — обычный SQL, без движения кут.

Формула и SQL живут в пакете nika/ — не в bot.runtime.nika. Образ api
собирается из server/ и пакета bot там нет.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db

log = logging.getLogger("admin_nika")
_schema_ok = False
_schema_lock = asyncio.Lock()
_schema_fail_mono = 0.0
_SCHEMA_RETRY_SEC = 45.0

WORKER_STALE_SEC = 600
# Тот же порог, что команда «все балансы» в боте (main.JERICHO_GROUP_EXCESS_THRESHOLD).
ALL_BALANCES_EXCESS = 3000


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


async def _universe_now(conn) -> Dict[str, Any]:
    from nika.policy import SOURCE_LADDER, SWEEP_DEST_CHAT_ID

    ladder_ids = [int(cid) for cid, _ in SOURCE_LADDER]
    vault = int(SWEEP_DEST_CHAT_ID)
    totals = await conn.fetchrow(
        """
        SELECT
            (SELECT COALESCE(SUM(balance), 0)::bigint FROM users) AS users_balance,
            (SELECT COALESCE(SUM(chatbalance), 0)::bigint FROM chat) AS chats_balance,
            (
                SELECT COALESCE(SUM(chatbalance), 0)::bigint
                FROM chat
                WHERE COALESCE(is_technical, FALSE) = FALSE
            ) AS live_chats_balance,
            (
                SELECT COALESCE(SUM(c.chatbalance), 0)::bigint
                FROM nika_group_settings s
                JOIN chat c ON c.chat_id = s.chat_id
            ) AS managed_balance,
            (
                SELECT COALESCE(SUM(chatbalance), 0)::bigint
                FROM chat
                WHERE chat_id = ANY($1::bigint[])
            ) AS ladder_balance,
            (
                SELECT COALESCE(chatbalance, 0)::bigint
                FROM chat
                WHERE chat_id = $2
            ) AS vault_balance
        """,
        ladder_ids,
        vault,
    )
    pressure = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(COALESCE(chatbalance, 0)), 0)::bigint AS groups_total,
            COALESCE(SUM(GREATEST(COALESCE(chatbalance, 0) - $1, 0)), 0)::bigint AS total_excess,
            COUNT(*) FILTER (WHERE COALESCE(chatbalance, 0) > $1)::int AS hot_groups
        FROM chat
        WHERE COALESCE(is_technical, FALSE) = FALSE
        """,
        ALL_BALANCES_EXCESS,
    )
    users = _as_int(totals["users_balance"] if totals else 0)
    chats = _as_int(totals["chats_balance"] if totals else 0)
    live = _as_int(totals["live_chats_balance"] if totals else 0)
    return {
        "users": users,
        "chats": chats,
        "system": users + chats,
        "liveChats": live,
        "managed": _as_int(totals["managed_balance"] if totals else 0),
        "ladder": _as_int(totals["ladder_balance"] if totals else 0),
        "vault": _as_int(totals["vault_balance"] if totals else 0),
        "vaultChatId": vault,
        "pressurePct": round(
            (100.0 * _as_int(pressure["total_excess"] if pressure else 0) / max(1, _as_int(pressure["groups_total"] if pressure else 0))),
            1,
        ) if pressure else 0,
        "hotGroups": _as_int(pressure["hot_groups"] if pressure else 0),
        "excess": _as_int(pressure["total_excess"] if pressure else 0),
        "liveTotal": _as_int(pressure["groups_total"] if pressure else 0),
        "excessThreshold": ALL_BALANCES_EXCESS,
        "hotList": [
            {
                "chatId": int(r["chat_id"]),
                "name": r["namechat"] or str(r["chat_id"]),
                "balance": _as_int(r["balance"]),
                "excess": _as_int(r["excess"]),
            }
            for r in (await conn.fetch(
                """
                SELECT chat_id, namechat,
                       COALESCE(chatbalance, 0)::bigint AS balance,
                       GREATEST(COALESCE(chatbalance, 0) - $1, 0)::bigint AS excess
                FROM chat
                WHERE COALESCE(is_technical, FALSE) = FALSE
                  AND COALESCE(chatbalance, 0) > $1
                ORDER BY chatbalance DESC NULLS LAST
                LIMIT 3
                """,
                ALL_BALANCES_EXCESS,
            ))
        ],
    }


def _aware(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _bucket_key(value, trunc: str) -> str:
    if isinstance(value, datetime):
        dt = _aware(value)
        return dt.strftime("%Y-%m-%dT%H") if trunc == "hour" else dt.strftime("%Y-%m-%d")
    text = str(value or "")
    if trunc == "hour":
        return text[:13].replace(" ", "T")
    return text[:10]


def _iter_buckets(since, until, trunc: str) -> List[datetime]:
    step = timedelta(hours=1) if trunc == "hour" else timedelta(days=1)
    cap = 48 if trunc == "hour" else 62
    end = _aware(until)
    start = _aware(since)
    if trunc == "hour":
        end = end.replace(minute=0, second=0, microsecond=0)
        start = start.replace(minute=0, second=0, microsecond=0)
    else:
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    out: List[datetime] = []
    cur = end
    while cur >= start and len(out) < cap:
        out.append(cur)
        cur = cur - step
    out.reverse()
    return out


def _extrema(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    plus_n = sum(1 for p in points if (p.get("net") or 0) > 0)
    minus_n = sum(1 for p in points if (p.get("net") or 0) < 0)
    best = max(points, key=lambda p: p.get("net") or 0) if points else None
    worst = min(points, key=lambda p: p.get("net") or 0) if points else None
    if best and (best.get("net") or 0) <= 0:
        best = None
    if worst and (worst.get("net") or 0) >= 0:
        worst = None
    return {
        "plusBuckets": plus_n,
        "minusBuckets": minus_n,
        "flatBuckets": max(0, len(points) - plus_n - minus_n),
        "best": best,
        "worst": worst,
    }


async def _flow_bucket(conn, since, trunc: str, *, until: Optional[datetime] = None) -> List[Dict[str, Any]]:
    trunc = "hour" if trunc == "hour" else "day"
    since_dt = _aware(since)
    until_dt = _aware(until or datetime.now(timezone.utc))
    transfers = await conn.fetch(
        f"""
        SELECT
            date_trunc('{trunc}', created_at) AS bucket,
            COALESCE(SUM(amount) FILTER (WHERE kind = 'sweep' AND status = 'done'), 0)::bigint AS plus_vault,
            COALESCE(SUM(amount) FILTER (WHERE kind = 'topup' AND status = 'done'), 0)::bigint AS minus_sources,
            COALESCE(SUM(amount) FILTER (WHERE kind = 'revert' AND status = 'done'), 0)::bigint AS reverted
        FROM nika_transfer_log
        WHERE created_at >= $1
        GROUP BY 1
        ORDER BY 1
        """,
        since_dt,
    )
    fees = []
    try:
        fees = await conn.fetch(
            f"""
            SELECT
                date_trunc('{trunc}', created_at) AS bucket,
                COALESCE(SUM(commission), 0)::bigint AS commission
            FROM growth_fund_ledger
            WHERE created_at >= $1
            GROUP BY 1
            """,
            since_dt,
        )
    except Exception:
        fees = []
    uni = []
    try:
        uni = await conn.fetch(
            f"""
            SELECT
                date_trunc('{trunc}', created_at) AS bucket,
                (ARRAY_AGG(users_balance ORDER BY created_at DESC))[1]::bigint AS users_balance,
                (ARRAY_AGG(chats_balance ORDER BY created_at DESC))[1]::bigint AS chats_balance,
                (ARRAY_AGG(vault_balance ORDER BY created_at DESC))[1]::bigint AS vault_balance,
                (ARRAY_AGG(ladder_balance ORDER BY created_at DESC))[1]::bigint AS ladder_balance
            FROM nika_universe_sample
            WHERE created_at >= $1
            GROUP BY 1
            ORDER BY 1
            """,
            since_dt,
        )
    except Exception:
        uni = []
    transfer_map = {_bucket_key(r["bucket"], trunc): r for r in transfers}
    fee_map = {_bucket_key(r["bucket"], trunc): _as_int(r["commission"]) for r in fees}
    uni_map = {
        _bucket_key(r["bucket"], trunc): {
            "users": _as_int(r["users_balance"]),
            "chats": _as_int(r["chats_balance"]),
            "vault": _as_int(r["vault_balance"]),
            "ladder": _as_int(r["ladder_balance"]),
            "system": _as_int(r["users_balance"]) + _as_int(r["chats_balance"]),
        }
        for r in uni
    }
    points = []
    for bucket in _iter_buckets(since_dt, until_dt, trunc):
        key = _bucket_key(bucket, trunc)
        row = transfer_map.get(key)
        plus_vault = _as_int(row["plus_vault"]) if row else 0
        minus_sources = _as_int(row["minus_sources"]) if row else 0
        reverted = _as_int(row["reverted"]) if row else 0
        commission = _as_int(fee_map.get(key))
        plus = plus_vault + commission
        minus = minus_sources
        uni_row = uni_map.get(key) or {}
        points.append({
            "t": bucket.isoformat(),
            "label": bucket.strftime("%d.%m") if trunc == "day" else bucket.strftime("%H:%M"),
            "plus": plus,
            "minus": minus,
            "net": plus - minus,
            "plusVault": plus_vault,
            "commission": commission,
            "minusSources": minus_sources,
            "reverted": reverted,
            "system": uni_row.get("system"),
            "systemDelta": None,
            "users": uni_row.get("users"),
            "chats": uni_row.get("chats"),
            "vault": uni_row.get("vault"),
            "ladder": uni_row.get("ladder"),
        })
    prev = None
    for point in points:
        if point["system"] is not None and prev is not None:
            point["systemDelta"] = point["system"] - prev
        if point["system"] is not None:
            prev = point["system"]
    return points


def _incident_out(row: Dict[str, Any]) -> Dict[str, Any]:
    from nika.incidents import actions_for

    actions = row.get("actions")
    if not isinstance(actions, list) or not actions:
        actions = actions_for(str(row.get("code") or ""))
    payload = row.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return {
        "id": _as_int(row.get("id")),
        "code": row.get("code"),
        "severity": row.get("severity") or "critical",
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "chatId": row.get("chat_id"),
        "payload": _jsonable(payload),
        "actions": actions,
        "status": row.get("status") or "open",
        "occurrenceCount": _as_int(row.get("occurrence_count"), 1),
        "createdAt": _jsonable(row.get("created_at")),
        "updatedAt": _jsonable(row.get("updated_at")),
        "resolvedAt": _jsonable(row.get("resolved_at")),
        "resolvedBy": row.get("resolved_by"),
        "resolveNote": row.get("resolve_note") or "",
    }


async def _open_admin_pool() -> None:
    if getattr(db, "pool", None) is not None:
        return
    ensure = getattr(db, "ensure_pool", None)
    if callable(ensure):
        if not await ensure():
            raise RuntimeError("Пул админки не открыт")
        return
    opener = getattr(db, "ensure_connected", None) or getattr(db, "connect", None)
    if callable(opener):
        await opener()
    if getattr(db, "pool", None) is None:
        raise RuntimeError("Пул админки не открыт")


async def _ensure() -> None:
    global _schema_ok, _schema_fail_mono
    if _schema_ok:
        return
    now = time.monotonic()
    if _schema_fail_mono and (now - _schema_fail_mono) < _SCHEMA_RETRY_SEC:
        return
    async with _schema_lock:
        if _schema_ok:
            return
        try:
            await _open_admin_pool()
            from nika.schema import ensure_nika_schema

            await ensure_nika_schema(db)
            _schema_ok = True
            _schema_fail_mono = 0.0
        except Exception as exc:
            _schema_fail_mono = time.monotonic()
            log.warning("nika schema ensure: %s: %s", type(exc).__name__, exc)


def _forbidden() -> List[int]:
    from nika.store import forbidden_managed_ids

    return forbidden_managed_ids()


def forecast_tick(
    settings: Dict[str, Any],
    group_rows: List[Any],
    group_out: List[Dict[str, Any]],
    ladder: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Что сделает следующий тик — той же формулой, что engine, без движения кут.

    Сбор излишка здесь честно остаётся «ждёт выдержку»: без окна истории
    Ника свежие куты не снимает, и панель это не прячет.
    """
    from nika.policy import (
        SOURCE_LADDER,
        allocate_from_ladder,
        apply_sweep_speed,
        pick_sweep_dest,
        plan_sweep,
        plan_topup,
        sweep_dest_title,
        sweep_keep,
    )
    from nika.store import policy_from_row

    if not bool(settings.get("enabled")):
        return {
            "mode": "paused",
            "summary": "Ника на паузе. Проверка смотрит цифры, но куты не двигает.",
            "items": [],
        }

    dry = bool(settings.get("dry_run"))
    titles = {int(cid): title for cid, title in SOURCE_LADDER}
    avail: Dict[int, int] = {}
    order: List[int] = []
    for src in ladder or []:
        cid = int(src["chatId"])
        avail[cid] = _as_int(src.get("balance"))
        order.append(cid)
    if not order:
        order = [int(cid) for cid, _ in SOURCE_LADDER]
        for cid in order:
            avail.setdefault(cid, 0)

    row_by_id: Dict[int, Any] = {}
    for row in group_rows or []:
        try:
            row_by_id[int(row["chat_id"])] = row
        except Exception:
            continue

    items: List[Dict[str, Any]] = []
    for item in group_out or []:
        name = str(item.get("name") or item.get("chatId"))
        chat_id = int(item["chatId"])
        if not item.get("enabled"):
            items.append({
                "chatId": chat_id,
                "name": name,
                "action": "paused",
                "amount": 0,
                "text": f"{name}: группа на паузе, баланс не трогает",
            })
            continue
        row = row_by_id.get(chat_id)
        if row is None:
            items.append({
                "chatId": chat_id,
                "name": name,
                "action": "hold",
                "amount": 0,
                "text": f"{name}: нет цели и скорости",
            })
            continue
        policy = apply_sweep_speed(policy_from_row(row), settings.get("sweep_speed"))
        balance = _as_int(item.get("balance"))
        top = plan_topup(policy, balance=balance)
        if top.action == "topup" and top.amount > 0:
            sources = tuple((cid, max(0, int(avail.get(cid, 0)))) for cid in order)
            takes, still = allocate_from_ladder(top.amount, sources)
            if not takes:
                items.append({
                    "chatId": chat_id,
                    "name": name,
                    "action": "blocked",
                    "amount": int(top.amount),
                    "text": f"{name}: хочет долить {int(top.amount)} кут, в играх и кассах пусто",
                })
            else:
                src_id, amt = takes[0]
                avail[src_id] = max(0, int(avail.get(src_id, 0)) - int(amt))
                title = titles.get(int(src_id), str(src_id))
                extra = f", ещё не хватает {int(still)}" if still else ""
                items.append({
                    "chatId": chat_id,
                    "name": name,
                    "action": "topup",
                    "amount": int(amt),
                    "sourceChatId": int(src_id),
                    "sourceTitle": title,
                    "text": f"{name}: возьмёт {int(amt)} с «{title}»{extra}",
                })
            continue

        surplus = balance - int(policy.target_balance)
        keep = sweep_keep(policy)
        if surplus > keep:
            dest = pick_sweep_dest(chat_id)
            dest_name = sweep_dest_title(dest) or "техгруппы"
            ready = plan_sweep(
                policy,
                balance=balance,
                stable_balance=balance,
                history_covers_delay=True,
            )
            if ready.action == "sweep" and ready.amount > 0:
                items.append({
                    "chatId": chat_id,
                    "name": name,
                    "action": "sweep",
                    "amount": int(ready.amount),
                    "destChatId": dest,
                    "destTitle": dest_name,
                    "text": (
                        f"{name}: снимет {int(ready.amount)} кут в «{dest_name}» "
                        f"(выдержка {int(policy.sweep_delay_sec)} сек)"
                    ),
                })
            else:
                items.append({
                    "chatId": chat_id,
                    "name": name,
                    "action": "watch",
                    "amount": int(surplus),
                    "text": (
                        f"{name}: излишек {int(surplus)} кут, ждёт выдержку "
                        f"{int(policy.sweep_delay_sec)} сек — потом в «{dest_name}»"
                    ),
                })
            continue

        hold = str(top.reason or "")
        if "мёртвой зоны" in hold:
            hold = "баланс группы в зоне"
        elif "потолком" in hold:
            hold = "сегодня уже доливали достаточно"
        elif "цель не задана" in hold:
            hold = "нет цели"
        items.append({
            "chatId": chat_id,
            "name": name,
            "action": "hold",
            "amount": 0,
            "text": f"{name}: {hold}",
        })

    n_top = sum(1 for i in items if i["action"] == "topup")
    n_sweep = sum(1 for i in items if i["action"] == "sweep")
    n_blk = sum(1 for i in items if i["action"] == "blocked")
    n_watch = sum(1 for i in items if i["action"] == "watch")
    if dry:
        summary = "Сухой прогон: посчитает шаг, куты не тронет."
    elif n_blk and not n_top:
        summary = "Хочет долить баланс группы, но в играх и кассах пусто."
    elif n_sweep and n_top:
        summary = f"Дольёт {n_top} и заберёт лишнее с {n_sweep} групп(ы) в техкассы."
    elif n_sweep:
        summary = f"На следующей проверке заберёт лишнее с {n_sweep} групп(ы) в техкассы."
    elif n_top:
        summary = f"На следующей проверке дольёт {n_top} групп(ы)."
    elif n_watch:
        summary = "Баланс групп выше цели. Сбор ждёт короткую выдержку — потом в техкассы."
    elif not items:
        summary = "Групп под Никой нет."
    else:
        summary = "Баланс групп в зоне. Следующая проверка ничего не двинет."

    return {
        "mode": "dry" if dry else "live",
        "summary": summary,
        "items": items,
    }


async def pulse() -> Dict[str, Any]:
    """Короткий снимок для красной полосы. Без движения денег."""
    await _ensure()
    from nika import incidents as inc
    from nika.policy import SOURCE_LADDER, dead_zone
    from nika.store import fetch_settings, policy_from_row, queued_command_stats

    async with db.pool.acquire() as conn:
        settings = await fetch_settings(conn) or {}
        groups = await conn.fetch(
            """
            SELECT s.*, COALESCE(c.chatbalance, 0)::bigint AS balance,
                   c.namechat, c.usernamechat, c.chatlink
            FROM nika_group_settings s
            LEFT JOIN chat c ON c.chat_id = s.chat_id
            ORDER BY s.enabled DESC, s.chat_id
            """
        )
        ladder_ids = [int(cid) for cid, _ in SOURCE_LADDER]
        ladder_rows = await conn.fetch(
            """
            SELECT chat_id, COALESCE(chatbalance, 0)::bigint AS balance
            FROM chat
            WHERE chat_id = ANY($1::bigint[])
            """,
            ladder_ids,
        )
        balances = {int(r["chat_id"]): _as_int(r["balance"]) for r in ladder_rows}
        open_rows = await inc.list_open(conn, limit=20)
        open_critical = await inc.count_open_critical(conn)
        cmd_stats = await queued_command_stats(conn)

    starving: List[Dict[str, Any]] = []
    group_out: List[Dict[str, Any]] = []
    for raw in groups:
        row = dict(raw)
        balance = _as_int(row["balance"])
        target = _as_int(row["target_balance"])
        enabled = bool(row["enabled"])
        dry = enabled and target > 0 and balance <= 0
        item = {
            "chatId": int(row["chat_id"]),
            "name": row["namechat"] or str(row["chat_id"]),
            "username": row.get("usernamechat") or "",
            "link": row.get("chatlink") or "",
            "balance": balance,
            "target": target,
            "gap": target - balance,
            "enabled": enabled,
            "starving": dry,
            "speedMode": row["speed_mode"] or "auto",
        }
        group_out.append(item)
        if dry:
            starving.append(item)

    ladder = [
        {
            "chatId": int(cid),
            "title": title,
            "balance": _as_int(balances.get(int(cid), 0)),
        }
        for cid, title in SOURCE_LADDER
    ]
    ladder_empty = all(int(x["balance"]) <= 0 for x in ladder) if ladder else True
    needy = []
    for row in groups:
        if not row["enabled"]:
            continue
        policy = policy_from_row(row)
        gap = policy.target_balance - _as_int(row["balance"])
        if policy.target_balance > 0 and gap > dead_zone(policy):
            needy.append(int(row["chat_id"]))

    last_tick = settings.get("last_tick_at")
    stale_worker = False
    if settings.get("enabled"):
        if last_tick is None:
            stale_worker = True
        else:
            now = datetime.now(timezone.utc)
            tick_at = last_tick
            if tick_at.tzinfo is None:
                tick_at = tick_at.replace(tzinfo=timezone.utc)
            stale_worker = (now - tick_at).total_seconds() > max(
                WORKER_STALE_SEC, _as_int(settings.get("tick_interval_sec"), 180) * 3
            )

    crisis = bool(
        open_critical > 0
        or starving
        or (ladder_empty and needy)
        or stale_worker
        or _as_int(cmd_stats.get("stale")) > 0
    )
    headline = ""
    detail = ""
    if starving:
        names = ", ".join(g["name"] for g in starving[:3])
        headline = "НЕТ КУТ у групп под Никой"
        detail = f"{len(starving)} групп(ы) с нулём: {names}."
        if ladder_empty:
            detail += " В играх и кассах тоже пусто — доливать не из чего."
    elif ladder_empty and needy:
        headline = "Доливать баланс групп не из чего"
        detail = "В играх и кассах пусто, а баланс групп уже ниже цели."
    elif open_critical:
        first = open_rows[0] if open_rows else None
        headline = (first or {}).get("title") or "Ника не смогла починить ошибку"
        detail = (first or {}).get("body") or ""
    elif stale_worker:
        headline = "Ника молчит"
        detail = "Бот не проводит проверки. Команды и долив стоят, пока процесс не оживёт."
    elif _as_int(cmd_stats.get("stale")) > 0:
        headline = "Команды Ники зависли"
        detail = "Админка отправила действие боту, а он его не забрал."

    return {
        "crisis": crisis,
        "headline": headline,
        "detail": detail[:500],
        "openCritical": int(open_critical),
        "starvingCount": len(starving),
        "starving": starving,
        "ladderEmpty": ladder_empty,
        "staleWorker": stale_worker,
        "enabled": bool(settings.get("enabled")),
        "dryRun": bool(settings.get("dry_run")),
        "lastTickAt": _jsonable(last_tick),
        "lastError": settings.get("last_error") or "",
        "commands": cmd_stats,
        "incidents": [_incident_out(r) for r in open_rows],
        "groups": group_out,
        "ladder": ladder,
        "forecast": forecast_tick(settings, groups, group_out, ladder),
        "tickIntervalSec": _as_int(settings.get("tick_interval_sec"), 20),
        "sweepSpeed": str(settings.get("sweep_speed") or "fast"),
    }


async def overview() -> Dict[str, Any]:
    await _ensure()
    from nika import incidents as inc
    from nika.policy import (
        SPEED_MODES,
        SWEEP_DEST_CHAT_ID,
        SWEEP_DEST_LADDER,
        SWEEP_SPEEDS,
        suggest_caps,
        sweep_speed_preset,
    )
    from nika.schema import FIRST_MANAGED_CHAT_ID, FIRST_MANAGED_TARGET
    from nika.store import fetch_settings

    snap = await pulse()
    async with db.pool.acquire() as conn:
        settings = await fetch_settings(conn) or {}
        recent = await inc.list_recent(conn, limit=40)
        transfers = await conn.fetch(
            """
            SELECT t.*,
                   sc.namechat AS source_name,
                   sc.usernamechat AS source_username,
                   dc.namechat AS dest_name,
                   dc.usernamechat AS dest_username
            FROM nika_transfer_log t
            LEFT JOIN chat sc ON sc.chat_id = t.source_chat_id
            LEFT JOIN chat dc ON dc.chat_id = t.dest_chat_id
            ORDER BY t.created_at DESC
            LIMIT 60
            """
        )
        commands = await conn.fetch(
            """
            SELECT id, kind, payload, status, requested_by, error, result,
                   created_at, started_at, finished_at
            FROM nika_operator_commands
            ORDER BY created_at DESC
            LIMIT 30
            """
        )
        try:
            universe = await _universe_now(conn)
        except Exception as exc:
            log.warning("nika universe: %s: %s", type(exc).__name__, exc)
            universe = {}

    return {
        **snap,
        "universe": universe,
        "settings": {
            "enabled": bool(settings.get("enabled")),
            "dryRun": bool(settings.get("dry_run")),
            "tickIntervalSec": _as_int(settings.get("tick_interval_sec"), 20),
            "sweepSpeed": str(settings.get("sweep_speed") or "fast"),
            "sweepPreset": sweep_speed_preset(settings.get("sweep_speed")),
            "ownerAlertUserId": settings.get("owner_alert_user_id"),
            "lastError": settings.get("last_error") or "",
            "lastErrorAt": _jsonable(settings.get("last_error_at")),
            "healOkStreak": _as_int(settings.get("heal_ok_streak")),
            "earningsSince": _jsonable(settings.get("earnings_since")),
            "updatedAt": _jsonable(settings.get("updated_at")),
        },
        "meta": {
            "officialChatId": int(FIRST_MANAGED_CHAT_ID),
            "officialTarget": int(FIRST_MANAGED_TARGET),
            "sweepDestChatId": int(SWEEP_DEST_CHAT_ID),
            "sweepDestLadder": [
                {"chatId": int(cid), "title": title} for cid, title in SWEEP_DEST_LADDER
            ],
            "speedModes": list(SPEED_MODES),
            "sweepSpeeds": list(SWEEP_SPEEDS),
            "sweepPreset": sweep_speed_preset(settings.get("sweep_speed")),
            "forbiddenChatIds": _forbidden(),
            "suggestCaps": suggest_caps(FIRST_MANAGED_TARGET),
        },
        "incidentArchive": [_incident_out(r) for r in recent],
        "transfers": [_transfer_out(dict(r)) for r in transfers],
        "commandLog": [_command_out(dict(r)) for r in commands],
    }


def _transfer_out(row: Dict[str, Any]) -> Dict[str, Any]:
    kind = row.get("kind")
    sign = 1 if kind == "sweep" else (-1 if kind == "topup" else 0)
    return {
        "id": _as_int(row.get("id")),
        "kind": kind,
        "status": row.get("status"),
        "chatId": row.get("chat_id"),
        "sourceChatId": row.get("source_chat_id"),
        "sourceName": row.get("source_name") or "",
        "sourceUsername": row.get("source_username") or "",
        "destChatId": row.get("dest_chat_id"),
        "destName": row.get("dest_name") or "",
        "destUsername": row.get("dest_username") or "",
        "amount": _as_int(row.get("amount")),
        "sign": sign,
        "reason": row.get("reason") or "",
        "error": row.get("error") or "",
        "createdAt": _jsonable(row.get("created_at")),
        "finishedAt": _jsonable(row.get("finished_at")),
        "revertedAt": _jsonable(row.get("reverted_at")),
    }


def _command_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": _as_int(row.get("id")),
        "kind": row.get("kind"),
        "status": row.get("status"),
        "payload": _jsonable(row.get("payload") or {}),
        "requestedBy": row.get("requested_by"),
        "error": row.get("error") or "",
        "result": _jsonable(row.get("result") or {}),
        "createdAt": _jsonable(row.get("created_at")),
        "startedAt": _jsonable(row.get("started_at")),
        "finishedAt": _jsonable(row.get("finished_at")),
    }


async def earnings() -> Dict[str, Any]:
    """Журнал с момента запуска Ники — без фейковой истории до этой даты."""
    await _ensure()
    from nika.store import fetch_settings

    try:
        from nika.store import maybe_sample_universe

        await maybe_sample_universe(db)
    except Exception as exc:
        log.warning("nika earnings sample: %s: %s", type(exc).__name__, exc)

    async with db.pool.acquire() as conn:
        settings = await fetch_settings(conn) or {}
        since = settings.get("earnings_since") or settings.get("updated_at")
        if since is None:
            since = datetime.now(timezone.utc)
        moved = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE kind = 'sweep' AND status = 'done'), 0)::bigint AS swept,
                COALESCE(SUM(amount) FILTER (WHERE kind = 'topup' AND status = 'done'), 0)::bigint AS topped,
                COALESCE(SUM(amount) FILTER (WHERE kind = 'revert' AND status = 'done'), 0)::bigint AS reverted,
                COUNT(*) FILTER (WHERE status = 'done')::int AS moves
            FROM nika_transfer_log
            WHERE created_at >= $1
            """,
            since,
        )
        by_kind = await conn.fetch(
            """
            SELECT kind, COUNT(*)::int AS n, COALESCE(SUM(amount), 0)::bigint AS amount
            FROM nika_transfer_log
            WHERE created_at >= $1 AND status = 'done'
            GROUP BY kind
            ORDER BY kind
            """,
            since,
        )
        commission = None
        try:
            commission = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(commission), 0)::bigint AS commission,
                    COALESCE(SUM(to_project), 0)::bigint AS to_project,
                    COUNT(*)::int AS events
                FROM growth_fund_ledger
                WHERE created_at >= $1
                """,
                since,
            )
        except Exception as exc:
            log.warning("nika earnings ledger: %s: %s", type(exc).__name__, exc)

        now = datetime.now(timezone.utc)
        days = await _flow_bucket(conn, since, "day", until=now)
        hours_since = now - timedelta(hours=48)
        stamp = _aware(since)
        if stamp > hours_since:
            hours_since = stamp
        hours = await _flow_bucket(conn, hours_since, "hour", until=now)
        spark = []
        try:
            spark_rows = await conn.fetch(
                """
                SELECT created_at,
                       (users_balance + chats_balance)::bigint AS system,
                       users_balance, chats_balance, vault_balance
                FROM nika_universe_sample
                WHERE created_at >= $1
                ORDER BY created_at
                LIMIT 240
                """,
                _aware(since),
            )
            spark = [
                {
                    "t": _jsonable(r["created_at"]),
                    "system": _as_int(r["system"]),
                    "users": _as_int(r["users_balance"]),
                    "chats": _as_int(r["chats_balance"]),
                    "vault": _as_int(r["vault_balance"]),
                }
                for r in spark_rows
            ]
        except Exception as exc:
            log.warning("nika spark: %s: %s", type(exc).__name__, exc)
        try:
            universe = await _universe_now(conn)
        except Exception as exc:
            log.warning("nika universe: %s: %s", type(exc).__name__, exc)
            universe = {}

    swept = _as_int(moved["swept"] if moved else 0)
    topped = _as_int(moved["topped"] if moved else 0)
    games_plus = _as_int(commission["commission"]) if commission else 0
    plus = swept + games_plus
    minus = topped
    return {
        "since": _jsonable(since),
        "universe": universe,
        "nika": {
            "sweptToVault": swept,
            "toppedToTables": topped,
            "reverted": _as_int(moved["reverted"] if moved else 0),
            "moves": _as_int(moved["moves"] if moved else 0),
            "plus": plus,
            "minus": minus,
            "net": plus - minus,
            "byKind": [
                {"kind": r["kind"], "count": _as_int(r["n"]), "amount": _as_int(r["amount"])}
                for r in by_kind
            ],
        },
        "games": {
            "commission": games_plus,
            "toProject": _as_int(commission["to_project"]) if commission else 0,
            "events": _as_int(commission["events"]) if commission else 0,
        },
        "days": days,
        "hours": hours[-48:],
        "spark": spark,
        "extrema": _extrema(days),
        "hourExtrema": _extrema(hours[-48:]),
        "note": "Считается только с момента запуска Ники. Старую историю не подмешиваем.",
    }


async def search_candidates(query: str) -> List[Dict[str, Any]]:
    await _ensure()
    forbidden = _forbidden()
    q = (query or "").strip()
    if not q:
        return []
    async with db.pool.acquire() as conn:
        if q.lstrip("-").isdigit():
            rows = await conn.fetch(
                """
                SELECT chat_id, namechat, usernamechat, COALESCE(chatbalance, 0)::bigint AS balance,
                       COALESCE(is_technical, FALSE) AS is_technical
                FROM chat
                WHERE chat_id = $1
                LIMIT 1
                """,
                int(q),
            )
        else:
            like = f"%{q}%"
            rows = await conn.fetch(
                """
                SELECT chat_id, namechat, usernamechat, COALESCE(chatbalance, 0)::bigint AS balance,
                       COALESCE(is_technical, FALSE) AS is_technical
                FROM chat
                WHERE COALESCE(is_technical, FALSE) = FALSE
                  AND chat_id <> ALL($1::bigint[])
                  AND (
                        namechat ILIKE $2
                     OR lower(coalesce(usernamechat, '')) LIKE lower($2)
                  )
                ORDER BY chatbalance DESC NULLS LAST
                LIMIT 20
                """,
                forbidden,
                like,
            )
    out = []
    for row in rows:
        cid = int(row["chat_id"])
        tech = bool(row["is_technical"]) or cid in set(forbidden)
        out.append({
            "chatId": cid,
            "name": row["namechat"] or str(cid),
            "username": row["usernamechat"],
            "balance": _as_int(row["balance"]),
            "forbidden": tech,
        })
    return out


async def save_settings(
    *,
    enabled: Optional[bool] = None,
    dry_run: Optional[bool] = None,
    tick_interval_sec: Optional[int] = None,
    sweep_speed: Optional[str] = None,
) -> Dict[str, Any]:
    await _ensure()
    from nika.store import update_global_settings

    await update_global_settings(
        db,
        enabled=enabled,
        dry_run=dry_run,
        tick_interval_sec=tick_interval_sec,
        sweep_speed=sweep_speed,
    )
    return await pulse()


async def save_group(
    chat_id: int,
    *,
    target_balance: int,
    speed_mode: str = "auto",
    enabled: bool = True,
    note: Optional[str] = None,
    updated_by: Optional[int] = None,
) -> Dict[str, Any]:
    await _ensure()
    from nika.store import upsert_group

    ok = await upsert_group(
        db,
        int(chat_id),
        int(target_balance),
        speed_mode=speed_mode,
        enabled=enabled,
        updated_by=updated_by,
        note=note,
    )
    if not ok:
        return {"ok": False, "error": "Эту группу нельзя поставить под Нику — это техкошелёк."}
    return {"ok": True, "pulse": await pulse()}


async def drop_group(chat_id: int) -> Dict[str, Any]:
    await _ensure()
    from nika.store import remove_group

    ok = await remove_group(db, int(chat_id))
    return {"ok": ok, "pulse": await pulse()}


async def apply_action(
    *,
    action: str,
    admin_id: int,
    incident_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    transfer_id: Optional[int] = None,
    note: str = "",
) -> Dict[str, Any]:
    """Кнопка с карточки. Деньги — в очередь бота. Пауза — сразу."""
    await _ensure()
    from nika import incidents as inc
    from nika.store import (
        disable_group,
        disable_system,
        enable_group,
        enable_system,
        request_revert,
    )

    kind = str(action or "").strip()
    payload: Dict[str, Any] = {}
    if chat_id is not None:
        payload["chat_id"] = int(chat_id)
    if transfer_id is not None:
        payload["transfer_id"] = int(transfer_id)
    if incident_id is not None:
        payload["incident_id"] = int(incident_id)

    incident = None
    if incident_id is not None:
        async with db.pool.acquire() as conn:
            incident = await inc.fetch_by_id(conn, int(incident_id))
        if incident and chat_id is None and incident.get("chat_id") is not None:
            payload["chat_id"] = int(incident["chat_id"])
            chat_id = int(incident["chat_id"])
        if incident and transfer_id is None:
            raw = incident.get("payload") or {}
            if isinstance(raw, dict) and raw.get("log_id") is not None:
                payload["transfer_id"] = int(raw["log_id"])
                transfer_id = int(raw["log_id"])

    immediate = None
    queued_id = None

    if kind == "pause_all":
        await disable_system(db)
        immediate = "pause_all"
    elif kind == "enable_all":
        await enable_system(db)
        immediate = "enable_all"
    elif kind == "pause_group":
        if chat_id is None:
            return {"ok": False, "error": "Нет группы для паузы"}
        await disable_group(db, int(chat_id))
        immediate = "pause_group"
    elif kind == "enable_group":
        if chat_id is None:
            return {"ok": False, "error": "Нет группы"}
        await enable_group(db, int(chat_id))
        immediate = "enable_group"
    elif kind == "resolve":
        if incident_id is None:
            return {"ok": False, "error": "Нет инцидента"}
        async with db.pool.acquire() as conn:
            await inc.resolve_id(conn, int(incident_id), note=note or "закрыто из панели", by=admin_id)
        immediate = "resolve"
    elif kind == "ack":
        if incident_id is None:
            return {"ok": False, "error": "Нет инцидента"}
        async with db.pool.acquire() as conn:
            await inc.ack_id(conn, int(incident_id), by=admin_id)
        immediate = "ack"
    elif kind == "revert":
        if transfer_id is None:
            return {"ok": False, "error": "Нет перевода для возврата"}
        await request_revert(db, int(transfer_id), admin_id)
        async with db.pool.acquire() as conn:
            queued_id = await inc.enqueue_command(conn, "revert", payload, admin_id)
    elif kind in inc.COMMAND_KINDS:
        async with db.pool.acquire() as conn:
            queued_id = await inc.enqueue_command(conn, kind, payload, admin_id)
    else:
        return {"ok": False, "error": f"Неизвестное действие: {kind}"}

    return {
        "ok": True,
        "immediate": immediate,
        "queuedId": queued_id,
        "pulse": await pulse(),
    }
