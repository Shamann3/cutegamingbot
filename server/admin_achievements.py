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
    {"code": "gbl_level_1", "title": "Спонсор группы", "description": "Открыл ★1 баланса группы", "rarity": 1, "sort": 10},
    {"code": "gbl_level_2", "title": "Меценат сообщества", "description": "Открыл ★2 баланса группы", "rarity": 2, "sort": 20},
    {"code": "gbl_level_3", "title": "Архитектор баланса", "description": "Открыл ★3 баланса группы", "rarity": 3, "sort": 30},
    {"code": "gbl_level_4", "title": "Покровитель круга", "description": "Открыл ★4 баланса группы", "rarity": 4, "sort": 40},
    {"code": "gbl_level_5", "title": "Легенда баланса", "description": "Открыл ★5 баланса группы", "rarity": 5, "sort": 50},
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
            "code": "Уникальный код (латиница), например legend_2026.",
            "title": "Название на витрине профиля.",
            "icon_emoji_id": "ID Telegram Premium emoji (кнопка в профиле).",
            "rarity": "Редкость 1–5 — для сортировки и визуального веса.",
            "sort": "Порядок в каталоге выдачи (меньше = выше).",
        },
    }
