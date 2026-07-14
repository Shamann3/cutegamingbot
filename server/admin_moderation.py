"""Модерация игроков: архив логов, доказательства, разбан."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from config import BOT_TOKEN
from db import db

logger = logging.getLogger(__name__)

# Все системы наказаний и их снятий, попадающие в архив модерации.
# Охват (одна группа / все офиц. группы / весь проект) хранится в
# staff_actions.scope ('chat' / 'all' / 'full') и пишется всеми системами бота
# (мут/кик/бан/варн и снятия), а также веб-панелью.
MODERATION_ACTION_TYPES = ("ban", "unban", "mute", "unmute", "kick", "warn", "unwarn")
_PUNISH_TYPES = ("ban", "mute", "kick", "warn")
_REMOVAL_TYPES = ("unban", "unmute", "unwarn")

# Единый список колонок, чтобы все выборки архива были идентичны.
_ACTION_COLUMNS = """
    id, created_at, admin_user_id, admin_name, action_type,
    target_player_id, target_name, reason, evidence,
    proof_media_id, duration_minutes, chat_id, scope
"""


def _resolve_action_filter(action_type: str | None) -> tuple[str, ...]:
    """Какие action_type показывать: конкретный тип, группа или все.

    Поддерживает алиасы-группы: 'punishments' (наказания) и 'removals' (снятия),
    чтобы фронт мог одной кнопкой отфильтровать все снятия/все наказания.
    """
    if not action_type:
        return MODERATION_ACTION_TYPES
    at = action_type.strip().lower()
    if at in MODERATION_ACTION_TYPES:
        return (at,)
    if at in ("punishments", "punish"):
        return _PUNISH_TYPES
    if at in ("removals", "removal", "unpunish"):
        return _REMOVAL_TYPES
    return MODERATION_ACTION_TYPES


def _effective_scope(scope, chat_id) -> str:
    """Охват для отображения. Легаси-строки без scope: грубо по chat_id.

    chat_id != 0 -> наказание в конкретной группе ('chat');
    chat_id 0/NULL -> проектное; точный all/full для старых строк неизвестен,
    поэтому берём безопасное 'all'. Новые строки всегда имеют явный scope.
    """
    if scope:
        return str(scope)
    return "chat" if chat_id else "all"


def _action_row(row) -> dict:
    chat_id = row["chat_id"]
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "adminId": int(row["admin_user_id"]),
        "adminName": row["admin_name"] or "",
        "actionType": row["action_type"],
        "scope": _effective_scope(row["scope"], chat_id),
        "chatId": int(chat_id) if chat_id else 0,
        "targetId": int(row["target_player_id"]) if row["target_player_id"] else None,
        "targetName": row["target_name"] or "",
        "reason": row["reason"] or "",
        "evidence": row["evidence"] or "",
        "hasProof": bool(row["proof_media_id"]),
        "proofMediaId": row["proof_media_id"] or None,
        "durationMinutes": row["duration_minutes"],
    }


async def list_moderation_logs(
    *,
    action_type: str | None = None,
    player_id: int | None = None,
    sort_by: str = "date",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    types = _resolve_action_filter(action_type)
    params: list[Any] = []
    idx = 1

    type_ph = ", ".join(f"${i}" for i in range(idx, idx + len(types)))
    params.extend(types)
    idx += len(types)
    conditions: list[str] = [f"action_type IN ({type_ph})"]

    if player_id and player_id > 0:
        conditions.append(f"target_player_id = ${idx}")
        params.append(player_id)
        idx += 1

    order = "action_type ASC, created_at DESC, id DESC" if sort_by == "type" else "created_at DESC, id DESC"

    where = " AND ".join(conditions)
    total = int(await db.pool.fetchval(f"SELECT COUNT(*)::int FROM staff_actions WHERE {where}", *params) or 0)

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT {_ACTION_COLUMNS}
        FROM staff_actions
        WHERE {where}
        ORDER BY {order}
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {"total": total, "items": [_action_row(r) for r in rows]}


async def delete_log(log_id: int) -> None:
    type_ph = ", ".join(f"'{t}'" for t in MODERATION_ACTION_TYPES)
    result = await db.pool.execute(
        f"DELETE FROM staff_actions WHERE id = $1 AND action_type IN ({type_ph})",
        log_id,
    )
    if result == "DELETE 0":
        raise ValueError("Запись не найдена")


async def _stored_proof_token(file_id: str) -> str | None:
    """Токен-владелец пруфа, сохранённый ботом рядом с file_id (staff_actions).

    Telegram file_id валиден ТОЛЬКО для бота, который его выдал; пруфы снимает
    отдельный бот модерации, чей токен серверу может быть неизвестен. Поэтому все
    системы наказаний пишут proof_bot_token — берём его и скачиваем фото именно им.
    """
    if not file_id:
        return None
    try:
        row = await db.pool.fetchrow(
            """
            SELECT proof_bot_token FROM staff_actions
            WHERE proof_media_id = $1
              AND proof_bot_token IS NOT NULL AND proof_bot_token <> ''
            ORDER BY id DESC
            LIMIT 1
            """,
            file_id,
        )
        return row["proof_bot_token"] if row else None
    except Exception as exc:  # noqa: BLE001 - колонка может отсутствовать до миграции
        logger.debug("proof_bot_token lookup failed: %s", exc)
        return None


def _token_bot_id(token: str | None) -> str:
    """bot_id — часть токена до ':' (стабильна при перевыпуске секрета в BotFather)."""
    raw = (token or "").strip()
    return raw.split(":", 1)[0] if ":" in raw else ""


async def candidate_tokens_for_file(file_id: str) -> list[str]:
    """Токены для скачивания пруфа в порядке приоритета (без дублей).

    Telegram file_id привязан к БОТУ (bot_id), а НЕ к строке токена: токен можно
    перевыпустить в BotFather — новый токен того же бота качает и старые file_id.
    Значит устойчивость к смене токена = всегда иметь актуальный токен нужного
    бота. Порядок:
      1) живые токены с тем же bot_id, что у сохранённого владельца пруфа —
         прежде всего MODERATION_BOT_TOKEN (читается из bot/config/config.py, тот
         же источник, что у бота), поэтому смена токена не ломает архив;
      2) сам сохранённый в БД токен-владелец (если бот вне текущего конфига);
      3) остальные живые токены (панельные пруфы, бот поддержки, старые записи
         без proof_bot_token — их закрывает актуальный MODERATION_BOT_TOKEN).
    Токены используются ТОЛЬКО на сервере (photo-proxy отдаёт байты) и клиенту
    не передаются.
    """
    from config import SUPPORT_BOT_TOKEN, ADMIN_BOT_TOKEN, MODERATION_BOT_TOKEN

    live = [t for t in (MODERATION_BOT_TOKEN, BOT_TOKEN, ADMIN_BOT_TOKEN, SUPPORT_BOT_TOKEN) if t]
    stored = await _stored_proof_token(file_id)

    ordered: list[str] = []

    def _add(token: str | None) -> None:
        if token and token not in ordered:
            ordered.append(token)

    # 1) свежие токены того же бота, что принял пруф (главное — переживает ротацию).
    owner_id = _token_bot_id(stored)
    if owner_id:
        for token in live:
            if _token_bot_id(token) == owner_id:
                _add(token)
    # 2) сам сохранённый токен-владелец.
    _add(stored)
    # 3) остальные живые токены как запас.
    for token in live:
        _add(token)
    return ordered


async def get_proof_url(log_id: int) -> str:
    """Возвращает временную ссылку на файл-доказательство через Telegram API."""
    row = await db.pool.fetchrow(
        "SELECT proof_media_id FROM staff_actions WHERE id = $1",
        log_id,
    )
    if not row or not row["proof_media_id"]:
        raise ValueError("Доказательство не найдено")

    file_id = row["proof_media_id"]

    # Сначала токен-владелец из БД, затем настроенные токены (см. helper выше).
    tokens = await candidate_tokens_for_file(file_id)
    if not tokens:
        raise RuntimeError("Ни один токен бота не задан")

    last_error = ""
    async with aiohttp.ClientSession() as session:
        for token in tokens:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                return f"https://api.telegram.org/file/bot{token}/{file_path}"
            last_error = data.get("description", "ошибка")

    raise RuntimeError(f"Telegram getFile error: {last_error}")


async def unban_player(user_id: int, *, admin_user_id: int, admin_name: str = "") -> None:
    """Снимает бан + пишет лог unban в staff_actions.

    Сам разбан (UPDATE users, audit_events, уведомление игроку, инвалидация
    кэша, broadcast админам) делегирован в admin_users.admin_set_banned -
    единый источник правды, чтобы разбан из архива Модерации не отличался
    от разбана из карточки игрока (Users): раньше это были два независимых
    пути, и разбан отсюда не писался в audit_events и не уведомлял игрока.
    staff_actions пишем отдельно - это специфичная для архива Модерации
    история дела, её health не зависит от общего audit_events.
    """
    row = await db.pool.fetchrow(
        "SELECT user_id, banned FROM users WHERE user_id = $1", user_id
    )
    if not row:
        raise ValueError("Игрок не найден")
    if not row["banned"]:
        raise ValueError("Игрок не забанен")

    from admin_users import admin_set_banned
    await admin_set_banned(user_id, False, admin_user_id=admin_user_id)

    target_name = await db.pool.fetchval(
        "SELECT COALESCE(display_name, first_name, username, '') FROM users WHERE user_id = $1",
        user_id,
    ) or ""
    await db.pool.execute(
        """
        INSERT INTO staff_actions
            (admin_user_id, admin_name, action_type, target_player_id,
             target_name, reason, evidence, chat_id, scope)
        VALUES ($1, $2, 'unban', $3, $4, '', '', 0, 'full')
        """,
        admin_user_id, admin_name, user_id, target_name,
    )


async def get_player_history(player_id: int) -> list[dict]:
    """Все наказания и снятия игрока (полная история для карточки дела)."""
    type_ph = ", ".join(f"'{t}'" for t in MODERATION_ACTION_TYPES)
    rows = await db.pool.fetch(
        f"""
        SELECT {_ACTION_COLUMNS}
        FROM staff_actions
        WHERE target_player_id = $1
          AND action_type IN ({type_ph})
        ORDER BY created_at DESC
        LIMIT 100
        """,
        player_id,
    )
    return [_action_row(r) for r in rows]


async def get_moderator_stats(period: str = "week") -> list[dict]:
    """Статистика по каждому модератору за период."""
    if period == "month":
        since = "NOW() - INTERVAL '30 days'"
    elif period == "all":
        since = "'1970-01-01'"
    else:
        since = "NOW() - INTERVAL '7 days'"

    type_ph = ", ".join(f"'{t}'" for t in MODERATION_ACTION_TYPES)
    rows = await db.pool.fetch(
        f"""
        SELECT
            admin_user_id,
            MAX(admin_name) AS admin_name,
            COUNT(*) FILTER (WHERE action_type = 'ban')    AS bans,
            COUNT(*) FILTER (WHERE action_type = 'mute')   AS mutes,
            COUNT(*) FILTER (WHERE action_type = 'kick')   AS kicks,
            COUNT(*) FILTER (WHERE action_type = 'warn')   AS warns,
            COUNT(*) FILTER (WHERE action_type = 'unban')  AS unbans,
            COUNT(*) FILTER (WHERE action_type = 'unmute') AS unmutes,
            COUNT(*) FILTER (WHERE action_type = 'unwarn') AS unwarns,
            COUNT(*) AS total,
            MAX(created_at) AS last_action_at
        FROM staff_actions
        WHERE created_at >= {since}
          AND action_type IN ({type_ph})
          AND admin_user_id <> 0
        GROUP BY admin_user_id
        ORDER BY total DESC
        """
    )
    return [
        {
            "adminId": int(r["admin_user_id"]),
            "adminName": r["admin_name"] or f"#{r['admin_user_id']}",
            "bans": int(r["bans"]),
            "mutes": int(r["mutes"]),
            "kicks": int(r["kicks"]),
            "warns": int(r["warns"]),
            "unbans": int(r["unbans"]),
            "unmutes": int(r["unmutes"]),
            "unwarns": int(r["unwarns"]),
            "total": int(r["total"]),
            "lastActionAt": r["last_action_at"].isoformat() if r["last_action_at"] else None,
        }
        for r in rows
    ]


async def get_recent_logs(limit: int = 5) -> list[dict]:
    """Последние N действий — для виджета на дашборде."""
    type_ph = ", ".join(f"'{t}'" for t in MODERATION_ACTION_TYPES)
    rows = await db.pool.fetch(
        f"""
        SELECT {_ACTION_COLUMNS}
        FROM staff_actions
        WHERE action_type IN ({type_ph})
        ORDER BY created_at DESC, id DESC
        LIMIT $1
        """,
        limit,
    )
    return [_action_row(r) for r in rows]
