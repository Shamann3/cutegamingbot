"""Топы для создателя: те же числа, что видят люди, и правка на месте.

Сообщения пишутся в chatchange (срок) и chatall (всё время).
Победы и проигрыши за всё время — users.wins и users.loose.
За день, неделю, месяц и год — user_games_day, сумма игр в топе лучших.
Донат — users.donate. Выиграно — users.winamount. Приглашения — users.refferals.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admin_audit import log_admin_action
from admin_auth import get_any_telegram_user_id
from admin_soft_restart import is_project_creator
from db import db
from stat_lens import (
    PERIODS,
    anchor_day,
    gained,
    period_bounds,
    phase,
    plan_period_total,
    seen_number,
)

router = APIRouter(prefix="/stat-board", tags=["stat-board"])

_MSK = timezone(timedelta(hours=3))
_READY = False
_MAX = 10**15

METRICS: dict[str, dict[str, Any]] = {
    "messages": {
        "id": "messages",
        "title": "Топ сообщений",
        "blurb": "Сообщения одной группы за выбранный срок.",
        "needsGroup": True,
        "periods": ["day", "week", "month", "year", "all"],
        "fields": [{"key": "messages", "label": "Сообщений"}],
        "rowUnit": "сообщений",
        "topLimit": 30,
        "season": "messages",
    },
    "players": {
        "id": "players",
        "title": "Лучшие игроки",
        "blurb": "Победы и проигрыши. За день, неделю, месяц и год — только игры этого срока.",
        "needsGroup": False,
        "periods": ["day", "week", "month", "year", "all"],
        "fields": [
            {"key": "wins", "label": "Победы"},
            {"key": "losses", "label": "Проигрыши"},
        ],
        "rowUnit": "сыгранных игр",
        "topLimit": 10,
        "season": "players",
    },
    "donors": {
        "id": "donors",
        "title": "Донатеры",
        "blurb": "Одно число на человека, без группы. В чате это «кут».",
        "needsGroup": False,
        "periods": ["all"],
        "fields": [{"key": "donate", "label": "Донат"}],
        "rowUnit": "кут",
        "topLimit": 10,
        "season": "donors",
    },
    "won": {
        "id": "won",
        "title": "Выиграно",
        "blurb": "Сколько кут человек выиграл. Группа не нужна.",
        "needsGroup": False,
        "periods": ["all"],
        "fields": [{"key": "winamount", "label": "Выиграно"}],
        "rowUnit": "кут выиграно",
        "topLimit": 10,
        "season": "won",
    },
    "invites": {
        "id": "invites",
        "title": "Приглашения",
        "blurb": "Сколько человек пригласил. Группа не нужна.",
        "needsGroup": False,
        "periods": ["all"],
        "fields": [{"key": "invites", "label": "Приглашено"}],
        "rowUnit": "чел.",
        "topLimit": 10,
        "season": "invites",
    },
}

_PERIOD_LABEL = {
    "day": "За день",
    "week": "За неделю",
    "month": "За месяц",
    "year": "За год",
    "all": "За всё время",
}


def _today() -> date:
    return datetime.now(_MSK).date()


def _require_creator(user_id: int) -> None:
    if not is_project_creator(user_id):
        raise HTTPException(status_code=403, detail="Только создатель проекта")


def _metric(metric: str) -> dict[str, Any]:
    found = METRICS.get(str(metric or "").strip())
    if not found:
        raise HTTPException(status_code=400, detail="Такой статистики нет")
    return found


def _period(metric: dict[str, Any], period: str) -> str:
    name = str(period or "all").strip().lower()
    if name not in metric["periods"] or name not in PERIODS:
        raise HTTPException(status_code=400, detail="Для этой статистики такого срока нет")
    return name


def _count_expr(alias: str) -> str:
    """Число из text, даже если в колонке встретится не цифра."""
    return (
        f"CASE WHEN {alias}.text::text ~ '^[0-9]+$' "
        f"THEN {alias}.text::text::bigint ELSE 0 END"
    )


def _wrote(result: Any) -> bool:
    parts = str(result or "").split()
    return len(parts) >= 2 and parts[0] == "UPDATE" and parts[1] != "0"


def _amount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=400, detail="Нужно целое число")
    if value < 0 or value > _MAX:
        raise HTTPException(status_code=400, detail="Число вне допустимого диапазона")
    return value


def _parse_day(raw: str) -> date:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Дата пишется как ГГГГ-ММ-ДД") from exc


class ValueBody(BaseModel):
    metric: str
    period: str = "all"
    chat_id: int = 0
    user_id: int = Field(ge=1)
    values: dict[str, int]
    model_config = {"extra": "forbid"}


class SeasonBody(BaseModel):
    metric: str
    chat_id: int = 0
    zero_from: str = ""
    zero_until: str = ""
    model_config = {"extra": "forbid"}


async def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_stat_season (
            metric TEXT NOT NULL,
            chat_id BIGINT NOT NULL DEFAULT 0,
            zero_from DATE NOT NULL,
            zero_until DATE NOT NULL,
            copied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (metric, chat_id)
        )
        """
    )
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_stat_snapshot (
            metric TEXT NOT NULL,
            chat_id BIGINT NOT NULL DEFAULT 0,
            user_id BIGINT NOT NULL,
            value BIGINT NOT NULL,
            PRIMARY KEY (metric, chat_id, user_id)
        )
        """
    )
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS user_games_day (
            user_id BIGINT NOT NULL,
            day DATE NOT NULL,
            games BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    await db.pool.execute(
        "ALTER TABLE user_games_day ADD COLUMN IF NOT EXISTS wins BIGINT NOT NULL DEFAULT 0"
    )
    await db.pool.execute(
        "ALTER TABLE user_games_day ADD COLUMN IF NOT EXISTS loose BIGINT NOT NULL DEFAULT 0"
    )
    _READY = True


def _catalog() -> dict:
    metrics = []
    for item in METRICS.values():
        metrics.append({
            **{key: item[key] for key in ("id", "title", "blurb", "needsGroup", "fields", "rowUnit", "topLimit")},
            "periods": [{"id": key, "label": _PERIOD_LABEL[key]} for key in item["periods"]],
        })
    return {"metrics": metrics}


async def _season_row(metric: str, chat_id: int):
    return await db.pool.fetchrow(
        """
        SELECT metric, chat_id, zero_from, zero_until, copied_at
        FROM epsilon_stat_season
        WHERE metric = $1 AND chat_id = $2
        """,
        metric,
        int(chat_id),
    )


async def _copied_map(snapshot_metric: str, chat_id: int) -> dict[int, int]:
    rows = await db.pool.fetch(
        """
        SELECT user_id, value
        FROM epsilon_stat_snapshot
        WHERE metric = $1 AND chat_id = $2
        """,
        snapshot_metric,
        int(chat_id),
    )
    return {int(row["user_id"]): int(row["value"] or 0) for row in rows}


def _season_payload(row, today: date) -> dict | None:
    if not row:
        return None
    stage = phase(today, row["zero_from"], row["zero_until"])
    notes = {
        "before": "Копия уже снята. До начала окна люди видят обычные числа.",
        "zero": "Сейчас люди видят нули. После конечной даты копия сложится с тем, что прибавилось.",
        "after": "Окно кончилось. Людям показывается копия плюс всё, что прибавилось с момента копии.",
    }
    return {
        "phase": stage,
        "zeroFrom": row["zero_from"].isoformat(),
        "zeroUntil": row["zero_until"].isoformat(),
        "copiedAt": row["copied_at"].isoformat() if row["copied_at"] else "",
        "note": notes.get(stage, ""),
    }


def _apply_seen(raw: int, copied: int | None, stage: str) -> dict:
    return {
        "raw": int(raw or 0),
        "copied": None if copied is None else int(copied),
        "gained": gained(raw, copied) if copied is not None else 0,
        "seen": seen_number(raw, copied, stage),
    }


async def _names(user_ids: list[int]) -> dict[int, dict]:
    if not user_ids:
        return {}
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, display_name, first_name
        FROM users
        WHERE user_id = ANY($1::bigint[])
        """,
        user_ids,
    )
    return {
        int(row["user_id"]): {
            "name": row["display_name"] or row["first_name"] or str(row["user_id"]),
            "username": row["username"] or "",
        }
        for row in rows
    }


async def _require_user(user_id: int) -> dict:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, display_name, first_name
        FROM users
        WHERE user_id = $1::bigint
        """,
        int(user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Такого пользователя нет")
    return {
        "userId": int(row["user_id"]),
        "name": row["display_name"] or row["first_name"] or str(row["user_id"]),
        "username": row["username"] or "",
    }


async def _require_chat(chat_id: int) -> dict:
    row = await db.pool.fetchrow(
        """
        SELECT chat_id, namechat, usernamechat
        FROM chat
        WHERE chat_id = $1::bigint
        """,
        int(chat_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Такой группы нет")
    return {
        "chatId": int(row["chat_id"]),
        "title": row["namechat"] or str(row["chat_id"]),
        "username": row["usernamechat"] or "",
    }


def _scope_chat(metric: dict[str, Any], chat_id: int) -> int:
    if metric["needsGroup"]:
        if not chat_id:
            raise HTTPException(status_code=400, detail="Сначала выберите группу")
        return int(chat_id)
    return 0


async def _message_rows(chat_id: int, period: str, today: date, limit: int):
    counted = _count_expr("c")
    if period == "all":
        rows = await db.pool.fetch(
            f"""
            SELECT c.user_id, COALESCE(SUM({counted}), 0)::bigint AS amount
            FROM chatall c
            WHERE c.chat_id = $1::bigint
            GROUP BY c.user_id
            HAVING COALESCE(SUM({counted}), 0) > 0
            ORDER BY amount DESC, c.user_id ASC
            LIMIT $2
            """,
            int(chat_id),
            limit,
        )
        total = int(await db.pool.fetchval(
            f"SELECT COALESCE(SUM({counted}), 0)::bigint FROM chatall c WHERE c.chat_id = $1::bigint",
            int(chat_id),
        ) or 0)
        return rows, total, "За всё время"
    start, end = period_bounds(period, today)
    rows = await db.pool.fetch(
        f"""
        SELECT c.user_id, COALESCE(SUM({counted}), 0)::bigint AS amount
        FROM chatchange c
        WHERE c.chat_id = $1::bigint AND c.date::date >= $2 AND c.date::date <= $3
        GROUP BY c.user_id
        HAVING COALESCE(SUM({counted}), 0) > 0
        ORDER BY amount DESC, c.user_id ASC
        LIMIT $4
        """,
        int(chat_id),
        start,
        end,
        limit,
    )
    total = int(await db.pool.fetchval(
        f"""
        SELECT COALESCE(SUM({counted}), 0)::bigint
        FROM chatchange c
        WHERE c.chat_id = $1::bigint AND c.date::date >= $2 AND c.date::date <= $3
        """,
        int(chat_id),
        start,
        end,
    ) or 0)
    label = _range_label(period, start, end)
    return rows, total, label


async def _player_rows(period: str, today: date, limit: int):
    if period == "all":
        rows = await db.pool.fetch(
            """
            SELECT user_id,
                   COALESCE(wins, 0)::bigint AS wins,
                   COALESCE(loose, 0)::bigint AS losses,
                   (COALESCE(wins, 0) + COALESCE(loose, 0))::bigint AS games
            FROM users
            WHERE (COALESCE(wins, 0) + COALESCE(loose, 0)) > 0
            ORDER BY games DESC, user_id ASC
            LIMIT $1
            """,
            limit,
        )
        return rows, "За всё время"
    start, end = period_bounds(period, today)
    rows = await db.pool.fetch(
        """
        SELECT user_id,
               COALESCE(SUM(wins), 0)::bigint AS wins,
               COALESCE(SUM(loose), 0)::bigint AS losses,
               COALESCE(SUM(games), 0)::bigint AS games
        FROM user_games_day
        WHERE day >= $1 AND day <= $2
        GROUP BY user_id
        HAVING COALESCE(SUM(games), 0) > 0
        ORDER BY games DESC, user_id ASC
        LIMIT $3
        """,
        start,
        end,
        limit,
    )
    return rows, _range_label(period, start, end)


def _range_label(period: str, start: date, end: date) -> str:
    if period == "day":
        return start.strftime("%d.%m.%Y")
    if start == end:
        return start.strftime("%d.%m.%Y")
    return f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}"


@router.get("/catalog")
async def stat_catalog(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    return _catalog()


def _period_title(period: str, today: date) -> str:
    if period == "all":
        return "За всё время"
    start, end = period_bounds(period, today)
    return _range_label(period, start, end)


def _group_item(row) -> dict:
    return {
        "chatId": int(row["chat_id"]),
        "title": row["title"] or str(row["chat_id"]),
        "username": row["username"] or "",
        "amount": int(row["amount"] or 0),
    }


async def _message_groups(period: str, today: date, query: str) -> list:
    counted = _count_expr("c")
    text = (query or "").strip().lstrip("@")
    if period == "all":
        source = "chatall"
        where_dates = ""
        args: list[Any] = []
    else:
        start, end = period_bounds(period, today)
        source = "chatchange"
        where_dates = "WHERE c.date::date >= $1 AND c.date::date <= $2"
        args = [start, end]
    if not text:
        rows = await db.pool.fetch(
            f"""
            SELECT c.chat_id,
                   COALESCE(MAX(ch.namechat), c.chat_id::text) AS title,
                   COALESCE(MAX(ch.usernamechat), '') AS username,
                   COALESCE(SUM({counted}), 0)::bigint AS amount
            FROM {source} c
            LEFT JOIN chat ch ON ch.chat_id = c.chat_id
            {where_dates}
            GROUP BY c.chat_id
            HAVING COALESCE(SUM({counted}), 0) > 0
            ORDER BY amount DESC, c.chat_id
            LIMIT 24
            """,
            *args,
        )
        return [_group_item(row) for row in rows]
    like = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    chat_id = None
    if text.lstrip("-").isdigit():
        try:
            chat_id = int(text)
        except ValueError:
            chat_id = None
    id_slot = len(args) + 1
    like_slot = len(args) + 2
    rows = await db.pool.fetch(
        f"""
        SELECT ch.chat_id,
               COALESCE(ch.namechat, ch.chat_id::text) AS title,
               COALESCE(ch.usernamechat, '') AS username,
               COALESCE(s.amount, 0)::bigint AS amount
        FROM chat ch
        LEFT JOIN (
            SELECT c.chat_id, COALESCE(SUM({counted}), 0)::bigint AS amount
            FROM {source} c
            {where_dates}
            GROUP BY c.chat_id
        ) s ON s.chat_id = ch.chat_id
        WHERE (${id_slot}::bigint IS NOT NULL AND ch.chat_id = ${id_slot}::bigint)
           OR ch.namechat ILIKE ${like_slot} ESCAPE '\\'
           OR ch.usernamechat ILIKE ${like_slot} ESCAPE '\\'
        ORDER BY amount DESC, title
        LIMIT 12
        """,
        *args,
        chat_id,
        like,
    )
    return [_group_item(row) for row in rows]


@router.get("/groups")
async def stat_groups(
    q: str = "",
    period: str = "day",
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    name = str(period or "day").strip().lower()
    if name not in PERIODS:
        raise HTTPException(status_code=400, detail="Для этой статистики такого срока нет")
    today = _today()
    items = await _message_groups(name, today, q)
    return {"period": name, "periodLabel": _period_title(name, today), "items": items}


@router.get("/board")
async def stat_board(
    metric: str,
    period: str = "all",
    chat_id: int = 0,
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    await ensure_tables()
    spec = _metric(metric)
    name = _period(spec, period)
    scope = _scope_chat(spec, chat_id)
    today = _today()
    chat = await _require_chat(scope) if spec["needsGroup"] else None
    season = await _season_row(spec["season"], scope)
    stage = phase(today, season["zero_from"], season["zero_until"]) if season else "off"
    copied = await _copied_map(spec["season"], scope) if season else {}
    limit = int(spec["topLimit"])
    rows_out = []
    total = None
    period_label = _PERIOD_LABEL[name]
    if spec["id"] == "messages":
        raw_rows, total, period_label = await _message_rows(scope, name, today, limit)
        for index, row in enumerate(raw_rows, start=1):
            uid = int(row["user_id"])
            raw = int(row["amount"] or 0)
            seen = seen_number(raw, copied.get(uid), stage if name == "all" else _period_stage(stage))
            rows_out.append({"place": index, "userId": uid, "raw": raw, "seen": seen, "messages": raw})
    elif spec["id"] == "players":
        raw_rows, period_label = await _player_rows(name, today, limit)
        for index, row in enumerate(raw_rows, start=1):
            uid = int(row["user_id"])
            games = int(row["games"] or 0)
            wins = int(row["wins"] or 0)
            losses = int(row["losses"] or 0)
            public = games
            seen = 0 if _period_stage(stage) == "zero" else public
            rows_out.append({
                "place": index,
                "userId": uid,
                "raw": public,
                "seen": seen,
                "wins": wins,
                "losses": losses,
                "games": games,
            })
    else:
        column = {"donors": "donate", "won": "winamount", "invites": "refferals"}[spec["id"]]
        raw_rows = await db.pool.fetch(
            f"""
            SELECT user_id, COALESCE({column}, 0)::bigint AS amount
            FROM users
            WHERE COALESCE({column}, 0) > 0
            ORDER BY amount DESC, user_id ASC
            LIMIT $1
            """,
            limit,
        )
        for index, row in enumerate(raw_rows, start=1):
            uid = int(row["user_id"])
            raw = int(row["amount"] or 0)
            rows_out.append({
                "place": index,
                "userId": uid,
                "raw": raw,
                "seen": seen_number(raw, copied.get(uid), stage),
            })
    names = await _names([item["userId"] for item in rows_out])
    for item in rows_out:
        who = names.get(item["userId"], {})
        item["name"] = who.get("name") or str(item["userId"])
        item["username"] = who.get("username") or ""
    return {
        "metric": spec["id"],
        "period": name,
        "periodLabel": period_label,
        "chat": chat,
        "total": total,
        "rowUnit": spec["rowUnit"],
        "rows": rows_out,
        "season": _season_payload(season, today),
    }


def _period_stage(stage: str) -> str:
    """Срок внутри окна тоже показывает ноль. После окна срок снова живой."""
    if stage == "zero":
        return "zero"
    return "off"


@router.get("/person")
async def stat_person(
    metric: str,
    user_id: int = Query(ge=1),
    period: str = "all",
    chat_id: int = 0,
    actor_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(actor_id)
    await ensure_tables()
    spec = _metric(metric)
    name = _period(spec, period)
    scope = _scope_chat(spec, chat_id)
    if spec["needsGroup"]:
        await _require_chat(scope)
    person = await _require_user(user_id)
    today = _today()
    season = await _season_row(spec["season"], scope)
    stage = phase(today, season["zero_from"], season["zero_until"]) if season else "off"
    fields = []
    if spec["id"] == "messages":
        raw = await _message_raw(scope, int(user_id), name, today)
        copied = await _one_copy("messages", scope, int(user_id)) if season and name == "all" else None
        view_stage = stage if name == "all" else _period_stage(stage)
        fields.append({"key": "messages", "label": "Сообщений", **_apply_seen(raw, copied, view_stage)})
    elif spec["id"] == "players":
        wins, losses, games = await _player_raw(int(user_id), name, today)
        if name == "all":
            win_copy = await _one_copy("players_wins", 0, int(user_id)) if season else None
            loss_copy = await _one_copy("players_losses", 0, int(user_id)) if season else None
            fields.append({"key": "wins", "label": "Победы", **_apply_seen(wins, win_copy, stage)})
            fields.append({"key": "losses", "label": "Проигрыши", **_apply_seen(losses, loss_copy, stage)})
        else:
            view_stage = _period_stage(stage)
            fields.append({"key": "wins", "label": "Победы", **_apply_seen(wins, None, view_stage)})
            fields.append({"key": "losses", "label": "Проигрыши", **_apply_seen(losses, None, view_stage)})
        fields.append({
            "key": "games",
            "label": "В топе сыграно",
            "raw": games,
            "copied": None,
            "gained": 0,
            "seen": 0 if view_stage_of(stage, name) == "zero" else games,
        })
    else:
        column = {"donors": "donate", "won": "winamount", "invites": "refferals"}[spec["id"]]
        raw = int(await db.pool.fetchval(
            f"SELECT COALESCE({column}, 0)::bigint FROM users WHERE user_id = $1::bigint",
            int(user_id),
        ) or 0)
        copied = await _one_copy(spec["season"], 0, int(user_id)) if season else None
        fields.append({
            "key": spec["fields"][0]["key"],
            "label": spec["fields"][0]["label"],
            **_apply_seen(raw, copied, stage),
        })
    return {
        **person,
        "metric": spec["id"],
        "period": name,
        "fields": fields,
        "season": _season_payload(season, today),
    }


def view_stage_of(stage: str, period: str) -> str:
    if period == "all":
        return stage
    return _period_stage(stage)


async def _one_copy(metric: str, chat_id: int, user_id: int) -> int:
    value = await db.pool.fetchval(
        """
        SELECT value FROM epsilon_stat_snapshot
        WHERE metric = $1 AND chat_id = $2 AND user_id = $3::bigint
        """,
        metric,
        int(chat_id),
        int(user_id),
    )
    return int(value or 0)


async def _message_raw(chat_id: int, user_id: int, period: str, today: date) -> int:
    counted = _count_expr("c")
    if period == "all":
        return int(await db.pool.fetchval(
            f"""
            SELECT COALESCE(SUM({counted}), 0)::bigint FROM chatall c
            WHERE c.chat_id = $1::bigint AND c.user_id = $2::bigint
            """,
            int(chat_id),
            int(user_id),
        ) or 0)
    start, end = period_bounds(period, today)
    return int(await db.pool.fetchval(
        f"""
        SELECT COALESCE(SUM({counted}), 0)::bigint
        FROM chatchange c
        WHERE c.chat_id = $1::bigint AND c.user_id = $2::bigint
          AND c.date::date >= $3 AND c.date::date <= $4
        """,
        int(chat_id),
        int(user_id),
        start,
        end,
    ) or 0)


async def _player_raw(user_id: int, period: str, today: date) -> tuple[int, int, int]:
    if period == "all":
        row = await db.pool.fetchrow(
            """
            SELECT COALESCE(wins, 0)::bigint AS wins, COALESCE(loose, 0)::bigint AS losses
            FROM users WHERE user_id = $1::bigint
            """,
            int(user_id),
        )
        wins = int(row["wins"] or 0) if row else 0
        losses = int(row["losses"] or 0) if row else 0
        return wins, losses, wins + losses
    start, end = period_bounds(period, today)
    row = await db.pool.fetchrow(
        """
        SELECT COALESCE(SUM(wins), 0)::bigint AS wins,
               COALESCE(SUM(loose), 0)::bigint AS losses,
               COALESCE(SUM(games), 0)::bigint AS games
        FROM user_games_day
        WHERE user_id = $1::bigint AND day >= $2 AND day <= $3
        """,
        int(user_id),
        start,
        end,
    )
    return int(row["wins"] or 0), int(row["losses"] or 0), int(row["games"] or 0)


@router.post("/value")
async def stat_value(body: ValueBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    spec = _metric(body.metric)
    name = _period(spec, body.period)
    scope = _scope_chat(spec, body.chat_id)
    if spec["needsGroup"]:
        await _require_chat(scope)
    await _require_user(body.user_id)
    allowed = {field["key"] for field in spec["fields"]}
    clean = {}
    for key, value in body.values.items():
        if key not in allowed:
            raise HTTPException(status_code=400, detail="Это поле этой статистике не принадлежит")
        clean[key] = _amount(value)
    if set(clean) != allowed:
        raise HTTPException(status_code=400, detail="Заполните каждое число статистики")
    today = _today()
    if spec["id"] == "messages":
        await _set_messages(scope, int(body.user_id), name, today, clean["messages"])
    elif spec["id"] == "players":
        await _set_players(int(body.user_id), name, today, clean["wins"], clean["losses"])
    elif spec["id"] == "donors":
        await _set_column("donate", int(body.user_id), clean["donate"])
    elif spec["id"] == "won":
        await _set_column("winamount", int(body.user_id), clean["winamount"])
    else:
        await _set_column("refferals", int(body.user_id), clean["invites"])
    await log_admin_action(
        int(user_id),
        "stat_set",
        target_type="user",
        target_id=str(body.user_id),
        details={"metric": spec["id"], "period": name, "chatId": scope, "values": clean},
    )
    return {"ok": True}


async def _set_column(column: str, user_id: int, value: int) -> None:
    if column not in {"donate", "winamount", "refferals", "wins", "loose"}:
        raise HTTPException(status_code=400, detail="Это поле нельзя записать")
    result = await db.pool.execute(
        f"UPDATE users SET {column} = $2::bigint WHERE user_id = $1::bigint",
        int(user_id),
        int(value),
    )
    if not _wrote(result):
        raise HTTPException(status_code=404, detail="Такого пользователя нет")


async def _set_messages(chat_id: int, user_id: int, period: str, today: date, target: int) -> None:
    if period == "all":
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM chatall WHERE chat_id = $1::bigint AND user_id = $2::bigint",
                    int(chat_id),
                    int(user_id),
                )
                await connection.execute(
                    """
                    INSERT INTO chatall (chat_id, user_id, text)
                    VALUES ($1::bigint, $2::bigint, $3::bigint)
                    """,
                    int(chat_id),
                    int(user_id),
                    int(target),
                )
        return
    start, end = period_bounds(period, today)
    counted = _count_expr("c")
    rows = await db.pool.fetch(
        f"""
        SELECT c.date::date AS date, COALESCE(SUM({counted}), 0)::bigint AS amount
        FROM chatchange c
        WHERE c.chat_id = $1::bigint AND c.user_id = $2::bigint
          AND c.date::date >= $3 AND c.date::date <= $4
        GROUP BY c.date::date
        """,
        int(chat_id),
        int(user_id),
        start,
        end,
    )
    have = []
    for row in rows:
        day = row["date"]
        if isinstance(day, datetime):
            day = day.date()
        have.append((day, int(row["amount"] or 0)))
    try:
        plan = plan_period_total(have, anchor_day(period, today), target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            for day, amount in plan:
                await _write_message_day(connection, chat_id, user_id, day, amount)


async def _write_message_day(connection, chat_id: int, user_id: int, day: date, total: int) -> None:
    rows = await connection.fetch(
        """
        SELECT ctid::text AS id
        FROM chatchange
        WHERE user_id = $1::bigint AND chat_id = $2::bigint AND date::date = $3
        """,
        int(user_id),
        int(chat_id),
        day,
    )
    if not rows:
        await connection.execute(
            """
            INSERT INTO chatchange (user_id, chat_id, date, text)
            VALUES ($1::bigint, $2::bigint, $3, $4::bigint)
            """,
            int(user_id),
            int(chat_id),
            day,
            int(total),
        )
        return
    first = rows[0]["id"]
    await connection.execute(
        "UPDATE chatchange SET text = $2::bigint WHERE ctid = $1::tid",
        first,
        int(total),
    )
    if len(rows) > 1:
        await connection.execute(
            """
            UPDATE chatchange SET text = 0
            WHERE user_id = $1::bigint AND chat_id = $2::bigint AND date::date = $3 AND ctid <> $4::tid
            """,
            int(user_id),
            int(chat_id),
            day,
            first,
        )


async def _set_players(user_id: int, period: str, today: date, wins: int, losses: int) -> None:
    if period == "all":
        await _set_column("wins", user_id, wins)
        await _set_column("loose", user_id, losses)
        return
    start, end = period_bounds(period, today)
    spot = anchor_day(period, today)
    games = int(wins) + int(losses)
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                UPDATE user_games_day
                SET wins = 0, loose = 0, games = 0
                WHERE user_id = $1::bigint AND day >= $2 AND day <= $3 AND day <> $4
                """,
                int(user_id),
                start,
                end,
                spot,
            )
            await connection.execute(
                """
                INSERT INTO user_games_day (user_id, day, games, wins, loose)
                VALUES ($1::bigint, $2, $3::bigint, $4::bigint, $5::bigint)
                ON CONFLICT (user_id, day) DO UPDATE
                SET games = EXCLUDED.games, wins = EXCLUDED.wins, loose = EXCLUDED.loose
                """,
                int(user_id),
                spot,
                games,
                int(wins),
                int(losses),
            )


@router.post("/season")
async def stat_season_copy(body: SeasonBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    spec = _metric(body.metric)
    scope = _scope_chat(spec, body.chat_id)
    if spec["needsGroup"]:
        await _require_chat(scope)
    start = _parse_day(body.zero_from)
    end = _parse_day(body.zero_until)
    if end < start:
        raise HTTPException(status_code=400, detail="Дата конца раньше даты начала")
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                "DELETE FROM epsilon_stat_snapshot WHERE metric LIKE $1 AND chat_id = $2",
                f"{spec['season']}%",
                scope,
            )
            await _copy_snapshot(connection, spec, scope)
            await connection.execute(
                """
                INSERT INTO epsilon_stat_season (metric, chat_id, zero_from, zero_until, copied_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (metric, chat_id) DO UPDATE
                SET zero_from = EXCLUDED.zero_from,
                    zero_until = EXCLUDED.zero_until,
                    copied_at = NOW()
                """,
                spec["season"],
                scope,
                start,
                end,
            )
    await log_admin_action(
        int(user_id),
        "stat_copy",
        target_type="stat",
        target_id=spec["id"],
        details={"chatId": scope, "zeroFrom": start.isoformat(), "zeroUntil": end.isoformat()},
    )
    return {"ok": True}


async def _copy_snapshot(connection, spec: dict, chat_id: int) -> None:
    if spec["id"] == "messages":
        counted = _count_expr("c")
        await connection.execute(
            f"""
            INSERT INTO epsilon_stat_snapshot (metric, chat_id, user_id, value)
            SELECT 'messages', c.chat_id, c.user_id, COALESCE(SUM({counted}), 0)::bigint
            FROM chatall c
            WHERE c.chat_id = $1::bigint
            GROUP BY c.chat_id, c.user_id
            HAVING COALESCE(SUM({counted}), 0) <> 0
            """,
            int(chat_id),
        )
        return
    if spec["id"] == "players":
        await connection.execute(
            """
            INSERT INTO epsilon_stat_snapshot (metric, chat_id, user_id, value)
            SELECT 'players_wins', 0, user_id, COALESCE(wins, 0)::bigint
            FROM users
            WHERE COALESCE(wins, 0) <> 0 OR COALESCE(loose, 0) <> 0
            """
        )
        await connection.execute(
            """
            INSERT INTO epsilon_stat_snapshot (metric, chat_id, user_id, value)
            SELECT 'players_losses', 0, user_id, COALESCE(loose, 0)::bigint
            FROM users
            WHERE COALESCE(wins, 0) <> 0 OR COALESCE(loose, 0) <> 0
            """
        )
        return
    column = {"donors": "donate", "won": "winamount", "invites": "refferals"}[spec["id"]]
    await connection.execute(
        f"""
        INSERT INTO epsilon_stat_snapshot (metric, chat_id, user_id, value)
        SELECT $1, 0, user_id, COALESCE({column}, 0)::bigint
        FROM users
        WHERE COALESCE({column}, 0) <> 0
        """,
        spec["season"],
    )


@router.delete("/season")
async def stat_season_clear(body: SeasonBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    spec = _metric(body.metric)
    scope = _scope_chat(spec, body.chat_id)
    await db.pool.execute(
        "DELETE FROM epsilon_stat_season WHERE metric = $1 AND chat_id = $2",
        spec["season"],
        scope,
    )
    await db.pool.execute(
        "DELETE FROM epsilon_stat_snapshot WHERE metric LIKE $1 AND chat_id = $2",
        f"{spec['season']}%",
        scope,
    )
    await log_admin_action(
        int(user_id),
        "stat_copy_clear",
        target_type="stat",
        target_id=spec["id"],
        details={"chatId": scope},
    )
    return {"ok": True}
