# -*- coding: utf-8 -*-
"""Admin API helpers for profile achievements catalog."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.funcs import achievements as ach  # noqa: E402
from db import db  # noqa: E402


async def ensure() -> None:
    await ach.ensure_achievements_schema(db)


async def list_catalog(*, enabled_only: bool = False, q: Optional[str] = None) -> List[Dict[str, Any]]:
    await ensure()
    return await ach.list_official(db, enabled_only=enabled_only, query=q, limit=200)


async def save_item(data: Dict[str, Any], *, actor_id: int) -> Dict[str, Any]:
    await ensure()
    return await ach.upsert_official(db, data, actor_id=actor_id)


async def remove_item(official_id: int) -> bool:
    await ensure()
    return await ach.delete_official(db, official_id)


async def overview() -> Dict[str, Any]:
    await ensure()
    items = await ach.list_official(db, enabled_only=False, limit=200)
    return {
        "items": items,
        "defaults": {
            "icon_emoji_id": ach.DEFAULT_ICON_EMOJI_ID,
            "icon_fallback": ach.DEFAULT_ICON_FALLBACK,
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
