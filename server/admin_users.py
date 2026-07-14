"""Admin: поиск игроков, профиль, модерация.

Действия админов логируются через admin_audit.log_admin_action (admin_audit_log,
видно в Security -> "Аудит действий") - здесь этого больше нет, чтобы не
дублировать одно и то же действие в две разные таблицы под разными именами."""

from __future__ import annotations

import json
from typing import Any

from db import db
from user_items import items_to_db, parse_items


def _safe_dict(value: Any) -> dict:
    """Безопасно преобразует JSONB/str/None в dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


async def is_user_banned(user_id: int) -> bool:
    row = await db.pool.fetchval(
        "SELECT banned FROM users WHERE user_id = $1",
        user_id,
    )
    return bool(row) if row is not None else False


async def search_users(query: str, *, limit: int = 20) -> list[dict]:
    raw = (query or "").strip()
    if not raw:
        return []

    limit = max(1, min(limit, 50))
    q = raw.lstrip("@")

    if q.isdigit():
        user_id = int(q)
        if user_id <= 0:
            return []
        row = await db.pool.fetchrow(
            """
            SELECT user_id, username, display_name, first_name, balance, banned, last_seen_at
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        return [_user_search_row(row)] if row else []

    if len(q) < 2:
        return []

    pattern = f"%{q}%"
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, display_name, first_name, balance, banned, last_seen_at
        FROM users
        WHERE username ILIKE $1
           OR display_name ILIKE $1
           OR first_name ILIKE $1
        ORDER BY user_id
        LIMIT $2
        """,
        pattern,
        limit,
    )
    return [_user_search_row(r) for r in rows]


def _user_search_row(row) -> dict:
    name = row["display_name"] or row["first_name"] or str(row["user_id"])
    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "displayName": name,
        "balance": int(row["balance"] or 0),
        "banned": bool(row["banned"]),
        "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
    }


async def get_user_admin_profile(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name, last_name, display_name, photo_url,
               balance, banned, banned_at, banned_reason, last_seen_at,
               onboarding_done, onboarding_active, onboarding_step,
               onboarding_seed_granted, onboarding_demo_logs,
               market_sales_count, market_items_sold
        FROM users WHERE user_id = $1
        """,
        user_id,
    )
    if not row:
        return None

    farm = await db.get_farm_state(user_id)
    inventory = await db.get_inventory_state(user_id)

    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "displayName": row["display_name"] or row["first_name"] or str(row["user_id"]),
        "photoUrl": row["photo_url"],
        "balance": int(row["balance"] or 0),
        "banned": bool(row["banned"]),
        "bannedAt": row["banned_at"].isoformat() if row["banned_at"] else None,
        "bannedReason": row["banned_reason"],
        "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
        "onboarding": {
            "done": bool(row["onboarding_done"]),
            "active": bool(row["onboarding_active"]),
            "step": int(row["onboarding_step"] or 0),
            "seedGranted": int(row["onboarding_seed_granted"] or 0),
            "demoLogs": int(row["onboarding_demo_logs"] or 0),
        },
        "marketSalesCount": int(row["market_sales_count"] or 0),
        "marketItemsSold": int(row["market_items_sold"] or 0),
        "ownedPlots": farm.get("ownedPlots", 0),
        "maxPlots": farm.get("maxPlots", 8),
        "plots": farm.get("plots", []),
        "inventory": inventory.get("items", []),
        "kut": farm.get("kut", 0),
    }


async def get_user_audit_history(user_id: int, *, limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    total = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM audit_events WHERE user_id = $1",
        user_id,
    )
    rows = await db.pool.fetch(
        """
        SELECT id, created_at, event_type, amount, balance_before, balance_after, details
        FROM audit_events
        WHERE user_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )

    events = []
    for row in rows:
        details = row["details"]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = {}
        events.append(
            {
                "id": int(row["id"]),
                "createdAt": row["created_at"].isoformat(),
                "eventType": row["event_type"],
                "amount": row["amount"],
                "balanceBefore": row["balance_before"],
                "balanceAfter": row["balance_after"],
                "details": details if isinstance(details, dict) else {},
            }
        )

    return {"events": events, "total": int(total or 0), "limit": limit, "offset": offset}


async def admin_adjust_balance(
    user_id: int,
    delta: int,
    *,
    admin_user_id: int,
    note: str = "",
    notify_player: bool = True,
) -> dict:
    if delta == 0:
        raise ValueError("Изменение баланса не может быть 0")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            before = await conn.fetchval(
                "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if before is None:
                raise ValueError("Игрок не найден")

            before = int(before)
            after = before + delta
            if after < 0:
                raise ValueError("Баланс не может быть отрицательным")

            await conn.execute(
                "UPDATE users SET balance = $2 WHERE user_id = $1",
                user_id,
                after,
            )

    if note.strip() and notify_player:
        from admin_player_notify import notify_balance_adjustment

        notify_balance_adjustment(
            user_id,
            delta=delta,
            balance_after=after,
            note=note.strip(),
        )

    return {"balance": after, "delta": delta}


async def admin_adjust_item(
    user_id: int,
    item_id: str,
    delta: int,
    *,
    admin_user_id: int,
    note: str = "",
) -> dict:
    item_id = (item_id or "").strip()
    if not item_id:
        raise ValueError("Укажите item_id")
    if delta == 0:
        raise ValueError("Изменение количества не может быть 0")

    from dex_catalog import dex_catalog
    from user_items import add_shop_item_to_storage, count_item_in_storage, take_item_from_storage

    item_id = dex_catalog.canonical_key(item_id)

    count_after = 0
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            raw = await conn.fetchval(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if raw is None:
                raise ValueError("Игрок не найден")

            parsed = parse_items(raw)

            if delta > 0:
                updated_items = add_shop_item_to_storage(parsed, item_id, delta)
            else:
                updated_items = take_item_from_storage(parsed, item_id, -delta)

            count_after = int(count_item_in_storage(updated_items, item_id))

            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                user_id,
                items_to_db(updated_items),
            )

    if note.strip():
        from admin_player_notify import notify_item_adjustment

        entry = dex_catalog.get(item_id)
        notify_item_adjustment(
            user_id,
            item_name=entry.name if entry else item_id,
            emoji=entry.emoji if entry else "📦",
            delta=delta,
            count_after=int(count_after),
            note=note.strip(),
        )

    return {"itemId": item_id, "delta": delta, "countAfter": int(count_after)}


async def admin_set_banned(
    user_id: int,
    banned: bool,
    *,
    admin_user_id: int,
    reason: str = "",
    notify: bool = True,
) -> dict:
    async with db.pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT user_id FROM users WHERE user_id = $1",
            user_id,
        )
        if exists is None:
            raise ValueError("Игрок не найден")

        reason_clean = reason.strip() or None
        await conn.execute(
            """
            UPDATE users
            SET banned = $2,
                banned_at = CASE WHEN $2 THEN NOW() ELSE NULL END,
                banned_reason = CASE WHEN $2 THEN $3 ELSE NULL END,
                last_seen_at = CASE WHEN $2 THEN NULL ELSE last_seen_at END
            WHERE user_id = $1
            """,
            user_id,
            banned,
            reason_clean,
        )

    if notify:
        from admin_player_notify import notify_banned, notify_unbanned

        if banned:
            notify_banned(user_id, reason=reason_clean or "")
        else:
            notify_unbanned(user_id)

    from rate_limit import invalidate_ban_cache
    invalidate_ban_cache(user_id)

    import asyncio
    from admin_ws import broadcast_to_admins
    asyncio.create_task(broadcast_to_admins({
        "event": "new_moderation_log",
        "data": {
            "actionType": "ban" if banned else "unban",
            "targetId": user_id,
            "reason": reason_clean or "",
            "adminId": admin_user_id,
        },
    }))

    return {"banned": banned, "reason": reason_clean}


async def admin_reset_onboarding(user_id: int, *, admin_user_id: int) -> dict:
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval(
                "SELECT user_id FROM users WHERE user_id = $1",
                user_id,
            )
            if exists is None:
                raise ValueError("Игрок не найден")

            await conn.execute(
                """
                UPDATE users
                SET onboarding_done = FALSE,
                    onboarding_active = FALSE,
                    onboarding_seed_granted = 0,
                    onboarding_demo_logs = 0,
                    onboarding_step = 0
                WHERE user_id = $1
                """,
                user_id,
            )
            await conn.execute(
                """
                UPDATE farm_plots
                SET status = 'EMPTY',
                    planted_at = NULL,
                    ripe_at = NULL,
                    dry_at = NULL,
                    needs_water = FALSE,
                    wilt_at = NULL,
                    waters_remaining = 0,
                    crop_id = NULL
                WHERE user_id = $1 AND plot_id = 1
                """,
                user_id,
            )

    from admin_player_notify import notify_onboarding_reset

    notify_onboarding_reset(user_id)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Квест-прогресс игрока
# ---------------------------------------------------------------------------

async def get_player_quest_info(user_id: int) -> dict:
    """Текущий квест-прогресс игрока + история из game_events."""
    import logging as _logging
    _log = _logging.getLogger("admin_users.quests")

    from quest_progress import parse_progress_store, _period_timer
    from quest_registry import quest_by_key

    raw = await db.pool.fetchval(
        "SELECT quest_progress FROM users WHERE user_id = $1",
        user_id,
    )
    _log.debug("quest_progress raw for %s: %r", user_id, raw)
    store = parse_progress_store(raw)
    _log.debug("parsed store for %s: %r", user_id, store)

    # Текущее состояние по периодам
    periods_info = []
    for period, bucket in store.items():
        active_quests = bucket.get("activeQuests") or []
        progress_dict = bucket.get("progress") or {}
        claimed = bucket.get("claimed") or []
        ends_ms, remaining = _period_timer(period) if active_quests else (None, None)

        # Показываем все активные квесты периода
        active_info = []
        for entry in active_quests:
            quest_id = entry.get("questId")
            quest = quest_by_key(str(quest_id)) if quest_id else None
            raw_prog = progress_dict.get(str(quest_id), 0) if quest_id else 0
            try:
                current = int(raw_prog) if raw_prog is not None else 0
            except (TypeError, ValueError):
                _log.warning("quest progress not int: %r for quest %s user %s", raw_prog, quest_id, user_id)
                current = 0
            active_info.append({
                "questId": quest_id,
                "questTitle": quest.title if quest else None,
                "questTarget": quest.target if quest else None,
                "questAction": quest.action if quest else None,
                "currentProgress": current,
                "acceptedAt": entry.get("acceptedAt"),
            })

        # Для обратной совместимости с фронтом — первый активный квест
        first = active_info[0] if active_info else {}

        periods_info.append({
            "period": period,
            "acceptedQuestId": first.get("questId"),
            "acceptedAt": first.get("acceptedAt"),
            "questTitle": first.get("questTitle"),
            "questTarget": first.get("questTarget"),
            "questAction": first.get("questAction"),
            "currentProgress": first.get("currentProgress", 0),
            "timerRemainingSeconds": remaining,
            "claimedCount": len(claimed),
            "allProgress": progress_dict,
            "activeQuests": active_info,
        })

    # История из game_events
    history_rows = await db.pool.fetch(
        """
        SELECT event_type, details, created_at
        FROM game_events
        WHERE user_id = $1 AND event_type IN ('quest_accept', 'quest_complete')
        ORDER BY created_at DESC
        LIMIT 50
        """,
        user_id,
    )
    history = []
    for r in history_rows:
        try:
            details = _safe_dict(r["details"])
            history.append({
                "eventType": r["event_type"],
                "questId": details.get("quest_id"),
                "period": details.get("period"),
                "createdAt": r["created_at"].isoformat(),
            })
        except Exception as e:
            _log.warning("quest history row error: %s row=%r", e, dict(r))

    return {"periods": periods_info, "history": history}


# ---------------------------------------------------------------------------
# История банов
# ---------------------------------------------------------------------------

async def get_player_ban_history(user_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, created_at, event_type, details
        FROM audit_events
        WHERE user_id = $1 AND event_type IN ('admin_ban', 'admin_unban')
        ORDER BY created_at DESC
        LIMIT 100
        """,
        user_id,
    )
    result = []
    for r in rows:
        details = r["details"] or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        result.append({
            "id": int(r["id"]),
            "action": "ban" if r["event_type"] == "admin_ban" else "unban",
            "reason": details.get("reason"),
            "adminUserId": details.get("admin_user_id"),
            "createdAt": r["created_at"].isoformat(),
        })
    return result


# ---------------------------------------------------------------------------
# Заметки администраторов
# ---------------------------------------------------------------------------

async def list_player_notes(player_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, admin_user_id, text, created_at, updated_at
        FROM player_admin_notes
        WHERE player_id = $1
        ORDER BY created_at DESC
        """,
        player_id,
    )
    return [
        {
            "id": int(r["id"]),
            "adminUserId": int(r["admin_user_id"]),
            "text": r["text"],
            "createdAt": r["created_at"].isoformat(),
            "updatedAt": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def upsert_player_note(
    player_id: int,
    text: str,
    *,
    admin_user_id: int,
    note_id: int | None = None,
) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Текст заметки не может быть пустым")
    if len(text) > 2000:
        raise ValueError("Максимум 2000 символов")

    if note_id:
        row = await db.pool.fetchrow(
            """
            UPDATE player_admin_notes
            SET text = $3, updated_at = NOW()
            WHERE id = $1 AND player_id = $2
            RETURNING id, admin_user_id, text, created_at, updated_at
            """,
            note_id,
            player_id,
            text,
        )
        if not row:
            raise ValueError("Заметка не найдена")
    else:
        row = await db.pool.fetchrow(
            """
            INSERT INTO player_admin_notes (player_id, admin_user_id, text)
            VALUES ($1, $2, $3)
            RETURNING id, admin_user_id, text, created_at, updated_at
            """,
            player_id,
            admin_user_id,
            text,
        )

    return {
        "id": int(row["id"]),
        "adminUserId": int(row["admin_user_id"]),
        "text": row["text"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
    }


async def delete_player_note(player_id: int, note_id: int, *, admin_user_id: int) -> None:
    deleted = await db.pool.fetchval(
        "DELETE FROM player_admin_notes WHERE id = $1 AND player_id = $2 RETURNING id",
        note_id,
        player_id,
    )
    if not deleted:
        raise ValueError("Заметка не найдена")


# ---------------------------------------------------------------------------
# Экспорт профиля
# ---------------------------------------------------------------------------

async def export_player_profile(user_id: int) -> dict:
    """Полные данные игрока для экспорта в JSON."""
    profile = await get_user_admin_profile(user_id)
    if not profile:
        raise ValueError("Игрок не найден")

    audit_data = await get_user_audit_history(user_id, limit=200)
    quest_info = await get_player_quest_info(user_id)
    ban_history = await get_player_ban_history(user_id)
    notes = await list_player_notes(user_id)

    game_events_rows = await db.pool.fetch(
        """
        SELECT event_type, details, created_at
        FROM game_events WHERE user_id = $1
        ORDER BY created_at DESC LIMIT 500
        """,
        user_id,
    )

    return {
        "exportedAt": None,  # filled by route
        "profile": profile,
        "auditHistory": audit_data["events"],
        "questInfo": quest_info,
        "banHistory": ban_history,
        "adminNotes": notes,
        "gameEvents": [
            {
                "eventType": r["event_type"],
                "details": _safe_dict(r["details"]),
                "createdAt": r["created_at"].isoformat(),
            }
            for r in game_events_rows
        ],
    }


async def get_player_inventory(user_id: int) -> list[dict]:
    """
    Инвентарь игрока из users.items.
    В базе друга ключи — это названия предметов ("Геймпад": 3).
    Джойним с dex.name чтобы получить emoji.
    """
    row = await db.pool.fetchrow(
        "SELECT items FROM users WHERE user_id = $1",
        user_id,
    )
    if not row:
        raise ValueError("Игрок не найден")

    from json_db_codec import decode_json_payload
    items = decode_json_payload(row["items"])
    if not items:
        return []

    keys = list(items.keys())

    # Пробуем джойн по name (база друга: ключи = названия)
    dex_by_name = {}
    try:
        dex_rows = await db.pool.fetch(
            "SELECT name, emoji FROM dex WHERE name = ANY($1::text[])",
            keys,
        )
        dex_by_name = {r["name"]: r["emoji"] for r in dex_rows}
    except Exception:
        pass

    # Пробуем джойн по id (наша база: ключи = числовые ID)
    dex_by_id = {}
    try:
        dex_rows_id = await db.pool.fetch(
            "SELECT id::text AS item_id, name, emoji FROM dex WHERE id::text = ANY($1::text[])",
            keys,
        )
        dex_by_id = {r["item_id"]: {"name": r["name"], "emoji": r["emoji"]} for r in dex_rows_id}
    except Exception:
        pass

    result = []
    for key, count in sorted(items.items(), key=lambda x: -x[1]):
        # Ключ — название предмета
        if key in dex_by_name:
            result.append({
                "itemId": key,
                "count": count,
                "name": key,
                "emoji": dex_by_name[key] or "📦",
            })
        # Ключ — числовой ID
        elif key in dex_by_id:
            info = dex_by_id[key]
            result.append({
                "itemId": key,
                "count": count,
                "name": info["name"] or key,
                "emoji": info["emoji"] or "📦",
            })
        # Неизвестный ключ — показываем как есть
        else:
            result.append({
                "itemId": key,
                "count": count,
                "name": key,
                "emoji": "📦",
            })
    return result
