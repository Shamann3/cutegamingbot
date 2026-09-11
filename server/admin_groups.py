# -*- coding: utf-8 -*-
"""Студия групп для создателя проекта: поиск, статистика, контроль бч/уровня, модерация."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import BOT_TOKEN
from db import db

_TME_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?(?:joinchat/|\+)?([A-Za-z0-9_/+-]+)",
    re.I,
)


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or 0)
    except Exception:
        return default


def _iint(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def parse_group_query(raw: str) -> Dict[str, Any]:
    """Разбор id / @username / t.me / текста названия."""
    q = (raw or "").strip()
    if not q:
        return {"kind": "empty"}
    if q.lstrip("-").isdigit():
        return {"kind": "id", "chat_id": int(q)}
    if q.startswith("@"):
        return {"kind": "username", "username": q[1:].strip()}
    m = _TME_RE.search(q.replace(" ", ""))
    if m:
        token = m.group(1).strip("/")
        if token.startswith("+") or "joinchat" in q.lower() or "/" in token:
            return {"kind": "invite", "token": token, "raw": q}
        if token.isdigit():
            # t.me/c/1234567890/...
            return {"kind": "id", "chat_id": int(f"-100{token}")}
        return {"kind": "username", "username": token.split("/")[0]}
    return {"kind": "text", "text": q}


async def _tg_api(method: str, **params) -> Dict[str, Any]:
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN не задан"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(url, json=params) as resp:
                data = await resp.json(content_type=None)
                return data if isinstance(data, dict) else {"ok": False, "description": "bad response"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


async def resolve_chat_id(query: str) -> Tuple[Optional[int], Optional[str]]:
    """(chat_id, error)."""
    parsed = parse_group_query(query)
    kind = parsed.get("kind")
    if kind == "empty":
        return None, "Введите id, @username, ссылку или название"
    if kind == "id":
        return int(parsed["chat_id"]), None
    if kind == "username":
        uname = str(parsed["username"]).lstrip("@")
        # 1) БД
        try:
            row = await db.pool.fetchrow(
                """
                SELECT chat_id FROM chat
                WHERE lower(coalesce(usernamechat, '')) IN ($1, $2)
                LIMIT 1
                """,
                uname.lower(),
                f"@{uname.lower()}",
            )
            if row:
                return int(row["chat_id"]), None
        except Exception:
            pass
        # 2) Telegram
        tg = await _tg_api("getChat", chat_id=f"@{uname}")
        if tg.get("ok") and isinstance(tg.get("result"), dict):
            return int(tg["result"]["id"]), None
        return None, tg.get("description") or "Группа по username не найдена"
    if kind == "invite":
        # invite link — пробуем getChat по полной ссылке
        raw = parsed.get("raw") or query
        tg = await _tg_api("getChat", chat_id=raw)
        if tg.get("ok") and isinstance(tg.get("result"), dict):
            return int(tg["result"]["id"]), None
        return None, (
            "Приватную ссылку Telegram не всегда отдаёт через getChat. "
            "Вставьте числовой chat_id (−100…) или @username, если есть."
        )
    # text search by name
    text = str(parsed.get("text") or "").strip()
    try:
        rows = await db.pool.fetch(
            """
            SELECT chat_id, namechat, usernamechat
            FROM chat
            WHERE namechat ILIKE $1
            ORDER BY abs(coalesce(chatbalance, 0)) DESC
            LIMIT 8
            """,
            f"%{text}%",
        )
        if not rows:
            return None, "По названию ничего не найдено"
        if len(rows) == 1:
            return int(rows[0]["chat_id"]), None
        # ambiguous — return first but caller may want list; we expose via search
        return int(rows[0]["chat_id"]), None
    except Exception as e:
        return None, str(e)


async def search_groups(query: str, *, limit: int = 12) -> List[Dict[str, Any]]:
    parsed = parse_group_query(query)
    out: List[Dict[str, Any]] = []
    if parsed.get("kind") == "id":
        detail = await get_group_brief(int(parsed["chat_id"]))
        return [detail] if detail else []
    if parsed.get("kind") == "username":
        cid, err = await resolve_chat_id(query)
        if cid:
            d = await get_group_brief(cid)
            return [d] if d else []
        return []
    text = (query or "").strip()
    if not text:
        return []
    try:
        rows = await db.pool.fetch(
            """
            SELECT chat_id, namechat, usernamechat, chatlink,
                   coalesce(chatbalance, 0) AS chatbalance,
                   coalesce(dexbalance, 0) AS dexbalance,
                   coalesce(group_balance_level, 0) AS group_balance_level,
                   creator_id
            FROM chat
            WHERE namechat ILIKE $1
               OR lower(coalesce(usernamechat, '')) LIKE lower($2)
               OR cast(chat_id AS text) LIKE $3
            ORDER BY coalesce(chatbalance, 0) DESC
            LIMIT $4
            """,
            f"%{text}%",
            f"%{text.lstrip('@')}%",
            f"%{text}%",
            int(limit),
        )
        for r in rows:
            out.append(_brief_from_row(dict(r)))
    except Exception:
        pass
    return out


def _brief_from_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chat_id": _iint(r.get("chat_id")),
        "name": r.get("namechat") or f"чат {_iint(r.get('chat_id'))}",
        "username": r.get("usernamechat"),
        "link": r.get("chatlink"),
        "chatbalance": _num(r.get("chatbalance")),
        "dexbalance": _num(r.get("dexbalance")),
        "level": max(0, min(5, _iint(r.get("group_balance_level")))),
        "creator_id": _iint(r.get("creator_id")) or None,
    }


async def get_group_brief(chat_id: int) -> Optional[Dict[str, Any]]:
    try:
        row = await db.pool.fetchrow(
            """
            SELECT chat_id, namechat, usernamechat, chatlink,
                   coalesce(chatbalance, 0) AS chatbalance,
                   coalesce(dexbalance, 0) AS dexbalance,
                   coalesce(group_balance_level, 0) AS group_balance_level,
                   group_balance_sponsor_id,
                   creator_id
            FROM chat WHERE chat_id = $1
            """,
            int(chat_id),
        )
        if row:
            return _brief_from_row(dict(row))
    except Exception:
        pass
    # Telegram fallback
    tg = await _tg_api("getChat", chat_id=int(chat_id))
    if tg.get("ok") and isinstance(tg.get("result"), dict):
        res = tg["result"]
        return {
            "chat_id": int(res.get("id") or chat_id),
            "name": res.get("title") or res.get("full_name") or str(chat_id),
            "username": res.get("username"),
            "link": f"https://t.me/{res['username']}" if res.get("username") else None,
            "chatbalance": 0,
            "dexbalance": 0,
            "level": 0,
            "creator_id": None,
            "from_telegram_only": True,
        }
    return None


async def _fund_stats(chat_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "pool_balance": 0,
        "pool_total_ever": 0,
        "pool_updated_at": None,
        "commission_sum": 0,
        "to_chat_sum": 0,
        "to_fund_sum": 0,
        "to_project_sum": 0,
        "events": 0,
        "avg_commission": 0,
        "last_7d": {"commission": 0, "to_project": 0, "to_chat": 0, "to_fund": 0, "events": 0},
        "last_30d": {"commission": 0, "to_project": 0, "to_chat": 0, "to_fund": 0, "events": 0},
        "by_game": [],
        "recent": [],
        "top_payers": [],
    }
    try:
        pool = await db.pool.fetchrow(
            """
            SELECT coalesce(balance, 0) AS balance,
                   coalesce(total_ever_added, 0) AS total_ever_added,
                   updated_at
            FROM growth_fund_pool WHERE chat_id = $1
            """,
            int(chat_id),
        )
        if pool:
            out["pool_balance"] = _num(pool["balance"])
            out["pool_total_ever"] = _num(pool["total_ever_added"])
            out["pool_updated_at"] = pool["updated_at"].isoformat() if pool["updated_at"] else None
    except Exception:
        pass

    async def _period(since: Optional[datetime]) -> Dict[str, Any]:
        try:
            if since is None:
                row = await db.pool.fetchrow(
                    """
                    SELECT coalesce(sum(commission), 0) AS commission,
                           coalesce(sum(to_chat_balance), 0) AS to_chat,
                           coalesce(sum(to_growth_fund), 0) AS to_fund,
                           coalesce(sum(to_project), 0) AS to_project,
                           count(*)::int AS events
                    FROM growth_fund_ledger WHERE chat_id = $1
                    """,
                    int(chat_id),
                )
            else:
                row = await db.pool.fetchrow(
                    """
                    SELECT coalesce(sum(commission), 0) AS commission,
                           coalesce(sum(to_chat_balance), 0) AS to_chat,
                           coalesce(sum(to_growth_fund), 0) AS to_fund,
                           coalesce(sum(to_project), 0) AS to_project,
                           count(*)::int AS events
                    FROM growth_fund_ledger
                    WHERE chat_id = $1 AND created_at >= $2
                    """,
                    int(chat_id),
                    since,
                )
            if not row:
                return {"commission": 0, "to_chat": 0, "to_fund": 0, "to_project": 0, "events": 0}
            return {
                "commission": _num(row["commission"]),
                "to_chat": _num(row["to_chat"]),
                "to_fund": _num(row["to_fund"]),
                "to_project": _num(row["to_project"]),
                "events": _iint(row["events"]),
            }
        except Exception:
            return {"commission": 0, "to_chat": 0, "to_fund": 0, "to_project": 0, "events": 0}

    life = await _period(None)
    out.update({
        "commission_sum": life["commission"],
        "to_chat_sum": life["to_chat"],
        "to_fund_sum": life["to_fund"],
        "to_project_sum": life["to_project"],
        "events": life["events"],
        "avg_commission": round(life["commission"] / life["events"], 2) if life["events"] else 0,
    })
    out["last_7d"] = await _period(datetime.now() - timedelta(days=7))
    out["last_30d"] = await _period(datetime.now() - timedelta(days=30))

    try:
        rows = await db.pool.fetch(
            """
            SELECT coalesce(nullif(trim(game), ''), '—') AS game,
                   coalesce(sum(commission), 0) AS commission,
                   coalesce(sum(to_project), 0) AS to_project,
                   count(*)::int AS events
            FROM growth_fund_ledger
            WHERE chat_id = $1
            GROUP BY 1
            ORDER BY commission DESC
            LIMIT 12
            """,
            int(chat_id),
        )
        out["by_game"] = [
            {
                "game": r["game"],
                "commission": _num(r["commission"]),
                "to_project": _num(r["to_project"]),
                "events": _iint(r["events"]),
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        rows = await db.pool.fetch(
            """
            SELECT created_at, user_id, game, pot, level, rate,
                   commission, to_chat_balance, to_growth_fund, to_project
            FROM growth_fund_ledger
            WHERE chat_id = $1
            ORDER BY created_at DESC NULLS LAST
            LIMIT 25
            """,
            int(chat_id),
        )
        out["recent"] = [
            {
                "at": r["created_at"].isoformat() if r["created_at"] else None,
                "user_id": _iint(r["user_id"]),
                "game": r["game"],
                "pot": _num(r["pot"]),
                "level": _iint(r["level"]),
                "rate": _num(r["rate"]),
                "commission": _num(r["commission"]),
                "to_chat": _num(r["to_chat_balance"]),
                "to_fund": _num(r["to_growth_fund"]),
                "to_project": _num(r["to_project"]),
            }
            for r in rows
        ]
    except Exception:
        pass

    try:
        rows = await db.pool.fetch(
            """
            SELECT l.user_id,
                   coalesce(sum(l.commission), 0) AS commission,
                   count(*)::int AS events,
                   max(u.first_name) AS first_name,
                   max(u.username) AS username
            FROM growth_fund_ledger l
            LEFT JOIN users u ON u.user_id = l.user_id
            WHERE l.chat_id = $1
            GROUP BY l.user_id
            ORDER BY commission DESC
            LIMIT 10
            """,
            int(chat_id),
        )
        out["top_payers"] = [
            {
                "user_id": _iint(r["user_id"]),
                "name": r["first_name"] or str(r["user_id"]),
                "username": r["username"],
                "commission": _num(r["commission"]),
                "events": _iint(r["events"]),
            }
            for r in rows
        ]
    except Exception:
        pass
    return out


async def _moderation_counts(chat_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "mutes": 0, "bans": 0, "warns": 0, "kicks": 0, "unmutes": 0, "unbans": 0,
        "actions_30d": 0, "actions_total": 0, "recent": [],
    }
    try:
        since = datetime.now() - timedelta(days=30)
        row = await db.pool.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE action_type = 'mute')::int AS mutes,
              count(*) FILTER (WHERE action_type = 'unmute')::int AS unmutes,
              count(*) FILTER (WHERE action_type = 'ban')::int AS bans,
              count(*) FILTER (WHERE action_type = 'unban')::int AS unbans,
              count(*) FILTER (WHERE action_type = 'warn')::int AS warns,
              count(*) FILTER (WHERE action_type = 'kick')::int AS kicks,
              count(*) FILTER (WHERE created_at >= $2)::int AS actions_30d,
              count(*)::int AS actions_total
            FROM staff_actions
            WHERE chat_id = $1
            """,
            int(chat_id),
            since,
        )
        if row:
            for k in ("mutes", "unmutes", "bans", "unbans", "warns", "kicks", "actions_30d", "actions_total"):
                out[k] = _iint(row[k])
    except Exception:
        pass
    try:
        rows = await db.pool.fetch(
            """
            SELECT created_at, action_type, target_player_id, admin_name, reason
            FROM staff_actions
            WHERE chat_id = $1
            ORDER BY created_at DESC NULLS LAST
            LIMIT 20
            """,
            int(chat_id),
        )
        out["recent"] = [
            {
                "at": r["created_at"].isoformat() if r["created_at"] else None,
                "action": r["action_type"],
                "target_user_id": _iint(r["target_player_id"]),
                "admin": r["admin_name"],
                "reason": (r["reason"] or "")[:120],
            }
            for r in rows
        ]
    except Exception:
        pass
    return out


async def _activity_hint(chat_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "writers_30d": None,
        "messages_30d": None,
        "members_tracked": None,
        "top_writers": [],
        "source": None,
    }
    try:
        members = await db.pool.fetchval(
            "SELECT count(*)::int FROM memberchat WHERE chat_id = $1", int(chat_id),
        )
        out["members_tracked"] = _iint(members)
    except Exception:
        pass
    try:
        since = (datetime.now() - timedelta(days=30)).date()
        row = await db.pool.fetchrow(
            """
            SELECT count(DISTINCT user_id)::int AS writers,
                   coalesce(sum(text), 0)::bigint AS messages
            FROM chatchange
            WHERE chat_id = $1 AND date >= $2
            """,
            int(chat_id),
            since,
        )
        if row:
            out["writers_30d"] = _iint(row["writers"])
            out["messages_30d"] = _iint(row["messages"])
            out["source"] = "chatchange"
        rows = await db.pool.fetch(
            """
            SELECT c.user_id, coalesce(sum(c.text), 0)::bigint AS messages,
                   max(u.first_name) AS first_name, max(u.username) AS username
            FROM chatchange c
            LEFT JOIN users u ON u.user_id = c.user_id
            WHERE c.chat_id = $1 AND c.date >= $2
            GROUP BY c.user_id
            ORDER BY messages DESC
            LIMIT 10
            """,
            int(chat_id),
            since,
        )
        out["top_writers"] = [
            {
                "user_id": _iint(r["user_id"]),
                "name": r["first_name"] or str(r["user_id"]),
                "username": r["username"],
                "messages": _iint(r["messages"]),
            }
            for r in rows
        ]
    except Exception:
        pass
    if out["messages_30d"] is None:
        try:
            row = await db.pool.fetchrow(
                """
                SELECT count(DISTINCT user_id)::int AS writers,
                       count(*)::int AS messages
                FROM chat_messages_30d
                WHERE chat_id = $1
                """,
                int(chat_id),
            )
            if row:
                out["writers_30d"] = _iint(row["writers"])
                out["messages_30d"] = _iint(row["messages"])
                out["source"] = "chat_messages_30d"
        except Exception:
            pass
    return out


async def _chat_row_full(chat_id: int) -> Dict[str, Any]:
    try:
        row = await db.pool.fetchrow("SELECT * FROM chat WHERE chat_id = $1", int(chat_id))
        if not row:
            return {}
        data = dict(row)
        for k, v in list(data.items()):
            if hasattr(v, "isoformat"):
                data[k] = v.isoformat()
            elif isinstance(v, (bytes, memoryview)):
                data[k] = str(v)
            elif hasattr(v, "as_tuple") and hasattr(v, "quantize"):
                # Decimal
                data[k] = float(v)
            elif not isinstance(v, (str, int, float, bool, type(None), list, dict)):
                data[k] = str(v)
        return data
    except Exception:
        return {}


async def _king_info(chat_id: int) -> Dict[str, Any]:
    try:
        row = await db.pool.fetchrow(
            """
            SELECT chat_id, creator_id, enabled, min_messages, period_kind,
                   active_until_ts, start_at_ts, reward_p1, reward_p2, reward_p3
            FROM chat_king_reward_settings
            WHERE chat_id = $1
            """,
            int(chat_id),
        )
        if not row:
            return {"configured": False}
        return {
            "configured": True,
            "enabled": bool(row["enabled"]),
            "min_messages": _iint(row["min_messages"]),
            "period_kind": row["period_kind"],
            "reward_p1": _iint(row["reward_p1"]),
            "reward_p2": _iint(row["reward_p2"]),
            "reward_p3": _iint(row["reward_p3"]),
            "active_until_ts": _iint(row["active_until_ts"]) or None,
            "start_at_ts": _iint(row["start_at_ts"]) or None,
            "creator_id": _iint(row["creator_id"]) or None,
        }
    except Exception:
        return {"configured": False}


async def _black_market_stats(chat_id: int) -> Dict[str, Any]:
    out = {"deposits_sum": 0, "deposits_count": 0}
    try:
        row = await db.pool.fetchrow(
            """
            SELECT coalesce(sum(amount), 0) AS s, count(*)::int AS c
            FROM black_market_shop_deposits
            WHERE target_chat_id = $1 OR source_chat_id = $1
            """,
            int(chat_id),
        )
        if row:
            out["deposits_sum"] = _num(row["s"])
            out["deposits_count"] = _iint(row["c"])
    except Exception:
        pass
    return out


async def _active_punishments(chat_id: int) -> Dict[str, Any]:
    mutes: List[Dict[str, Any]] = []
    bans: List[Dict[str, Any]] = []
    warns: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT user_id, chat_id, mute_until, target_name, scope, reason
            FROM active_mutes
            WHERE chat_id IN ($1, 0)
            ORDER BY mute_until
            LIMIT 30
            """,
            int(chat_id),
        )
        for r in rows:
            mutes.append({
                "user_id": _iint(r["user_id"]),
                "chat_id": _iint(r["chat_id"]),
                "until": r["mute_until"].isoformat() if r["mute_until"] else None,
                "name": r["target_name"],
                "scope": r["scope"],
                "reason": (r["reason"] or "")[:80],
            })
    except Exception:
        pass
    try:
        rows = await db.pool.fetch(
            """
            SELECT user_id, ban_until, target_name, scope, reason, mode
            FROM active_bans WHERE chat_id = $1
            ORDER BY ban_until NULLS LAST
            LIMIT 30
            """,
            int(chat_id),
        )
        for r in rows:
            bans.append({
                "user_id": _iint(r["user_id"]),
                "until": r["ban_until"].isoformat() if r["ban_until"] else None,
                "name": r["target_name"],
                "scope": r["scope"],
                "mode": r["mode"],
                "reason": (r["reason"] or "")[:80],
            })
    except Exception:
        pass
    try:
        rows = await db.pool.fetch(
            """
            SELECT id, user_id, expires_at, reason, mode, scope, admin_name
            FROM active_warns
            WHERE chat_id = $1 AND (expires_at IS NULL OR expires_at > now())
            ORDER BY id DESC
            LIMIT 30
            """,
            int(chat_id),
        )
        for r in rows:
            warns.append({
                "id": _iint(r["id"]),
                "user_id": _iint(r["user_id"]),
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                "reason": (r["reason"] or "")[:80],
                "mode": r["mode"],
                "scope": r["scope"],
                "admin": r["admin_name"],
            })
    except Exception:
        pass
    return {"mutes": mutes, "bans": bans, "warns": warns}


async def _gbl_limits(level: int, chat_id: Optional[int] = None) -> Dict[str, Any]:
    try:
        from admin_group_balance_level import get_settings, effective_stake_cap, stars_label
        cfg = get_settings()
        caps = cfg.get("stake_caps") or {}
        lvl = max(0, min(5, int(level)))
        if lvl <= 0:
            base = int(cfg.get("level_0_cap") or 30)
        elif lvl >= 5 and caps.get("5") is None:
            base = None
        else:
            v = caps.get(str(lvl))
            base = int(v) if v is not None else int(cfg.get("level_0_cap") or 30)
        prices = cfg.get("prices") or {}
        stake_eff = None
        if chat_id is not None:
            try:
                stake_eff = effective_stake_cap(int(chat_id), cfg)
            except Exception:
                stake_eff = base
        return {
            "stake_cap_base": base,
            "stake_cap_effective": stake_eff if stake_eff is not None else base,
            "stars_label": stars_label(lvl),
            "next_price": int(prices.get(str(lvl + 1)) or 0) if lvl < 5 else None,
            "badge_title": (cfg.get("badge_titles") or {}).get(str(lvl)),
            "enabled": bool(cfg.get("enabled", True)),
            "prices": {str(k): int(v) for k, v in prices.items() if str(k).isdigit()},
            "stake_caps": {str(k): (None if v is None else int(v)) for k, v in caps.items()},
        }
    except Exception:
        return {}


async def get_group_detail(chat_id: int) -> Dict[str, Any]:
    brief = await get_group_brief(chat_id)
    if not brief:
        raise ValueError("Группа не найдена")

    chat_full = await _chat_row_full(chat_id)
    if chat_full:
        brief["chatbalance"] = _num(chat_full.get("chatbalance", brief["chatbalance"]))
        brief["dexbalance"] = _num(chat_full.get("dexbalance", brief.get("dexbalance")))
        brief["level"] = max(0, min(5, _iint(chat_full.get("group_balance_level", brief["level"]))))
        if chat_full.get("namechat"):
            brief["name"] = chat_full["namechat"]
        if chat_full.get("usernamechat"):
            brief["username"] = chat_full["usernamechat"]
        if chat_full.get("chatlink"):
            brief["link"] = chat_full["chatlink"]
        if chat_full.get("creator_id"):
            brief["creator_id"] = _iint(chat_full["creator_id"])
        if chat_full.get("created_at"):
            brief["created_at"] = chat_full["created_at"]

    tg = await _tg_api("getChat", chat_id=int(chat_id))
    tg_meta: Dict[str, Any] = {}
    if tg.get("ok") and isinstance(tg.get("result"), dict):
        res = tg["result"]
        tg_meta = {
            "title": res.get("title"),
            "username": res.get("username"),
            "type": res.get("type"),
            "description": (res.get("description") or "")[:500] or None,
            "invite_link": res.get("invite_link"),
            "is_forum": bool(res.get("is_forum")),
            "slow_mode": res.get("slow_mode_delay"),
            "has_protected_content": bool(res.get("has_protected_content")),
            "join_to_send": bool(res.get("join_to_send_messages")),
            "join_by_request": bool(res.get("join_by_request")),
            "permissions": res.get("permissions"),
        }
        if tg_meta.get("title"):
            brief["name"] = tg_meta["title"]
        if tg_meta.get("username"):
            brief["username"] = tg_meta["username"]
            brief["link"] = f"https://t.me/{tg_meta['username']}"

    members = None
    mc = await _tg_api("getChatMemberCount", chat_id=int(chat_id))
    if mc.get("ok"):
        members = _iint(mc.get("result"))

    admins: List[Dict[str, Any]] = []
    bot_status: Dict[str, Any] = {}
    ad = await _tg_api("getChatAdministrators", chat_id=int(chat_id))
    if ad.get("ok") and isinstance(ad.get("result"), list):
        for a in ad["result"][:40]:
            user = a.get("user") or {}
            first = (user.get("first_name") or "").strip()
            last = (user.get("last_name") or "").strip()
            full = f"{first} {last}".strip() or str(user.get("id"))
            admins.append({
                "user_id": _iint(user.get("id")),
                "name": full,
                "username": user.get("username"),
                "status": a.get("status"),
                "is_bot": bool(user.get("is_bot")),
            })
    me = await _tg_api("getMe")
    if me.get("ok") and isinstance(me.get("result"), dict):
        bot_id = _iint(me["result"].get("id"))
        st = await _tg_api("getChatMember", chat_id=int(chat_id), user_id=bot_id)
        if st.get("ok") and isinstance(st.get("result"), dict):
            r = st["result"]
            bot_status = {
                "user_id": bot_id,
                "status": r.get("status"),
                "can_restrict": bool(r.get("can_restrict_members")),
                "can_delete": bool(r.get("can_delete_messages")),
                "can_invite": bool(r.get("can_invite_users")),
                "can_promote": bool(r.get("can_promote_members")),
            }

    fund = await _fund_stats(chat_id)
    mods = await _moderation_counts(chat_id)
    activity = await _activity_hint(chat_id)
    active = await _active_punishments(chat_id)
    king = await _king_info(chat_id)
    bm = await _black_market_stats(chat_id)
    gbl = await _gbl_limits(brief["level"], chat_id=int(chat_id))

    sponsor = None
    try:
        sid = chat_full.get("group_balance_sponsor_id") or await db.pool.fetchval(
            "SELECT group_balance_sponsor_id FROM chat WHERE chat_id = $1", int(chat_id),
        )
        if sid:
            u = await db.pool.fetchrow(
                "SELECT user_id, first_name, username, balance, donate FROM users WHERE user_id = $1",
                int(sid),
            )
            if u:
                sponsor = {
                    "user_id": int(u["user_id"]),
                    "name": u["first_name"] or str(u["user_id"]),
                    "username": u["username"],
                    "balance": _num(u.get("balance")),
                    "donate": _num(u.get("donate")),
                }
    except Exception:
        pass

    creator = None
    if brief.get("creator_id"):
        try:
            u = await db.pool.fetchrow(
                "SELECT user_id, first_name, username, balance FROM users WHERE user_id = $1",
                int(brief["creator_id"]),
            )
            if u:
                creator = {
                    "user_id": int(u["user_id"]),
                    "name": u["first_name"] or str(u["user_id"]),
                    "username": u["username"],
                    "balance": _num(u.get("balance")),
                }
        except Exception:
            creator = {"user_id": int(brief["creator_id"]), "name": str(brief["creator_id"])}

    scale = (
        math.log10(max(1.0, brief["chatbalance"] + 1)) * 18
        + math.log10(max(1.0, fund["commission_sum"] + 1)) * 22
        + math.log10(max(1.0, (members or 0) + 1)) * 16
        + brief["level"] * 8
        + math.log10(max(1.0, (activity.get("messages_30d") or 0) + 1)) * 10
    )

    # health bars 0..100 for UI
    def _bar(v: float, soft_cap: float) -> float:
        return round(min(100.0, 100.0 * math.log10(max(1.0, v + 1)) / math.log10(max(2.0, soft_cap))), 1)

    return {
        "chat": brief,
        "chat_raw": chat_full,
        "telegram": tg_meta,
        "members": members,
        "admins": admins,
        "bot": bot_status,
        "fund": fund,
        "moderation": {
            **{k: mods[k] for k in mods if k != "recent"},
            "active_mutes": len(active["mutes"]),
            "active_bans": len(active["bans"]),
            "active_warns": len(active["warns"]),
            "recent": mods.get("recent") or [],
            "active": active,
        },
        "activity": activity,
        "king": king,
        "black_market": bm,
        "gbl": gbl,
        "sponsor": sponsor,
        "creator": creator,
        "scale_score": round(scale, 1),
        "stars": "★" * brief["level"] + "☆" * (5 - brief["level"]),
        "bars": {
            "balance": _bar(brief["chatbalance"], 100_000),
            "commission": _bar(fund["commission_sum"], 50_000),
            "project": _bar(fund["to_project_sum"], 20_000),
            "activity": _bar(float(activity.get("messages_30d") or 0), 50_000),
            "members": _bar(float(members or 0), 5_000),
            "level": brief["level"] * 20,
        },
    }


async def overview() -> Dict[str, Any]:
    """Сводка по всем группам: топы и глобальные цифры."""
    global_totals = {
        "commission": 0,
        "to_project": 0,
        "to_chat": 0,
        "to_fund": 0,
        "events": 0,
    }
    try:
        row = await db.pool.fetchrow(
            """
            SELECT coalesce(total_commission, 0) AS commission,
                   coalesce(total_to_project, 0) AS to_project,
                   coalesce(total_to_chat_balance, 0) AS to_chat,
                   coalesce(total_to_growth_fund, 0) AS to_fund,
                   coalesce(total_events, 0) AS events
            FROM growth_fund_global_totals WHERE id = 1
            """
        )
        if row:
            global_totals = {k: _num(row[k]) if k != "events" else _iint(row[k]) for k in global_totals}
    except Exception:
        pass

    top_commission: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT l.chat_id,
                   coalesce(sum(l.commission), 0) AS commission,
                   coalesce(sum(l.to_project), 0) AS to_project,
                   coalesce(sum(l.to_chat_balance), 0) AS to_chat,
                   count(*)::int AS events,
                   max(c.namechat) AS namechat,
                   max(c.usernamechat) AS usernamechat,
                   max(coalesce(c.chatbalance, 0)) AS chatbalance,
                   max(coalesce(c.group_balance_level, 0)) AS level
            FROM growth_fund_ledger l
            LEFT JOIN chat c ON c.chat_id = l.chat_id
            GROUP BY l.chat_id
            ORDER BY commission DESC
            LIMIT 15
            """
        )
        for r in rows:
            top_commission.append({
                "chat_id": _iint(r["chat_id"]),
                "name": r["namechat"] or str(r["chat_id"]),
                "username": r["usernamechat"],
                "commission": _num(r["commission"]),
                "to_project": _num(r["to_project"]),
                "to_chat": _num(r["to_chat"]),
                "events": _iint(r["events"]),
                "chatbalance": _num(r["chatbalance"]),
                "level": _iint(r["level"]),
            })
    except Exception:
        pass

    top_balance: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT chat_id, namechat, usernamechat,
                   coalesce(chatbalance, 0) AS chatbalance,
                   coalesce(group_balance_level, 0) AS level
            FROM chat
            ORDER BY chatbalance DESC NULLS LAST
            LIMIT 15
            """
        )
        for r in rows:
            top_balance.append({
                "chat_id": _iint(r["chat_id"]),
                "name": r["namechat"] or str(r["chat_id"]),
                "username": r["usernamechat"],
                "chatbalance": _num(r["chatbalance"]),
                "level": _iint(r["level"]),
            })
    except Exception:
        pass

    top_project: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT l.chat_id,
                   coalesce(sum(l.to_project), 0) AS to_project,
                   coalesce(sum(l.commission), 0) AS commission,
                   max(c.namechat) AS namechat,
                   max(c.usernamechat) AS usernamechat
            FROM growth_fund_ledger l
            LEFT JOIN chat c ON c.chat_id = l.chat_id
            GROUP BY l.chat_id
            ORDER BY to_project DESC
            LIMIT 15
            """
        )
        for r in rows:
            top_project.append({
                "chat_id": _iint(r["chat_id"]),
                "name": r["namechat"] or str(r["chat_id"]),
                "username": r["usernamechat"],
                "to_project": _num(r["to_project"]),
                "commission": _num(r["commission"]),
            })
    except Exception:
        pass

    chats_total = 0
    try:
        chats_total = _iint(await db.pool.fetchval("SELECT count(*) FROM chat"))
    except Exception:
        pass

    return {
        "chats_total": chats_total,
        "global": global_totals,
        "top_commission": top_commission,
        "top_balance": top_balance,
        "top_project": top_project,
        "hint": (
            "to_project — доля комиссий в дом проекта (из growth_fund_ledger). "
            "commission — вся комиссия с игр группы. chatbalance — текущий бч."
        ),
    }


async def set_chat_balance(chat_id: int, balance: float) -> Dict[str, Any]:
    bal = max(0.0, float(balance))
    result = await db.pool.execute(
        "UPDATE chat SET chatbalance = $2 WHERE chat_id = $1",
        int(chat_id),
        bal,
    )
    try:
        touched = int(str(result).split()[-1])
    except Exception:
        touched = 1
    if touched <= 0:
        raise ValueError("Группа не найдена в таблице chat")
    return {"chat_id": int(chat_id), "chatbalance": bal}


async def set_chat_level(chat_id: int, level: int, *, sponsor_id: Optional[int] = None) -> Dict[str, Any]:
    lvl = max(0, min(5, int(level)))
    try:
        from admin_group_balance_level import set_chat_level as gbl_set
        result = await gbl_set(int(chat_id), lvl)
        if sponsor_id is not None:
            try:
                await db.pool.execute(
                    "UPDATE chat SET group_balance_sponsor_id = $2 WHERE chat_id = $1",
                    int(chat_id),
                    int(sponsor_id),
                )
            except Exception:
                pass
        return {"chat_id": int(chat_id), "level": int(result.get("level", lvl))}
    except Exception:
        await db.pool.execute(
            """
            UPDATE chat
            SET group_balance_level = $2,
                group_balance_sponsor_id = COALESCE($3, group_balance_sponsor_id)
            WHERE chat_id = $1
            """,
            int(chat_id),
            lvl,
            int(sponsor_id) if sponsor_id else None,
        )
        return {"chat_id": int(chat_id), "level": lvl}


async def moderate_action(
    *,
    chat_id: int,
    user_id: int,
    action: str,
    until_sec: Optional[int] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """Модерация через игровой BOT_TOKEN: mute / unmute / kick / ban / unban."""
    action = (action or "").strip().lower()
    cid, uid = int(chat_id), int(user_id)
    reason = (reason or "")[:200]

    if action == "mute":
        until_date = None
        if until_sec and until_sec > 0:
            until_date = int(datetime.now().timestamp()) + max(35, int(until_sec))
        perms = {
            "can_send_messages": False,
            "can_send_audios": False,
            "can_send_documents": False,
            "can_send_photos": False,
            "can_send_videos": False,
            "can_send_video_notes": False,
            "can_send_voice_notes": False,
            "can_send_polls": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False,
        }
        params: Dict[str, Any] = {
            "chat_id": cid,
            "user_id": uid,
            "permissions": perms,
        }
        if until_date:
            params["until_date"] = until_date
        res = await _tg_api("restrictChatMember", **params)
    elif action == "unmute":
        perms = {
            "can_send_messages": True,
            "can_send_audios": True,
            "can_send_documents": True,
            "can_send_photos": True,
            "can_send_videos": True,
            "can_send_video_notes": True,
            "can_send_voice_notes": True,
            "can_send_polls": True,
            "can_send_other_messages": True,
            "can_add_web_page_previews": True,
        }
        res = await _tg_api("restrictChatMember", chat_id=cid, user_id=uid, permissions=perms)
    elif action == "kick":
        res = await _tg_api("banChatMember", chat_id=cid, user_id=uid)
        if res.get("ok"):
            await _tg_api("unbanChatMember", chat_id=cid, user_id=uid, only_if_banned=True)
    elif action == "ban":
        params = {"chat_id": cid, "user_id": uid}
        if until_sec and until_sec > 0:
            params["until_date"] = int(datetime.now().timestamp()) + max(35, int(until_sec))
        res = await _tg_api("banChatMember", **params)
    elif action == "unban":
        res = await _tg_api("unbanChatMember", chat_id=cid, user_id=uid, only_if_banned=True)
    else:
        return {"ok": False, "error": f"Неизвестное действие: {action}"}

    ok = bool(res.get("ok"))
    # audit (best-effort)
    if ok:
        try:
            await db.pool.execute(
                """
                INSERT INTO staff_actions
                  (admin_user_id, admin_name, target_player_id, action_type, reason, chat_id, created_at)
                VALUES (0, 'Админ-панель', $1, $2, $3, $4, NOW())
                """,
                uid,
                action,
                reason or f"panel:{action}",
                cid,
            )
        except Exception:
            pass
    return {
        "ok": ok,
        "action": action,
        "chat_id": cid,
        "user_id": uid,
        "telegram": res.get("description") if not ok else "ok",
        "reason": reason,
    }
