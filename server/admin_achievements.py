# -*- coding: utf-8 -*-
"""Admin API for profile achievements catalog (server-only, no bot imports)."""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from db import db

DEFAULT_ICON_EMOJI_ID = "5404534885324988233"
DEFAULT_ICON_FALLBACK = "⭐"
MAX_TITLE_HTML_LEN = 500
MAX_DESCRIPTION_LEN = 400

GBL_OFFICIAL_SEEDS: List[Dict[str, Any]] = [
    {"code": "gbl_level_1", "title": "Спонсор группы", "description": "Открыл 1-й уровень баланса группы", "rarity": 1, "sort": 10},
    {"code": "gbl_level_2", "title": "Меценат сообщества", "description": "Открыл 2-й уровень баланса группы", "rarity": 2, "sort": 20},
    {"code": "gbl_level_3", "title": "Архитектор баланса", "description": "Открыл 3-й уровень баланса группы", "rarity": 3, "sort": 30},
    {"code": "gbl_level_4", "title": "Покровитель круга", "description": "Открыл 4-й уровень баланса группы", "rarity": 4, "sort": 40},
    {"code": "gbl_level_5", "title": "Легенда баланса", "description": "Открыл 5-й уровень баланса группы", "rarity": 5, "sort": 50},
]

ENSURE_SQL = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_achievements JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS official_achievements (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    title_html TEXT NOT NULL DEFAULT '',
    icon_emoji_id TEXT,
    icon_fallback TEXT NOT NULL DEFAULT '⭐',
    description TEXT NOT NULL DEFAULT '',
    rarity INT NOT NULL DEFAULT 1 CHECK (rarity >= 1 AND rarity <= 5),
    sort INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS official_achievements_enabled_sort_idx
    ON official_achievements (enabled, sort, id);
"""

_SCHEMA_READY = False


async def ensure() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    await db.pool.execute(ENSURE_SQL)
    for seed in GBL_OFFICIAL_SEEDS:
        title = seed["title"]
        await db.pool.execute(
            """
            INSERT INTO official_achievements
                (code, title, title_html, icon_emoji_id, icon_fallback, description, rarity, sort, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
            ON CONFLICT (code) DO NOTHING
            """,
            seed["code"],
            title,
            html.escape(title),
            DEFAULT_ICON_EMOJI_ID,
            DEFAULT_ICON_FALLBACK,
            seed.get("description") or "",
            int(seed.get("rarity") or 1),
            int(seed.get("sort") or 0),
        )
    _SCHEMA_READY = True


async def list_catalog(*, enabled_only: bool = False, q: Optional[str] = None) -> List[Dict[str, Any]]:
    await ensure()
    lim = 200
    if q:
        needle = f"%{q.strip().lower()}%"
        rows = await db.pool.fetch(
            """
            SELECT * FROM official_achievements
            WHERE ($1::bool = FALSE OR enabled = TRUE)
              AND (lower(code) LIKE $2 OR lower(title) LIKE $2)
            ORDER BY sort ASC, id ASC
            LIMIT $3
            """,
            enabled_only,
            needle,
            lim,
        )
    else:
        rows = await db.pool.fetch(
            """
            SELECT * FROM official_achievements
            WHERE ($1::bool = FALSE OR enabled = TRUE)
            ORDER BY sort ASC, id ASC
            LIMIT $2
            """,
            enabled_only,
            lim,
        )
    return [dict(r) for r in rows]


async def save_item(data: Dict[str, Any], *, actor_id: int) -> Dict[str, Any]:
    await ensure()
    code = str(data.get("code") or "").strip().lower().replace(" ", "_")
    if not code:
        raise ValueError("code_required")
    title = str(data.get("title") or "").strip()[:80]
    if not title:
        raise ValueError("title_required")
    title_html = str(data.get("title_html") or html.escape(title))[:MAX_TITLE_HTML_LEN]
    icon_emoji_id = data.get("icon_emoji_id")
    if icon_emoji_id is not None:
        icon_emoji_id = str(icon_emoji_id).strip() or None
    icon_fallback = str(data.get("icon_fallback") or DEFAULT_ICON_FALLBACK)[:8]
    description = str(data.get("description") or "")[:MAX_DESCRIPTION_LEN]
    rarity = max(1, min(5, int(data.get("rarity") or 1)))
    sort = int(data.get("sort") or 0)
    enabled = bool(data.get("enabled", True))
    oid = data.get("id")
    if oid:
        row = await db.pool.fetchrow(
            """
            UPDATE official_achievements SET
                code = $2, title = $3, title_html = $4,
                icon_emoji_id = $5, icon_fallback = $6, description = $7,
                rarity = $8, sort = $9, enabled = $10, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            int(oid), code, title, title_html, icon_emoji_id, icon_fallback,
            description, rarity, sort, enabled,
        )
        if not row:
            raise ValueError("not_found")
    else:
        row = await db.pool.fetchrow(
            """
            INSERT INTO official_achievements
                (code, title, title_html, icon_emoji_id, icon_fallback, description,
                 rarity, sort, enabled, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                title_html = EXCLUDED.title_html,
                icon_emoji_id = EXCLUDED.icon_emoji_id,
                icon_fallback = EXCLUDED.icon_fallback,
                description = EXCLUDED.description,
                rarity = EXCLUDED.rarity,
                sort = EXCLUDED.sort,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING *
            """,
            code, title, title_html, icon_emoji_id, icon_fallback,
            description, rarity, sort, enabled, actor_id,
        )
    return dict(row)


async def remove_item(official_id: int) -> bool:
    await ensure()
    tag = await db.pool.execute(
        "DELETE FROM official_achievements WHERE id = $1",
        int(official_id),
    )
    return str(tag).endswith("1")


async def overview() -> Dict[str, Any]:
    await ensure()
    items = await list_catalog(enabled_only=False)
    return {
        "items": items,
        "defaults": {
            "icon_emoji_id": DEFAULT_ICON_EMOJI_ID,
            "icon_fallback": DEFAULT_ICON_FALLBACK,
            "rarity": 1,
            "sort": 0,
            "enabled": True,
        },
        "help": {
            "code": "Уникальный код (латиница), например legend_2026. Коды gbl_level_1…5 — метки уровней баланса группы.",
            "title": "Название на витрине профиля. Для gbl_level_* меняйте здесь — так и выдастся.",
            "icon_emoji_id": "ID Telegram Premium emoji (кнопка в профиле).",
            "rarity": "Редкость 1–5 — для сортировки и визуального веса.",
            "sort": "Порядок в каталоге выдачи (меньше = выше).",
            "grant_user_id": "Telegram user_id игрока, которому выдаём или снимаем награду.",
            "grant_free_title": "Текст свободной награды (без ссылок).",
            "revoke_instance": "instance_id из списка достижений игрока. Снятие пишется в журнал с админом.",
        },
    }


# ── Выдача игроку из панели ──────────────────────────────────────────

MAX_ITEMS_PER_USER = 40
MAX_TITLE_GRANT = 500


def _empty_doc() -> Dict[str, Any]:
    return {"version": 1, "items": {}, "order": [], "showcase": []}


def _normalize_doc(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty_doc()
    items = raw.get("items") if isinstance(raw.get("items"), dict) else {}
    order = raw.get("order") if isinstance(raw.get("order"), list) else []
    showcase = raw.get("showcase") if isinstance(raw.get("showcase"), list) else []
    clean_items = {str(k): v for k, v in items.items() if isinstance(v, dict)}
    clean_order = [str(x) for x in order if str(x) in clean_items]
    for k in clean_items:
        if k not in clean_order:
            clean_order.append(k)
    clean_showcase = [str(x) for x in showcase if str(x) in clean_items][:3]
    return {
        "version": 1,
        "items": clean_items,
        "order": clean_order,
        "showcase": clean_showcase,
    }


async def _load_user_doc(user_id: int) -> Dict[str, Any]:
    row = await db.pool.fetchrow(
        "SELECT profile_achievements FROM users WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        raise ValueError("user_not_found")
    raw = row["profile_achievements"]
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return _normalize_doc(raw)


async def _save_user_doc(user_id: int, doc: Dict[str, Any]) -> None:
    import json
    await db.pool.execute(
        """
        UPDATE users
        SET profile_achievements = $2::jsonb
        WHERE user_id = $1
        """,
        int(user_id),
        json.dumps(_normalize_doc(doc), ensure_ascii=False),
    )


def _new_iid() -> str:
    import time
    import uuid
    return f"a{int(time.time())}_{uuid.uuid4().hex[:8]}"


async def grant_official_to_user(
    *,
    user_id: int,
    official_id: Optional[int] = None,
    code: Optional[str] = None,
    actor_id: int,
    actor_name: str = "Админ-панель",
) -> Dict[str, Any]:
    await ensure()
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("bad_user_id")
    row = None
    if official_id:
        row = await db.pool.fetchrow(
            "SELECT * FROM official_achievements WHERE id = $1",
            int(official_id),
        )
    elif code:
        row = await db.pool.fetchrow(
            "SELECT * FROM official_achievements WHERE code = $1",
            str(code).strip().lower(),
        )
    if not row:
        raise ValueError("official_not_found")
    if not bool(row["enabled"]):
        raise ValueError("official_disabled")

    doc = await _load_user_doc(uid)
    unique = str(row["code"] or "")
    for iid, it in doc["items"].items():
        if it.get("kind") == "official" and it.get("unique_code") == unique:
            return {
                "ok": True,
                "already": True,
                "instance_id": iid,
                "title": row["title"],
                "code": unique,
            }
    if len(doc["items"]) >= MAX_ITEMS_PER_USER:
        raise ValueError("user_limit")

    iid = _new_iid()
    title_html = row["title_html"] or html.escape(str(row["title"] or ""))
    item = {
        "kind": "official",
        "official_id": int(row["id"]),
        "title_html": str(title_html)[:MAX_TITLE_GRANT],
        "icon_emoji_id": row["icon_emoji_id"],
        "icon_fallback": str(row["icon_fallback"] or DEFAULT_ICON_FALLBACK),
        "granted_at": __import__("time").time(),
        "granted_by": int(actor_id),
        "granted_by_name": (actor_name or "Админ-панель")[:64],
        "source": "panel",
        "unique_code": unique,
    }
    doc["items"][iid] = item
    insert_at = 0
    for i, existing in enumerate(doc["order"]):
        if doc["items"].get(existing, {}).get("kind") == "official":
            insert_at = i + 1
    doc["order"].insert(insert_at, iid)
    await _save_user_doc(uid, doc)
    return {
        "ok": True,
        "already": False,
        "instance_id": iid,
        "title": row["title"],
        "code": unique,
    }


async def grant_free_to_user(
    *,
    user_id: int,
    title: str,
    icon_emoji_id: Optional[str] = None,
    icon_fallback: str = DEFAULT_ICON_FALLBACK,
    actor_id: int,
    actor_name: str = "Админ-панель",
) -> Dict[str, Any]:
    await ensure()
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("bad_user_id")
    title_plain = str(title or "").strip()
    if not title_plain:
        raise ValueError("title_required")
    # Простая защита: без URL / HTML-ссылок
    low = title_plain.lower()
    if "http://" in low or "https://" in low or "t.me/" in low or "<a " in low:
        raise ValueError("links_forbidden")
    title_html = html.escape(title_plain)[:MAX_TITLE_GRANT]

    doc = await _load_user_doc(uid)
    if len(doc["items"]) >= MAX_ITEMS_PER_USER:
        raise ValueError("user_limit")
    iid = _new_iid()
    doc["items"][iid] = {
        "kind": "free",
        "title_html": title_html,
        "icon_emoji_id": (str(icon_emoji_id).strip() or None) if icon_emoji_id else None,
        "icon_fallback": str(icon_fallback or DEFAULT_ICON_FALLBACK)[:8],
        "granted_at": __import__("time").time(),
        "granted_by": int(actor_id),
        "granted_by_name": (actor_name or "Админ-панель")[:64],
        "source": "panel",
    }
    doc["order"].append(iid)
    await _save_user_doc(uid, doc)
    return {"ok": True, "instance_id": iid, "title": title_plain}


def _plain_title(title_html: Any) -> str:
    raw = str(title_html or "")
    # лёгкий срез тегов для списка в панели
    import re
    return re.sub(r"<[^>]+>", "", raw).strip() or "—"


async def list_user_achievements(user_id: int) -> Dict[str, Any]:
    await ensure()
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("bad_user_id")
    doc = await _load_user_doc(uid)
    items = []
    for iid in doc.get("order") or []:
        it = (doc.get("items") or {}).get(iid)
        if not isinstance(it, dict):
            continue
        items.append({
            "instance_id": iid,
            "kind": it.get("kind") or "free",
            "title": _plain_title(it.get("title_html")),
            "unique_code": it.get("unique_code"),
            "official_id": it.get("official_id"),
            "icon_fallback": it.get("icon_fallback") or DEFAULT_ICON_FALLBACK,
            "granted_at": it.get("granted_at"),
            "granted_by": it.get("granted_by"),
            "granted_by_name": it.get("granted_by_name"),
            "source": it.get("source"),
        })
    return {"user_id": uid, "items": items, "count": len(items)}


async def revoke_from_user(
    *,
    user_id: int,
    instance_id: str,
    actor_id: int,
    actor_name: str = "Админ-панель",
) -> Dict[str, Any]:
    await ensure()
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("bad_user_id")
    iid = str(instance_id or "").strip()
    if not iid:
        raise ValueError("instance_id_required")
    doc = await _load_user_doc(uid)
    it = (doc.get("items") or {}).get(iid)
    if not isinstance(it, dict):
        raise ValueError("not_found")
    kind = str(it.get("kind") or "free")
    title = _plain_title(it.get("title_html"))
    code = it.get("unique_code")
    # метаданные снятия — для будущего красивого уведомления
    revoked_meta = {
        "instance_id": iid,
        "kind": kind,
        "title": title,
        "unique_code": code,
        "revoked_at": __import__("time").time(),
        "revoked_by": int(actor_id),
        "revoked_by_name": (actor_name or "Админ-панель")[:64],
        "was_granted_by": it.get("granted_by"),
        "was_granted_by_name": it.get("granted_by_name"),
        "source": it.get("source"),
    }
    doc["items"].pop(iid, None)
    doc["order"] = [x for x in (doc.get("order") or []) if x != iid]
    if isinstance(doc.get("showcase"), list):
        doc["showcase"] = [x for x in doc["showcase"] if x != iid]
    await _save_user_doc(uid, doc)
    return {"ok": True, **revoked_meta, "user_id": uid}
