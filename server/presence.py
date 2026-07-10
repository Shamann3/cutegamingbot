"""Онлайн игроков: last_seen, снимки и пик по дням."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from config import (
    ANALYTICS_TZ,
    ONLINE_SNAPSHOT_INTERVAL_SECONDS,
    ONLINE_WINDOW_SECONDS,
    PRESENCE_TOUCH_INTERVAL_SECONDS,
)
from db import db

logger = logging.getLogger("cute-farm")

_presence_touch_at: dict[int, float] = {}
PRESENCE_TOUCH_INTERVAL = float(max(5, PRESENCE_TOUCH_INTERVAL_SECONDS))

# Max entries in the throttle dict. Evicts the oldest when exceeded.
# At 100 concurrent players with 30-min sessions this stays under ~200 entries.
_MAX_PRESENCE_ENTRIES = 10_000


def _analytics_tz():
    from zoneinfo import ZoneInfo

    return ZoneInfo(ANALYTICS_TZ)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _local_today() -> date:
    return _utcnow().astimezone(_analytics_tz()).date()


async def touch_user(user_id: int) -> None:
    await db.pool.execute(
        "UPDATE users SET last_seen_at = NOW() WHERE user_id = $1",
        user_id,
    )


async def touch_user_throttled(user_id: int, *, now: float | None = None, force: bool = False) -> None:
    import time

    ts = now if now is not None else time.time()
    if not force:
        last = _presence_touch_at.get(user_id, 0.0)
        if ts - last < PRESENCE_TOUCH_INTERVAL:
            return

    # Evict oldest entries when the dict grows too large (e.g. server running for months
    # accumulates entries for all historical users that never disconnect cleanly).
    if len(_presence_touch_at) >= _MAX_PRESENCE_ENTRIES:
        oldest_uid = min(_presence_touch_at, key=_presence_touch_at.__getitem__)
        del _presence_touch_at[oldest_uid]

    _presence_touch_at[user_id] = ts
    await touch_user(user_id)


async def mark_user_online(user_id: int) -> None:
    """Отметить игрока онлайн (throttled UPDATE last_seen_at)."""
    await touch_user_throttled(user_id)


async def mark_user_offline(user_id: int) -> None:
    """Снять игрока с онлайна сразу (закрыл WebApp)."""
    _presence_touch_at.pop(user_id, None)
    await db.pool.execute(
        "UPDATE users SET last_seen_at = NULL WHERE user_id = $1",
        user_id,
    )


async def count_online() -> int:
    window_sec = max(15, ONLINE_WINDOW_SECONDS)
    return int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM users
            WHERE last_seen_at IS NOT NULL
              AND last_seen_at >= NOW() - ($1 * INTERVAL '1 second')
            """,
            window_sec,
        )
        or 0
    )


async def record_snapshot() -> int:
    online = await count_online()
    now = _utcnow()

    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO online_snapshots (recorded_at, online_count) VALUES ($1, $2)",
            now,
            online,
        )

        stat_date = now.astimezone(_analytics_tz()).date()
        row = await conn.fetchrow(
            "SELECT peak_online FROM online_daily_stats WHERE stat_date = $1",
            stat_date,
        )
        if row is None:
            await conn.execute(
                """
                INSERT INTO online_daily_stats (stat_date, peak_online, peak_at)
                VALUES ($1, $2, $3)
                """,
                stat_date,
                online,
                now,
            )
        elif online > int(row["peak_online"]):
            await conn.execute(
                """
                UPDATE online_daily_stats
                SET peak_online = $2, peak_at = $3
                WHERE stat_date = $1
                """,
                stat_date,
                online,
                now,
            )

        await conn.execute(
            """
            DELETE FROM online_snapshots
            WHERE recorded_at < NOW() - INTERVAL '90 days'
            """,
        )

    return online


async def get_online_summary() -> dict:
    online_now = await count_online()
    today = _local_today()
    row = await db.pool.fetchrow(
        """
        SELECT peak_online, peak_at
        FROM online_daily_stats
        WHERE stat_date = $1
        """,
        today,
    )
    peak = int(row["peak_online"]) if row else 0
    peak_at = row["peak_at"] if row else None
    if online_now > peak:
        peak = online_now
        peak_at = _utcnow()

    return {
        "onlineNow": online_now,
        "todayPeak": peak,
        "todayPeakAt": peak_at.isoformat() if peak_at else None,
        "windowSeconds": max(15, ONLINE_WINDOW_SECONDS),
    }


async def get_day_analytics(day: date) -> dict:
    tz = _analytics_tz()
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)

    daily = await db.pool.fetchrow(
        """
        SELECT peak_online, peak_at
        FROM online_daily_stats
        WHERE stat_date = $1
        """,
        day,
    )

    rows = await db.pool.fetch(
        """
        SELECT
            EXTRACT(HOUR FROM recorded_at AT TIME ZONE $3)::int AS hour,
            MAX(online_count)::int AS peak,
            AVG(online_count)::int AS avg
        FROM online_snapshots
        WHERE recorded_at >= $1 AND recorded_at < $2
        GROUP BY 1
        ORDER BY 1
        """,
        start,
        end,
        ANALYTICS_TZ,
    )

    hours = {int(r["hour"]): {"hour": int(r["hour"]), "peak": int(r["peak"]), "avg": int(r["avg"])} for r in rows}
    timeline = []
    for h in range(24):
        if h in hours:
            timeline.append(hours[h])
        else:
            timeline.append({"hour": h, "peak": 0, "avg": 0})

    snapshot_peak = max((h["peak"] for h in timeline), default=0)
    peak = int(daily["peak_online"]) if daily else snapshot_peak
    peak_at = daily["peak_at"] if daily else None

    return {
        "date": day.isoformat(),
        "peak": peak,
        "peakAt": peak_at.isoformat() if peak_at else None,
        "avg": _average_from_hours(timeline),
        "hours": timeline,
        "hasData": bool(rows),
        "granularity": "hour",
        "timezone": ANALYTICS_TZ,
    }


def _average_from_hours(hours: list[dict]) -> int:
    active = [h for h in hours if h.get("peak", 0) > 0 or h.get("avg", 0) > 0]
    if not active:
        return 0
    return round(sum(int(h.get("avg", 0)) for h in active) / len(active))


async def get_range_analytics(from_date: date, to_date: date) -> dict:
    if to_date < from_date:
        raise ValueError("to must be >= from")
    span_days = (to_date - from_date).days + 1
    if span_days > 90:
        raise ValueError("range too large (max 90 days)")

    tz = _analytics_tz()
    start_local = datetime.combine(from_date, datetime.min.time(), tzinfo=tz)
    end_local = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    daily_rows = await db.pool.fetch(
        """
        SELECT stat_date, peak_online, peak_at
        FROM online_daily_stats
        WHERE stat_date >= $1 AND stat_date <= $2
        ORDER BY stat_date
        """,
        from_date,
        to_date,
    )
    daily_map = {
        r["stat_date"]: {
            "peak": int(r["peak_online"]),
            "peakAt": r["peak_at"],
        }
        for r in daily_rows
    }

    avg_rows = await db.pool.fetch(
        """
        SELECT
            (recorded_at AT TIME ZONE $3)::date AS stat_date,
            AVG(online_count)::int AS avg,
            COUNT(*)::int AS samples
        FROM online_snapshots
        WHERE recorded_at >= $1 AND recorded_at < $2
        GROUP BY 1
        ORDER BY 1
        """,
        start_utc,
        end_utc,
        ANALYTICS_TZ,
    )
    avg_map = {r["stat_date"]: int(r["avg"]) for r in avg_rows}

    today = _local_today()
    online_now = await count_online() if to_date >= today else 0

    timeline: list[dict] = []
    cursor = from_date
    while cursor <= to_date:
        daily = daily_map.get(cursor, {"peak": 0, "peakAt": None})
        peak = daily["peak"]
        peak_at = daily["peakAt"]
        if cursor == today and online_now > peak:
            peak = online_now
            peak_at = _utcnow()
        timeline.append(
            {
                "date": cursor.isoformat(),
                "peak": peak,
                "avg": avg_map.get(cursor, 0),
                "peakAt": peak_at.isoformat() if peak_at else None,
            }
        )
        cursor += timedelta(days=1)

    peaks = [p["peak"] for p in timeline if p["peak"] > 0]
    avgs = [p["avg"] for p in timeline if p["avg"] > 0]
    best = max(timeline, key=lambda p: p["peak"], default=None)
    peak_total = max(peaks) if peaks else 0
    avg_total = round(sum(avgs) / len(avgs)) if avgs else 0

    return {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "peak": peak_total,
        "peakAt": best["peakAt"] if best and best["peak"] > 0 else None,
        "peakDate": best["date"] if best and best["peak"] > 0 else None,
        "avg": avg_total,
        "points": timeline,
        "hasData": bool(daily_rows or avg_rows),
        "granularity": "day",
        "timezone": ANALYTICS_TZ,
    }


async def online_snapshot_loop(stop: asyncio.Event) -> None:
    interval = max(15, ONLINE_SNAPSHOT_INTERVAL_SECONDS)
    while not stop.is_set():
        try:
            await record_snapshot()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("online snapshot failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
