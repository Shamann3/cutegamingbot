# -*- coding: utf-8 -*-
"""Админская аналитика групповой капчи."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from db import db

from bot.funcs.group_captcha import VARIANT_LABELS, ensure_tables


def _iint(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _label(variant: Any) -> str:
    try:
        return VARIANT_LABELS.get(int(variant), str(variant))
    except Exception:
        return str(variant or "—")


async def _ready() -> bool:
    pool = getattr(db, "pool", None)
    if pool is None:
        return False
    try:
        await ensure_tables(pool)
        return True
    except Exception:
        return False


async def user_captcha(user_id: int) -> Dict[str, Any]:
    empty = {
        "passedGroups": 0,
        "fails": 0,
        "shown": 0,
        "firstTryPasses": 0,
        "avgDurationMs": None,
        "lastPassedAt": None,
        "groups": [],
        "hardestVariant": None,
        "favoriteVariant": None,
    }
    if not await _ready():
        return empty
    uid = int(user_id)
    try:
        passes = await db.pool.fetch(
            """
            SELECT p.chat_id, p.passed_at, p.variant, p.attempts, p.duration_ms, p.trigger,
                   c.namechat, c.usernamechat
              FROM group_captcha_passes p
              LEFT JOIN chat c ON c.chat_id = p.chat_id
             WHERE p.user_id = $1
             ORDER BY p.passed_at DESC
             LIMIT 80
            """,
            uid,
        )
    except Exception:
        return empty

    groups = []
    durations: List[int] = []
    first_try = 0
    variant_counts: Dict[str, int] = {}
    for r in passes:
        dur = r["duration_ms"]
        if dur is not None:
            durations.append(int(dur))
        if int(r["attempts"] or 1) <= 1:
            first_try += 1
        key = str(r["variant"])
        variant_counts[key] = variant_counts.get(key, 0) + 1
        groups.append({
            "chatId": int(r["chat_id"]),
            "name": r["namechat"] or str(r["chat_id"]),
            "username": r["usernamechat"],
            "variant": key,
            "variantLabel": _label(key),
            "attempts": _iint(r["attempts"], 1),
            "durationMs": None if dur is None else int(dur),
            "trigger": r["trigger"],
            "passedAt": _iso(r["passed_at"]),
        })

    fails = 0
    shown = 0
    fail_by_variant: Dict[str, int] = {}
    try:
        ev = await db.pool.fetch(
            """
            SELECT event, variant, count(*)::int AS n
              FROM group_captcha_events
             WHERE user_id = $1 AND event IN ('fail', 'shown')
             GROUP BY event, variant
            """,
            uid,
        )
        for r in ev:
            if r["event"] == "fail":
                fails += int(r["n"])
                if r["variant"]:
                    fail_by_variant[str(r["variant"])] = int(r["n"])
            elif r["event"] == "shown":
                shown += int(r["n"])
    except Exception:
        pass

    hardest = None
    if fail_by_variant:
        hardest_key = max(fail_by_variant, key=fail_by_variant.get)
        hardest = {"variant": hardest_key, "label": _label(hardest_key), "fails": fail_by_variant[hardest_key]}
    favorite = None
    if variant_counts:
        fav_key = max(variant_counts, key=variant_counts.get)
        favorite = {"variant": fav_key, "label": _label(fav_key), "passes": variant_counts[fav_key]}

    return {
        "passedGroups": len(groups),
        "fails": fails,
        "shown": shown,
        "firstTryPasses": first_try,
        "avgDurationMs": int(sum(durations) / len(durations)) if durations else None,
        "lastPassedAt": groups[0]["passedAt"] if groups else None,
        "groups": groups,
        "hardestVariant": hardest,
        "favoriteVariant": favorite,
    }


async def chat_captcha(chat_id: int, *, members: Optional[int] = None) -> Dict[str, Any]:
    empty = {
        "enabled": True,
        "disabledAt": None,
        "disabledBy": None,
        "passed": 0,
        "fails": 0,
        "shown": 0,
        "pending": 0,
        "passRate": None,
        "avgDurationMs": None,
        "notPassedHint": None,
        "variants": [],
        "recentFails": [],
        "recentPasses": [],
        "nightPasses": 0,
        "joinPasses": 0,
        "messagePasses": 0,
    }
    if not await _ready():
        return empty
    cid = int(chat_id)
    enabled = True
    disabled_at = None
    disabled_by = None
    try:
        st = await db.pool.fetchrow(
            "SELECT enabled, disabled_at, disabled_by FROM group_captcha_settings WHERE chat_id = $1",
            cid,
        )
        if st:
            enabled = bool(st["enabled"])
            disabled_at = _iso(st["disabled_at"])
            disabled_by = None if st["disabled_by"] is None else int(st["disabled_by"])
    except Exception:
        pass

    passed = 0
    avg_ms = None
    join_passes = 0
    message_passes = 0
    night_passes = 0
    try:
        row = await db.pool.fetchrow(
            """
            SELECT count(*)::int AS n,
                   avg(duration_ms)::int AS avg_ms,
                   count(*) FILTER (WHERE trigger = 'join')::int AS join_n,
                   count(*) FILTER (WHERE trigger = 'message')::int AS msg_n,
                   count(*) FILTER (
                       WHERE EXTRACT(HOUR FROM passed_at AT TIME ZONE 'Europe/Moscow') < 6
                          OR EXTRACT(HOUR FROM passed_at AT TIME ZONE 'Europe/Moscow') >= 23
                   )::int AS night_n
              FROM group_captcha_passes
             WHERE chat_id = $1
            """,
            cid,
        )
        if row:
            passed = _iint(row["n"])
            avg_ms = None if row["avg_ms"] is None else int(row["avg_ms"])
            join_passes = _iint(row["join_n"])
            message_passes = _iint(row["msg_n"])
            night_passes = _iint(row["night_n"])
    except Exception:
        pass

    shown = 0
    fails = 0
    try:
        ev = await db.pool.fetchrow(
            """
            SELECT count(*) FILTER (WHERE event = 'shown')::int AS shown,
                   count(*) FILTER (WHERE event = 'fail')::int AS fails
              FROM group_captcha_events
             WHERE chat_id = $1
            """,
            cid,
        )
        if ev:
            shown = _iint(ev["shown"])
            fails = _iint(ev["fails"])
    except Exception:
        pass

    pending = 0
    try:
        pending = _iint(await db.pool.fetchval(
            "SELECT count(*) FROM group_captcha_challenges WHERE chat_id = $1 AND expires_at > NOW()",
            cid,
        ))
    except Exception:
        pass

    variants: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT variant,
                   count(*) FILTER (WHERE event = 'shown')::int AS shown,
                   count(*) FILTER (WHERE event = 'pass')::int AS passed,
                   count(*) FILTER (WHERE event = 'fail')::int AS fails
              FROM group_captcha_events
             WHERE chat_id = $1 AND variant IS NOT NULL
             GROUP BY variant
             ORDER BY shown DESC
            """,
            cid,
        )
        for r in rows:
            s = _iint(r["shown"])
            p = _iint(r["passed"])
            f = _iint(r["fails"])
            variants.append({
                "variant": str(r["variant"]),
                "label": _label(r["variant"]),
                "shown": s,
                "passed": p,
                "fails": f,
                "failRate": round(100.0 * f / max(1, f + p), 1),
            })
    except Exception:
        pass

    recent_fails: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT e.user_id, e.variant, e.created_at, e.meta,
                   u.first_name, u.username
              FROM group_captcha_events e
              LEFT JOIN users u ON u.user_id = e.user_id
             WHERE e.chat_id = $1 AND e.event = 'fail'
             ORDER BY e.created_at DESC
             LIMIT 20
            """,
            cid,
        )
        for r in rows:
            recent_fails.append({
                "userId": int(r["user_id"]),
                "name": r["first_name"] or str(r["user_id"]),
                "username": r["username"],
                "variant": str(r["variant"] or ""),
                "variantLabel": _label(r["variant"]),
                "at": _iso(r["created_at"]),
                "pick": (r["meta"] or {}).get("pick") if isinstance(r["meta"], dict) else None,
            })
    except Exception:
        pass

    recent_passes: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT p.user_id, p.variant, p.passed_at, p.attempts, p.duration_ms,
                   u.first_name, u.username
              FROM group_captcha_passes p
              LEFT JOIN users u ON u.user_id = p.user_id
             WHERE p.chat_id = $1
             ORDER BY p.passed_at DESC
             LIMIT 20
            """,
            cid,
        )
        for r in rows:
            recent_passes.append({
                "userId": int(r["user_id"]),
                "name": r["first_name"] or str(r["user_id"]),
                "username": r["username"],
                "variant": str(r["variant"] or ""),
                "variantLabel": _label(r["variant"]),
                "attempts": _iint(r["attempts"], 1),
                "durationMs": None if r["duration_ms"] is None else int(r["duration_ms"]),
                "at": _iso(r["passed_at"]),
            })
    except Exception:
        pass

    not_passed_hint = None
    if members and members > 0:
        not_passed_hint = max(0, int(members) - passed)

    pass_rate = None
    if shown > 0:
        pass_rate = round(100.0 * passed / shown, 1)

    return {
        "enabled": enabled,
        "disabledAt": disabled_at,
        "disabledBy": disabled_by,
        "passed": passed,
        "fails": fails,
        "shown": shown,
        "pending": pending,
        "passRate": pass_rate,
        "avgDurationMs": avg_ms,
        "notPassedHint": not_passed_hint,
        "variants": variants,
        "recentFails": recent_fails,
        "recentPasses": recent_passes,
        "nightPasses": night_passes,
        "joinPasses": join_passes,
        "messagePasses": message_passes,
    }


async def overview_captcha() -> Dict[str, Any]:
    empty = {
        "enabledChats": 0,
        "disabledChats": 0,
        "passed": 0,
        "fails": 0,
        "shown": 0,
        "pending": 0,
        "uniqueUsers": 0,
        "passRate": None,
        "avgDurationMs": None,
        "firstTryRate": None,
        "hardestVariant": None,
        "easiestVariant": None,
        "variants": [],
        "topFailUsers": [],
        "topGroups": [],
        "nightShare": None,
        "facts": [],
    }
    if not await _ready():
        return empty

    disabled_chats = 0
    try:
        disabled_chats = _iint(await db.pool.fetchval(
            "SELECT count(*) FROM group_captcha_settings WHERE enabled = FALSE"
        ))
    except Exception:
        pass

    totals = {"passed": 0, "fails": 0, "shown": 0, "pending": 0, "unique_users": 0, "avg_ms": None, "first_try": 0, "night": 0}
    try:
        row = await db.pool.fetchrow(
            """
            SELECT count(*)::int AS passed,
                   count(DISTINCT user_id)::int AS unique_users,
                   avg(duration_ms)::int AS avg_ms,
                   count(*) FILTER (WHERE attempts <= 1)::int AS first_try,
                   count(*) FILTER (
                       WHERE EXTRACT(HOUR FROM passed_at AT TIME ZONE 'Europe/Moscow') < 6
                          OR EXTRACT(HOUR FROM passed_at AT TIME ZONE 'Europe/Moscow') >= 23
                   )::int AS night
              FROM group_captcha_passes
            """
        )
        if row:
            totals["passed"] = _iint(row["passed"])
            totals["unique_users"] = _iint(row["unique_users"])
            totals["avg_ms"] = None if row["avg_ms"] is None else int(row["avg_ms"])
            totals["first_try"] = _iint(row["first_try"])
            totals["night"] = _iint(row["night"])
    except Exception:
        pass
    try:
        ev = await db.pool.fetchrow(
            """
            SELECT count(*) FILTER (WHERE event = 'shown')::int AS shown,
                   count(*) FILTER (WHERE event = 'fail')::int AS fails
              FROM group_captcha_events
            """
        )
        if ev:
            totals["shown"] = _iint(ev["shown"])
            totals["fails"] = _iint(ev["fails"])
    except Exception:
        pass
    try:
        totals["pending"] = _iint(await db.pool.fetchval(
            "SELECT count(*) FROM group_captcha_challenges WHERE expires_at > NOW()"
        ))
    except Exception:
        pass

    variants: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT variant,
                   count(*) FILTER (WHERE event = 'shown')::int AS shown,
                   count(*) FILTER (WHERE event = 'pass')::int AS passed,
                   count(*) FILTER (WHERE event = 'fail')::int AS fails
              FROM group_captcha_events
             WHERE variant IS NOT NULL
             GROUP BY variant
            """
        )
        for r in rows:
            p = _iint(r["passed"])
            f = _iint(r["fails"])
            variants.append({
                "variant": str(r["variant"]),
                "label": _label(r["variant"]),
                "shown": _iint(r["shown"]),
                "passed": p,
                "fails": f,
                "failRate": round(100.0 * f / max(1, f + p), 1),
            })
        variants.sort(key=lambda x: x["shown"], reverse=True)
    except Exception:
        pass

    hardest = easiest = None
    scored = [v for v in variants if (v["passed"] + v["fails"]) >= 3]
    if scored:
        hardest = max(scored, key=lambda x: x["failRate"])
        easiest = min(scored, key=lambda x: x["failRate"])

    top_fail_users: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT e.user_id, count(*)::int AS fails, max(u.first_name) AS first_name, max(u.username) AS username
              FROM group_captcha_events e
              LEFT JOIN users u ON u.user_id = e.user_id
             WHERE e.event = 'fail'
             GROUP BY e.user_id
             ORDER BY fails DESC
             LIMIT 8
            """
        )
        for r in rows:
            top_fail_users.append({
                "userId": int(r["user_id"]),
                "name": r["first_name"] or str(r["user_id"]),
                "username": r["username"],
                "fails": int(r["fails"]),
            })
    except Exception:
        pass

    top_groups: List[Dict[str, Any]] = []
    try:
        rows = await db.pool.fetch(
            """
            SELECT p.chat_id, count(*)::int AS passed,
                   max(c.namechat) AS name, max(c.usernamechat) AS username
              FROM group_captcha_passes p
              LEFT JOIN chat c ON c.chat_id = p.chat_id
             GROUP BY p.chat_id
             ORDER BY passed DESC
             LIMIT 8
            """
        )
        for r in rows:
            top_groups.append({
                "chatId": int(r["chat_id"]),
                "name": r["name"] or str(r["chat_id"]),
                "username": r["username"],
                "passed": int(r["passed"]),
            })
    except Exception:
        pass

    pass_rate = round(100.0 * totals["passed"] / totals["shown"], 1) if totals["shown"] else None
    first_try_rate = round(100.0 * totals["first_try"] / totals["passed"], 1) if totals["passed"] else None
    night_share = round(100.0 * totals["night"] / totals["passed"], 1) if totals["passed"] else None

    facts = []
    if pass_rate is not None:
        facts.append(f"Доходят до успеха {pass_rate}% показанных карточек")
    if first_try_rate is not None:
        facts.append(f"С первой попытки проходят {first_try_rate}%")
    if hardest:
        facts.append(f"Чаще всего путают «{hardest['label']}» — {hardest['failRate']}% ошибок")
    if easiest:
        facts.append(f"Самый лёгкий тип — «{easiest['label']}»")
    if night_share:
        facts.append(f"{night_share}% прохождений ночью по Москве")
    if totals["pending"]:
        facts.append(f"Сейчас висят {totals['pending']} незакрытых карточек")
    if disabled_chats:
        facts.append(f"Владельцы выключили капчу в {disabled_chats} группах")
    if not facts:
        facts.append("Капча только запускается — факты появятся после первых прохождений")

    return {
        "enabledChats": max(0, len(top_groups)),  # ориентир по группам с прохождениями
        "disabledChats": disabled_chats,
        "passed": totals["passed"],
        "fails": totals["fails"],
        "shown": totals["shown"],
        "pending": totals["pending"],
        "uniqueUsers": totals["unique_users"],
        "passRate": pass_rate,
        "avgDurationMs": totals["avg_ms"],
        "firstTryRate": first_try_rate,
        "hardestVariant": hardest,
        "easiestVariant": easiest,
        "variants": variants,
        "topFailUsers": top_fail_users,
        "topGroups": top_groups,
        "nightShare": night_share,
        "facts": facts,
    }
