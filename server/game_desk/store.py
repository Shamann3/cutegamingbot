# -*- coding: utf-8 -*-
"""Чтение и запись настроек игр. Бот только читает. Пишет админка."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Optional

from .catalog import (
    DEFAULT_COMMISSION,
    GAMES,
    default_payload,
    game_meta,
    resolve_key,
)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "да"}
    return bool(value)


def _as_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = int(default)
    return max(lo, min(hi, n))


def _as_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = float(default)
    if n != n:
        n = float(default)
    return max(lo, min(hi, n))


def _normalize_params(meta: Dict[str, Any], raw: Any) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, Any] = {}
    defaults = dict((meta.get("defaults") or {}).get("params") or {})
    fields = {f["key"]: f for f in (meta.get("fields") or [])}
    keys = set(defaults) | set(src) | set(fields)
    for key in keys:
        field = fields.get(key) or {}
        kind = field.get("kind") or "multiplier"
        default = defaults.get(key, 0)
        incoming = src.get(key, default)
        if kind == "int":
            out[key] = _as_int(incoming, int(default or 0), int(field.get("min", 0)), int(field.get("max", 10_000)))
        elif kind == "chance":
            out[key] = _as_float(incoming, float(default or 0), float(field.get("min", 0)), float(field.get("max", 1)))
        elif kind == "seconds":
            out[key] = _as_float(incoming, float(default or 0), float(field.get("min", 0.05)), float(field.get("max", 120)))
        else:
            out[key] = _as_float(incoming, float(default or 0), float(field.get("min", 0.05)), float(field.get("max", 20)))
    return out


def normalize_game(key: str, raw: Any) -> Dict[str, Any]:
    meta = game_meta(key)
    base = (meta or {}).get("defaults") or {
        "enabled": True,
        "minBet": 1,
        "maxBet": 500_000,
        "commissionMult": 1.0,
        "params": {},
    }
    src = raw if isinstance(raw, dict) else {}
    min_bet = _as_int(src.get("minBet", base["minBet"]), int(base["minBet"]), 0, 1_000_000)
    max_bet = _as_int(src.get("maxBet", base["maxBet"]), int(base["maxBet"]), 1, 5_000_000)
    if max_bet < min_bet:
        max_bet = min_bet
    return {
        "enabled": _as_bool(src.get("enabled", base["enabled"]), True),
        "minBet": min_bet,
        "maxBet": max_bet,
        "commissionMult": _as_float(src.get("commissionMult", base["commissionMult"]), float(base["commissionMult"]), 0.0, 5.0),
        "params": _normalize_params(meta or {"defaults": {"params": {}}, "fields": []}, src.get("params")),
    }


def normalize_payload(raw: Any) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    comm_src = src.get("commission") if isinstance(src.get("commission"), dict) else {}
    rates_src = comm_src.get("rateByLevel") if isinstance(comm_src.get("rateByLevel"), dict) else {}
    rates = {}
    for lvl in range(6):
        default = float(DEFAULT_COMMISSION["rateByLevel"][str(lvl)])
        rates[str(lvl)] = _as_float(rates_src.get(str(lvl), rates_src.get(lvl, default)), default, 0.0, 0.8)
    games_src = src.get("games") if isinstance(src.get("games"), dict) else {}
    games = {}
    for meta in GAMES:
        key = meta["key"]
        games[key] = normalize_game(key, games_src.get(key))
    return {
        "commission": {
            "enabled": _as_bool(comm_src.get("enabled", True), True),
            "minPot": _as_int(comm_src.get("minPot", DEFAULT_COMMISSION["minPot"]), int(DEFAULT_COMMISSION["minPot"]), 0, 1_000_000),
            "rateByLevel": rates,
        },
        "games": games,
    }


def merge_payload(current: Any, patch: Any) -> Dict[str, Any]:
    cur = normalize_payload(current)
    if not isinstance(patch, dict):
        return cur
    nxt = copy.deepcopy(cur)
    if isinstance(patch.get("commission"), dict):
        nxt["commission"] = normalize_payload({"commission": {**cur["commission"], **patch["commission"]}})["commission"]
    games_patch = patch.get("games")
    if isinstance(games_patch, dict):
        for key, value in games_patch.items():
            real = resolve_key(key)
            if real not in nxt["games"]:
                continue
            if not isinstance(value, dict):
                continue
            merged = dict(nxt["games"][real])
            for field in ("enabled", "minBet", "maxBet", "commissionMult"):
                if field in value:
                    merged[field] = value[field]
            if isinstance(value.get("params"), dict):
                merged["params"] = {**(merged.get("params") or {}), **value["params"]}
            nxt["games"][real] = normalize_game(real, merged)
    return normalize_payload(nxt)


async def load_payload(db) -> Dict[str, Any]:
    pool = getattr(db, "pool", None)
    if pool is None:
        return default_payload()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT payload FROM game_desk_settings WHERE id = 1")
        raw = row["payload"] if row else {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        return normalize_payload(raw)
    except Exception:
        return default_payload()


async def save_payload(db, payload: Dict[str, Any], *, admin_id: int, patch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    clean = normalize_payload(payload)
    hist = patch if patch is not None else clean
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO game_desk_settings (id, payload, updated_at, updated_by)
            VALUES (1, $1::jsonb, NOW(), $2)
            ON CONFLICT (id) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            """,
            json.dumps(clean, ensure_ascii=False),
            int(admin_id),
        )
        await conn.execute(
            "INSERT INTO game_desk_history (admin_id, patch) VALUES ($1, $2::jsonb)",
            int(admin_id),
            json.dumps(hist, ensure_ascii=False),
        )
    return clean
