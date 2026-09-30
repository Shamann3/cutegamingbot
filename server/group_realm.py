"""Контур администраторов групп.

Официальная группа, должность и права решают, что человек видит.
Сотрудник проекта этим местом не становится.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_any_telegram_user_id
from config import owner_user_ids
from db import db

router = APIRouter(prefix="/group-realm", tags=["group-realm"])

_READY = False

ALL_RIGHTS = (
    "view_members",
    "view_archive",
    "view_analytics",
    "punish_mute",
    "punish_ban",
    "punish_kick",
    "punish_warn",
    "punish_voice",
    "manage_positions",
    # Права Telegram в чате (без передачи владения).
    "can_manage_chat",
    "can_change_info",
    "can_delete_messages",
    "can_restrict_members",
    "can_invite_users",
    "can_pin_messages",
    "can_manage_topics",
    "can_manage_video_chats",
    "can_promote_members",
    "can_post_messages",
    "can_edit_messages",
    "can_send_messages",
    "can_send_photos",
    "can_send_videos",
    "can_send_audios",
    "can_send_documents",
    "can_send_voice_notes",
    "can_send_video_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
)

ACTION_RIGHT = {
    "mute": "punish_mute",
    "unmute": "punish_mute",
    "kick": "punish_kick",
    "warn": "punish_warn",
    "ban": "punish_ban",
    "unban": "punish_ban",
    "voice": "punish_voice",
    "unvoice": "punish_voice",
}

LOCAL_ACTIONS = frozenset(ACTION_RIGHT)

PRESETS: tuple[tuple[str, int, tuple[str, ...], bool], ...] = (
    ("Создатель группы", 5, ALL_RIGHTS, False),
    (
        "Администратор",
        3,
        tuple(r for r in ALL_RIGHTS if r != "manage_positions"),
        True,
    ),
    (
        "Модератор",
        2,
        ("view_members", "view_archive", "punish_mute", "punish_kick", "punish_warn"),
        True,
    ),
    ("Хелпер", 1, ("view_members", "punish_warn"), True),
)

KIND_POST = "post"
KIND_MEMBER = "member"
KIND_SPAMBLOCK = "spamblock"
KINDS = frozenset({KIND_POST, KIND_MEMBER, KIND_SPAMBLOCK})
SPAMBLOCK_PREFIX = "спам блок"

# То, что обычный участник и так может отправлять. Наказаний здесь нет.
MEMBER_RIGHTS = (
    "can_send_messages",
    "can_send_photos",
    "can_send_videos",
    "can_send_audios",
    "can_send_documents",
    "can_send_voice_notes",
    "can_send_video_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
)

# Единственный флаг Telegram, который оставляет человека администратором
# без бана, удаления и назначения. Без него спам-блок снова не пускает писать.
# Снятие — все флаги False.
_TG_ADMIN_FLAGS = (
    "can_manage_chat",
    "can_delete_messages",
    "can_manage_video_chats",
    "can_restrict_members",
    "can_promote_members",
    "can_change_info",
    "can_invite_users",
    "can_pin_messages",
    "can_manage_topics",
    "can_post_messages",
    "can_edit_messages",
    "can_post_stories",
    "can_edit_stories",
    "can_delete_stories",
)


def action_right(action: str) -> str | None:
    return ACTION_RIGHT.get((action or "").strip().lower())


def cabinet_pages(rights: list[str] | set[str], *, creator: bool = False) -> list[str]:
    """Страницы кабинета группы, которые открывает набор прав.

    Обзор и «Ещё» есть всегда. «Активность» открывается от списка людей,
    от цифр или от любого наказания.
    """
    have = set(rights or [])
    pages = ["overview"]
    sees_activity = (
        creator
        or "view_members" in have
        or "view_analytics" in have
        or any(str(item).startswith("punish_") for item in have)
    )
    if sees_activity:
        pages.append("activity")
    if creator or "view_archive" in have:
        pages.append("archive")
    if creator or "manage_positions" in have:
        pages.append("rights")
    pages.append("more")
    return pages


def activity_window(period: str, today):
    """Начало, конец и шаг графика: день, неделя, календарный месяц или год."""
    from datetime import timedelta

    name = period if period in {"day", "week", "month", "year"} else "month"
    if name == "day":
        return today, today, "day"
    if name == "week":
        return today - timedelta(days=6), today, "day"
    if name == "year":
        return today.replace(month=1, day=1), today, "month"
    return today.replace(day=1), today, "day"


def previous_window(period: str, start, end):
    """Такой же прошлый отрезок, чтобы сравнить с текущим без выдуманных процентов."""
    from datetime import timedelta

    if period == "day":
        day = start - timedelta(days=1)
        return day, day
    if period == "week":
        return start - timedelta(days=7), start - timedelta(days=1)
    if period == "year":
        return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
    previous_end = start - timedelta(days=1)
    return previous_end.replace(day=1), previous_end


def activity_buckets(start, end, grain: str) -> list:
    """Все точки графика, включая дни и месяцы без сообщений."""
    from datetime import timedelta

    points = []
    if grain == "month":
        cursor = start.replace(day=1)
        last = end.replace(day=1)
        while cursor <= last:
            points.append(cursor)
            month = cursor.month + 1
            year = cursor.year + (1 if month > 12 else 0)
            next_month = 1 if month > 12 else month
            cursor = cursor.replace(year=year, month=next_month, day=1)
        return points
    cursor = start
    while cursor <= end:
        points.append(cursor)
        cursor += timedelta(days=1)
    return points


def rights_allow(rights: list[str] | set[str], action: str) -> bool:
    need = action_right(action)
    return bool(need) and need in set(rights or [])


def may_edit_position(actor_rank: int, position_rank: int, *, creator: bool) -> bool:
    """Создатель правит любую должность. Остальные — только строго младшую."""
    if creator:
        return True
    return int(position_rank) < int(actor_rank)


def editable_rights(rank: int, requested: list[str] | set[str], *, creator: bool) -> list[str]:
    """Должность создателя группы всегда держит полный набор прав."""
    if int(rank) >= 5:
        return list(ALL_RIGHTS)
    clean = _rights(requested)
    if not creator:
        clean = [item for item in clean if item != "manage_positions"]
    return clean


def rights_for_kind(kind: str, rank: int, requested: list[str] | set[str], *, creator: bool) -> list[str]:
    """Спам-блок — пустой набор. Ранг 0 и обычный пользователь — только отправка."""
    name = kind if kind in KINDS else KIND_POST
    if name == KIND_SPAMBLOCK:
        return []
    if name == KIND_MEMBER or int(rank) <= 0:
        wanted = set(_rights(requested))
        chosen = [item for item in MEMBER_RIGHTS if item in wanted]
        return chosen or list(MEMBER_RIGHTS)
    return editable_rights(int(rank), requested, creator=creator)


def stored_rank(kind: str, rank: int) -> int:
    """Обычный пользователь и спам-блок всегда на ранге 0: их можно наказать как участника."""
    if kind in {KIND_MEMBER, KIND_SPAMBLOCK}:
        return 0
    return max(0, min(4, int(rank)))


def term_bounds(start_raw: str | None, end_raw: str | None) -> tuple[datetime | None, datetime | None, str | None]:
    """Срок спам-блока. Конец обязателен. Даты — календарные, конец дня по UTC."""
    try:
        start = _parse_day(start_raw, end=False) if (start_raw or "").strip() else None
        end = _parse_day(end_raw, end=True) if (end_raw or "").strip() else None
    except ValueError:
        return None, None, "Дата пишется как ГГГГ-ММ-ДД"
    if end is None:
        return None, None, "Укажите, по какое число держать спам-блок"
    if start and start > end:
        return None, None, "Дата начала позже даты конца"
    return start, end, None


def _parse_day(value: str | None, *, end: bool) -> datetime | None:
    raw = (value or "").strip()[:10]
    if not raw:
        return None
    day = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end:
        return day.replace(hour=23, minute=59, second=59)
    return day


def clean_prefix(value: str) -> tuple[str, str | None]:
    text = " ".join((value or "").split())
    if len(text) > 16:
        return "", "Префикс в Telegram не длиннее 16 символов"
    return text, None


def chat_title(kind: str, title: str, stored: str, requested: str) -> tuple[str, str | None]:
    """Префикс в группе: то, что вписали, иначе префикс должности, иначе её название."""
    if kind == KIND_MEMBER:
        return "", None
    asked, error = clean_prefix(requested)
    if error:
        return "", error
    if asked:
        return asked, None
    saved, saved_error = clean_prefix(stored)
    if saved_error:
        saved = " ".join((stored or "").split())[:16]
    if saved:
        return saved, None
    if kind == KIND_SPAMBLOCK:
        return SPAMBLOCK_PREFIX, None
    return " ".join((title or "").split())[:16], None


def may_punish_rank(actor_rank: int, target_rank: int, *, same_person: bool) -> str | None:
    """Наказать можно только того, кто строго младше в этой группе.

    Нет должности — ранг 0, такой человек младше любого администратора.
    Равный и старший не проходят. Себя наказать нельзя.
    """
    if same_person:
        return "Себя наказать нельзя"
    if int(target_rank) >= int(actor_rank):
        return "Наказать можно только того, кто младше вашей должности в этой группе"
    return None


async def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_official_groups (
            chat_id BIGINT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            is_official BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS epsilon_positions (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            rank INT NOT NULL,
            rights JSONB NOT NULL DEFAULT '[]',
            accepting BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS epsilon_positions_chat_idx
            ON epsilon_positions (chat_id, rank DESC);
        CREATE TABLE IF NOT EXISTS epsilon_seats (
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            position_id INT NOT NULL,
            appointed_by BIGINT,
            reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, chat_id)
        );
        CREATE TABLE IF NOT EXISTS epsilon_group_applications (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            position_id INT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            rules_read BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT NOT NULL DEFAULT '',
            reviewer_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS epsilon_group_app_user_idx
            ON epsilon_group_applications (user_id, status);
        CREATE TABLE IF NOT EXISTS epsilon_group_keys (
            user_id BIGINT PRIMARY KEY,
            key_hash TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    await db.pool.execute(
        """
        ALTER TABLE epsilon_positions ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'post';
        ALTER TABLE epsilon_positions ADD COLUMN IF NOT EXISTS prefix TEXT NOT NULL DEFAULT '';
        ALTER TABLE epsilon_seats ADD COLUMN IF NOT EXISTS prefix TEXT NOT NULL DEFAULT '';
        ALTER TABLE epsilon_seats ADD COLUMN IF NOT EXISTS term_start TIMESTAMPTZ;
        ALTER TABLE epsilon_seats ADD COLUMN IF NOT EXISTS term_end TIMESTAMPTZ;
        CREATE TABLE IF NOT EXISTS epsilon_realm_log (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            user_id BIGINT,
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            actor_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS epsilon_realm_log_chat_idx
            ON epsilon_realm_log (chat_id, created_at DESC);
        """
    )
    chats = await db.pool.fetch(
        "SELECT chat_id FROM epsilon_official_groups WHERE is_official"
    )
    for row in chats:
        await _ensure_builtin_posts(int(row["chat_id"]))
    _READY = True


def _is_creator(user_id: int) -> bool:
    return int(user_id) in set(owner_user_ids())


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_key() -> tuple[str, str]:
    plain = secrets.token_urlsafe(18)
    return plain, _hash_key(plain)


async def _issue_key(user_id: int) -> str:
    plain, hashed = _new_key()
    await db.pool.execute(
        """
        INSERT INTO epsilon_group_keys (user_id, key_hash)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET key_hash = EXCLUDED.key_hash, updated_at = NOW()
        """,
        int(user_id),
        hashed,
    )
    return plain


async def _realm_log(chat_id: int, user_id: int | None, action: str, detail: str, actor_id: int | None) -> None:
    await db.pool.execute(
        """
        INSERT INTO epsilon_realm_log (chat_id, user_id, action, detail, actor_id)
        VALUES ($1, $2, $3, $4, $5)
        """,
        int(chat_id),
        int(user_id) if user_id else None,
        action,
        (detail or "")[:500],
        int(actor_id) if actor_id else None,
    )


async def sweep_expired_spamblocks() -> int:
    """Снимает спам-блок, когда срок вышел, и пишет это в журнал группы."""
    try:
        await ensure_tables()
    except Exception:
        return 0
    rows = await db.pool.fetch(
        """
        SELECT s.user_id, s.chat_id, p.title, s.term_end
        FROM epsilon_seats s
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE p.kind = $1
          AND s.term_end IS NOT NULL
          AND s.term_end <= NOW()
        """,
        KIND_SPAMBLOCK,
    )
    removed = 0
    for row in rows:
        await db.pool.execute(
            "DELETE FROM epsilon_seats WHERE user_id = $1 AND chat_id = $2",
            int(row["user_id"]),
            int(row["chat_id"]),
        )
        note = await _apply_chat_title(int(row["chat_id"]), int(row["user_id"]), "", rights=None)
        end = row["term_end"]
        end_label = end.date().isoformat() if end else ""
        await _realm_log(
            int(row["chat_id"]),
            int(row["user_id"]),
            "spamblock_expired",
            f"Срок спам-блока кончился {end_label}. Должность «{row['title']}» снята. {note}".strip(),
            None,
        )
        removed += 1
    return removed


def _promote_body(chat_id: int, user_id: int, rights: list[str] | None) -> dict:
    """None снимает админку. Пустой список оставляет администратора без наказаний — так ставится префикс."""
    body = {"chat_id": int(chat_id), "user_id": int(user_id), "is_anonymous": False}
    granted = set(rights or [])
    for flag in _TG_ADMIN_FLAGS:
        body[flag] = flag in granted
    if rights is not None and not any(body[flag] for flag in _TG_ADMIN_FLAGS):
        body["can_manage_chat"] = True
    return body


async def _telegram_call(method: str, payload: dict) -> tuple[bool, str, dict]:
    try:
        from config import BOT_TOKEN
    except Exception:
        return False, "Бот не настроен", {}
    if not BOT_TOKEN:
        return False, "Бот не настроен", {}
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
    except Exception:
        return False, "Telegram не ответил", {}
    if isinstance(data, dict) and data.get("ok"):
        return True, "", data
    description = ""
    if isinstance(data, dict):
        description = str(data.get("description") or "")[:180]
    return False, description or "Telegram отказал", data if isinstance(data, dict) else {}


async def _apply_chat_title(chat_id: int, user_id: int, title: str, *, rights: list[str] | None) -> str:
    """Ставит или снимает админку и префикс в группе. Токен в ответ не попадает.

    rights=None снимает админку: человек остаётся в чате обычным участником.
    """
    ok, err, _data = await _telegram_call(
        "promoteChatMember",
        _promote_body(chat_id, user_id, rights),
    )
    if not ok:
        if rights is None:
            return f"Должность в панели снята. В группе админка могла остаться: {err}"
        return f"Место в панели есть. Префикс в группе не встал: {err}"
    if rights is None:
        return "В группе админка и префикс сняты. Человек остаётся обычным участником."
    text = " ".join((title or "").split())[:16]
    if not text:
        return "Админка в группе обновлена."
    titled, title_err, _title_data = await _telegram_call(
        "setChatAdministratorCustomTitle",
        {"chat_id": int(chat_id), "user_id": int(user_id), "custom_title": text},
    )
    if not titled:
        return f"Админка в группе есть. Префикс «{text}» не встал: {title_err}"
    return f"В группе стоит префикс «{text}»."


async def _telegram_member(chat_id: int, user_id: int) -> dict:
    ok, err, data = await _telegram_call("getChatMember", {"chat_id": int(chat_id), "user_id": int(user_id)})
    if not ok:
        return {
            "ok": False,
            "note": f"Telegram не показал участника: {err}. Срок спам-блока Bot API не сообщает — дату конца задаёте вы.",
        }
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return {"ok": False, "note": "Telegram не показал участника. Дату конца задаёте вы."}
    status = str(result.get("status") or "")
    until = result.get("until_date")
    until_iso = ""
    if isinstance(until, int) and until > 0:
        until_iso = datetime.fromtimestamp(until, tz=timezone.utc).date().isoformat()
    if status == "restricted" and until_iso:
        note = f"Telegram ограничивает человека до {until_iso}. Это ограничение чата, не глобальный спам-блок. Дату всё равно подтверждаете вы."
    elif status == "restricted":
        note = "Telegram ограничивает человека без даты конца. Глобальный спам-блок Bot API не показывает — дату задаёте вы."
    elif status == "administrator":
        note = "Человек уже администратор этого чата. Глобальный спам-блок отсюда не виден — срок пишете вы."
    elif status == "kicked":
        note = "Человек исключён из чата. Сначала верните его, потом назначайте спам-блок."
    else:
        note = "Ограничения в ответе Telegram нет. Глобальный спам-блок Bot API не сообщает — срок от и до задаёте вы."
    return {"ok": True, "status": status, "until": until_iso, "note": note}


def _rights(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            raw = []
    else:
        raw = []
    allowed = set(ALL_RIGHTS)
    return [str(item) for item in raw if str(item) in allowed]


def _position_out(row) -> dict:
    kind = row["kind"] if row["kind"] in KINDS else KIND_POST
    rank = int(row["rank"])
    return {
        "id": int(row["id"]),
        "title": row["title"],
        "rank": rank,
        "kind": kind,
        "prefix": row["prefix"] or "",
        "rights": rights_for_kind(kind, rank, _rights(row["rights"]), creator=True),
        "accepting": bool(row["accepting"]),
    }


async def _ensure_builtin_posts(chat_id: int) -> None:
    """Ранг 0 — обычный участник. Спам-блок — то же место без наказаний, со сроком."""
    member = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_positions WHERE chat_id = $1 AND kind = $2",
        int(chat_id),
        KIND_MEMBER,
    )
    if not member:
        await db.pool.execute(
            """
            INSERT INTO epsilon_positions (chat_id, title, rank, rights, accepting, kind, prefix)
            VALUES ($1, $2, 0, $3::jsonb, FALSE, $4, '')
            """,
            int(chat_id),
            "Обычный пользователь",
            json.dumps(list(MEMBER_RIGHTS)),
            KIND_MEMBER,
        )
    spam = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_positions WHERE chat_id = $1 AND kind = $2",
        int(chat_id),
        KIND_SPAMBLOCK,
    )
    if not spam:
        await db.pool.execute(
            """
            INSERT INTO epsilon_positions (chat_id, title, rank, rights, accepting, kind, prefix)
            VALUES ($1, $2, 0, '[]'::jsonb, FALSE, $3, $4)
            """,
            int(chat_id),
            "Спам блок",
            KIND_SPAMBLOCK,
            SPAMBLOCK_PREFIX,
        )


async def _seed_positions(chat_id: int) -> None:
    count = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM epsilon_positions WHERE chat_id = $1",
        int(chat_id),
    )
    if int(count or 0) == 0:
        for title, rank, rights, accepting in PRESETS:
            await db.pool.execute(
                """
                INSERT INTO epsilon_positions (chat_id, title, rank, rights, accepting, kind, prefix)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, '')
                """,
                int(chat_id),
                title,
                int(rank),
                json.dumps(list(rights)),
                bool(accepting),
                KIND_POST,
            )
    await _ensure_builtin_posts(int(chat_id))


async def seats_for(user_id: int) -> list[dict]:
    """Группы, куда этот человек может войти, и права должности."""
    try:
        await ensure_tables()
    except Exception:
        return []
    if _is_creator(user_id):
        rows = await db.pool.fetch(
            """
            SELECT chat_id, title, username
            FROM epsilon_official_groups
            WHERE is_official = TRUE
            ORDER BY title, chat_id
            """
        )
        return [
            {
                "chatId": int(r["chat_id"]),
                "title": r["title"] or str(r["chat_id"]),
                "username": r["username"] or "",
                "position": "Создатель",
                "rank": 5,
                "rights": list(ALL_RIGHTS),
            }
            for r in rows
        ]
    rows = await db.pool.fetch(
        """
        SELECT s.chat_id, g.title, g.username, p.title AS position, p.rank, p.rights, p.kind
        FROM epsilon_seats s
        JOIN epsilon_official_groups g ON g.chat_id = s.chat_id AND g.is_official
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1
          AND (s.term_end IS NULL OR s.term_end > NOW())
        ORDER BY p.rank DESC, g.title
        """,
        int(user_id),
    )
    return [
        {
            "chatId": int(r["chat_id"]),
            "title": r["title"] or str(r["chat_id"]),
            "username": r["username"] or "",
            "position": r["position"],
            "rank": int(r["rank"]),
            "kind": r["kind"] or KIND_POST,
            "rights": rights_for_kind(r["kind"] or KIND_POST, int(r["rank"]), _rights(r["rights"]), creator=False),
        }
        for r in rows
    ]


async def _seat_rank(user_id: int, chat_id: int) -> int:
    """Ранг должности в этом чате. Создатель проекта — 5. Без места — 0."""
    if _is_creator(user_id):
        return 5
    row = await db.pool.fetchrow(
        """
        SELECT p.rank
        FROM epsilon_seats s
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1 AND s.chat_id = $2
          AND (s.term_end IS NULL OR s.term_end > NOW())
        """,
        int(user_id),
        int(chat_id),
    )
    if not row:
        return 0
    return int(row["rank"])


async def _access(user_id: int, chat_id: int) -> dict | None:
    groups = await seats_for(user_id)
    for group in groups:
        if int(group["chatId"]) == int(chat_id):
            return group
    return None


def _require_creator(user_id: int) -> None:
    if not _is_creator(user_id):
        raise HTTPException(status_code=403, detail="Только создатель проекта отмечает группы и должности")


class OfficialBody(BaseModel):
    chat_id: int
    title: str = ""
    username: str = ""
    official: bool = True
    model_config = {"extra": "forbid"}


class PositionEditBody(BaseModel):
    title: str = Field(min_length=2, max_length=40)
    rights: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class PositionCreateBody(BaseModel):
    chat_id: int
    title: str = Field(min_length=2, max_length=40)
    rank: int = Field(ge=0, le=4)
    rights: list[str] = Field(default_factory=list)
    kind: str = KIND_POST
    prefix: str = Field(default="", max_length=16)
    model_config = {"extra": "forbid"}


class AppointBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    position_id: int = Field(ge=1)
    reason: str = Field(default="", max_length=300)
    prefix: str = Field(default="", max_length=16)
    term_start: str = Field(default="", max_length=10)
    term_end: str = Field(default="", max_length=10)
    model_config = {"extra": "forbid"}


class PrefixBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    prefix: str = Field(default="", max_length=16)
    model_config = {"extra": "forbid"}


class ApplyBody(BaseModel):
    chat_id: int
    position_id: int = Field(ge=1)
    body: str = Field(min_length=20, max_length=2000)
    rules_read: bool
    model_config = {"extra": "forbid"}


class DecideBody(BaseModel):
    application_id: int = Field(ge=1)
    approve: bool
    position_id: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=500)
    model_config = {"extra": "forbid"}


class ActBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    action: str = Field(min_length=2, max_length=24)
    until_sec: int | None = Field(default=None, ge=1, le=366 * 24 * 3600)
    reason: str = Field(default="", max_length=200)
    model_config = {"extra": "forbid"}


class KeyBody(BaseModel):
    key: str = Field(min_length=8, max_length=200)
    model_config = {"extra": "forbid"}


@router.get("/open")
async def group_open(user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT g.chat_id, g.title, g.username, p.id AS position_id, p.title AS position, p.rank, p.rights
        FROM epsilon_official_groups g
        JOIN epsilon_positions p ON p.chat_id = g.chat_id
        WHERE g.is_official AND p.accepting AND p.rank < 5 AND p.kind = 'post'
        ORDER BY g.title, p.rank DESC
        """
    )
    mine = await db.pool.fetch(
        """
        SELECT id, chat_id, position_id, status, review_note, created_at
        FROM epsilon_group_applications
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 12
        """,
        int(user_id),
    )
    return {
        "positions": [
            {
                "chatId": int(r["chat_id"]),
                "title": r["title"] or str(r["chat_id"]),
                "username": r["username"] or "",
                "positionId": int(r["position_id"]),
                "position": r["position"],
                "rank": int(r["rank"]),
                "rights": _rights(r["rights"]),
            }
            for r in rows
        ],
        "mine": [
            {
                "id": int(r["id"]),
                "chatId": int(r["chat_id"]),
                "positionId": int(r["position_id"]),
                "status": r["status"],
                "note": r["review_note"] or "",
                "at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in mine
        ],
    }


@router.post("/apply")
async def group_apply(body: ApplyBody, user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    if not body.rules_read:
        raise HTTPException(status_code=400, detail="Сначала прочитайте правила CuteRules")
    pos = await db.pool.fetchrow(
        """
        SELECT p.id, p.rank, p.accepting, g.is_official
        FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id
        WHERE p.id = $1 AND p.chat_id = $2
        """,
        int(body.position_id),
        int(body.chat_id),
    )
    if not pos or not pos["is_official"] or not pos["accepting"] or int(pos["rank"]) >= 5:
        raise HTTPException(status_code=400, detail="На эту должность набор закрыт")
    seat = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_seats WHERE user_id = $1 AND chat_id = $2",
        int(user_id),
        int(body.chat_id),
    )
    if seat:
        raise HTTPException(status_code=409, detail="Вы уже администратор этой группы")
    pending = await db.pool.fetchval(
        """
        SELECT 1 FROM epsilon_group_applications
        WHERE user_id = $1 AND chat_id = $2 AND status = 'pending'
        """,
        int(user_id),
        int(body.chat_id),
    )
    if pending:
        raise HTTPException(status_code=409, detail="Заявка в эту группу уже на рассмотрении")
    recent_reject = await db.pool.fetchval(
        """
        SELECT decided_at FROM epsilon_group_applications
        WHERE user_id = $1 AND chat_id = $2 AND status = 'rejected'
        ORDER BY decided_at DESC NULLS LAST
        LIMIT 1
        """,
        int(user_id),
        int(body.chat_id),
    )
    if recent_reject:
        if recent_reject.tzinfo is None:
            recent_reject = recent_reject.replace(tzinfo=timezone.utc)
        if recent_reject > datetime.now(timezone.utc) - timedelta(days=7):
            raise HTTPException(status_code=409, detail="Повторная заявка в эту группу откроется через 7 дней после отказа")
    app_id = await db.pool.fetchval(
        """
        INSERT INTO epsilon_group_applications
            (user_id, chat_id, position_id, body, rules_read, status)
        VALUES ($1, $2, $3, $4, TRUE, 'pending')
        RETURNING id
        """,
        int(user_id),
        int(body.chat_id),
        int(body.position_id),
        body.body.strip(),
    )
    return {"ok": True, "id": int(app_id)}


@router.post("/official")
async def group_official(body: OfficialBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    await db.pool.execute(
        """
        INSERT INTO epsilon_official_groups (chat_id, title, username, is_official)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET title = EXCLUDED.title,
            username = EXCLUDED.username,
            is_official = EXCLUDED.is_official
        """,
        int(body.chat_id),
        (body.title or str(body.chat_id))[:120],
        body.username.lstrip("@")[:64],
        bool(body.official),
    )
    if body.official:
        await _seed_positions(int(body.chat_id))
        from group_guard import apply_policy_to_chat
        await apply_policy_to_chat(int(body.chat_id), int(user_id))
    return {"ok": True, "chatId": int(body.chat_id), "official": bool(body.official)}


async def _can_edit_positions(user_id: int, chat_id: int) -> dict | None:
    if _is_creator(user_id):
        return {"rank": 5, "creator": True}
    access = await _access(user_id, chat_id)
    if not access or "manage_positions" not in set(access["rights"]):
        return None
    return {"rank": int(access["rank"]), "creator": False}


STAFF_PANEL_ROLES = ("owner", "senior_admin", "junior_admin", "moderator")


async def _seated_people() -> dict[int, list[dict]]:
    """Кто сидит на должностях: chat_id → люди. Нужен копии кабинета «от лица»."""
    try:
        rows = await db.pool.fetch(
            """
            SELECT s.chat_id, s.user_id, s.position_id, s.prefix, s.term_end,
                   u.username, u.display_name, u.first_name,
                   aa.role AS staff_role, aa.status AS staff_status
            FROM epsilon_seats s
            LEFT JOIN users u ON u.user_id = s.user_id
            LEFT JOIN LATERAL (
                SELECT role, status
                FROM admin_accounts
                WHERE user_id = s.user_id
                ORDER BY registered_at DESC NULLS LAST
                LIMIT 1
            ) aa ON TRUE
            ORDER BY s.created_at, s.user_id
            """
        )
    except Exception:
        return {}
    out: dict[int, list[dict]] = {}
    for r in rows:
        uid = int(r["user_id"])
        staff = _is_creator(uid) or (
            r["staff_status"] == "active" and r["staff_role"] in STAFF_PANEL_ROLES
        )
        end = r["term_end"]
        out.setdefault(int(r["chat_id"]), []).append({
            "userId": uid,
            "name": r["display_name"] or r["first_name"] or str(uid),
            "username": r["username"] or "",
            "positionId": int(r["position_id"]),
            "seatPrefix": r["prefix"] or "",
            "termEnd": end.date().isoformat() if end else "",
            "staff": bool(staff),
        })
    return out


@router.get("/board")
async def rights_board(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    await sweep_expired_spamblocks()
    groups = await seats_for(user_id)
    seated = await _seated_people()
    payload = []
    for group in groups:
        rows = await db.pool.fetch(
            """
            SELECT id, title, rank, rights, accepting, kind, prefix
            FROM epsilon_positions
            WHERE chat_id = $1
            ORDER BY rank DESC, id
            """,
            int(group["chatId"]),
        )
        positions = [_position_out(r) for r in rows]
        by_id = {p["id"]: p for p in positions}
        seats = []
        for person in seated.get(int(group["chatId"]), []):
            post = by_id.get(person["positionId"])
            if not post:
                continue
            seats.append({
                **person,
                "position": post["title"],
                "rank": post["rank"],
                "kind": post["kind"],
                "prefix": person.get("seatPrefix") or post["prefix"],
                "termEnd": person.get("termEnd") or "",
                "rights": post["rights"],
            })
        payload.append({**group, "positions": positions, "seats": seats})
    return {"groups": payload}


@router.get("/positions/{chat_id}")
async def group_positions(chat_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    if not await _can_edit_positions(user_id, chat_id):
        raise HTTPException(status_code=403, detail="Права должностей этой группы вам не открыты")
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT id, title, rank, rights, accepting, kind, prefix
        FROM epsilon_positions
        WHERE chat_id = $1
        ORDER BY rank DESC, id
        """,
        int(chat_id),
    )
    return {"positions": [_position_out(r) for r in rows]}


@router.post("/positions")
async def create_position(body: PositionCreateBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    kind = body.kind if body.kind in KINDS else ""
    if not kind:
        raise HTTPException(status_code=400, detail="Тип должности: обычная, обычный пользователь или спам-блок")
    official = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_official_groups WHERE chat_id = $1 AND is_official",
        int(body.chat_id),
    )
    if not official:
        raise HTTPException(status_code=404, detail="Свои должности есть только у официальной группы")
    title = " ".join(body.title.split())
    prefix, prefix_error = clean_prefix(body.prefix)
    if prefix_error:
        raise HTTPException(status_code=400, detail=prefix_error)
    if kind == KIND_SPAMBLOCK and not prefix:
        prefix = SPAMBLOCK_PREFIX
    rank = stored_rank(kind, int(body.rank))
    rights = rights_for_kind(kind, rank, body.rights, creator=True)
    accepting = kind == KIND_POST and rank > 0
    row = await db.pool.fetchrow(
        """
        INSERT INTO epsilon_positions (chat_id, title, rank, rights, accepting, kind, prefix)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
        RETURNING id
        """,
        int(body.chat_id),
        title,
        rank,
        json.dumps(rights),
        accepting,
        kind,
        prefix,
    )
    await _realm_log(
        int(body.chat_id),
        None,
        "position_created",
        f"Должность «{title}», тип {kind}, ранг {rank}",
        int(user_id),
    )
    return {"ok": True, "id": int(row["id"]), "title": title, "rank": rank, "kind": kind, "rights": rights}


@router.post("/positions/{position_id}")
async def edit_position(
    position_id: int,
    body: PositionEditBody,
    user_id: int = Depends(get_any_telegram_user_id),
):
    await ensure_tables()
    row = await db.pool.fetchrow(
        """
        SELECT p.id, p.chat_id, p.rank, p.kind
        FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id AND g.is_official
        WHERE p.id = $1
        """,
        int(position_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Такой должности нет")
    actor = await _can_edit_positions(user_id, int(row["chat_id"]))
    if not actor or not may_edit_position(actor["rank"], int(row["rank"]), creator=actor["creator"]):
        raise HTTPException(status_code=403, detail="Эту должность может менять только тот, кто старше неё")
    title = " ".join(body.title.split())
    kind = row["kind"] if row["kind"] in KINDS else KIND_POST
    rights = rights_for_kind(kind, int(row["rank"]), body.rights, creator=actor["creator"])
    await db.pool.execute(
        """
        UPDATE epsilon_positions
        SET title = $2, rights = $3::jsonb
        WHERE id = $1
        """,
        int(position_id),
        title,
        json.dumps(rights),
    )
    return {"ok": True, "id": int(position_id), "title": title, "rights": rights}


async def drop_group_access(user_id: int) -> dict:
    """Снимает места и личный ключ. Следующий вход потребует новый ключ."""
    await ensure_tables()
    seats = await db.pool.execute(
        "DELETE FROM epsilon_seats WHERE user_id = $1",
        int(user_id),
    )
    keys = await db.pool.execute(
        "DELETE FROM epsilon_group_keys WHERE user_id = $1",
        int(user_id),
    )

    def _count(result: str) -> int:
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0

    return {"seats": _count(seats), "keys": _count(keys)}


@router.post("/appoint")
async def group_appoint(body: AppointBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    await sweep_expired_spamblocks()
    pos = await db.pool.fetchrow(
        """
        SELECT p.id, p.kind, p.prefix, p.title, p.rank, p.rights
        FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id AND g.is_official
        WHERE p.id = $1 AND p.chat_id = $2 AND p.rank < 5
        """,
        int(body.position_id),
        int(body.chat_id),
    )
    if not pos:
        raise HTTPException(status_code=400, detail="Должность не найдена в официальной группе")
    kind = pos["kind"] if pos["kind"] in KINDS else KIND_POST
    prefix, prefix_error = chat_title(kind, pos["title"] or "", pos["prefix"] or "", body.prefix)
    if prefix_error:
        raise HTTPException(status_code=400, detail=prefix_error)
    term_start = None
    term_end = None
    if kind == KIND_SPAMBLOCK:
        term_start, term_end, term_error = term_bounds(body.term_start, body.term_end)
        if term_error:
            raise HTTPException(status_code=400, detail=term_error)
    held_rights = None if kind == KIND_MEMBER else rights_for_kind(
        kind, int(pos["rank"]), _rights(pos["rights"]), creator=True,
    )
    await db.pool.execute(
        """
        INSERT INTO epsilon_seats (
            user_id, chat_id, position_id, appointed_by, reason, prefix, term_start, term_end
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET position_id = EXCLUDED.position_id,
            appointed_by = EXCLUDED.appointed_by,
            reason = EXCLUDED.reason,
            prefix = EXCLUDED.prefix,
            term_start = EXCLUDED.term_start,
            term_end = EXCLUDED.term_end,
            created_at = NOW()
        """,
        int(body.user_id),
        int(body.chat_id),
        int(body.position_id),
        int(user_id),
        body.reason.strip(),
        prefix,
        term_start,
        term_end,
    )
    telegram_note = await _apply_chat_title(
        int(body.chat_id),
        int(body.user_id),
        prefix,
        rights=held_rights,
    )
    detail = f"«{pos['title']}»"
    if kind == KIND_SPAMBLOCK and term_end:
        detail += f", до {term_end.date().isoformat()}"
    if prefix:
        detail += f", префикс «{prefix}»"
    if telegram_note:
        detail += f". {telegram_note}"
    await _realm_log(int(body.chat_id), int(body.user_id), "appointed", detail, int(user_id))
    entry_key = await _issue_key(int(body.user_id))
    return {"ok": True, "entryKey": entry_key, "telegram": telegram_note, "prefix": prefix}


class DismissBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    model_config = {"extra": "forbid"}


@router.post("/dismiss")
async def group_dismiss(body: DismissBody, user_id: int = Depends(get_any_telegram_user_id)):
    """Снимает должность. Человек остаётся в группе, префикс и админка чата уходят."""
    _require_creator(user_id)
    await ensure_tables()
    seat = await db.pool.fetchrow(
        """
        SELECT s.user_id, p.title
        FROM epsilon_seats s
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1 AND s.chat_id = $2
        """,
        int(body.user_id),
        int(body.chat_id),
    )
    if not seat:
        raise HTTPException(status_code=404, detail="У этого человека нет должности в группе")
    await db.pool.execute(
        "DELETE FROM epsilon_seats WHERE user_id = $1 AND chat_id = $2",
        int(body.user_id),
        int(body.chat_id),
    )
    note = await _apply_chat_title(int(body.chat_id), int(body.user_id), "", rights=None)
    await _realm_log(
        int(body.chat_id),
        int(body.user_id),
        "position_removed",
        f"Должность «{seat['title']}» снята. {note}",
        int(user_id),
    )
    return {"ok": True, "telegram": note}


@router.post("/prefix")
async def group_prefix(body: PrefixBody, user_id: int = Depends(get_any_telegram_user_id)):
    """Префикс в чате. Создатель проекта. Для спам-блока пустое поле возвращает «спам блок»."""
    _require_creator(user_id)
    await ensure_tables()
    prefix, prefix_error = clean_prefix(body.prefix)
    if prefix_error:
        raise HTTPException(status_code=400, detail=prefix_error)
    seat = await db.pool.fetchrow(
        """
        SELECT s.user_id, p.kind, p.rank, p.rights, p.title, p.prefix
        FROM epsilon_seats s
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1 AND s.chat_id = $2
        """,
        int(body.user_id),
        int(body.chat_id),
    )
    if not seat:
        raise HTTPException(status_code=404, detail="У этого человека нет должности в группе")
    kind = seat["kind"] if seat["kind"] in KINDS else KIND_POST
    if not prefix:
        prefix, prefix_error = chat_title(kind, seat["title"] or "", seat["prefix"] or "", "")
        if prefix_error:
            raise HTTPException(status_code=400, detail=prefix_error)
    await db.pool.execute(
        "UPDATE epsilon_seats SET prefix = $3 WHERE user_id = $1 AND chat_id = $2",
        int(body.user_id),
        int(body.chat_id),
        prefix,
    )
    held = None if kind == KIND_MEMBER else rights_for_kind(
        kind, int(seat["rank"]), _rights(seat["rights"]), creator=True,
    )
    note = ""
    if prefix or kind == KIND_MEMBER:
        note = await _apply_chat_title(
            int(body.chat_id),
            int(body.user_id),
            prefix,
            rights=held,
        )
    await _realm_log(
        int(body.chat_id),
        int(body.user_id),
        "prefix",
        f"Префикс «{prefix or 'убран'}». {note}".strip(),
        int(user_id),
    )
    return {"ok": True, "prefix": prefix, "telegram": note}


@router.get("/member-check")
async def group_member_check(
    chat_id: int,
    member_id: int,
    user_id: int = Depends(get_any_telegram_user_id),
):
    """Что Telegram сообщает о человеке. Срока глобального спам-блока в Bot API нет."""
    _require_creator(user_id)
    await ensure_tables()
    return await _telegram_member(int(chat_id), int(member_id))


@router.get("/logs")
async def group_logs(
    chat_id: int,
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    await ensure_tables()
    await sweep_expired_spamblocks()
    rows = await db.pool.fetch(
        """
        SELECT id, user_id, action, detail, actor_id, created_at
        FROM epsilon_realm_log
        WHERE chat_id = $1
        ORDER BY created_at DESC
        LIMIT 40
        """,
        int(chat_id),
    )
    return {
        "items": [
            {
                "id": int(r["id"]),
                "userId": int(r["user_id"]) if r["user_id"] else None,
                "action": r["action"],
                "detail": r["detail"] or "",
                "actorId": int(r["actor_id"]) if r["actor_id"] else None,
                "at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/applications")
async def group_applications(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT a.id, a.user_id, a.chat_id, a.position_id, a.body, a.status, a.review_note, a.created_at,
               g.title AS group_title, p.title AS position, p.rank,
               u.username, u.display_name, u.first_name
        FROM epsilon_group_applications a
        JOIN epsilon_official_groups g ON g.chat_id = a.chat_id
        JOIN epsilon_positions p ON p.id = a.position_id
        LEFT JOIN users u ON u.user_id = a.user_id
        WHERE a.status = 'pending'
        ORDER BY a.created_at
        LIMIT 50
        """
    )
    return {
        "items": [
            {
                "id": int(r["id"]),
                "userId": int(r["user_id"]),
                "chatId": int(r["chat_id"]),
                "positionId": int(r["position_id"]),
                "group": r["group_title"] or str(r["chat_id"]),
                "position": r["position"],
                "rank": int(r["rank"]),
                "name": (r["display_name"] or r["first_name"] or "").strip(),
                "username": (r["username"] or "").strip(),
                "body": r["body"],
                "at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/decide")
async def group_decide(body: DecideBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    app = await db.pool.fetchrow(
        """
        SELECT id, user_id, chat_id, position_id, status
        FROM epsilon_group_applications
        WHERE id = $1
        """,
        int(body.application_id),
    )
    if not app or app["status"] != "pending":
        raise HTTPException(status_code=404, detail="Заявка уже решена или не найдена")
    note = body.note.strip()
    if not body.approve and not note:
        raise HTTPException(status_code=400, detail="Отказ пишется с причиной")
    if not body.approve:
        await db.pool.execute(
            """
            UPDATE epsilon_group_applications
            SET status = 'rejected', review_note = $2, reviewer_id = $3, decided_at = NOW()
            WHERE id = $1
            """,
            int(app["id"]),
            note,
            int(user_id),
        )
        return {"ok": True, "status": "rejected"}
    position_id = int(body.position_id or app["position_id"])
    pos = await db.pool.fetchrow(
        "SELECT id, rank, kind FROM epsilon_positions WHERE id = $1 AND chat_id = $2",
        position_id,
        int(app["chat_id"]),
    )
    asked = await db.pool.fetchrow(
        "SELECT rank FROM epsilon_positions WHERE id = $1",
        int(app["position_id"]),
    )
    if not pos or not asked or int(pos["rank"]) > int(asked["rank"]) or int(pos["rank"]) >= 5:
        raise HTTPException(status_code=400, detail="Можно одобрить запрошенную должность или более низкую")
    if pos["kind"] in {KIND_SPAMBLOCK, KIND_MEMBER}:
        raise HTTPException(
            status_code=400,
            detail="Спам-блок и обычного пользователя назначают отдельно: у спам-блока нужен срок",
        )
    await db.pool.execute(
        """
        INSERT INTO epsilon_seats (user_id, chat_id, position_id, appointed_by, reason)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET position_id = EXCLUDED.position_id, appointed_by = EXCLUDED.appointed_by, reason = EXCLUDED.reason
        """,
        int(app["user_id"]),
        int(app["chat_id"]),
        position_id,
        int(user_id),
        note or "заявка одобрена",
    )
    await db.pool.execute(
        """
        UPDATE epsilon_group_applications
        SET status = 'approved', review_note = $2, reviewer_id = $3, decided_at = NOW(), position_id = $4
        WHERE id = $1
        """,
        int(app["id"]),
        note,
        int(user_id),
        position_id,
    )
    entry_key = await _issue_key(int(app["user_id"]))
    return {"ok": True, "status": "approved", "entryKey": entry_key}


async def load_activity(chat_id: int, period: str, today, slice_day=None) -> dict:
    """Сообщения чата из chatchange. Если таблица не ответила — цифр нет, нулей нет."""
    name = period if period in {"day", "week", "month", "year"} else "month"
    start, end, grain = activity_window(name, today)
    focus_start, focus_end = start, end
    if slice_day is not None:
        if grain == "day" and start <= slice_day <= end:
            focus_start = focus_end = slice_day
        elif grain == "month":
            month_start = slice_day.replace(day=1)
            if start.replace(day=1) <= month_start <= end.replace(day=1):
                next_month = month_start.month + 1
                year = month_start.year + (1 if next_month > 12 else 0)
                next_month = 1 if next_month > 12 else next_month
                month_end = month_start.replace(year=year, month=next_month, day=1)
                from datetime import timedelta
                focus_start = month_start
                focus_end = min(end, month_end - timedelta(days=1))

    async def _totals(range_start, range_end):
        row = await db.pool.fetchrow(
            """
            SELECT coalesce(sum(text), 0)::bigint AS messages,
                   count(DISTINCT user_id)::int AS writers
            FROM chatchange
            WHERE chat_id = $1 AND date >= $2 AND date <= $3
            """,
            int(chat_id),
            range_start,
            range_end,
        )
        return int(row["messages"]), int(row["writers"])

    messages, writers = await _totals(focus_start, focus_end)
    period_messages, period_writers = await _totals(start, end)
    prev_start, prev_end = previous_window(name, start, end)
    previous_messages, _previous_writers = await _totals(prev_start, prev_end)
    if grain == "month":
        series_rows = await db.pool.fetch(
            """
            SELECT to_char(date_trunc('month', date), 'YYYY-MM-01') AS bucket,
                   coalesce(sum(text), 0)::bigint AS messages,
                   count(DISTINCT user_id)::int AS writers
            FROM chatchange
            WHERE chat_id = $1 AND date >= $2 AND date <= $3
            GROUP BY 1
            ORDER BY 1
            """,
            int(chat_id),
            start,
            end,
        )
    else:
        series_rows = await db.pool.fetch(
            """
            SELECT date::text AS bucket,
                   coalesce(sum(text), 0)::bigint AS messages,
                   count(DISTINCT user_id)::int AS writers
            FROM chatchange
            WHERE chat_id = $1 AND date >= $2 AND date <= $3
            GROUP BY date
            ORDER BY date
            """,
            int(chat_id),
            start,
            end,
        )
    counts = {
        str(row["bucket"])[:10]: (int(row["messages"]), int(row["writers"]))
        for row in series_rows
    }
    series = []
    for bucket in activity_buckets(start, end, grain):
        key = bucket.isoformat()
        got = counts.get(key, (0, 0))
        series.append({"date": key, "messages": got[0], "writers": got[1]})
    people_rows = await db.pool.fetch(
        """
        SELECT c.user_id, coalesce(sum(c.text), 0)::bigint AS messages,
               max(u.first_name) AS first_name, max(u.username) AS username
        FROM chatchange c
        LEFT JOIN users u ON u.user_id = c.user_id
        WHERE c.chat_id = $1 AND c.date >= $2 AND c.date <= $3
        GROUP BY c.user_id
        ORDER BY messages DESC
        LIMIT 15
        """,
        int(chat_id),
        focus_start,
        focus_end,
    )
    return {
        "available": True,
        "period": name,
        "grain": grain,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "focus": focus_start.isoformat(),
        "messages": messages,
        "writers": writers,
        "periodMessages": period_messages,
        "periodWriters": period_writers,
        "previousMessages": previous_messages,
        "series": series,
        "people": [
            {
                "userId": int(row["user_id"]),
                "name": row["first_name"] or str(row["user_id"]),
                "username": row["username"],
                "messages": int(row["messages"]),
            }
            for row in people_rows
        ],
    }


@router.get("/activity/{chat_id}")
async def group_activity(
    chat_id: int,
    period: str = "month",
    slice: str | None = None,
    user_id: int = Depends(get_any_telegram_user_id),
):
    access = await _access(user_id, chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    pages = cabinet_pages(access["rights"], creator=bool(access.get("isCreator")))
    if "activity" not in pages:
        raise HTTPException(status_code=403, detail="Должность не открывает активность")
    from datetime import date

    chosen = None
    if slice:
        try:
            chosen = date.fromisoformat(slice[:10])
        except ValueError:
            chosen = None
    try:
        return await load_activity(int(chat_id), period, date.today(), chosen)
    except Exception:
        return {
            "available": False,
            "period": period if period in {"day", "week", "month", "year"} else "month",
            "messages": None,
            "writers": None,
            "previousMessages": None,
            "series": [],
            "people": [],
        }


@router.get("/summary/{chat_id}")
async def group_summary(chat_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    access = await _access(user_id, chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    from admin_groups import _activity_hint, _moderation_counts, chat_warn_watch

    activity = await _activity_hint(int(chat_id))
    mods = await _moderation_counts(int(chat_id))
    watch = await chat_warn_watch(int(chat_id))
    return {
        "chat": access,
        "messages30d": activity.get("messages_30d"),
        "writers30d": activity.get("writers_30d"),
        "members": activity.get("members_tracked"),
        "writers": activity.get("top_writers") or [],
        "moderation": {
            "actions30d": mods.get("actions_30d"),
            "mutes": mods.get("mutes"),
            "bans": mods.get("bans"),
            "warns": mods.get("warns"),
            "kicks": mods.get("kicks"),
            "recent": mods.get("recent") or [],
            "watch": watch,
        },
    }


@router.post("/act")
async def group_act(body: ActBody, user_id: int = Depends(get_any_telegram_user_id)):
    access = await _access(user_id, body.chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    action = (body.action or "").strip().lower()
    if action not in LOCAL_ACTIONS:
        raise HTTPException(status_code=400, detail="Это действие живёт только внутри одной группы")
    if not rights_allow(access["rights"], action):
        raise HTTPException(status_code=403, detail="Должность не даёт этого наказания")
    if int(body.user_id) <= 0:
        raise HTTPException(status_code=400, detail="Укажите id человека")
    blocked = may_punish_rank(
        int(access["rank"]),
        await _seat_rank(int(body.user_id), int(body.chat_id)),
        same_person=int(body.user_id) == int(user_id),
    )
    if blocked:
        raise HTTPException(status_code=403, detail=blocked)
    from admin_groups import moderate_action

    result = await moderate_action(
        chat_id=int(body.chat_id),
        user_id=int(body.user_id),
        action=action,
        until_sec=body.until_sec,
        reason=body.reason.strip(),
        admin_id=int(user_id),
    )
    warns = None
    if action == "warn":
        try:
            warns = await db.pool.fetchval(
                """
                SELECT count(*)::int FROM active_warns
                WHERE user_id = $1 AND chat_id = $2
                  AND coalesce(mode, 'chat') = 'chat'
                  AND (expires_at IS NULL OR expires_at > now())
                """,
                int(body.user_id),
                int(body.chat_id),
            )
        except Exception:
            warns = None
    from group_guard_rules import punish_receipt
    receipt = punish_receipt(access.get("position") or "", action, int(warns) if warns is not None else None)
    return {"ok": True, "result": result, "receipt": receipt}


class GuardBody(BaseModel):
    chat_id: int
    captcha: bool = False
    links: bool = False
    flood: bool = False
    follow: bool = False
    model_config = {"extra": "forbid"}


class PolicyBody(BaseModel):
    captcha: bool = True
    links: bool = False
    flood: bool = False
    morning: bool = True
    morning_hour: int = 9
    model_config = {"extra": "forbid"}


class AllowBody(BaseModel):
    user_id: int
    note: str = ""
    model_config = {"extra": "forbid"}


@router.get("/guard-desk")
async def group_guard_desk(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    from group_guard import guard_desk
    return await guard_desk()


@router.put("/guard-policy")
async def group_guard_policy(body: PolicyBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    from group_guard import guard_desk, set_policy
    try:
        await set_policy(
            {
                "captcha": body.captcha,
                "links": body.links,
                "flood": body.flood,
                "morning": body.morning,
                "morningHour": body.morning_hour,
            },
            int(user_id),
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Час лички — от 0 до 23")
    return await guard_desk()


@router.post("/guard-allow")
async def group_guard_allow(body: AllowBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    from group_guard import add_allow, guard_desk
    try:
        await add_allow(int(body.user_id), body.note)
    except ValueError:
        raise HTTPException(status_code=400, detail="Нужен id человека и короткая пометка, зачем он в исключениях")
    return await guard_desk()


@router.delete("/guard-allow/{target_id}")
async def group_guard_allow_remove(target_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    from group_guard import guard_desk, remove_allow
    await remove_allow(int(target_id))
    return await guard_desk()


@router.get("/guard/{chat_id}")
async def group_guard_get(chat_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    access = await _access(user_id, chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    from group_guard import guard_view
    data = await guard_view(int(chat_id))
    data["canEdit"] = _is_creator(user_id)
    data["position"] = access.get("position") or ""
    return data


@router.put("/guard/{chat_id}")
async def group_guard_put(chat_id: int, body: GuardBody, user_id: int = Depends(get_any_telegram_user_id)):
    if int(body.chat_id) != int(chat_id):
        raise HTTPException(status_code=400, detail="Чат не совпал")
    _require_creator(user_id)
    official = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_official_groups WHERE chat_id = $1 AND is_official",
        int(chat_id),
    )
    if not official:
        raise HTTPException(status_code=404, detail="Защита включается только в официальной группе")
    from group_guard import follow_policy, set_guard
    if body.follow:
        data = await follow_policy(int(chat_id), int(user_id))
    else:
        data = await set_guard(
            int(chat_id),
            links=body.links,
            flood=body.flood,
            captcha=body.captcha,
            updated_by=int(user_id),
        )
    data["canEdit"] = True
    return data


@router.post("/key/check")
async def group_key_check(body: KeyBody, user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    if _is_creator(user_id):
        return {"ok": True}
    row = await db.pool.fetchrow(
        "SELECT key_hash FROM epsilon_group_keys WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        raise HTTPException(status_code=403, detail="Личный ключ ещё не выдан. Откройте панель из бота или попросите создателя назначить вас снова")
    if not secrets.compare_digest(_hash_key(body.key.strip()), row["key_hash"]):
        raise HTTPException(status_code=403, detail="Ключ не подошёл")
    return {"ok": True}
