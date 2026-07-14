"""Admin: рассылки — WebApp toast + Telegram DM через игрового бота."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config import ONLINE_WINDOW_SECONDS, WEBAPP_URL
from db import db
from presence import count_online
from user_notify import create_admin_message_notifications_batch
from telegram_notify import send_telegram_message

logger = logging.getLogger("cute-farm.admin.broadcast")

_VAR_PATTERN = re.compile(r"\{\{\s*(name|username|balance)\s*\}\}", re.IGNORECASE)

BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "key": "builtin:maintenance",
        "name": "Техработы",
        "title": "<tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> <b>Технические работы</b>",
        "body": "<tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> <b>Сервер будет недоступен некоторое время.</b>",
        "detail": "<b>Спасибо за терпение!</b>",
        "telegramText": (
            "<b><tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> Технические работы</b>\n"
            "<b>Сервер будет недоступен некоторое время.\n</b>"
            "<b>Спасибо за терпение!</b>"
        ),
    },
    {
        "key": "builtin:event",
        "name": "Ивент",
        "title": "<tg-emoji emoji-id='5461151367559141950'>🎉</tg-emoji> <b>Ивент!</b>",
        "body": "<b>Заходите в бот - вас ждёт что-то интересное!</b>",
        "detail": "",
        "telegramText": "<b><tg-emoji emoji-id='5461151367559141950'>🎉</tg-emoji> Ивент!</b>\n<b>Заходите в игру - вас ждёт что-то интересное</b>",
    },
    {
        "key": "builtin:update",
        "name": "Обновление",
        "title": "<tg-emoji emoji-id='5251367744435141446'>✨</tg-emoji> <b>Обновление!</b>",
        "body": "<b>Разработчики проекта небольшое обновление, взгляните на ферму!</b>",
        "detail": "",
        "telegramText": (
            "<b><tg-emoji emoji-id='5251367744435141446'>✨</tg-emoji> Обновление!</b>\n"
            "<b>Разработчики проекта добавили небольшое обновление. Взгляните на ферму!</b>"
        ),
    },
    {
        "key": "builtin:personal",
        "name": "Персональное",
        "name": "Персональное",
        "title": "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Добро пожаловать, {{name}}!</b>",
        "body": "<b>На вашем балансе : {{balance}} кут.</b>",
        "detail": "",
        "telegramText": (
            "<b><tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Добро пожаловать, {{name}}!</b>\n"
            "<b>На вашем балансе : {{balance}} кут.</b>"
        ),
    },
]

# Ежедневная ротация "напоминалок" (см. server/event_scheduler.py::_fire_daily_rotation_broadcast).
# minBalance - опциональный порог: сообщение шлётся только тем, у кого баланс СТРОГО больше
# указанного значения. Тексты и условия зафиксированы с владельцем проекта - каждое утверждение
# в тексте должно быть верно для любого получателя (без ложных заявлений о состоянии игрока).
DAILY_ROTATION_TEMPLATES: list[dict[str, Any]] = [
    {
        "label": "Ежедневная рассылка #1 (баланс > 100)",
        "text": "🐰 Ферма ждёт тебя. Баланс {{balance}} кут, дел на сегодня хватит на пару минут.",
        "min_balance": 101,
    },
    {
        "label": "Ежедневная рассылка #2",
        "text": "☀️ Новый день на ферме уже начался. Загляни, пока не пропустил ничего интересного.",
        "min_balance": None,
    },
    {
        "label": "Ежедневная рассылка #3 (баланс > 50)",
        "text": "🧺 У тебя {{balance}} кут в кармане. Всегда приятно посмотреть, что на них можно взять.",
        "min_balance": 51,
    },
    {
        "label": "Ежедневная рассылка #4",
        "text": "🎲 Заходи глянуть, что нового в игре сегодня — обычно там что-то да меняется.",
        "min_balance": None,
    },
    {
        "label": "Ежедневная рассылка #5",
        "text": "🎯 Каждый день на ферме — это шанс продвинуться чуть дальше. Сегодняшний ещё не использован.",
        "min_balance": None,
    },
    {
        "label": "Ежедневная рассылка #6",
        "text": "🌤 Пять минут на ферме — и день уже не прошёл зря.",
        "min_balance": None,
    },
    {
        "label": "Ежедневная рассылка #7",
        "text": "📊 Твоя позиция в топе изменилась за последний день. Глянь, что там сейчас.",
        "min_balance": None,
    },
    {
        "label": "Ежедневная рассылка #8",
        "text": "🔝 Топ недели обновляется каждый день. Сегодня твой шанс подвинуться выше.",
        "min_balance": None,
    },
]

DAILY_BROADCAST_CTA_TEXT = "🌾 Открыть ферму"


def daily_broadcast_cta_url() -> str | None:
    return WEBAPP_URL or None


TELEGRAM_SEND_DELAY = 0.04
PROGRESS_UPDATE_EVERY = 25
RECIPIENT_PAGE_SIZE = 500
WEBAPP_NOTIFY_BATCH_SIZE = 100

_broadcast_tasks: dict[int, asyncio.Task] = {}
_cancel_requested: set[int] = set()


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if not row:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        value = row[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


def _display_name(row: dict) -> str:
    for key in ("display_name", "first_name", "username"):
        val = _row_get(row, key)
        if val and str(val).strip():
            return str(val).strip()
    return f"Игрок {_row_get(row, 'user_id', '?')}"


def render_template(text: str, row: dict | None) -> str:
    if not text:
        return ""
    user = row or {}
    name = _display_name(user)
    username = _row_get(user, "username") or ""
    if username and not username.startswith("@"):
        username = f"@{username}"
    balance = _row_get(user, "balance")
    balance_str = str(balance) if balance is not None else "0"

    def repl(match: re.Match) -> str:
        key = match.group(1).lower()
        if key == "name":
            return name
        if key == "username":
            return username or name
        if key == "balance":
            return balance_str
        return match.group(0)

    return _VAR_PATTERN.sub(repl, text)


def render_telegram_template(text: str, row: dict | None) -> str:
    if not text:
        return ""
    user = row or {}
    name = _escape(_display_name(user))
    username_raw = _row_get(user, "username") or ""
    if username_raw and not str(username_raw).startswith("@"):
        username_raw = f"@{username_raw}"
    username = _escape(username_raw) if username_raw else name
    balance = _row_get(user, "balance")
    balance_str = _escape(balance if balance is not None else 0)

    def repl(match: re.Match) -> str:
        key = match.group(1).lower()
        if key == "name":
            return name
        if key == "username":
            return username
        if key == "balance":
            return balance_str
        return match.group(0)

    return _VAR_PATTERN.sub(repl, text)


def _default_telegram_html(title: str, body: str, detail: str = "") -> str:
    lines = [f"<b>{_escape(title)}</b>"]
    if body.strip():
        lines.append(_escape(body.strip()))
    if detail.strip():
        lines.append(_escape(detail.strip()))
    return "\n".join(lines)


def _normalize_channels(channels: dict | None) -> dict[str, bool]:
    data = channels or {}
    return {
        "webapp": bool(data.get("webapp", True)),
        "telegram": bool(data.get("telegram", True)),
    }


def _normalize_filter(filter_data: dict | None) -> dict[str, Any]:
    raw = dict(filter_data or {})
    result: dict[str, Any] = {
        "excludeBanned": bool(raw.get("excludeBanned", True)),
    }
    for key in ("minBalance", "maxBalance"):
        if raw.get(key) is not None:
            result[key] = int(raw[key])
    if raw.get("hasPlots") is not None:
        result["hasPlots"] = bool(raw["hasPlots"])
    username = (raw.get("username") or "").strip().lstrip("@")
    if username:
        result["username"] = username
    user_ids = raw.get("userIds")
    if user_ids:
        cleaned = sorted({int(uid) for uid in user_ids if int(uid) > 0})
        if cleaned:
            result["userIds"] = cleaned
    return result


def _build_recipient_sql(
    audience: str,
    filter_data: dict[str, Any],
) -> tuple[str, list[Any]]:
    audience = (audience or "all").strip().lower()
    conditions = ["1=1"]
    params: list[Any] = []
    idx = 1

    if filter_data.get("excludeBanned", True):
        conditions.append("u.banned = FALSE")

    if audience == "online":
        window = max(15, ONLINE_WINDOW_SECONDS)
        conditions.append(
            f"u.last_seen_at IS NOT NULL AND u.last_seen_at >= NOW() - (${idx} * INTERVAL '1 second')"
        )
        params.append(window)
        idx += 1

    if filter_data.get("minBalance") is not None:
        conditions.append(f"u.balance >= ${idx}")
        params.append(int(filter_data["minBalance"]))
        idx += 1

    if filter_data.get("maxBalance") is not None:
        conditions.append(f"u.balance <= ${idx}")
        params.append(int(filter_data["maxBalance"]))
        idx += 1

    if filter_data.get("hasPlots"):
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM farm_plots fp
                WHERE fp.user_id = u.user_id
                  AND fp.status <> 'EMPTY'
            )
            """
        )

    if filter_data.get("username"):
        pattern = f"%{filter_data['username']}%"
        conditions.append(
            f"(u.username ILIKE ${idx} OR u.display_name ILIKE ${idx} OR u.first_name ILIKE ${idx})"
        )
        params.append(pattern)
        idx += 1

    if filter_data.get("userIds"):
        conditions.append(f"u.user_id = ANY(${idx}::bigint[])")
        params.append(filter_data["userIds"])
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT u.user_id, u.username, u.display_name, u.first_name, u.balance
        FROM users u
        WHERE {where}
        ORDER BY u.user_id
    """
    return sql, params


async def count_recipients(audience: str, filter_data: dict | None = None) -> int:
    filt = _normalize_filter(filter_data)
    sql, params = _build_recipient_sql(audience, filt)
    count_sql = f"SELECT COUNT(*)::int FROM ({sql}) sub"
    return int(await db.pool.fetchval(count_sql, *params) or 0)


async def fetch_recipients(
    audience: str,
    filter_data: dict | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    filt = _normalize_filter(filter_data)
    sql, params = _build_recipient_sql(audience, filt)
    if limit is not None:
        sql += f" LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([max(1, int(limit)), max(0, int(offset))])
    rows = await db.pool.fetch(sql, *params)
    return [
        {
            "user_id": int(r["user_id"]),
            "username": r["username"],
            "display_name": r["display_name"],
            "first_name": r["first_name"],
            "balance": int(r["balance"] or 0),
        }
        for r in rows
    ]


async def get_sample_user(user_id: int | None = None) -> dict | None:
    if user_id and user_id > 0:
        row = await db.pool.fetchrow(
            """
            SELECT user_id, username, display_name, first_name, balance
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        if row:
            return dict(row)
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, display_name, first_name, balance
        FROM users
        WHERE banned = FALSE
        ORDER BY last_seen_at DESC NULLS LAST
        LIMIT 1
        """
    )
    return dict(row) if row else None


async def preview_broadcast(
    *,
    title: str,
    body: str,
    detail: str = "",
    telegram_text: str = "",
    sample_user_id: int | None = None,
) -> dict:
    sample = await get_sample_user(sample_user_id)
    sample_row = sample or {
        "user_id": 123456789,
        "username": "farmer",
        "display_name": "Farmer",
        "first_name": "Farmer",
        "balance": 250,
    }
    tg_raw = telegram_text.strip() or _default_telegram_html(title, body, detail)
    return {
        "sampleUser": {
            "userId": int(sample_row["user_id"]),
            "displayName": _display_name(sample_row),
            "username": _row_get(sample_row, "username"),
            "balance": int(_row_get(sample_row, "balance", 0) or 0),
        },
        "webapp": {
            "title": render_template(title, sample_row),
            "body": render_template(body, sample_row),
            "detail": render_template(detail, sample_row) or None,
        },
        "telegramHtml": render_telegram_template(tg_raw, sample_row),
    }


def _template_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "key": f"custom:{row['id']}",
        "name": row["name"],
        "title": row["title"],
        "body": row["body"] or "",
        "detail": row["detail"] or "",
        "telegramText": row["telegram_text"] or "",
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def list_templates() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, name, title, body, detail, telegram_text, created_at, updated_at
        FROM broadcast_templates
        ORDER BY updated_at DESC, id DESC
        """
    )
    custom = [_template_row(r) for r in rows]
    return [*BUILTIN_TEMPLATES, *custom]


async def save_template(
    *,
    name: str,
    title: str,
    body: str = "",
    detail: str = "",
    telegram_text: str = "",
    admin_user_id: int,
    template_id: int | None = None,
) -> dict:
    name_clean = (name or "").strip()
    title_clean = (title or "").strip()
    if not name_clean:
        raise ValueError("Укажите название шаблона")
    if not title_clean:
        raise ValueError("Укажите заголовок")

    body_clean = (body or "").strip()
    detail_clean = (detail or "").strip()
    tg_clean = (telegram_text or "").strip() or _default_telegram_html(title_clean, body_clean, detail_clean)

    if template_id:
        row = await db.pool.fetchrow(
            """
            UPDATE broadcast_templates
            SET name = $2, title = $3, body = $4, detail = $5, telegram_text = $6, updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, title, body, detail, telegram_text, created_at, updated_at
            """,
            template_id,
            name_clean,
            title_clean,
            body_clean,
            detail_clean,
            tg_clean,
        )
        if not row:
            raise ValueError("Шаблон не найден")
        return _template_row(row)

    row = await db.pool.fetchrow(
        """
        INSERT INTO broadcast_templates (name, title, body, detail, telegram_text, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, name, title, body, detail, telegram_text, created_at, updated_at
        """,
        name_clean,
        title_clean,
        body_clean,
        detail_clean,
        tg_clean,
        admin_user_id,
    )
    return _template_row(row)


async def delete_template(template_id: int) -> None:
    result = await db.pool.execute(
        "DELETE FROM broadcast_templates WHERE id = $1",
        template_id,
    )
    if result == "DELETE 0":
        raise ValueError("Шаблон не найден")


def _filter_summary(audience: str, filter_data: dict | None) -> str:
    filt = filter_data or {}
    parts: list[str] = []
    if audience == "online":
        parts.append("онлайн")
    elif audience == "filtered":
        parts.append("фильтр")
    else:
        parts.append("все игроки")
    if filt.get("excludeBanned", True):
        parts.append("без бана")
    if filt.get("minBalance") is not None:
        parts.append(f"баланс ≥ {filt['minBalance']}")
    if filt.get("maxBalance") is not None:
        parts.append(f"баланс ≤ {filt['maxBalance']}")
    if filt.get("hasPlots"):
        parts.append("с грядками")
    if filt.get("username"):
        parts.append(f"@{filt['username']}")
    if filt.get("userIds"):
        ids = filt["userIds"]
        if len(ids) == 1:
            parts.append(f"ID {ids[0]}")
        else:
            parts.append(f"{len(ids)} ID")
    return " · ".join(parts)


def _calc_progress(
    status: str,
    recipient_count: int,
    webapp_sent: int,
    telegram_sent: int,
    channels: dict,
) -> int:
    if status == "done":
        return 100
    if status in ("cancelled", "failed"):
        if recipient_count <= 0:
            return 0
        ch = _normalize_channels(channels)
        if ch["webapp"] and ch["telegram"]:
            processed = max(webapp_sent, telegram_sent)
        elif ch["telegram"]:
            processed = telegram_sent
        else:
            processed = webapp_sent
        return min(100, int(processed * 100 / recipient_count))
    if recipient_count <= 0:
        return 0
    ch = _normalize_channels(channels)
    if ch["webapp"] and ch["telegram"]:
        processed = min(webapp_sent, telegram_sent) if webapp_sent and telegram_sent else max(webapp_sent, telegram_sent)
    elif ch["telegram"]:
        processed = telegram_sent
    else:
        processed = webapp_sent
    return min(100, int(processed * 100 / recipient_count))


def _seconds_between(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds()))


def _run_row(row) -> dict:
    filter_json = row["filter_json"]
    if isinstance(filter_json, str):
        filter_json = json.loads(filter_json)
    channels_json = row["channels_json"]
    if isinstance(channels_json, str):
        channels_json = json.loads(channels_json)
    channels = channels_json or {}
    recipient_count = int(row["recipient_count"] or 0)
    webapp_sent = int(row["webapp_sent"] or 0)
    telegram_sent = int(row["telegram_sent"] or 0)
    status = row["status"]
    created_at = row["created_at"]
    finished_at = row["finished_at"]
    now = datetime.now(timezone.utc)
    duration_seconds = _seconds_between(created_at, finished_at)
    elapsed_seconds = None
    if status in ("pending", "running") and created_at:
        elapsed_seconds = _seconds_between(created_at, now)

    return {
        "id": int(row["id"]),
        "adminUserId": int(row["admin_user_id"]),
        "audience": row["audience"],
        "filter": filter_json or {},
        "filterSummary": _filter_summary(row["audience"], filter_json or {}),
        "channels": channels,
        "title": row["title"],
        "body": row["body"] or "",
        "detail": row["detail"] or "",
        "telegramText": row["telegram_text"] or "",
        "templateKey": row["template_key"],
        "recipientCount": recipient_count,
        "webappSent": webapp_sent,
        "telegramSent": telegram_sent,
        "telegramFailed": int(row["telegram_failed"] or 0),
        "progressPercent": _calc_progress(status, recipient_count, webapp_sent, telegram_sent, channels),
        "durationSeconds": duration_seconds,
        "elapsedSeconds": elapsed_seconds,
        "status": status,
        "errorMessage": row["error_message"],
        "createdAt": created_at.isoformat() if created_at else None,
        "finishedAt": finished_at.isoformat() if finished_at else None,
    }


async def get_broadcast_run(run_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT
            id, admin_user_id, audience, filter_json, channels_json,
            title, body, detail, telegram_text, template_key,
            recipient_count, webapp_sent, telegram_sent, telegram_failed,
            status, error_message, created_at, finished_at
        FROM broadcast_runs
        WHERE id = $1
        """,
        run_id,
    )
    return _run_row(row) if row else None


async def list_broadcast_history(
    *,
    limit: int = 30,
    offset: int = 0,
    status: str | None = None,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    status_norm = (status or "").strip().lower()
    if status_norm and status_norm not in ("pending", "running", "done", "failed", "cancelled"):
        status_norm = ""

    if status_norm:
        total = int(
            await db.pool.fetchval(
                "SELECT COUNT(*)::int FROM broadcast_runs WHERE status = $1",
                status_norm,
            )
            or 0
        )
        rows = await db.pool.fetch(
            """
            SELECT
                id, admin_user_id, audience, filter_json, channels_json,
                title, body, detail, telegram_text, template_key,
                recipient_count, webapp_sent, telegram_sent, telegram_failed,
                status, error_message, created_at, finished_at
            FROM broadcast_runs
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status_norm,
            limit,
            offset,
        )
    else:
        total = int(await db.pool.fetchval("SELECT COUNT(*)::int FROM broadcast_runs") or 0)
        rows = await db.pool.fetch(
            """
            SELECT
                id, admin_user_id, audience, filter_json, channels_json,
                title, body, detail, telegram_text, template_key,
                recipient_count, webapp_sent, telegram_sent, telegram_failed,
                status, error_message, created_at, finished_at
            FROM broadcast_runs
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    active_count = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM broadcast_runs
            WHERE status IN ('pending', 'running')
            """
        )
        or 0
    )
    return {
        "total": total,
        "activeCount": active_count,
        "items": [_run_row(r) for r in rows],
    }


async def get_broadcast_overview() -> dict:
    online_now = await count_online()
    total_users = int(
        await db.pool.fetchval("SELECT COUNT(*)::int FROM users WHERE banned = FALSE") or 0
    )
    history = await list_broadcast_history(limit=15, offset=0)
    return {
        "onlineNow": online_now,
        "totalUsers": total_users,
        "windowSeconds": max(15, ONLINE_WINDOW_SECONDS),
        "templates": await list_templates(),
        "history": history["items"],
        "historyTotal": history["total"],
        "activeBroadcasts": history["activeCount"],
    }


async def _is_cancelled(run_id: int) -> bool:
    if run_id in _cancel_requested:
        return True
    status = await db.pool.fetchval(
        "SELECT status FROM broadcast_runs WHERE id = $1",
        run_id,
    )
    return status == "cancelled"


async def recover_orphaned_broadcasts() -> int:
    """После перезапуска сервера — снять зависшие рассылки."""
    result = await db.pool.execute(
        """
        UPDATE broadcast_runs
        SET status = 'cancelled',
            error_message = COALESCE(NULLIF(error_message, ''), 'Остановлено: сервер перезапущен'),
            finished_at = COALESCE(finished_at, NOW())
        WHERE status IN ('pending', 'running')
        """
    )
    try:
        return int(str(result).split()[-1])
    except (ValueError, IndexError):
        return 0


async def cancel_broadcast(run_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow(
        """
        SELECT status, webapp_sent, telegram_sent, telegram_failed
        FROM broadcast_runs WHERE id = $1
        """,
        run_id,
    )
    if not row:
        raise ValueError("Рассылка не найдена")
    if row["status"] not in ("pending", "running"):
        raise ValueError("Рассылка уже завершена")

    _cancel_requested.add(run_id)
    await _update_run(
        run_id,
        status="cancelled",
        webapp_sent=int(row["webapp_sent"] or 0),
        telegram_sent=int(row["telegram_sent"] or 0),
        telegram_failed=int(row["telegram_failed"] or 0),
        error_message="Отменено администратором",
        finished=True,
    )
    return {
        "ok": True,
        "runId": run_id,
        "status": "cancelled",
        "adminUserId": admin_user_id,
    }


async def _update_run(
    run_id: int,
    *,
    status: str | None = None,
    webapp_sent: int | None = None,
    telegram_sent: int | None = None,
    telegram_failed: int | None = None,
    recipient_count: int | None = None,
    error_message: str | None = None,
    finished: bool = False,
) -> None:
    sets = []
    params: list[Any] = []
    idx = 1

    def add(field: str, value: Any) -> None:
        nonlocal idx
        sets.append(f"{field} = ${idx}")
        params.append(value)
        idx += 1

    if status is not None:
        add("status", status)
    if webapp_sent is not None:
        add("webapp_sent", webapp_sent)
    if telegram_sent is not None:
        add("telegram_sent", telegram_sent)
    if telegram_failed is not None:
        add("telegram_failed", telegram_failed)
    if recipient_count is not None:
        add("recipient_count", recipient_count)
    if error_message is not None:
        add("error_message", error_message)
    if finished:
        add("finished_at", datetime.now(timezone.utc))

    if not sets:
        return

    params.append(run_id)
    await db.pool.execute(
        f"UPDATE broadcast_runs SET {', '.join(sets)} WHERE id = ${idx}",
        *params,
    )


async def _execute_broadcast(run_id: int) -> None:
    row = await db.pool.fetchrow(
        """
        SELECT
            id, audience, filter_json, channels_json,
            title, body, detail, telegram_text, cta_text, cta_url
        FROM broadcast_runs
        WHERE id = $1
        """,
        run_id,
    )
    if not row:
        return

    filter_json = row["filter_json"]
    if isinstance(filter_json, str):
        filter_json = json.loads(filter_json)
    channels_json = row["channels_json"]
    if isinstance(channels_json, str):
        channels_json = json.loads(channels_json)

    channels = _normalize_channels(channels_json)
    title = row["title"] or ""
    body = row["body"] or ""
    detail = row["detail"] or ""
    telegram_tpl = row["telegram_text"] or ""
    cta_text = row["cta_text"] or None
    cta_url = row["cta_url"] or None

    await _update_run(run_id, status="running")

    webapp_sent = 0
    telegram_sent = 0
    telegram_failed = 0

    try:
        recipient_total = await count_recipients(row["audience"], filter_json or {})
        await _update_run(run_id, recipient_count=recipient_total)

        offset = 0
        processed = 0

        while True:
            page = await fetch_recipients(
                row["audience"],
                filter_json or {},
                limit=RECIPIENT_PAGE_SIZE,
                offset=offset,
            )
            if not page:
                break

            # Batch WebApp notifications to reduce DB round-trips.
            webapp_batch: list[tuple[int, str, str, str]] = []

            for user in page:
                if await _is_cancelled(run_id):
                    row_now = await db.pool.fetchrow(
                        """
                        SELECT webapp_sent, telegram_sent, telegram_failed
                        FROM broadcast_runs WHERE id = $1
                        """,
                        run_id,
                    )
                    await _update_run(
                        run_id,
                        status="cancelled",
                        webapp_sent=int(row_now["webapp_sent"] or 0) if row_now else webapp_sent,
                        telegram_sent=int(row_now["telegram_sent"] or 0) if row_now else telegram_sent,
                        telegram_failed=int(row_now["telegram_failed"] or 0) if row_now else telegram_failed,
                        error_message="Отменено администратором",
                        finished=True,
                    )
                    return

                user_id = int(user["user_id"])
                web_title = render_template(title, user)
                web_body = render_template(body, user)
                web_detail = render_template(detail, user)
                tg_text = render_telegram_template(
                    telegram_tpl or _default_telegram_html(title, body, detail),
                    user,
                )

                if channels["webapp"]:
                    webapp_batch.append((user_id, web_title, web_body, web_detail))
                    if len(webapp_batch) >= WEBAPP_NOTIFY_BATCH_SIZE:
                        webapp_sent += await create_admin_message_notifications_batch(
                            db.pool, webapp_batch
                        )
                        webapp_batch.clear()

                if channels["telegram"] and tg_text.strip():
                    try:
                        await send_telegram_message(
                            tg_text, chat_id=str(user_id),
                            cta_text=cta_text, cta_url=cta_url,
                        )
                        telegram_sent += 1
                        await asyncio.sleep(TELEGRAM_SEND_DELAY)
                    except Exception:
                        telegram_failed += 1
                        logger.exception("Telegram broadcast failed (user_id=%s)", user_id)

                processed += 1
                if processed % PROGRESS_UPDATE_EVERY == 0 or processed == recipient_total:
                    await _update_run(
                        run_id,
                        webapp_sent=webapp_sent,
                        telegram_sent=telegram_sent,
                        telegram_failed=telegram_failed,
                    )

            if webapp_batch and channels["webapp"]:
                webapp_sent += await create_admin_message_notifications_batch(
                    db.pool, webapp_batch
                )
                webapp_batch.clear()

            offset += RECIPIENT_PAGE_SIZE
            if len(page) < RECIPIENT_PAGE_SIZE:
                break

        await _update_run(
            run_id,
            status="done",
            webapp_sent=webapp_sent,
            telegram_sent=telegram_sent,
            telegram_failed=telegram_failed,
            finished=True,
        )
    except Exception as exc:
        logger.exception("Broadcast run failed (id=%s)", run_id)
        await _update_run(
            run_id,
            status="failed",
            webapp_sent=webapp_sent,
            telegram_sent=telegram_sent,
            telegram_failed=telegram_failed,
            error_message=str(exc)[:500],
            finished=True,
        )


def schedule_broadcast_run(run_id: int) -> None:
    async def runner() -> None:
        try:
            await _execute_broadcast(run_id)
        finally:
            _broadcast_tasks.pop(run_id, None)
            _cancel_requested.discard(run_id)

    _cancel_requested.discard(run_id)
    task = asyncio.create_task(runner())
    _broadcast_tasks[run_id] = task


async def start_broadcast(
    *,
    audience: str,
    filter_data: dict | None,
    channels: dict | None,
    title: str,
    body: str = "",
    detail: str = "",
    telegram_text: str = "",
    template_key: str | None = None,
    scheduled_at=None,
    label: str = "",
    admin_user_id: int,
    cta_text: str | None = None,
    cta_url: str | None = None,
) -> dict:
    audience_norm = (audience or "all").strip().lower()
    if audience_norm not in ("all", "online", "filtered"):
        raise ValueError("Неверная аудитория")

    title_clean = (title or "").strip()
    if not title_clean:
        raise ValueError("Укажите заголовок")

    body_clean = (body or "").strip()
    detail_clean = (detail or "").strip()
    tg_clean = (telegram_text or "").strip() or _default_telegram_html(title_clean, body_clean, detail_clean)
    filt = _normalize_filter(filter_data)
    ch = _normalize_channels(channels)

    if not ch["webapp"] and not ch["telegram"]:
        raise ValueError("Выберите хотя бы один канал")

    recipient_count = await count_recipients(audience_norm, filt)
    if recipient_count <= 0:
        raise ValueError("Нет получателей по выбранным фильтрам")

    is_scheduled = scheduled_at is not None
    status = "scheduled" if is_scheduled else "pending"
    label_clean = (label or "").strip()[:120]

    cta_text_clean = (cta_text or "").strip()[:64] or None
    cta_url_clean = (cta_url or "").strip()[:512] or None

    row = await db.pool.fetchrow(
        """
        INSERT INTO broadcast_runs (
            admin_user_id, audience, filter_json, channels_json,
            title, body, detail, telegram_text, template_key,
            recipient_count, status, scheduled_at, label,
            cta_text, cta_url
        )
        VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        RETURNING id
        """,
        admin_user_id,
        audience_norm,
        json.dumps(filt, ensure_ascii=False),
        json.dumps(ch, ensure_ascii=False),
        title_clean,
        body_clean,
        detail_clean,
        tg_clean,
        template_key,
        recipient_count,
        status,
        scheduled_at,
        label_clean,
        cta_text_clean,
        cta_url_clean,
    )
    run_id = int(row["id"])

    if not is_scheduled:
        schedule_broadcast_run(run_id)

    return {
        "ok": True,
        "runId": run_id,
        "recipientCount": recipient_count,
        "status": status,
        "scheduledAt": scheduled_at.isoformat() if scheduled_at else None,
    }


DAILY_BROADCAST_SYSTEM_ACTOR_ID = 0  # sentinel admin_user_id для авто-рассылок, не реальный юзер


async def start_daily_rotation_broadcast(rotation_index: int) -> dict:
    """Запускает один из DAILY_ROTATION_TEMPLATES по индексу (с переносом по модулю).
    Вызывается только из event_scheduler._fire_daily_rotation_broadcast."""
    template = DAILY_ROTATION_TEMPLATES[rotation_index % len(DAILY_ROTATION_TEMPLATES)]
    filter_data = {"minBalance": template["min_balance"]} if template["min_balance"] else None
    audience = "filtered" if filter_data else "all"

    return await start_broadcast(
        audience=audience,
        filter_data=filter_data,
        channels={"webapp": False, "telegram": True},
        title=template["label"],
        telegram_text=template["text"],
        template_key=f"daily_rotation:{rotation_index % len(DAILY_ROTATION_TEMPLATES)}",
        label=template["label"],
        admin_user_id=DAILY_BROADCAST_SYSTEM_ACTOR_ID,
        cta_text=DAILY_BROADCAST_CTA_TEXT,
        cta_url=daily_broadcast_cta_url(),
    )


async def list_scheduled_broadcasts(*, limit: int = 50, offset: int = 0) -> dict:
    rows = await db.pool.fetch(
        """
        SELECT id, admin_user_id, title, label, audience, recipient_count,
               status, scheduled_at, created_at
        FROM broadcast_runs
        WHERE status = 'scheduled'
        ORDER BY scheduled_at ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM broadcast_runs WHERE status = 'scheduled'"
        ) or 0
    )
    return {
        "items": [
            {
                "id": int(r["id"]),
                "adminUserId": int(r["admin_user_id"]),
                "title": r["title"],
                "label": r["label"] or "",
                "audience": r["audience"],
                "recipientCount": int(r["recipient_count"]),
                "status": r["status"],
                "scheduledAt": r["scheduled_at"].isoformat() if r["scheduled_at"] else None,
                "createdAt": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
    }


async def cancel_scheduled_broadcast(run_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow(
        "SELECT id, status, title FROM broadcast_runs WHERE id = $1",
        run_id,
    )
    if not row:
        raise ValueError("Рассылка не найдена")
    if row["status"] != "scheduled":
        raise ValueError(f"Рассылка уже в статусе «{row['status']}» — отмена невозможна")

    await db.pool.execute(
        """
        UPDATE broadcast_runs
        SET status = 'cancelled',
            error_message = 'Отменено администратором',
            finished_at = NOW()
        WHERE id = $1
        """,
        run_id,
    )
    return {"ok": True, "runId": run_id}
