"""TikTok-заработок: схема, очередь, начисление, доступы вкладок."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import require_admin_session
from admin_permissions import ROLE_LABELS, ROLE_OWNER
from db import db
from tiktok_earn_logic import (
    BARNUM_REJECTS,
    COMMENT_REWARD,
    COMMENT_REWARD_MAX,
    COMMENT_REWARD_MIN,
    DEFAULT_COMMENT_TAG,
    DEFAULT_PHOTO_REJECT_REASONS,
    DEFAULT_REJECT_REASONS,
    DEFAULT_VIDEO_HASHTAG,
    HASH_THRESHOLD,
    KUT_PER_UNIT,
    MAX_NICKS,
    PHOTOS_REQUIRED,
    RECHECK_DAYS,
    TAB_TEASERS,
    VIDEO_REWARD_MAX,
    VIDEO_REWARD_MIN,
    VIEWS_PER_UNIT,
    assert_can_approve_comments,
    comment_progress,
    find_matches,
    next_queue_item,
    validate_comment_reward,
    validate_video_reward,
    format_photo_reject_html,
    hashes_from_image_bytes,
    hashes_similar,
    normalize_nick,
    pair_key,
    parse_tiktok_url,
    payout_delta,
    validate_nick,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tiktok", tags=["tiktok"])

TIKTOK_TABS = (
    {"id": "comments", "label": "Очередь комментариев", "blurb": "Пачки из 15 скринов. Сравни похожие кадры и решай."},
    {"id": "videos", "label": "Очередь видео", "blurb": "Открой TikTok, впиши просмотры — код сам посчитает куты."},
    {"id": "live", "label": "Живые видео", "blurb": "Уже принятые ролики и запросы на доплату за новые тысячи."},
    {"id": "archive", "label": "Архив", "blurb": "Закрытые дела: одобрения, отказы, кто и когда решил."},
    {"id": "settings", "label": "Настройки", "blurb": "Хештеги, награды, причины отказа и пауза между проверками."},
)

_SCHEMA_READY = False


async def ensure_tiktok_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS tiktok_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            comment_tag TEXT NOT NULL DEFAULT 'тг звезды',
            video_hashtag TEXT NOT NULL DEFAULT '@CuteGamingBot',
            comment_reward INTEGER NOT NULL DEFAULT 5,
            views_per_unit INTEGER NOT NULL DEFAULT 1000,
            kut_per_unit INTEGER NOT NULL DEFAULT 30,
            recheck_days INTEGER NOT NULL DEFAULT 7,
            max_nicks INTEGER NOT NULL DEFAULT 3,
            photos_required INTEGER NOT NULL DEFAULT 15,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            barnum_rejects JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tiktok_nicks (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            nick TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (nick)
        );
        CREATE INDEX IF NOT EXISTS tiktok_nicks_user_idx ON tiktok_nicks (user_id);

        CREATE TABLE IF NOT EXISTS tiktok_sessions (
            user_id BIGINT PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT '',
            extra JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS tiktok_comment_cases (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            photos JSONB NOT NULL DEFAULT '[]'::jsonb,
            nick_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
            reviewed_by BIGINT,
            reviewed_at TIMESTAMPTZ,
            reject_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS tiktok_comment_status_idx
            ON tiktok_comment_cases (status, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_comment_one_pending
            ON tiktok_comment_cases (user_id) WHERE status = 'pending';

        CREATE TABLE IF NOT EXISTS tiktok_videos (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            url TEXT NOT NULL,
            canonical_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            last_views INTEGER NOT NULL DEFAULT 0,
            last_paid_thousands INTEGER NOT NULL DEFAULT 0,
            last_checked_at TIMESTAMPTZ,
            recheck_requested_at TIMESTAMPTZ,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            reviewed_by BIGINT,
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS tiktok_videos_status_idx
            ON tiktok_videos (status, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_video_one_pending
            ON tiktok_videos (user_id) WHERE status = 'pending';
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_video_canonical_active
            ON tiktok_videos (canonical_key) WHERE status IN ('pending', 'live');

        CREATE TABLE IF NOT EXISTS tiktok_hash_verdicts (
            id SERIAL PRIMARY KEY,
            hash_a TEXT NOT NULL,
            hash_b TEXT NOT NULL,
            verdict TEXT NOT NULL,
            decided_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (hash_a, hash_b)
        );
        CREATE INDEX IF NOT EXISTS tiktok_hash_verdicts_pair_idx
            ON tiktok_hash_verdicts (hash_a, hash_b);
        ALTER TABLE tiktok_settings
            ADD COLUMN IF NOT EXISTS barnum_rejects JSONB NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE tiktok_settings
            ADD COLUMN IF NOT EXISTS comment_reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;
        CREATE INDEX IF NOT EXISTS tiktok_videos_recheck_idx
            ON tiktok_videos (status, recheck_requested_at)
            WHERE recheck_requested_at IS NOT NULL;
        """
    )
    await db.pool.execute(
        """
        INSERT INTO tiktok_settings (id, reject_reasons)
        VALUES (1, $1::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        json.dumps(DEFAULT_REJECT_REASONS, ensure_ascii=False),
    )
    _SCHEMA_READY = True


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


async def get_settings() -> dict[str, Any]:
    await ensure_tiktok_schema()
    row = await db.pool.fetchrow("SELECT * FROM tiktok_settings WHERE id = 1")
    if not row:
        return {
            "commentTag": DEFAULT_COMMENT_TAG,
            "videoHashtag": DEFAULT_VIDEO_HASHTAG,
            "commentReward": COMMENT_REWARD,
            "viewsPerUnit": VIEWS_PER_UNIT,
            "kutPerUnit": KUT_PER_UNIT,
            "recheckDays": RECHECK_DAYS,
            "maxNicks": MAX_NICKS,
            "photosRequired": PHOTOS_REQUIRED,
            "rejectReasons": list(DEFAULT_REJECT_REASONS),
            "commentRejectReasons": list(DEFAULT_PHOTO_REJECT_REASONS),
            "barnumRejects": list(BARNUM_REJECTS),
            "rewardCaps": {
                "commentMin": COMMENT_REWARD_MIN,
                "commentMax": COMMENT_REWARD_MAX,
                "videoMin": VIDEO_REWARD_MIN,
                "videoMax": VIDEO_REWARD_MAX,
            },
        }
    reasons = _json(row["reject_reasons"]) or list(DEFAULT_REJECT_REASONS)
    photo_reasons = (
        _json(row["comment_reject_reasons"])
        if "comment_reject_reasons" in row.keys()
        else []
    )
    if not photo_reasons:
        photo_reasons = list(DEFAULT_PHOTO_REJECT_REASONS)
    barnum = _json(row["barnum_rejects"]) if "barnum_rejects" in row.keys() else []
    if not barnum:
        barnum = list(BARNUM_REJECTS)
    return {
        "commentTag": row["comment_tag"],
        "videoHashtag": row["video_hashtag"],
        "commentReward": int(row["comment_reward"]),
        "viewsPerUnit": int(row["views_per_unit"]),
        "kutPerUnit": int(row["kut_per_unit"]),
        "recheckDays": int(row["recheck_days"]),
        "maxNicks": int(row["max_nicks"]),
        "photosRequired": int(row["photos_required"]),
        "rejectReasons": reasons,
        "commentRejectReasons": photo_reasons,
        "barnumRejects": barnum,
        "rewardCaps": {
            "commentMin": COMMENT_REWARD_MIN,
            "commentMax": COMMENT_REWARD_MAX,
            "videoMin": VIDEO_REWARD_MIN,
            "videoMax": VIDEO_REWARD_MAX,
        },
    }


async def list_nicks(user_id: int) -> list[str]:
    await ensure_tiktok_schema()
    rows = await db.pool.fetch(
        "SELECT nick FROM tiktok_nicks WHERE user_id = $1 ORDER BY id",
        int(user_id),
    )
    return [r["nick"] for r in rows]


async def add_nick(user_id: int, raw: str) -> str:
    await ensure_tiktok_schema()
    settings = await get_settings()
    nick = validate_nick(raw)
    nicks = await list_nicks(user_id)
    if nick in nicks:
        raise ValueError("Такой ник уже есть в твоём списке")
    if len(nicks) >= int(settings["maxNicks"]):
        raise ValueError(f"Можно не больше {settings['maxNicks']} ников")
    owner = await db.pool.fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    if await _has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Ники можно менять после ответа.")
    try:
        await db.pool.execute(
            "INSERT INTO tiktok_nicks (user_id, nick) VALUES ($1, $2)",
            int(user_id),
            nick,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise ValueError("Этот ник уже занят другим игроком") from exc
        raise
    return nick


async def replace_nick(user_id: int, old_nick: str, raw: str) -> str:
    await ensure_tiktok_schema()
    if await _has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Ники можно менять после ответа.")
    new_nick = validate_nick(raw)
    old = normalize_nick(old_nick)
    current = await list_nicks(user_id)
    if old not in current:
        raise ValueError("Такого ника нет в твоём списке")
    if new_nick in current and new_nick != old:
        raise ValueError("Такой ник уже есть в твоём списке")
    owner = await db.pool.fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", new_nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    await db.pool.execute(
        "UPDATE tiktok_nicks SET nick = $3 WHERE user_id = $1 AND nick = $2",
        int(user_id),
        old,
        new_nick,
    )
    return new_nick


async def _has_pending(user_id: int) -> bool:
    comment = await db.pool.fetchval(
        "SELECT 1 FROM tiktok_comment_cases WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    video = await db.pool.fetchval(
        """
        SELECT 1 FROM tiktok_videos
        WHERE user_id = $1 AND (status = 'pending' OR recheck_requested_at IS NOT NULL)
        """,
        int(user_id),
    )
    return bool(comment or video)


async def get_session(user_id: int) -> dict[str, Any]:
    await ensure_tiktok_schema()
    row = await db.pool.fetchrow(
        "SELECT mode, extra FROM tiktok_sessions WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        return {"mode": "", "extra": {}}
    extra = _json(row["extra"]) or {}
    if not isinstance(extra, dict):
        extra = {}
    return {"mode": row["mode"] or "", "extra": extra}


async def set_session(user_id: int, mode: str, extra: dict[str, Any] | None = None) -> None:
    await ensure_tiktok_schema()
    payload = extra if extra is not None else {}
    await db.pool.execute(
        """
        INSERT INTO tiktok_sessions (user_id, mode, extra, updated_at)
        VALUES ($1, $2, $3::jsonb, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET mode = EXCLUDED.mode, extra = EXCLUDED.extra, updated_at = NOW()
        """,
        int(user_id),
        mode or "",
        json.dumps(payload, ensure_ascii=False),
    )


async def clear_session(user_id: int) -> None:
    await set_session(user_id, "", {})


async def _user_card(user_id: int) -> dict[str, Any]:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name,
               COALESCE(display_name, first_name, username, '') AS display
        FROM users WHERE user_id = $1
        """,
        int(user_id),
    )
    nicks = await list_nicks(user_id)
    if not row:
        return {
            "userId": int(user_id),
            "username": "",
            "firstName": "",
            "displayName": str(user_id),
            "nicks": nicks,
        }
    return {
        "userId": int(row["user_id"]),
        "username": row["username"] or "",
        "firstName": row["first_name"] or "",
        "displayName": row["display"] or str(user_id),
        "nicks": nicks,
    }


async def _load_verdicts() -> dict[tuple[str, str], str]:
    rows = await db.pool.fetch("SELECT hash_a, hash_b, verdict FROM tiktok_hash_verdicts")
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        out[pair_key(r["hash_a"], r["hash_b"])] = r["verdict"]
    return out


def _photo_file_ids(photo: Any) -> tuple[str, str]:
    if isinstance(photo, str):
        raw = photo.strip()
        return raw, ""
    if not isinstance(photo, dict):
        return "", ""
    nested = photo.get("hashes") if isinstance(photo.get("hashes"), dict) else {}
    file_id = str(
        photo.get("fileId")
        or photo.get("file_id")
        or photo.get("telegramFileId")
        or nested.get("fileId")
        or nested.get("file_id")
        or ""
    ).strip()
    thumb = str(
        photo.get("thumbFileId")
        or photo.get("thumb_file_id")
        or photo.get("thumbFileID")
        or nested.get("thumbFileId")
        or nested.get("thumb_file_id")
        or ""
    ).strip()
    return file_id, thumb


def _photo_records(case_id: int, user_id: int, photos: list[dict], created_at: Any) -> list[dict]:
    out = []
    for i, photo in enumerate(photos):
        data = photo if isinstance(photo, dict) else {}
        nested = data.get("hashes") if isinstance(data.get("hashes"), dict) else {}
        file_id, thumb = _photo_file_ids(photo)
        out.append(
            {
                "id": f"{case_id}:{i}",
                "caseId": case_id,
                "userId": user_id,
                "index": i,
                "fileId": file_id,
                "thumbFileId": thumb,
                "ahash": data.get("ahash") or nested.get("ahash") or "",
                "dhash": data.get("dhash") or nested.get("dhash") or "",
                "phash": data.get("phash") or nested.get("phash") or "",
                "md5": data.get("md5") or nested.get("md5") or "",
                "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
            }
        )
    return out


async def _library_photos(exclude_case_id: int | None = None) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, user_id, photos, created_at, status
        FROM tiktok_comment_cases
        WHERE status IN ('pending', 'approved', 'rejected')
        ORDER BY id DESC
        LIMIT 200
        """
    )
    lib: list[dict] = []
    for row in rows:
        if exclude_case_id and int(row["id"]) == int(exclude_case_id):
            continue
        photos = _json(row["photos"]) or []
        lib.extend(_photo_records(int(row["id"]), int(row["user_id"]), photos, row["created_at"]))
    return lib


def _nick_breakdown(photos: list[dict], nicks: list[str]) -> list[dict[str, Any]]:
    counts = {n: 0 for n in nicks}
    unknown = 0
    for photo in photos:
        hint = normalize_nick(str(photo.get("nickHint") or ""))
        if hint in counts:
            counts[hint] += 1
        else:
            unknown += 1
    items = [{"nick": n, "count": counts[n]} for n in nicks]
    if unknown:
        items.append({"nick": "не размечено", "count": unknown})
    return items


async def submit_comment_case(user_id: int, photos: list[dict[str, Any]]) -> dict[str, Any]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    needed = int(settings["photosRequired"])
    if len(photos) != needed:
        raise ValueError(f"Нужно ровно {needed} скриншотов")
    nicks = await list_nicks(user_id)
    if not nicks:
        raise ValueError("Сначала укажи свой ник в TikTok. Без него скриншоты принять нельзя.")
    existing = await db.pool.fetchval(
        "SELECT id FROM tiktok_comment_cases WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    if existing:
        raise ValueError("Эта пачка ещё на проверке. Как ответим - можно прислать новую.")
    clean = []
    for photo in photos:
        file_id = (photo.get("fileId") or photo.get("file_id") or "").strip()
        if not file_id:
            raise ValueError("В пачке есть кадр без файла")
        clean.append(
            {
                "fileId": file_id,
                "thumbFileId": (photo.get("thumbFileId") or photo.get("thumb_file_id") or "").strip(),
                "ahash": photo.get("ahash") or "",
                "dhash": photo.get("dhash") or "",
                "phash": photo.get("phash") or "",
                "md5": photo.get("md5") or "",
                "nickHint": photo.get("nickHint") or "",
            }
        )
    row = await db.pool.fetchrow(
        """
        INSERT INTO tiktok_comment_cases (user_id, status, photos, nick_snapshot)
        VALUES ($1, 'pending', $2::jsonb, $3::jsonb)
        RETURNING id, created_at
        """,
        int(user_id),
        json.dumps(clean, ensure_ascii=False),
        json.dumps(nicks, ensure_ascii=False),
    )
    await clear_session(user_id)
    return {"id": int(row["id"]), "createdAt": row["created_at"].isoformat()}


async def submit_video(user_id: int, raw_url: str) -> dict[str, Any]:
    await ensure_tiktok_schema()
    nicks = await list_nicks(user_id)
    if not nicks:
        raise ValueError("Сначала укажи свой ник в TikTok. Без него скриншоты принять нельзя.")
    parsed = parse_tiktok_url(raw_url)
    pending = await db.pool.fetchval(
        "SELECT id FROM tiktok_videos WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    if pending:
        raise ValueError("Это видео ещё на проверке. Как ответим - можно прислать новую ссылку.")
    taken = await db.pool.fetchrow(
        """
        SELECT id, user_id FROM tiktok_videos
        WHERE canonical_key = $1 AND status IN ('pending', 'live')
        """,
        parsed["canonical"],
    )
    if taken:
        if int(taken["user_id"]) == int(user_id):
            raise ValueError("Этот ролик уже в системе.")
        raise ValueError("Этот ролик уже в системе.")
    row = await db.pool.fetchrow(
        """
        INSERT INTO tiktok_videos (user_id, url, canonical_key, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING id, created_at
        """,
        int(user_id),
        parsed["url"],
        parsed["canonical"],
    )
    await clear_session(user_id)
    return {"id": int(row["id"]), "createdAt": row["created_at"].isoformat()}


async def request_recheck(user_id: int, video_id: int) -> dict[str, Any]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    row = await db.pool.fetchrow(
        "SELECT * FROM tiktok_videos WHERE id = $1 AND user_id = $2",
        int(video_id),
        int(user_id),
    )
    if not row:
        raise ValueError("Видео не найдено")
    if row["status"] != "live":
        raise ValueError("Перепроверка доступна только для принятого видео")
    if row["recheck_requested_at"]:
        raise ValueError("Запрос уже на проверке")
    last = row["last_checked_at"]
    days = int(settings["recheckDays"])
    if last:
        ready_at = last + timedelta(days=days)
        now = datetime.now(timezone.utc)
        if last.tzinfo is None:
            ready_at = last.replace(tzinfo=timezone.utc) + timedelta(days=days)
            now = datetime.now(timezone.utc)
        if ready_at > now:
            wait = (ready_at - now).total_seconds()
            from tiktok_earn_logic import recheck_wait_text

            raise ValueError(recheck_wait_text(wait))
    await db.pool.execute(
        "UPDATE tiktok_videos SET recheck_requested_at = NOW() WHERE id = $1",
        int(video_id),
    )
    return {"ok": True}


async def _credit(user_id: int, amount: int, cause: str) -> int:
    if amount <= 0:
        return int(
            await db.pool.fetchval("SELECT balance FROM users WHERE user_id = $1", int(user_id)) or 0
        )
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            before = await conn.fetchval(
                "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            if before is None:
                raise ValueError("Игрок не найден")
            after = int(before) + int(amount)
            await conn.execute(
                "UPDATE users SET balance = $2 WHERE user_id = $1",
                int(user_id),
                after,
            )
            first_name = await conn.fetchval(
                "SELECT COALESCE(first_name, '') FROM users WHERE user_id = $1",
                int(user_id),
            )
            username = await conn.fetchval(
                "SELECT COALESCE(username, '') FROM users WHERE user_id = $1",
                int(user_id),
            )
            stamped = datetime.now().strftime("%H:%M %d.%m.%Y")
            try:
                await conn.execute(
                    """
                    INSERT INTO cutehistory
                        ("user_id", "+", cause, data, first_name, username, balance)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    int(user_id),
                    int(amount),
                    cause,
                    stamped,
                    first_name or "",
                    username or "",
                    after,
                )
            except Exception:
                logger.exception("cutehistory insert failed for tiktok user=%s", user_id)
    return after


def _notify(user_id: int, text: str) -> None:
    from user_notify import schedule_player_telegram_dm

    schedule_player_telegram_dm(int(user_id), text)


def _case_dict(
    row,
    *,
    matches: list | None = None,
    settings: dict | None = None,
    light: bool = False,
) -> dict[str, Any]:
    photos = _json(row["photos"]) or []
    nicks = _json(row["nick_snapshot"]) or []
    photo_recs = _photo_records(int(row["id"]), int(row["user_id"]), photos, row["created_at"])
    needed = int((settings or {}).get("photosRequired") or PHOTOS_REQUIRED)
    progress = comment_progress(photo_recs, needed)
    payload = {
        "id": int(row["id"]),
        "userId": int(row["user_id"]),
        "status": row["status"],
        "photos": [] if light else photo_recs,
        "photoCount": progress["received"],
        "photosRequired": progress["needed"],
        "complete": progress["complete"],
        "incomplete": progress["incomplete"],
        "nicks": nicks,
        "nickBreakdown": _nick_breakdown(photos, nicks),
        "hasSimilar": bool(matches),
        "matches": [] if light else (matches or []),
        "matchCount": len(matches or []),
        "reviewedBy": int(row["reviewed_by"]) if row["reviewed_by"] else None,
        "reviewedAt": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "rejectText": row["reject_text"] or "",
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "reward": (settings or {}).get("commentReward", COMMENT_REWARD),
    }
    return payload


async def _decorate_case(row) -> dict[str, Any]:
    settings = await get_settings()
    photos = _json(row["photos"]) or []
    recs = _photo_records(int(row["id"]), int(row["user_id"]), photos, row["created_at"])
    library = recs + await _library_photos(int(row["id"]))
    verdicts = await _load_verdicts()
    matches = find_matches(recs, library, verdicts=verdicts)
    data = _case_dict(row, matches=matches, settings=settings)
    data["user"] = await _user_card(int(row["user_id"]))
    return data


async def list_comment_cases(
    status: str = "pending",
    limit: int = 40,
    offset: int = 0,
    *,
    light: bool = True,
) -> list[dict]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    rows = await db.pool.fetch(
        """
        SELECT * FROM tiktok_comment_cases
        WHERE status = $1
        ORDER BY created_at ASC, id ASC
        LIMIT $2 OFFSET $3
        """,
        status,
        limit,
        offset,
    )
    if not rows:
        return []
    needed = int(settings.get("photosRequired") or PHOTOS_REQUIRED)
    if status == "pending":
        rows = sorted(
            rows,
            key=lambda row: (
                comment_progress(_json(row["photos"]) or [], needed)["complete"],
                row["created_at"],
                int(row["id"]),
            ),
        )
    library: list[dict] = []
    verdicts: dict = {}
    if status == "pending":
        library = await _library_photos()
        verdicts = await _load_verdicts()
    out = []
    for row in rows:
        photos = _json(row["photos"]) or []
        recs = _photo_records(int(row["id"]), int(row["user_id"]), photos, row["created_at"])
        matches = []
        if status == "pending":
            matches = find_matches(recs, recs + library, verdicts=verdicts)
        data = _case_dict(row, matches=matches, settings=settings, light=light)
        data["user"] = await _user_card(int(row["user_id"]))
        out.append(data)
    return out


async def list_comment_archive(limit: int = 20, offset: int = 0) -> list[dict]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    rows = await db.pool.fetch(
        """
        SELECT * FROM tiktok_comment_cases
        WHERE status IN ('approved', 'rejected')
        ORDER BY COALESCE(reviewed_at, created_at) DESC, id DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    out = []
    for row in rows:
        data = _case_dict(row, matches=[], settings=settings, light=True)
        data["user"] = await _user_card(int(row["user_id"]))
        out.append(data)
    return out


async def get_comment_case(case_id: int) -> dict:
    await ensure_tiktok_schema()
    row = await db.pool.fetchrow("SELECT * FROM tiktok_comment_cases WHERE id = $1", int(case_id))
    if not row:
        raise ValueError("Заявка не найдена")
    return await _decorate_case(row)


async def approve_comment_case(case_id: int, admin_id: int) -> dict:
    await ensure_tiktok_schema()
    settings = await get_settings()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM tiktok_comment_cases WHERE id = $1 FOR UPDATE",
                int(case_id),
            )
            if not row:
                raise ValueError("Заявка не найдена")
            if row["status"] != "pending":
                raise ValueError("Заявка уже закрыта")
            assert_can_approve_comments(_json(row["photos"]) or [], settings["photosRequired"])
            await conn.execute(
                """
                UPDATE tiktok_comment_cases
                SET status = 'approved', reviewed_by = $2, reviewed_at = NOW()
                WHERE id = $1
                """,
                int(case_id),
                int(admin_id),
            )
    amount = int(settings["commentReward"])
    after = await _credit(int(row["user_id"]), amount, "+ tiktok комментарии")
    text = (
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Комментарии приняты.</b>\n"
        f"<i>На баланс зачислено</i> <b>{amount} кут</b><i>.</i>"
    )
    _notify(int(row["user_id"]), text)
    return {"ok": True, "balance": after, "kut": amount}


def _clean_reason_catalog(raw, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    clean = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id") or "").strip()[:40]
        label = str(item.get("label") or "").strip()[:180]
        if rid and label:
            clean.append({"id": rid, "label": label})
    if not clean:
        raise ValueError("Нужна хотя бы одна причина отказа")
    return clean[:20]


async def reject_comment_case(case_id: int, admin_id: int, reason_ids: list[str] | None = None) -> dict:
    await ensure_tiktok_schema()
    settings = await get_settings()
    catalog = {r["id"]: r["label"] for r in settings.get("commentRejectReasons") or []}
    labels = [catalog[rid] for rid in (reason_ids or []) if rid in catalog]
    text = format_photo_reject_html(labels)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM tiktok_comment_cases WHERE id = $1 FOR UPDATE",
                int(case_id),
            )
            if not row:
                raise ValueError("Заявка не найдена")
            if row["status"] != "pending":
                raise ValueError("Заявка уже закрыта")
            await conn.execute(
                """
                UPDATE tiktok_comment_cases
                SET status = 'rejected', reviewed_by = $2, reviewed_at = NOW(), reject_text = $3
                WHERE id = $1
                """,
                int(case_id),
                int(admin_id),
                text,
            )
    _notify(
        int(row["user_id"]),
        f"<tg-emoji emoji-id='5314346928660554905'>⚠️</tg-emoji> {text}",
    )
    return {"ok": True, "rejectText": text, "reasons": labels}


async def save_verdict(hash_a: str, hash_b: str, verdict: str, admin_id: int) -> None:
    await ensure_tiktok_schema()
    if verdict not in {"copy", "unique"}:
        raise ValueError("Вердикт: copy или unique")
    a, b = pair_key((hash_a or "").strip(), (hash_b or "").strip())
    if not a or not b:
        raise ValueError("Нет хешей для сравнения")
    await db.pool.execute(
        """
        INSERT INTO tiktok_hash_verdicts (hash_a, hash_b, verdict, decided_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (hash_a, hash_b) DO UPDATE
        SET verdict = EXCLUDED.verdict, decided_by = EXCLUDED.decided_by
        """,
        a,
        b,
        verdict,
        int(admin_id),
    )


def _video_dict(row, settings: dict | None = None) -> dict[str, Any]:
    settings = settings or {}
    kut_unit = int(settings.get("kutPerUnit") or KUT_PER_UNIT)
    last_views = int(row["last_views"] or 0)
    return {
        "id": int(row["id"]),
        "userId": int(row["user_id"]),
        "url": row["url"],
        "canonicalKey": row["canonical_key"],
        "status": row["status"],
        "lastViews": last_views,
        "lastPaidThousands": int(row["last_paid_thousands"] or 0),
        "lastCheckedAt": row["last_checked_at"].isoformat() if row["last_checked_at"] else None,
        "recheckRequestedAt": row["recheck_requested_at"].isoformat() if row["recheck_requested_at"] else None,
        "recheckPending": bool(row["recheck_requested_at"]),
        "rejectReasons": _json(row["reject_reasons"]) or [],
        "reviewedBy": int(row["reviewed_by"]) if row["reviewed_by"] else None,
        "reviewedAt": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "kutPerUnit": kut_unit,
        "viewsPerUnit": int(settings.get("viewsPerUnit") or VIEWS_PER_UNIT),
    }


async def list_videos(kind: str = "pending", limit: int = 40, offset: int = 0) -> list[dict]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    if kind == "live":
        rows = await db.pool.fetch(
            """
            SELECT * FROM tiktok_videos
            WHERE status = 'live'
            ORDER BY COALESCE(recheck_requested_at, created_at) DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    elif kind == "recheck":
        rows = await db.pool.fetch(
            """
            SELECT * FROM tiktok_videos
            WHERE status = 'live' AND recheck_requested_at IS NOT NULL
            ORDER BY recheck_requested_at ASC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    elif kind == "archive":
        rows = await db.pool.fetch(
            """
            SELECT * FROM tiktok_videos
            WHERE status IN ('live', 'rejected')
            ORDER BY COALESCE(reviewed_at, created_at) DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    else:
        rows = await db.pool.fetch(
            """
            SELECT * FROM tiktok_videos
            WHERE status = 'pending'
            ORDER BY created_at ASC, id ASC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    out = []
    for row in rows:
        item = _video_dict(row, settings)
        item["user"] = await _user_card(int(row["user_id"]))
        out.append(item)
    return out


async def list_user_videos(user_id: int) -> list[dict]:
    await ensure_tiktok_schema()
    settings = await get_settings()
    rows = await db.pool.fetch(
        """
        SELECT * FROM tiktok_videos
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        int(user_id),
    )
    return [_video_dict(r, settings) for r in rows]


async def approve_video(video_id: int, admin_id: int, views: int) -> dict:
    await ensure_tiktok_schema()
    settings = await get_settings()
    kut_unit = int(settings["kutPerUnit"])
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM tiktok_videos WHERE id = $1 FOR UPDATE",
                int(video_id),
            )
            if not row:
                raise ValueError("Видео не найдено")
            is_recheck = row["status"] == "live" and bool(row["recheck_requested_at"])
            if row["status"] not in {"pending", "live"}:
                raise ValueError("Видео уже закрыто")
            if row["status"] == "live" and not is_recheck:
                raise ValueError("Нет запроса на перепроверку")
            old_views = int(row["last_views"] or 0) if is_recheck else 0
            delta = payout_delta(old_views, int(views), kut_unit)
            await conn.execute(
                """
                UPDATE tiktok_videos
                SET status = 'live',
                    last_views = $2,
                    last_paid_thousands = $3,
                    last_checked_at = NOW(),
                    recheck_requested_at = NULL,
                    reviewed_by = $4,
                    reviewed_at = NOW()
                WHERE id = $1
                """,
                int(video_id),
                int(views),
                delta["newThousands"],
                int(admin_id),
            )
    user_id = int(row["user_id"])
    kut = int(delta["kut"])
    after = await _credit(user_id, kut, "+ tiktok видео")
    days = int(settings["recheckDays"])
    if is_recheck:
        if kut > 0:
            text = (
                f"<b>Новые просмотры: {delta['newViews']}.</b>\n"
                f"<i>Было учтено {delta['oldViews']}. Доплата -</i> <b>{kut} кут</b><i>.</i>"
            )
        else:
            text = (
                f"<b>Просмотры обновили.</b>\n"
                f"<i>Полных новых тысяч нет, доплаты нет. Следующая проверка через {days} дней.</i>"
            )
    elif kut > 0:
        text = (
            f"<b>Видео принято.</b>\n"
            f"<i>Просмотры на проверке:</i> <b>{delta['newViews']}</b><i>.</i>\n"
            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> "
            f"<b>Начислено: {kut} кут.</b>"
        )
    else:
        text = (
            "<b>Видео принято.</b>\n"
            "<i>Ролик закреплён за Вами. Пока меньше 1000 просмотров - куты появятся после перепроверки.</i>"
        )
    _notify(user_id, text)
    return {"ok": True, "balance": after, **delta}


async def reject_video(video_id: int, admin_id: int, reason_ids: list[str]) -> dict:
    await ensure_tiktok_schema()
    settings = await get_settings()
    catalog = {r["id"]: r["label"] for r in settings["rejectReasons"]}
    labels = [catalog[rid] for rid in reason_ids if rid in catalog]
    if not labels:
        raise ValueError("Отметь хотя бы одну причину отказа")
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM tiktok_videos WHERE id = $1 FOR UPDATE",
                int(video_id),
            )
            if not row:
                raise ValueError("Видео не найдено")
            if row["status"] != "pending":
                raise ValueError("Отклонить можно только первую проверку")
            await conn.execute(
                """
                UPDATE tiktok_videos
                SET status = 'rejected',
                    reject_reasons = $2::jsonb,
                    reviewed_by = $3,
                    reviewed_at = NOW(),
                    recheck_requested_at = NULL
                WHERE id = $1
                """,
                int(video_id),
                json.dumps(reason_ids, ensure_ascii=False),
                int(admin_id),
            )
    bullets = "\n".join(f"<i>• {label}</i>" for label in labels)
    text = (
        f"<b>Видео не принято.</b>\n\n{bullets}\n\n"
        f"<i>Опубликуйте правки и пришлите новую ссылку. Если нужна помощь - @JerichoCute.</i>"
    )
    _notify(int(row["user_id"]), text)
    return {"ok": True, "reasons": labels}


async def update_settings(payload: dict[str, Any]) -> dict:
    await ensure_tiktok_schema()
    current = await get_settings()
    comment_tag = str(payload.get("commentTag") or current["commentTag"]).strip() or DEFAULT_COMMENT_TAG
    video_hashtag = str(payload.get("videoHashtag") or current["videoHashtag"]).strip() or DEFAULT_VIDEO_HASHTAG
    if payload.get("commentReward") is not None:
        comment_reward = validate_comment_reward(payload["commentReward"])
    else:
        comment_reward = int(current["commentReward"])
    if payload.get("kutPerUnit") is not None:
        kut_per_unit = validate_video_reward(payload["kutPerUnit"])
    else:
        kut_per_unit = int(current["kutPerUnit"])
    # 15 скринов / 7 дней / 3 ника / 1000 просмотров - правила продукта, не из формы.
    views_per_unit = int(current["viewsPerUnit"])
    recheck_days = int(current["recheckDays"])
    max_nicks = int(current["maxNicks"])
    photos_required = int(current["photosRequired"])
    reasons = payload.get("rejectReasons") or current["rejectReasons"]
    photo_reasons = payload.get("commentRejectReasons") or current.get("commentRejectReasons")
    barnum = payload.get("barnumRejects")
    if barnum is None:
        barnum = current.get("barnumRejects") or list(BARNUM_REJECTS)
    reasons = _clean_reason_catalog(reasons, DEFAULT_REJECT_REASONS)
    photo_reasons = _clean_reason_catalog(photo_reasons, DEFAULT_PHOTO_REJECT_REASONS)
    clean_barnum = [str(t).strip()[:500] for t in barnum if str(t).strip()]
    if not clean_barnum:
        clean_barnum = list(BARNUM_REJECTS)
    barnum = clean_barnum[:12]
    if views_per_unit < 1:
        raise ValueError("Награды должны быть положительными")
    if recheck_days < 1 or max_nicks < 1 or photos_required < 1:
        raise ValueError("Лимиты должны быть больше нуля")
    await db.pool.execute(
        """
        UPDATE tiktok_settings
        SET comment_tag = $1,
            video_hashtag = $2,
            comment_reward = $3,
            views_per_unit = $4,
            kut_per_unit = $5,
            recheck_days = $6,
            max_nicks = $7,
            photos_required = $8,
            reject_reasons = $9::jsonb,
            barnum_rejects = $10::jsonb,
            comment_reject_reasons = $11::jsonb,
            updated_at = NOW()
        WHERE id = 1
        """,
        comment_tag,
        video_hashtag,
        comment_reward,
        views_per_unit,
        kut_per_unit,
        recheck_days,
        max_nicks,
        photos_required,
        json.dumps(reasons, ensure_ascii=False),
        json.dumps(barnum, ensure_ascii=False),
        json.dumps(photo_reasons, ensure_ascii=False),
    )
    return await get_settings()


async def overview_counts() -> dict[str, int]:
    await ensure_tiktok_schema()
    comments = await db.pool.fetchval(
        "SELECT COUNT(*) FROM tiktok_comment_cases WHERE status = 'pending'"
    )
    videos = await db.pool.fetchval(
        "SELECT COUNT(*) FROM tiktok_videos WHERE status = 'pending'"
    )
    rechecks = await db.pool.fetchval(
        "SELECT COUNT(*) FROM tiktok_videos WHERE status = 'live' AND recheck_requested_at IS NOT NULL"
    )
    return {
        "pendingComments": int(comments or 0),
        "pendingVideos": int(videos or 0),
        "pendingRechecks": int(rechecks or 0),
        "pendingTotal": int(comments or 0) + int(videos or 0) + int(rechecks or 0),
    }


async def access_map() -> dict[str, Any]:
    from panel_access import list_panel_access_overview

    overview = await list_panel_access_overview()
    defaults = overview.get("roleDefaults") or {}
    members = overview.get("members") or []
    tabs = []
    for tab in TIKTOK_TABS:
        key = f"tiktok.{tab['id']}"
        roles = []
        for role in overview.get("roles") or []:
            role_id = role["id"]
            if (defaults.get(role_id) or {}).get(key) or (defaults.get(role_id) or {}).get("tiktok"):
                if (defaults.get(role_id) or {}).get(key, True) and (defaults.get(role_id) or {}).get("tiktok"):
                    roles.append(role)
        # точнее: вкладка открыта если родитель и child включены
        roles = []
        for role in overview.get("roles") or []:
            role_map = defaults.get(role["id"]) or {}
            parent_on = bool(role_map.get("tiktok", True))
            child_on = bool(role_map.get(key, True))
            if parent_on and child_on:
                roles.append(role)
        people = []
        for m in members:
            tabs_map = m.get("effectiveTabs") or {}
            if "tiktok" in (m.get("effectiveSections") or []) and tab["id"] in (tabs_map.get("tiktok") or []):
                people.append(
                    {
                        "userId": m["userId"],
                        "name": m.get("firstName") or (f"@{m['username']}" if m.get("username") else f"ID {m['userId']}"),
                        "roleLabel": m.get("roleLabel") or m.get("role"),
                    }
                )
        tabs.append(
            {
                **tab,
                "teaser": TAB_TEASERS.get(tab["id"], ""),
                "openRoles": roles,
                "openPeople": people,
            }
        )
    return {"tabs": tabs, "roleLabels": ROLE_LABELS}


async def assert_tiktok_tab(admin_id: int, tab_id: str) -> int:
    from admin_db import get_admin_account
    from panel_access import resolve_account_access

    acc = await get_admin_account(admin_id)
    if not acc:
        raise HTTPException(status_code=403, detail="Нет доступа")
    role = acc.get("role")
    status = acc.get("status") or "active"
    if role == ROLE_OWNER:
        return admin_id
    _perms, sections, tabs = await resolve_account_access(role, admin_id, status)
    if "tiktok" not in sections:
        raise HTTPException(status_code=403, detail="Раздел TikTok закрыт")
    allowed = tabs.get("tiktok") or []
    if tab_id and tab_id not in allowed:
        raise HTTPException(status_code=403, detail="Эта вкладка закрыта для вашей должности")
    return admin_id


async def is_tiktok_rewards_owner(admin_id: int) -> bool:
    """Создатель проекта или роль owner - единственные, кто меняет награды."""
    from admin_db import get_admin_account
    from config import owner_user_ids

    if int(admin_id) in owner_user_ids():
        return True
    acc = await get_admin_account(admin_id)
    return bool(acc and acc.get("role") == ROLE_OWNER)


def require_tiktok_tab(tab_id: str):
    async def _dep(admin_id: int = Depends(require_admin_session)) -> int:
        return await assert_tiktok_tab(admin_id, tab_id)

    return _dep


class SettingsBody(BaseModel):
    commentTag: str | None = None
    videoHashtag: str | None = None
    commentReward: int | None = Field(default=None, ge=COMMENT_REWARD_MIN, le=COMMENT_REWARD_MAX)
    viewsPerUnit: int | None = Field(default=None, ge=1, le=1000000)
    kutPerUnit: int | None = Field(default=None, ge=VIDEO_REWARD_MIN, le=VIDEO_REWARD_MAX)
    recheckDays: int | None = Field(default=None, ge=1, le=90)
    maxNicks: int | None = Field(default=None, ge=1, le=10)
    photosRequired: int | None = Field(default=None, ge=1, le=30)
    rejectReasons: list[dict] | None = None
    commentRejectReasons: list[dict] | None = None
    barnumRejects: list[str] | None = None


class VerdictBody(BaseModel):
    hashA: str
    hashB: str
    verdict: str


class VideoDecideBody(BaseModel):
    views: int | None = Field(default=None, ge=0, le=2_000_000_000)
    reasonIds: list[str] = Field(default_factory=list)


@router.get("/overview")
async def tiktok_overview(_admin_id: int = Depends(require_admin_session)):
    await ensure_tiktok_schema()
    counts = await overview_counts()
    settings = await get_settings()
    settings["canEditRewards"] = await is_tiktok_rewards_owner(_admin_id)
    return {**counts, "settings": settings, "tabs": TIKTOK_TABS}


@router.get("/counts")
async def tiktok_counts(_admin_id: int = Depends(require_admin_session)):
    return await overview_counts()


@router.get("/access-map")
async def tiktok_access_map(_admin_id: int = Depends(require_admin_session)):
    return await access_map()


@router.get("/settings")
async def tiktok_get_settings(admin_id: int = Depends(require_tiktok_tab("settings"))):
    settings = await get_settings()
    settings["canEditRewards"] = await is_tiktok_rewards_owner(admin_id)
    return settings


@router.put("/settings")
async def tiktok_put_settings(
    body: SettingsBody,
    admin_id: int = Depends(require_tiktok_tab("settings")),
):
    payload = body.model_dump(exclude_none=True)
    owner = await is_tiktok_rewards_owner(admin_id)
    if not owner:
        current = await get_settings()
        for key, current_key in (("commentReward", "commentReward"), ("kutPerUnit", "kutPerUnit")):
            incoming = payload.get(key)
            if incoming is not None and int(incoming) != int(current[current_key]):
                raise HTTPException(
                    status_code=403,
                    detail="Награду меняет только создатель проекта",
                )
        payload.pop("commentReward", None)
        payload.pop("kutPerUnit", None)
    try:
        saved = await update_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved["canEditRewards"] = owner
    return saved


@router.get("/comments")
async def tiktok_comments(
    status: str = "pending",
    limit: int = 40,
    offset: int = 0,
    _admin_id: int = Depends(require_tiktok_tab("comments")),
):
    cap = max(1, min(int(limit), 80))
    skip = max(0, int(offset))
    if status != "pending":
        return {"items": await list_comment_cases(status, cap, skip, light=True)}
    return {"items": await list_comment_cases("pending", cap, skip, light=True)}


@router.get("/comments/archive")
async def tiktok_comments_archive(
    limit: int = 20,
    offset: int = 0,
    _admin_id: int = Depends(require_tiktok_tab("archive")),
):
    cap = max(1, min(int(limit), 80))
    skip = max(0, int(offset))
    return {"items": await list_comment_archive(cap, skip)}


@router.get("/comments/next")
async def tiktok_comment_next(
    after_id: int = 0,
    _admin_id: int = Depends(require_tiktok_tab("comments")),
):
    items = await list_comment_cases("pending", limit=40, offset=0, light=True)
    nxt = next_queue_item(items, after_id or None)
    return {"item": nxt}


@router.get("/comments/{case_id}")
async def tiktok_comment_one(
    case_id: int,
    _admin_id: int = Depends(require_admin_session),
):
    try:
        return await get_comment_case(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/comments/{case_id}/approve")
async def tiktok_comment_approve(
    case_id: int,
    admin_id: int = Depends(require_tiktok_tab("comments")),
):
    try:
        return await approve_comment_case(case_id, admin_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class CommentRejectBody(BaseModel):
    reasonIds: list[str] = Field(default_factory=list)


@router.post("/comments/{case_id}/reject")
async def tiktok_comment_reject(
    case_id: int,
    body: CommentRejectBody,
    admin_id: int = Depends(require_tiktok_tab("comments")),
):
    try:
        return await reject_comment_case(case_id, admin_id, body.reasonIds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verdict")
async def tiktok_verdict(
    body: VerdictBody,
    admin_id: int = Depends(require_tiktok_tab("comments")),
):
    try:
        await save_verdict(body.hashA, body.hashB, body.verdict, admin_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/videos")
async def tiktok_videos(
    kind: str = "pending",
    limit: int = 40,
    offset: int = 0,
    admin_id: int = Depends(require_admin_session),
):
    tab = {"pending": "videos", "recheck": "videos", "live": "live", "archive": "archive"}.get(kind, "videos")
    await assert_tiktok_tab(admin_id, tab)
    cap = max(1, min(int(limit), 80))
    skip = max(0, int(offset))
    return {"items": await list_videos(kind, cap, skip)}


@router.post("/videos/{video_id}/approve")
async def tiktok_video_approve(
    video_id: int,
    body: VideoDecideBody,
    admin_id: int = Depends(require_admin_session),
):
    if body.views is None:
        raise HTTPException(status_code=400, detail="Укажи просмотры")
    try:
        row = await db.pool.fetchrow("SELECT status, recheck_requested_at FROM tiktok_videos WHERE id = $1", video_id)
        tab = "live" if row and row["status"] == "live" else "videos"
        await assert_tiktok_tab(admin_id, tab)
        return await approve_video(video_id, admin_id, int(body.views))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/videos/{video_id}/reject")
async def tiktok_video_reject(
    video_id: int,
    body: VideoDecideBody,
    admin_id: int = Depends(require_tiktok_tab("videos")),
):
    try:
        return await reject_video(video_id, admin_id, body.reasonIds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
