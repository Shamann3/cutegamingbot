"""Admin: поиск игроков, профиль, модерация.

Действия админов логируются через admin_audit.log_admin_action (admin_audit_log,
видно в Security -> "Аудит действий") - здесь этого больше нет, чтобы не
дублировать одно и то же действие в две разные таблицы под разными именами."""

from __future__ import annotations

import json
from typing import Any

from db import db
from user_items import items_to_db, parse_items
from admin_db import get_admin_account


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
    if bool(row):
        return True
    try:
        in_banusers = await db.pool.fetchval(
            "SELECT 1 FROM banusers WHERE user_id = $1",
            user_id,
        )
        return bool(in_banusers)
    except Exception:
        return False


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
        row = await conn.fetchrow(
            """
            SELECT user_id, username, first_name, display_name
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        if row is None:
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

        # Зеркало в banusers — именно его проверяет игровой бот (is_user_banned)
        try:
            if banned:
                uname = (row["username"] or "").lstrip("@") or None
                name = (row["first_name"] or row["display_name"] or str(user_id))
                exists_ban = await conn.fetchval(
                    "SELECT 1 FROM banusers WHERE user_id = $1", user_id,
                )
                if exists_ban:
                    await conn.execute(
                        """
                        UPDATE banusers
                        SET username = COALESCE($2, username),
                            name = COALESCE($3, name),
                            data = NOW(),
                            cause = COALESCE($4, cause)
                        WHERE user_id = $1
                        """,
                        user_id, uname, name, reason_clean or "Бан в боте",
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO banusers (user_id, username, name, data, cause)
                        VALUES ($1, $2, $3, NOW(), $4)
                        """,
                        user_id, uname, name, reason_clean or "Бан в боте",
                    )
            else:
                await conn.execute("DELETE FROM banusers WHERE user_id = $1", user_id)
        except Exception:
            # Не откатываем users.banned — WebApp-блок уже выставлен
            pass

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
        SELECT
            n.id,
            n.admin_user_id,
            n.text,
            n.created_at,
            n.updated_at,
            a.first_name AS admin_first_name,
            a.username AS admin_username
        FROM player_admin_notes n
        LEFT JOIN LATERAL (
            SELECT first_name, username
            FROM admin_accounts
            WHERE user_id = n.admin_user_id
            ORDER BY registered_at DESC NULLS LAST
            LIMIT 1
        ) a ON TRUE
        WHERE n.player_id = $1
        ORDER BY n.created_at DESC
        """,
        player_id,
    )
    return [_serialize_player_note(r) for r in rows]


def _admin_display_name(first_name, username, user_id: int) -> str:
    name = (first_name or "").strip()
    if name:
        return name
    un = (username or "").strip().lstrip("@")
    if un:
        return f"@{un}"
    return f"#{int(user_id)}"


def _serialize_player_note(row) -> dict:
    admin_id = int(row["admin_user_id"])
    first_name = row["admin_first_name"] if "admin_first_name" in row.keys() else None
    username = row["admin_username"] if "admin_username" in row.keys() else None
    return {
        "id": int(row["id"]),
        "adminUserId": admin_id,
        "adminName": _admin_display_name(first_name, username, admin_id),
        "text": row["text"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
    }


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

    acc = await get_admin_account(int(row["admin_user_id"]))
    payload = dict(row)
    payload["admin_first_name"] = (acc or {}).get("first_name")
    payload["admin_username"] = (acc or {}).get("username")
    return _serialize_player_note(payload)


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


def _amount_thresholds(balance: int, lifetime_in: int = 0) -> dict:
    """Пороги «крупности» суммы относительно богатства игрока."""
    wealth = max(int(balance or 0), int(lifetime_in or 0) // 8, 100)
    notable = max(50, int(wealth * 0.05))
    large = max(notable * 3, int(wealth * 0.12))
    huge = max(large * 2, int(wealth * 0.25))
    return {"notable": notable, "large": large, "huge": huge, "wealth": wealth}


def _classify_amount(amount: int, thresholds: dict) -> str:
    a = abs(int(amount or 0))
    if a >= thresholds["huge"]:
        return "huge"
    if a >= thresholds["large"]:
        return "large"
    if a >= thresholds["notable"]:
        return "notable"
    return "small"


async def get_user_intel(user_id: int, *, is_owner: bool = False) -> dict | None:
    """Полная аналитика игрока: активность в группах, переводы, крупные суммы."""
    profile = await get_user_admin_profile(user_id)
    if not profile:
        return None

    balance = int(profile.get("balance") or 0)

    economy = {
        "balance": balance,
        "donateLifetime": 0,
        "canWithdrawal": 0,
        "wins": 0,
        "losses": 0,
        "winAmount": 0,
        "transferLimit": None,
    }
    try:
        row = await db.pool.fetchrow(
            """
            SELECT donate, canwithdrawal, wins, loose, winamount, give
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        if row:
            economy["donateLifetime"] = int(row["donate"] or 0)
            economy["canWithdrawal"] = int(row["canwithdrawal"] or 0)
            economy["wins"] = int(row["wins"] or 0)
            economy["losses"] = int(row["loose"] or 0)
            economy["winAmount"] = int(row["winamount"] or 0)
            economy["transferLimit"] = int(row["give"]) if row["give"] is not None else None
    except Exception:
        pass

    donate_journal = {"count": 0, "total": 0}
    try:
        d = await db.pool.fetchrow(
            """
            SELECT COUNT(*)::int AS n, COALESCE(SUM(count), 0)::bigint AS total
            FROM donate WHERE user_id = $1
            """,
            user_id,
        )
        if d:
            donate_journal = {"count": int(d["n"] or 0), "total": int(d["total"] or 0)}
    except Exception:
        pass

    activity_by_chat: list[dict] = []
    total_messages = 0
    try:
        rows = await db.pool.fetch(
            """
            SELECT c.chat_id,
                   COALESCE(MAX(ch.namechat), c.chat_id::text) AS chat_name,
                   COALESCE(MAX(ch.usernamechat), '') AS chat_username,
                   COALESCE(SUM(c.text::bigint), 0)::bigint AS messages
            FROM chatchange c
            LEFT JOIN chat ch ON ch.chat_id = c.chat_id
            WHERE c.user_id = $1
              AND c.date >= (CURRENT_DATE - 29)
            GROUP BY c.chat_id
            ORDER BY messages DESC
            LIMIT 40
            """,
            user_id,
        )
        for r in rows:
            msgs = int(r["messages"] or 0)
            total_messages += msgs
            activity_by_chat.append(
                {
                    "chatId": int(r["chat_id"]),
                    "chatName": r["chat_name"] or str(r["chat_id"]),
                    "chatUsername": r["chat_username"] or None,
                    "messages": msgs,
                }
            )
    except Exception:
        activity_by_chat = []
        total_messages = 0

    most_active = activity_by_chat[0] if activity_by_chat else None

    engagement = await _build_engagement_stats(user_id, profile=profile)

    p2p = {
        "sentCount": 0,
        "sentSum": 0,
        "recvCount": 0,
        "recvSum": 0,
        "recent": [],
    }
    try:
        agg = await db.pool.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE sender_id = $1)::int AS sent_n,
              COALESCE(SUM(amount) FILTER (WHERE sender_id = $1), 0)::bigint AS sent_sum,
              COUNT(*) FILTER (WHERE receiver_id = $1)::int AS recv_n,
              COALESCE(SUM(amount) FILTER (WHERE receiver_id = $1), 0)::bigint AS recv_sum
            FROM p2p_transfers
            WHERE sender_id = $1 OR receiver_id = $1
            """,
            user_id,
        )
        if agg:
            p2p["sentCount"] = int(agg["sent_n"] or 0)
            p2p["sentSum"] = int(agg["sent_sum"] or 0)
            p2p["recvCount"] = int(agg["recv_n"] or 0)
            p2p["recvSum"] = int(agg["recv_sum"] or 0)

        trows = await db.pool.fetch(
            """
            SELECT t.id, t.sender_id, t.receiver_id, t.amount, t.cause, t.created_at,
                   su.username AS sender_username,
                   COALESCE(su.display_name, su.first_name) AS sender_name,
                   ru.username AS receiver_username,
                   COALESCE(ru.display_name, ru.first_name) AS receiver_name
            FROM p2p_transfers t
            LEFT JOIN users su ON su.user_id = t.sender_id
            LEFT JOIN users ru ON ru.user_id = t.receiver_id
            WHERE t.sender_id = $1 OR t.receiver_id = $1
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT 40
            """,
            user_id,
        )
        for t in trows:
            direction = "out" if int(t["sender_id"]) == user_id else "in"
            cp_id = int(t["receiver_id"] if direction == "out" else t["sender_id"])
            p2p["recent"].append(
                {
                    "id": int(t["id"]),
                    "direction": direction,
                    "amount": int(t["amount"] or 0),
                    "cause": t["cause"] or "",
                    "createdAt": t["created_at"].isoformat() if t["created_at"] else None,
                    "counterparty": {
                        "userId": cp_id,
                        "name": (t["receiver_name"] if direction == "out" else t["sender_name"])
                        or str(cp_id),
                        "username": t["receiver_username"]
                        if direction == "out"
                        else t["sender_username"],
                    },
                }
            )
    except Exception:
        pass

    lifetime_in = p2p["recvSum"] + donate_journal["total"] + economy["donateLifetime"]
    thresholds = _amount_thresholds(balance, lifetime_in)

    significant_moves: list[dict] = []
    try:
        crow = await db.pool.fetch(
            """
            SELECT id, "+" AS plus, "-" AS minus, cause, balance, transfer_id, chat_id, data
            FROM cutehistory
            WHERE user_id = $1
            ORDER BY id DESC
            LIMIT 120
            """,
            user_id,
        )
        for r in crow:
            plus = int(r["plus"] or 0)
            minus = int(r["minus"] or 0)
            direction = "in" if plus else "out"
            amount = plus if direction == "in" else minus
            level = _classify_amount(amount, thresholds)
            if level == "small":
                continue
            significant_moves.append(
                {
                    "id": int(r["id"]),
                    "direction": direction,
                    "amount": amount,
                    "cause": r["cause"] or "",
                    "balanceAfter": int(r["balance"]) if r["balance"] is not None else None,
                    "level": level,
                    "isTransfer": r["transfer_id"] is not None,
                    "chatId": int(r["chat_id"]) if r["chat_id"] is not None else None,
                    "when": r["data"],
                }
            )
            if len(significant_moves) >= 25:
                break
    except Exception:
        significant_moves = []

    for item in p2p["recent"]:
        item["level"] = _classify_amount(item["amount"], thresholds)

    item_trades = 0
    try:
        item_trades = int(
            await db.pool.fetchval(
                """
                SELECT COUNT(*)::int FROM cutehistory
                WHERE user_id = $1 AND cause = 'передача предметов'
                """,
                user_id,
            )
            or 0
        )
    except Exception:
        item_trades = 0

    cute_preview = {"total": 0, "items": [], "donations": donate_journal}
    try:
        from admin_cute_history import get_user_cute_history

        cute_preview = await get_user_cute_history(user_id, limit=25, offset=0)
        if isinstance(cute_preview, dict):
            cute_preview["donations"] = cute_preview.get("donations") or donate_journal
            for it in cute_preview.get("items") or []:
                it["level"] = _classify_amount(it.get("amount") or 0, thresholds)
    except Exception:
        cute_preview = {"total": 0, "items": [], "donations": donate_journal}

    quests = None
    try:
        quests = await get_player_quest_info(user_id)
    except Exception:
        quests = None

    bans = []
    try:
        bans = await get_player_ban_history(user_id)
    except Exception:
        bans = []

    notes = []
    try:
        notes = await list_player_notes(user_id)
    except Exception:
        notes = []

    dossier = await _build_user_dossier(user_id, is_owner=is_owner)

    achievements = {"items": [], "count": 0}
    try:
        from admin_achievements import list_user_achievements

        achievements = await list_user_achievements(user_id)
    except Exception:
        achievements = {"items": [], "count": 0}

    editable = {
        "balance": bool(is_owner),
        "items": bool(is_owner),
        "ban": True,
        "unban": True,
        "onboardingReset": bool(is_owner),
        "notes": True,
        "farmReset": bool(is_owner),
        "ownerFields": bool(is_owner),
    }

    return {
        "profile": profile,
        "economy": {**economy, "donateJournal": donate_journal},
        "dossier": dossier,
        "achievements": achievements,
        "thresholds": thresholds,
        "activity30d": {
            "totalMessages": total_messages,
            "chatCount": len(activity_by_chat),
            "byChat": activity_by_chat,
            "mostActive": most_active,
        },
        "engagement": engagement,
        "p2p": p2p,
        "significantMoves": significant_moves,
        "cuteRecent": cute_preview,
        "itemTrades": {"count": item_trades},
        "quests": quests,
        "bans": bans if isinstance(bans, list) else bans,
        "notes": notes if isinstance(notes, list) else notes,
        "editable": editable,
        "viewer": {"isOwner": bool(is_owner)},
    }


def _elapsed_ru(reg_dt) -> str | None:
    if not reg_dt:
        return None
    try:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if getattr(reg_dt, "tzinfo", None) is None:
            from datetime import timezone as tz

            reg_dt = reg_dt.replace(tzinfo=tz.utc)
        delta = now - reg_dt
        days = max(0, delta.days)
        months, rem_days = divmod(days, 30)
        hours = delta.seconds // 3600
        parts = []
        if months:
            parts.append(f"{months} мес.")
        if rem_days:
            parts.append(f"{rem_days} дн.")
        if hours and not months:
            parts.append(f"{hours} ч.")
        return ", ".join(parts) if parts else "менее часа"
    except Exception:
        return None


async def _build_engagement_stats(user_id: int, *, profile: dict | None = None) -> dict:
    """Полная аналитика присутствия: группы, частота, оценка активного времени."""
    from datetime import date, datetime, timedelta, timezone

    today = date.today()
    out: dict[str, Any] = {
        "lastSeenAt": (profile or {}).get("lastSeenAt"),
        "accountAgeDays": None,
        "messages": {
            "day": 0,
            "week": 0,
            "month": 0,
            "year": 0,
            "lifetime": 0,
            "avgPerActiveDay": 0,
            "avgPerDayMonth": 0,
            "avgPerDayYear": 0,
        },
        "activeDays": {"week": 0, "month": 0, "year": 0, "lifetime": 0},
        "streak": {"current": 0, "best": 0},
        "topGroupsLifetime": [],
        "topGroups30d": [],
        "hourlyHeat": [0] * 24,
        "weekdayHeat": [0] * 7,
        "sessions": {
            "estimatedMinutesTotal": 0,
            "estimatedMinutes30d": 0,
            "avgMinutesPerActiveDay": 0,
            "avgMinutesPerDayMonth": 0,
            "loginEvents30d": 0,
            "sessionCount30d": 0,
        },
        "farm": {"plants": 0, "waters": 0, "harvests": 0, "withers": 0, "efficiencyPct": None},
        "gamesOpens": {"total": 0, "byChat": []},
        "signals": {
            "engagementScore": 0,
            "churnRisk": "low",
            "inactiveDays": None,
            "labels": [],
        },
        "platform": None,
        "timezone": None,
    }

    # lifetime + windows from chatchange
    try:
        agg = await db.pool.fetchrow(
            """
            SELECT
              COALESCE(SUM(text::bigint), 0)::bigint AS lifetime,
              COALESCE(SUM(text::bigint) FILTER (WHERE date = CURRENT_DATE), 0)::bigint AS day,
              COALESCE(SUM(text::bigint) FILTER (WHERE date >= CURRENT_DATE - 6), 0)::bigint AS week,
              COALESCE(SUM(text::bigint) FILTER (WHERE date >= CURRENT_DATE - 29), 0)::bigint AS month,
              COALESCE(SUM(text::bigint) FILTER (WHERE date >= CURRENT_DATE - 364), 0)::bigint AS year,
              COUNT(DISTINCT date)::int AS days_life,
              COUNT(DISTINCT date) FILTER (WHERE date >= CURRENT_DATE - 6)::int AS days_week,
              COUNT(DISTINCT date) FILTER (WHERE date >= CURRENT_DATE - 29)::int AS days_month,
              COUNT(DISTINCT date) FILTER (WHERE date >= CURRENT_DATE - 364)::int AS days_year
            FROM chatchange
            WHERE user_id = $1
            """,
            user_id,
        )
        if agg:
            out["messages"]["lifetime"] = int(agg["lifetime"] or 0)
            out["messages"]["day"] = int(agg["day"] or 0)
            out["messages"]["week"] = int(agg["week"] or 0)
            out["messages"]["month"] = int(agg["month"] or 0)
            out["messages"]["year"] = int(agg["year"] or 0)
            out["activeDays"]["lifetime"] = int(agg["days_life"] or 0)
            out["activeDays"]["week"] = int(agg["days_week"] or 0)
            out["activeDays"]["month"] = int(agg["days_month"] or 0)
            out["activeDays"]["year"] = int(agg["days_year"] or 0)
            life_days = max(1, out["activeDays"]["lifetime"])
            out["messages"]["avgPerActiveDay"] = round(out["messages"]["lifetime"] / life_days, 1)
            out["messages"]["avgPerDayMonth"] = round(out["messages"]["month"] / 30, 1)
            out["messages"]["avgPerDayYear"] = round(out["messages"]["year"] / 365, 1)
    except Exception:
        pass

    try:
        rows = await db.pool.fetch(
            """
            SELECT c.chat_id,
                   COALESCE(MAX(ch.namechat), MAX(c.chat_name), c.chat_id::text) AS chat_name,
                   COALESCE(SUM(c.text::bigint), 0)::bigint AS messages,
                   COUNT(DISTINCT c.date)::int AS active_days
            FROM chatchange c
            LEFT JOIN chat ch ON ch.chat_id = c.chat_id
            WHERE c.user_id = $1
            GROUP BY c.chat_id
            ORDER BY messages DESC
            LIMIT 12
            """,
            user_id,
        )
        out["topGroupsLifetime"] = [
            {
                "chatId": int(r["chat_id"]),
                "chatName": r["chat_name"] or str(r["chat_id"]),
                "messages": int(r["messages"] or 0),
                "activeDays": int(r["active_days"] or 0),
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        rows = await db.pool.fetch(
            """
            SELECT c.chat_id,
                   COALESCE(MAX(ch.namechat), MAX(c.chat_name), c.chat_id::text) AS chat_name,
                   COALESCE(SUM(c.text::bigint), 0)::bigint AS messages
            FROM chatchange c
            LEFT JOIN chat ch ON ch.chat_id = c.chat_id
            WHERE c.user_id = $1 AND c.date >= CURRENT_DATE - 29
            GROUP BY c.chat_id
            ORDER BY messages DESC
            LIMIT 10
            """,
            user_id,
        )
        out["topGroups30d"] = [
            {
                "chatId": int(r["chat_id"]),
                "chatName": r["chat_name"] or str(r["chat_id"]),
                "messages": int(r["messages"] or 0),
            }
            for r in rows
        ]
    except Exception:
        pass

    # streak from daily activity dates
    try:
        days = await db.pool.fetch(
            """
            SELECT DISTINCT date AS d
            FROM chatchange
            WHERE user_id = $1
            ORDER BY d DESC
            LIMIT 800
            """,
            user_id,
        )
        day_set = {r["d"] for r in days if r["d"]}
        best = 0
        cur = 0
        # current streak: walk back from today/yesterday
        probe = today
        if probe not in day_set and (today - timedelta(days=1)) in day_set:
            probe = today - timedelta(days=1)
        while probe in day_set:
            cur += 1
            probe -= timedelta(days=1)
        out["streak"]["current"] = cur
        # best streak
        sorted_days = sorted(day_set)
        run = 0
        prev = None
        for d in sorted_days:
            if prev is not None and d == prev + timedelta(days=1):
                run += 1
            else:
                run = 1
            best = max(best, run)
            prev = d
        out["streak"]["best"] = best
    except Exception:
        pass

    # heatmaps from game_events + login events
    try:
        rows = await db.pool.fetch(
            """
            SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC')::int AS h,
                   EXTRACT(DOW FROM created_at AT TIME ZONE 'UTC')::int AS dow,
                   COUNT(*)::int AS n
            FROM game_events
            WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '90 days'
            GROUP BY 1, 2
            """,
            user_id,
        )
        hourly = [0] * 24
        weekday = [0] * 7
        for r in rows:
            h = int(r["h"] or 0)
            dow = int(r["dow"] or 0)
            n = int(r["n"] or 0)
            if 0 <= h < 24:
                hourly[h] += n
            if 0 <= dow < 7:
                weekday[dow] += n
        out["hourlyHeat"] = hourly
        out["weekdayHeat"] = weekday
    except Exception:
        pass

    # farm events
    try:
        f = await db.pool.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE event_type = 'farm_plant')::int AS plants,
              COUNT(*) FILTER (WHERE event_type = 'farm_water')::int AS waters,
              COUNT(*) FILTER (WHERE event_type = 'farm_harvest')::int AS harvests,
              COUNT(*) FILTER (WHERE event_type = 'farm_wither')::int AS withers
            FROM game_events
            WHERE user_id = $1
            """,
            user_id,
        )
        if f:
            plants = int(f["plants"] or 0)
            harvests = int(f["harvests"] or 0)
            out["farm"] = {
                "plants": plants,
                "waters": int(f["waters"] or 0),
                "harvests": harvests,
                "withers": int(f["withers"] or 0),
                "efficiencyPct": round(100 * harvests / plants, 1) if plants else None,
            }
    except Exception:
        pass

    # session estimate from user_login_events
    try:
        logins = await db.pool.fetch(
            """
            SELECT created_at, platform, timezone
            FROM user_login_events
            WHERE user_id = $1
            ORDER BY created_at ASC
            LIMIT 2000
            """,
            user_id,
        )
        if logins:
            out["platform"] = logins[-1]["platform"]
            out["timezone"] = logins[-1]["timezone"]
            gap = timedelta(minutes=30)
            sessions: list[tuple[datetime, datetime]] = []
            start = end = None
            for r in logins:
                ts = r["created_at"]
                if ts is None:
                    continue
                if getattr(ts, "tzinfo", None) is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if start is None:
                    start = end = ts
                    continue
                if ts - end <= gap:
                    end = ts
                else:
                    sessions.append((start, end))
                    start = end = ts
            if start is not None:
                sessions.append((start, end))

            def _mins(a, b):
                raw = max(2, int((b - a).total_seconds() / 60) + 2)
                return min(180, raw)

            total_m = sum(_mins(a, b) for a, b in sessions)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            s30 = [(a, b) for a, b in sessions if b >= cutoff]
            m30 = sum(_mins(a, b) for a, b in s30)
            out["sessions"]["estimatedMinutesTotal"] = total_m
            out["sessions"]["estimatedMinutes30d"] = m30
            out["sessions"]["sessionCount30d"] = len(s30)
            out["sessions"]["loginEvents30d"] = sum(1 for r in logins if r["created_at"] and r["created_at"] >= cutoff)
            ad_month = max(1, out["activeDays"]["month"] or 1)
            out["sessions"]["avgMinutesPerActiveDay"] = round(m30 / ad_month, 1)
            out["sessions"]["avgMinutesPerDayMonth"] = round(m30 / 30, 1)
    except Exception:
        pass

    # historygames opens
    try:
        g = await db.pool.fetchrow(
            "SELECT COALESCE(SUM(use1), 0)::bigint AS n FROM historygames WHERE user_id = $1",
            user_id,
        )
        out["gameOpens"]["total"] = int((g or {}).get("n") or 0)
        grows = await db.pool.fetch(
            """
            SELECT chat_id, COALESCE(MAX(chat_name), chat_id::text) AS chat_name,
                   COALESCE(SUM(use1), 0)::bigint AS opens
            FROM historygames
            WHERE user_id = $1
            GROUP BY chat_id
            ORDER BY opens DESC
            LIMIT 8
            """,
            user_id,
        )
        out["gameOpens"]["byChat"] = [
            {
                "chatId": int(r["chat_id"]) if r["chat_id"] is not None else None,
                "chatName": r["chat_name"] or "—",
                "opens": int(r["opens"] or 0),
            }
            for r in grows
        ]
    except Exception:
        pass

    # signals / score
    inactive_days = None
    last_seen_raw = (profile or {}).get("lastSeenAt")
    try:
        if last_seen_raw:
            ls = last_seen_raw
            if isinstance(ls, str):
                ls = datetime.fromisoformat(ls.replace("Z", "+00:00"))
            if getattr(ls, "tzinfo", None) is None:
                ls = ls.replace(tzinfo=timezone.utc)
            inactive_days = max(0, (datetime.now(timezone.utc) - ls).days)
    except Exception:
        inactive_days = None
    out["signals"]["inactiveDays"] = inactive_days

    score = 0
    score += min(25, out["activeDays"]["month"] * 2)
    score += min(20, int(out["messages"]["month"] / 20))
    score += min(15, int((out["sessions"]["estimatedMinutes30d"] or 0) / 30))
    score += min(15, out["farm"]["harvests"])
    score += min(10, out["streak"]["current"])
    score += min(15, int((out["gameOpens"]["total"] or 0) / 50))
    if inactive_days is not None:
        if inactive_days >= 14:
            score = max(0, score - 25)
        elif inactive_days >= 7:
            score = max(0, score - 12)
    out["signals"]["engagementScore"] = min(100, score)

    if inactive_days is None:
        churn = "unknown"
    elif inactive_days >= 21:
        churn = "high"
    elif inactive_days >= 7:
        churn = "medium"
    else:
        churn = "low"
    out["signals"]["churnRisk"] = churn

    labels = []
    if out["streak"]["current"] >= 7:
        labels.append("серия ≥7 дней")
    if out["activeDays"]["month"] >= 20:
        labels.append("ежедневный игрок")
    if out["farm"]["efficiencyPct"] is not None and out["farm"]["efficiencyPct"] >= 70:
        labels.append("сильный фермер")
    if out["messages"]["month"] >= 500:
        labels.append("активен в чатах")
    if churn == "high":
        labels.append("риск оттока")
    if out["topGroupsLifetime"]:
        labels.append(f"дом: {out['topGroupsLifetime'][0]['chatName']}")
    out["signals"]["labels"] = labels

    return out


async def _build_user_dossier(user_id: int, *, is_owner: bool) -> dict:
    """Карточка как в боте: фонд, донаты, репутация, рефералы, дата и т.д."""
    out: dict[str, Any] = {
        "registeredAt": None,
        "registeredAtLabel": None,
        "accountAge": None,
        "referrals": 0,
        "referrerName": None,
        "reputationPlus": 0,
        "reputationMinus": 0,
        "transferLimit": None,
        "withdrawLimit": 0,
        "donated": 0,
        "wins": 0,
        "losses": 0,
        "winAmount": 0,
        "growthFundContributed": 0,
        "growthFundMilestone": None,
        "country": None,
        "sponsoredChats": [],
    }
    try:
        row = await db.pool.fetchrow(
            """
            SELECT balance, donate, canwithdrawal, wins, loose, winamount, give,
                   first_name, username
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
    except Exception:
        row = None

    if row:
        keys = set(row.keys())
        out["donated"] = int(row["donate"] or 0) if "donate" in keys else 0
        out["withdrawLimit"] = int(row["canwithdrawal"] or 0) if "canwithdrawal" in keys else 0
        out["wins"] = int(row["wins"] or 0) if "wins" in keys else 0
        out["losses"] = int(row["loose"] or 0) if "loose" in keys else 0
        out["winAmount"] = int(row["winamount"] or 0) if "winamount" in keys else 0
        if "give" in keys and row["give"] is not None:
            out["transferLimit"] = int(row["give"])

    for col, dest, cast in (
        ("referrals", "referrals", int),
        ("date", "registeredAt", None),
        ("country_emoji", "country", str),
    ):
        try:
            val = await db.pool.fetchval(
                f"SELECT {col} FROM users WHERE user_id = $1",
                user_id,
            )
            if val is None:
                continue
            if col == "date":
                out["registeredAt"] = val.isoformat() if hasattr(val, "isoformat") else str(val)
                try:
                    out["registeredAtLabel"] = val.strftime("%d.%m.%Y в %H:%M") if hasattr(val, "strftime") else str(val)
                except Exception:
                    out["registeredAtLabel"] = str(val)
                out["accountAge"] = _elapsed_ru(val)
            elif col == "country_emoji":
                out["country"] = str(val)
            else:
                out[dest] = cast(val or 0)
        except Exception:
            pass

    for plus_col, minus_col in (("rep_plus", "rep_minus"), ("reputation_plus", "reputation_minus")):
        try:
            r2 = await db.pool.fetchrow(
                f"SELECT COALESCE({plus_col}, 0) AS rp, COALESCE({minus_col}, 0) AS rm FROM users WHERE user_id = $1",
                user_id,
            )
            if r2:
                out["reputationPlus"] = int(r2["rp"] or 0)
                out["reputationMinus"] = int(r2["rm"] or 0)
                break
        except Exception:
            continue

    try:
        ref = await db.pool.fetchval(
            """
            SELECT COALESCE(u.display_name, u.first_name, u.username)
            FROM users me
            JOIN users u ON u.user_id = me.referer_id
            WHERE me.user_id = $1
            """,
            user_id,
        )
        if ref:
            out["referrerName"] = str(ref)
    except Exception:
        try:
            ref = await db.pool.fetchval(
                """
                SELECT COALESCE(u.display_name, u.first_name, u.username)
                FROM users me
                JOIN users u ON u.user_id = me.invited_by
                WHERE me.user_id = $1
                """,
                user_id,
            )
            if ref:
                out["referrerName"] = str(ref)
        except Exception:
            pass

    try:
        gf = await db.pool.fetchrow(
            """
            SELECT COALESCE(total_contributed, 0)::bigint AS contributed,
                   COALESCE(milestone_tier, 0)::int AS tier,
                   COALESCE(milestone_progress, 0)::bigint AS progress
            FROM growth_fund_user_stats WHERE user_id = $1
            """,
            user_id,
        )
        if gf:
            progress = int(gf["progress"] or 0)
            target = 100
            try:
                from bot.funcs.growth_fund import get_milestone_target

                target = int(get_milestone_target(int(gf["tier"] or 0)) or 100)
            except Exception:
                target = 100
            filled = max(0, min(10, int(round((progress / max(1, target)) * 10))))
            bar = ("█" * filled) + ("░" * (10 - filled))
            out["growthFundContributed"] = int(gf["contributed"] or 0)
            out["growthFundMilestone"] = {
                "tier": int(gf["tier"] or 0),
                "progress": progress,
                "target": target,
                "bar": bar,
            }
    except Exception:
        pass

    try:
        chats = await db.pool.fetch(
            """
            SELECT chat_id, namechat, usernamechat, group_balance_level
            FROM chat
            WHERE group_balance_sponsor_id = $1
            ORDER BY group_balance_level DESC NULLS LAST
            LIMIT 20
            """,
            user_id,
        )
        out["sponsoredChats"] = [
            {
                "chatId": int(c["chat_id"]),
                "name": c["namechat"] or str(c["chat_id"]),
                "username": c["usernamechat"],
                "level": int(c["group_balance_level"] or 0),
            }
            for c in chats
        ]
    except Exception:
        out["sponsoredChats"] = []

    if is_owner:
        secrets: dict[str, Any] = {"demo": 0, "zeroDemo": 0}
        try:
            s = await db.pool.fetchrow(
                """
                SELECT COALESCE(demo, 0)::bigint AS demo,
                       COALESCE("0demo", 0)::bigint AS zero_demo
                FROM users WHERE user_id = $1
                """,
                user_id,
            )
            if s:
                secrets["demo"] = int(s["demo"] or 0)
                secrets["zeroDemo"] = int(s["zero_demo"] or 0)
        except Exception:
            pass
        out["ownerSecrets"] = secrets

    return out


async def list_user_p2p_transfers(
    user_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    near: str | None = None,
    limit: int = 50,
) -> dict:
    """P2P переводы с фильтром по дате / дате-времени."""
    from datetime import datetime, timedelta

    limit = max(1, min(int(limit), 200))
    conds = ["(t.sender_id = $1 OR t.receiver_id = $1)"]
    params: list[Any] = [user_id]
    idx = 2

    def _parse_dt(raw: str | None):
        if not raw:
            return None
        s = str(raw).strip().replace("Z", "")
        try:
            if len(s) <= 10:
                return datetime.fromisoformat(s[:10])
            return datetime.fromisoformat(s[:19])
        except ValueError:
            return None

    near_dt = _parse_dt(near)
    if near_dt is not None:
        window = timedelta(hours=12)
        conds.append(f"t.created_at >= ${idx} AND t.created_at < ${idx + 1}")
        params.extend([near_dt - window, near_dt + window])
        idx += 2
    else:
        df = _parse_dt(date_from)
        dt = _parse_dt(date_to)
        if df is not None:
            conds.append(f"t.created_at >= ${idx}")
            params.append(df)
            idx += 1
        if dt is not None:
            end = dt
            if len(str(date_to or "").strip()) <= 10:
                end = dt + timedelta(days=1)
            conds.append(f"t.created_at < ${idx}")
            params.append(end)
            idx += 1

    where = " AND ".join(conds)
    total = int(
        await db.pool.fetchval(
            f"SELECT COUNT(*)::int FROM p2p_transfers t WHERE {where}",
            *params,
        )
        or 0
    )
    rows = await db.pool.fetch(
        f"""
        SELECT t.id, t.sender_id, t.receiver_id, t.amount, t.cause, t.created_at,
               su.username AS sender_username,
               COALESCE(su.display_name, su.first_name) AS sender_name,
               ru.username AS receiver_username,
               COALESCE(ru.display_name, ru.first_name) AS receiver_name
        FROM p2p_transfers t
        LEFT JOIN users su ON su.user_id = t.sender_id
        LEFT JOIN users ru ON ru.user_id = t.receiver_id
        WHERE {where}
        ORDER BY t.created_at DESC, t.id DESC
        LIMIT ${idx}
        """,
        *params,
        limit,
    )
    items = []
    for t in rows:
        direction = "out" if int(t["sender_id"]) == user_id else "in"
        cp_id = int(t["receiver_id"] if direction == "out" else t["sender_id"])
        items.append(
            {
                "id": int(t["id"]),
                "direction": direction,
                "amount": int(t["amount"] or 0),
                "cause": t["cause"] or "",
                "createdAt": t["created_at"].isoformat() if t["created_at"] else None,
                "counterparty": {
                    "userId": cp_id,
                    "name": (t["receiver_name"] if direction == "out" else t["sender_name"])
                    or str(cp_id),
                    "username": t["receiver_username"]
                    if direction == "out"
                    else t["sender_username"],
                },
            }
        )
    return {"items": items, "total": total, "limit": limit}


async def owner_update_user_fields(user_id: int, fields: dict) -> dict:
    """Только владелец: правит произвольные безопасные поля игрока."""
    from datetime import datetime

    allowed = {
        "balance": "balance",
        "donate": "donate",
        "canwithdrawal": "canwithdrawal",
        "wins": "wins",
        "loose": "loose",
        "winamount": "winamount",
        "give": "give",
        "referrals": "referrals",
        "demo": "demo",
        "zeroDemo": '"0demo"',
        "firstName": "first_name",
        "username": "username",
        "displayName": "display_name",
        "banned": "banned",
        "bannedReason": "banned_reason",
    }
    sets = []
    params: list[Any] = []
    idx = 1
    for key, col in allowed.items():
        if key not in fields:
            continue
        val = fields[key]
        if key in ("balance", "donate", "canwithdrawal", "wins", "loose", "winamount", "give", "referrals", "demo", "zeroDemo"):
            val = int(val)
            if val < 0:
                raise ValueError(f"{key} не может быть отрицательным")
        elif key == "banned":
            val = bool(val)
        else:
            val = None if val is None else str(val)[:255]
        sets.append(f"{col} = ${idx}")
        params.append(val)
        idx += 1

    if fields.get("registeredAt"):
        raw = str(fields["registeredAt"]).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "")[:19])
        except ValueError as e:
            raise ValueError("Некорректная дата регистрации") from e
        label = dt.strftime("%d.%m.%Y %H:%M")
        sets.append(f"date = ${idx}")
        params.append(label)
        idx += 1

    if not sets:
        raise ValueError("Нет полей для обновления")

    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(sets)} WHERE user_id = ${idx}"
    result = await db.pool.execute(sql, *params)
    if str(result).endswith("0"):
        raise ValueError("Игрок не найден")
    return {"ok": True, "userId": user_id}
