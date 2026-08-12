# -*- coding: utf-8 -*-
"""Admin API helpers for group balance levels (owner-only)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.funcs import group_balance_level as gbl  # noqa: E402


def get_overview() -> Dict[str, Any]:
    cfg = gbl.get_settings()
    return {
        "settings": cfg,
        "defaults": gbl.DEFAULT_SETTINGS,
        "recent": gbl.list_recent_purchases(40),
        "param_help": PARAM_HELP,
    }


def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    return gbl.save_settings(patch or {})


def reset_settings() -> Dict[str, Any]:
    return gbl.reset_settings_to_defaults()


def set_chat_level(chat_id: int, level: int) -> Dict[str, Any]:
    lvl = gbl.set_chat_level(int(chat_id), int(level), sponsor_id=None)
    return {"chat_id": int(chat_id), "level": int(lvl)}


def get_chat_level(chat_id: int) -> Dict[str, Any]:
    cfg = gbl.get_settings()
    level = gbl.get_chat_level(int(chat_id))
    return {
        "chat_id": int(chat_id),
        "level": level,
        "stars": gbl.stars_label(level),
        "stake_cap": gbl.effective_stake_cap(int(chat_id), cfg=cfg),
        "next": (
            {"level": gbl.next_level_price(int(chat_id), cfg)[0],
             "price": gbl.next_level_price(int(chat_id), cfg)[1]}
            if gbl.next_level_price(int(chat_id), cfg)
            else None
        ),
    }


PARAM_HELP: Dict[str, str] = {
    "enabled": "Вкл/выкл всю систему уровней баланса группы.",
    "level_0_cap": "Макс. ставка в группе без купленных звёзд (★0).",
    "prices": "Цена шага в Telegram Stars, чтобы ДОСТИЧЬ уровня N с N-1.",
    "stake_caps": "Потолок ставки на уровне. Пусто/null на ★5 = без лимита уровня.",
    "recommend_pct": "% от бч → рекомендуемая ставка (кнопка бч и подсказки).",
    "health_success_min": "Если рек.ставка/лимит ≥ этого — кнопка бч success (зелёная).",
    "health_primary_min": "Если ниже success, но ≥ этого — primary. Иначе danger.",
    "atmosphere_enabled": "Включить надбавку к лимиту от донатеров/активности.",
    "atmosphere_max_bonus_pct": "Максимум надбавки атмосферы в % от базового лимита.",
    "badge_titles": "Названия меток спонсора в достижениях профиля.",
    "raise_button_text": "Текст кнопки апгрейда в экране бч.",
    "system_title": "Заголовок системы (внутренний/админ).",
}
