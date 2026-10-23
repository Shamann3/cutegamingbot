# -*- coding: utf-8 -*-
"""Огонёк сообщений: серия, тёплый час, статусы, подарочный бонус 🎁."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

MSK = timezone(timedelta(hours=3))
KINDS = ("bonus", "bonus_x2", "item", "kuty")
WARM_KINDS = ("bonus", "bonus_x2", "item", "kuty")
GIFT_KINDS = ("kuty", "item")
EMOJI = "5355118129783553944"
STATUS_EMOJI = "5355118129783553944"

_DEFAULTS = {
    "enabled": False,
    "base_messages": 200,
    "warm_enabled": False,
    "warm_min_day": 3,
    "warm_every": 40,
    "warm_cap": 3,
    "warm_from": 15,
    "warm_to": 24,
    "status_enabled": True,
    "profit_enabled": True,
    "profit_hour": 21,
    "min_words": 2,
    "block_dup": True,
    "gift_enabled": True,
    "gift_mult": 1,
    "gift_kuty_min": 1,
    "gift_kuty_max": 3,
    "gift_extra_kuty_on": True,
    "gift_extra_kuty_chance": 35,
    "gift_extra_kuty_min": 5,
    "gift_extra_kuty_max": 25,
    "gift_item_on": True,
    "gift_item_chance": 40,
    "gift_item_count": 1,
    "gift_fallback_pct": 30,
    "restore_enabled": True,
    "restore_days": 3,
    "restore_kuty": 500,
    "restore_item": "",
    "restore_item_count": 1,
    "gift_cell_emojis": "",
}


def msk_today(now: datetime | None = None) -> date:
    moment = now or datetime.now(MSK)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=MSK)
    return moment.astimezone(MSK).date()


def msk_now(now: datetime | None = None) -> datetime:
    moment = now or datetime.now(MSK)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=MSK)
    return moment.astimezone(MSK)


def ru_count(n: int, one: str, few: str, many: str) -> str:
    num = abs(int(n))
    n10, n100 = num % 10, num % 100
    if n10 == 1 and n100 != 11:
        word = one
    elif 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        word = few
    else:
        word = many
    return f"{num} {word}"


def span_label(days: int) -> str:
    left = max(0, int(days))
    if left <= 0:
        return "0 дней"
    years, rem = divmod(left, 365)
    months, day = divmod(rem, 30)
    parts: list[str] = []
    if years:
        parts.append(ru_count(years, "год", "года", "лет"))
    if months:
        parts.append(ru_count(months, "месяц", "месяца", "месяцев"))
    if day or not parts:
        parts.append(ru_count(day, "день", "дня", "дней"))
    return " ".join(parts)


def need_for(day: int, base: int, steps: list[dict]) -> int:
    target = max(1, int(day))
    floor = max(1, int(base or 1))
    best_from = 0
    chosen = floor
    for step in steps or []:
        start = int(step.get("from_day") or step.get("fromDay") or 0)
        messages = int(step.get("messages") or 0)
        if start < 1 or messages < 1:
            continue
        if start <= target and start >= best_from:
            best_from = start
            chosen = messages
    return chosen


def title_for(days: int, titles: list[dict]) -> dict | None:
    best = None
    for row in titles or []:
        start = int(row.get("from_day") or row.get("fromDay") or 0)
        name = str(row.get("title") or "").strip()
        if start < 1 or not name:
            continue
        if start <= int(days or 0) and (best is None or start >= int(best["from_day"])):
            best = {
                "from_day": start,
                "title": name,
                "emoji_id": str(row.get("emoji_id") or row.get("emojiId") or STATUS_EMOJI),
            }
    return best


def profile_line(days: int, titles: list[dict] | None = None) -> str:
    if int(days or 0) <= 0:
        return ""
    from flame_copy import profile_line as draw

    badge = title_for(days, titles or [])
    label = span_label(days)
    if badge:
        return draw(label, badge["title"], badge["emoji_id"] or STATUS_EMOJI)
    return draw(label)


def _reward_line(row: dict) -> str:
    day = int(row.get("day") or 0)
    if day < 1:
        return ""
    kind = str(row.get("kind") or "")
    amount = max(1, int(row.get("amount") or 1))
    item = str(row.get("item_name") or row.get("itemName") or "").strip()
    gift = _kind_words(kind, amount, item)
    if not gift:
        return ""
    return f"· <b>{span_label(day)}</b> — {gift}"


def _reward_lines_grouped(rewards: list[dict]) -> list[str]:
    """Одна строка на день: все подарки этого дня через «·»."""
    by_day: dict[int, list[str]] = {}
    for row in sorted(rewards or [], key=lambda item: (int(item.get("day") or 0), int(item.get("id") or 0))):
        day = int(row.get("day") or 0)
        if day < 1:
            continue
        kind = str(row.get("kind") or "")
        amount = max(1, int(row.get("amount") or 1))
        item = str(row.get("item_name") or row.get("itemName") or "").strip()
        gift = _kind_words(kind, amount, item)
        if not gift:
            continue
        by_day.setdefault(day, []).append(gift)
    lines = []
    for day in sorted(by_day):
        gifts = by_day[day]
        body = " · ".join(gifts)
        lines.append(f"· <b>{span_label(day)}</b> — {body}")
    return lines


def _kind_words(kind: str, amount: int, item: str = "") -> str:
    from flame_copy import kind_words

    return kind_words(kind, amount, item)


def restore_price(settings: dict | None) -> dict:
    """Цена возврата из вкладки. enabled — только если есть чем платить."""
    raw = settings or {}
    asked = bool(raw.get("restore_enabled"))
    days = max(1, min(30, int(raw.get("restore_days") or 3)))
    kuty = max(0, min(10_000_000, int(raw.get("restore_kuty") or 0)))
    item = str(raw.get("restore_item") or "").strip()[:80]
    count = max(1, min(100, int(raw.get("restore_item_count") or 1)))
    if not item:
        count = 0
    buyable = asked and (kuty > 0 or bool(item))
    return {
        "enabled": buyable,
        "days": days,
        "kuty": kuty if asked else 0,
        "item": item if asked else "",
        "count": count if asked and item else 0,
    }


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def gap_starts_new_series(last: date | None, today: date) -> bool:
    """Пропуск дня начинает новую серию и сжигает право вернуть старую."""
    kept = _as_date(last)
    if kept is None:
        return False
    return kept < today - timedelta(days=1)


def restore_view(
    streak: int,
    lost: int,
    lost_on,
    settings: dict | None,
    today: date,
) -> dict:
    """off | alive | none | late | ready. Оплата сюда не входит."""
    price = restore_price(settings)
    view = {**price, "code": "off", "label": "", "days_left": 0, "streak": 0}
    if not price["enabled"]:
        return view
    if int(streak or 0) > 0:
        view["code"] = "alive"
        return view
    lost_days = int(lost or 0)
    died = _as_date(lost_on)
    if lost_days < 1 or died is None:
        view["code"] = "none"
        return view
    age = (today - died).days
    if age < 0 or age >= price["days"]:
        view["code"] = "late"
        return view
    view.update({
        "code": "ready",
        "label": span_label(lost_days),
        "days_left": price["days"] - age,
        "streak": lost_days,
    })
    return view


def help_html(board: dict) -> str:
    from flame_copy import restore_help_line, screen_help

    settings = board.get("settings") or {}
    steps = board.get("steps") or []
    rewards = board.get("rewards") or []
    titles = board.get("titles") or []
    warm = board.get("warm") or {}
    gift = board.get("gift") or {}
    rises = []
    for step in sorted(steps, key=lambda row: int(row.get("from_day") or 0)):
        start = int(step.get("from_day") or 0)
        messages = int(step.get("messages") or 0)
        if start <= 1 or messages < 1:
            continue
        rises.append(f"с {start}-го — <b>{messages}</b>")
    lines = _reward_lines_grouped(rewards)
    title_lines = []
    for row in sorted(titles, key=lambda item: int(item.get("from_day") or 0)):
        start = int(row.get("from_day") or 0)
        name = str(row.get("title") or "").strip()
        if start < 1 or not name:
            continue
        title_lines.append(f"· с {span_label(start)} — <b>{name}</b>")
    warm_hour = ""
    if warm.get("hour") is not None:
        hour = int(warm["hour"])
        warm_hour = f"{hour:02d}:00–{(hour + 1) % 24:02d}:00"
    price = restore_price(settings)
    restore_line = ""
    if price["enabled"]:
        restore_line = restore_help_line(
            days=price["days"],
            kuty=price["kuty"],
            item=price["item"],
            count=price["count"],
        )
    return screen_help(
        base=int(settings.get("base_messages") or 200),
        words=int(settings.get("min_words") or 2),
        enabled=bool(settings.get("enabled")),
        rises=rises,
        rewards=lines,
        titles=title_lines,
        warm_on=bool(warm.get("enabled")),
        warm_from=span_label(int(warm.get("min_day") or 3)),
        warm_every=int(warm.get("every") or 40),
        warm_cap=int(warm.get("cap") or 3),
        warm_hour=warm_hour,
        gift_on=bool(gift.get("enabled")),
        gift_mult=int(gift.get("mult") or 1),
        gift_item_count=int(gift.get("item_count") or settings.get("gift_item_count") or 1),
        restore_line=restore_line,
    )


async def _add_column(pool, table: str, column: str, spec: str) -> None:
    exists = await pool.fetchval(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = $1 AND column_name = $2
        """,
        table,
        column,
    )
    if not exists:
        await pool.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")


async def ensure_tables(pool) -> None:
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_settings (
            id INT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            base_messages INT NOT NULL DEFAULT 200
        )
        """
    )
    await pool.execute(
        """
        INSERT INTO flame_settings (id, enabled, base_messages)
        VALUES (1, FALSE, 200)
        ON CONFLICT (id) DO NOTHING
        """
    )
    for column, spec in (
        ("warm_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("warm_min_day", "INT NOT NULL DEFAULT 3"),
        ("warm_every", "INT NOT NULL DEFAULT 40"),
        ("warm_cap", "INT NOT NULL DEFAULT 3"),
        ("warm_from", "INT NOT NULL DEFAULT 15"),
        ("warm_to", "INT NOT NULL DEFAULT 24"),
        ("status_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("profit_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("profit_hour", "INT NOT NULL DEFAULT 21"),
        ("min_words", "INT NOT NULL DEFAULT 2"),
        ("block_dup", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("gift_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("gift_mult", "INT NOT NULL DEFAULT 1"),
        ("gift_kuty_min", "INT NOT NULL DEFAULT 1"),
        ("gift_kuty_max", "INT NOT NULL DEFAULT 3"),
        ("gift_extra_kuty_on", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("gift_extra_kuty_chance", "INT NOT NULL DEFAULT 35"),
        ("gift_extra_kuty_min", "INT NOT NULL DEFAULT 5"),
        ("gift_extra_kuty_max", "INT NOT NULL DEFAULT 25"),
        ("gift_item_on", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("gift_item_chance", "INT NOT NULL DEFAULT 40"),
        ("gift_item_count", "INT NOT NULL DEFAULT 1"),
        ("gift_fallback_pct", "INT NOT NULL DEFAULT 30"),
        ("restore_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("restore_days", "INT NOT NULL DEFAULT 3"),
        ("restore_kuty", "INT NOT NULL DEFAULT 500"),
        ("restore_item", "TEXT NOT NULL DEFAULT ''"),
        ("restore_item_count", "INT NOT NULL DEFAULT 1"),
        ("gift_cell_emojis", "TEXT NOT NULL DEFAULT ''"),
    ):
        await _add_column(pool, "flame_settings", column, spec)

    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_steps (
            from_day INT PRIMARY KEY,
            messages INT NOT NULL
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_rewards (
            id BIGSERIAL PRIMARY KEY,
            day INT NOT NULL,
            kind TEXT NOT NULL,
            amount INT NOT NULL DEFAULT 1,
            item_name TEXT NOT NULL DEFAULT ''
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_titles (
            from_day INT PRIMARY KEY,
            title TEXT NOT NULL,
            emoji_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_warm_day (
            day DATE PRIMARY KEY,
            hour INT NOT NULL
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_warm_rewards (
            id BIGSERIAL PRIMARY KEY,
            kind TEXT NOT NULL,
            amount INT NOT NULL DEFAULT 1,
            item_name TEXT NOT NULL DEFAULT '',
            weight INT NOT NULL DEFAULT 1
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_gift_drops (
            id BIGSERIAL PRIMARY KEY,
            kind TEXT NOT NULL,
            amount_min INT NOT NULL DEFAULT 1,
            amount_max INT NOT NULL DEFAULT 1,
            item_name TEXT NOT NULL DEFAULT '',
            weight INT NOT NULL DEFAULT 1,
            show_preview BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    await _add_column(pool, "flame_gift_drops", "show_preview", "BOOLEAN NOT NULL DEFAULT FALSE")
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_users (
            user_id BIGINT PRIMARY KEY,
            streak_days INT NOT NULL DEFAULT 0,
            best_days INT NOT NULL DEFAULT 0,
            last_kept DATE,
            bonus_opens INT NOT NULL DEFAULT 0,
            bonus_x2 INT NOT NULL DEFAULT 0
        )
        """
    )
    for column, spec in (
        ("warm_day", "DATE"),
        ("warm_count", "INT NOT NULL DEFAULT 0"),
        ("warm_hits", "INT NOT NULL DEFAULT 0"),
        ("profit_day", "DATE"),
        ("lost_streak", "INT NOT NULL DEFAULT 0"),
        ("lost_on", "DATE"),
    ):
        await _add_column(pool, "flame_users", column, spec)

    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_grants (
            user_id BIGINT NOT NULL,
            reward_id BIGINT NOT NULL,
            PRIMARY KEY (user_id, reward_id)
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS flame_loot (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            source TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount INT NOT NULL DEFAULT 1,
            item_name TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        "CREATE INDEX IF NOT EXISTS flame_loot_user_idx ON flame_loot (user_id, id DESC)"
    )


def _board_cells(settings: dict | None) -> list[dict]:
    from flame_bonus_plus import board_cells
    return board_cells((settings or {}).get("gift_cell_emojis"))


def _row_settings(row) -> dict:
    out = dict(_DEFAULTS)
    if not row:
        return out
    out["enabled"] = bool(row["enabled"])
    out["base_messages"] = int(row["base_messages"] or 200)
    keys = set(row.keys())
    for key in (
        "warm_enabled", "status_enabled", "profit_enabled", "block_dup", "gift_enabled",
        "gift_extra_kuty_on", "gift_item_on", "restore_enabled",
    ):
        if key in keys:
            out[key] = bool(row[key])
    for key in (
        "warm_min_day", "warm_every", "warm_cap", "warm_from", "warm_to",
        "profit_hour", "min_words", "gift_mult", "gift_kuty_min", "gift_kuty_max",
        "gift_extra_kuty_chance", "gift_extra_kuty_min", "gift_extra_kuty_max",
        "gift_item_chance", "gift_item_count", "gift_fallback_pct",
        "restore_days", "restore_kuty", "restore_item_count",
    ):
        if key in keys and row[key] is not None:
            out[key] = int(row[key])
    if "restore_item" in keys:
        out["restore_item"] = str(row["restore_item"] or "").strip()[:80]
    from flame_bonus_plus import canon_board_cells
    stored_cells = row["gift_cell_emojis"] if "gift_cell_emojis" in keys else ""
    out["gift_cell_emojis"] = canon_board_cells(stored_cells)
    out["warm_from"] = max(0, min(23, out["warm_from"]))
    out["warm_to"] = max(out["warm_from"] + 1, min(24, out["warm_to"]))
    out["gift_kuty_min"] = max(1, out["gift_kuty_min"])
    out["gift_kuty_max"] = max(out["gift_kuty_min"], out["gift_kuty_max"])
    out["gift_mult"] = max(1, min(10, out["gift_mult"]))
    out["gift_extra_kuty_chance"] = max(0, min(100, int(out.get("gift_extra_kuty_chance") or 0)))
    out["gift_extra_kuty_min"] = max(0, int(out.get("gift_extra_kuty_min") or 0))
    out["gift_extra_kuty_max"] = max(out["gift_extra_kuty_min"], int(out.get("gift_extra_kuty_max") or 0))
    out["gift_item_chance"] = max(0, min(100, int(out.get("gift_item_chance") or 0)))
    out["gift_item_count"] = max(1, min(5, int(out.get("gift_item_count") or 1)))
    out["gift_fallback_pct"] = max(1, min(100, int(out.get("gift_fallback_pct") or 30)))
    out["min_words"] = max(1, min(20, out["min_words"]))
    out["warm_every"] = max(1, min(10_000, out["warm_every"]))
    out["warm_cap"] = max(1, min(50, out["warm_cap"]))
    out["warm_min_day"] = max(1, min(100_000, out["warm_min_day"]))
    out["profit_hour"] = max(0, min(23, out["profit_hour"]))
    out["restore_days"] = max(1, min(30, int(out.get("restore_days") or 3)))
    out["restore_kuty"] = max(0, min(10_000_000, int(out.get("restore_kuty") or 0)))
    out["restore_item"] = str(out.get("restore_item") or "").strip()[:80]
    out["restore_item_count"] = max(1, min(100, int(out.get("restore_item_count") or 1)))
    return out


async def ensure_warm_hour(pool, today: date | None = None, settings: dict | None = None) -> int | None:
    await ensure_tables(pool)
    day = today or msk_today()
    conf = settings or _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    if not conf.get("warm_enabled"):
        return None
    row = await pool.fetchrow("SELECT hour FROM flame_warm_day WHERE day = $1", day)
    if row:
        return int(row["hour"])
    start = int(conf["warm_from"])
    end = int(conf["warm_to"])
    hours = list(range(start, end))
    if not hours:
        hours = [15, 16, 17, 18, 19, 20, 21, 22, 23]
    hour = random.choice(hours)
    await pool.execute(
        """
        INSERT INTO flame_warm_day (day, hour) VALUES ($1, $2)
        ON CONFLICT (day) DO NOTHING
        """,
        day,
        hour,
    )
    again = await pool.fetchrow("SELECT hour FROM flame_warm_day WHERE day = $1", day)
    return int(again["hour"]) if again else hour


def gift_preview(
    drops: list[dict],
    mult: int,
    kuty_min: int,
    kuty_max: int,
    item_count: int = 1,
) -> dict:
    """Средний профит за одно открытие и за 100 открытий."""
    mult = max(1, int(mult or 1))
    lo = max(1, int(kuty_min or 1))
    hi = max(lo, int(kuty_max or lo))
    slots = max(1, min(5, int(item_count or 1)))
    board_avg = ((lo + hi) / 2.0) * mult
    weight_sum = 0
    item_chance = 0.0
    extra_kuty = 0.0
    items = []
    for row in drops or []:
        weight = max(0, int(row.get("weight") or 0))
        if weight <= 0:
            continue
        weight_sum += weight
    for row in drops or []:
        weight = max(0, int(row.get("weight") or 0))
        if weight <= 0 or weight_sum <= 0:
            continue
        chance = weight / weight_sum
        kind = row.get("kind")
        if kind == "item":
            item_chance += chance
            name = str(row.get("item_name") or row.get("itemName") or "").strip()
            if name:
                items.append({"name": name, "chance": round(chance * 100, 2), "weight": weight})
        elif kind == "kuty":
            a = max(1, int(row.get("amount_min") or row.get("amountMin") or 1))
            b = max(a, int(row.get("amount_max") or row.get("amountMax") or a))
            extra_kuty += chance * ((a + b) / 2.0)
    per = board_avg + extra_kuty
    return {
        "boardAvg": round(board_avg, 2),
        "extraKutyAvg": round(extra_kuty, 2),
        "itemChancePct": round(item_chance * 100, 2),
        "itemCount": slots,
        "avgPerOpen": round(per, 2),
        "avgPer100": round(per * 100, 1),
        "items": items,
        "mult": mult,
        "kutyMin": lo * mult,
        "kutyMax": hi * mult,
    }


async def load_board(pool) -> dict:
    await ensure_tables(pool)
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    steps = [
        {"from_day": int(row["from_day"]), "messages": int(row["messages"])}
        for row in await pool.fetch("SELECT from_day, messages FROM flame_steps ORDER BY from_day")
    ]
    rewards = [
        {
            "id": int(row["id"]),
            "day": int(row["day"]),
            "kind": row["kind"],
            "amount": int(row["amount"] or 1),
            "item_name": row["item_name"] or "",
        }
        for row in await pool.fetch(
            "SELECT id, day, kind, amount, item_name FROM flame_rewards ORDER BY day, id"
        )
    ]
    titles = [
        {
            "from_day": int(row["from_day"]),
            "title": row["title"],
            "emoji_id": row["emoji_id"] or STATUS_EMOJI,
        }
        for row in await pool.fetch(
            "SELECT from_day, title, emoji_id FROM flame_titles ORDER BY from_day"
        )
    ]
    warm_rewards = [
        {
            "id": int(row["id"]),
            "kind": row["kind"],
            "amount": int(row["amount"] or 1),
            "item_name": row["item_name"] or "",
            "weight": int(row["weight"] or 1),
        }
        for row in await pool.fetch(
            "SELECT id, kind, amount, item_name, weight FROM flame_warm_rewards ORDER BY id"
        )
    ]
    gift_drops = [
        {
            "id": int(row["id"]),
            "kind": row["kind"],
            "amount_min": int(row["amount_min"] or 1),
            "amount_max": int(row["amount_max"] or 1),
            "item_name": row["item_name"] or "",
            "weight": int(row["weight"] or 1),
            "show_preview": bool(row["show_preview"]) if "show_preview" in row.keys() else False,
        }
        for row in await pool.fetch(
            """
            SELECT id, kind, amount_min, amount_max, item_name, weight,
                   COALESCE(show_preview, FALSE) AS show_preview
            FROM flame_gift_drops
            ORDER BY id
            """
        )
    ]
    hour = await ensure_warm_hour(pool, settings=settings) if settings.get("warm_enabled") else None
    people = await leaderboard(pool, 12, titles if settings.get("status_enabled") else [])
    kept = await pool.fetchval(
        "SELECT COUNT(*) FROM flame_users WHERE last_kept = $1 AND streak_days > 0",
        msk_today(),
    )
    alive = await pool.fetchval("SELECT COUNT(*) FROM flame_users WHERE streak_days > 0")
    loot = await recent_loot(pool, 30)
    warm = {
        "enabled": settings["warm_enabled"],
        "min_day": settings["warm_min_day"],
        "every": settings["warm_every"],
        "cap": settings["warm_cap"],
        "from": settings["warm_from"],
        "to": settings["warm_to"],
        "hour": hour,
        "rewards": warm_rewards,
    }
    gift = {
        "enabled": settings["gift_enabled"],
        "mult": settings["gift_mult"],
        "kuty_min": settings["gift_kuty_min"],
        "kuty_max": settings["gift_kuty_max"],
        "extra_kuty_on": settings["gift_extra_kuty_on"],
        "extra_kuty_chance": settings["gift_extra_kuty_chance"],
        "extra_kuty_min": settings["gift_extra_kuty_min"],
        "extra_kuty_max": settings["gift_extra_kuty_max"],
        "item_on": settings["gift_item_on"],
        "item_chance": settings["gift_item_chance"],
        "item_count": settings["gift_item_count"],
        "fallback_pct": settings["gift_fallback_pct"],
        "cell_emojis": _board_cells(settings),
        "drops": gift_drops,
        "preview": gift_preview(
            gift_drops,
            settings["gift_mult"],
            settings["gift_kuty_min"],
            settings["gift_kuty_max"],
            item_count=settings["gift_item_count"],
        ),
    }
    board = {
        "settings": settings,
        "steps": steps,
        "rewards": rewards,
        "titles": titles if settings.get("status_enabled") else titles,
        "warm": warm,
        "gift": gift,
        "people": people,
        "loot": loot,
        "keptToday": int(kept or 0),
        "alive": int(alive or 0),
    }
    board["help"] = help_html(board)
    return board


async def save_settings(pool, body: dict) -> None:
    await ensure_tables(pool)
    conf = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    mapping = {
        "enabled": "enabled",
        "baseMessages": "base_messages",
        "base_messages": "base_messages",
        "warmEnabled": "warm_enabled",
        "warm_enabled": "warm_enabled",
        "warmMinDay": "warm_min_day",
        "warm_min_day": "warm_min_day",
        "warmEvery": "warm_every",
        "warm_every": "warm_every",
        "warmCap": "warm_cap",
        "warm_cap": "warm_cap",
        "warmFrom": "warm_from",
        "warm_from": "warm_from",
        "warmTo": "warm_to",
        "warm_to": "warm_to",
        "statusEnabled": "status_enabled",
        "status_enabled": "status_enabled",
        "profitEnabled": "profit_enabled",
        "profit_enabled": "profit_enabled",
        "profitHour": "profit_hour",
        "profit_hour": "profit_hour",
        "minWords": "min_words",
        "min_words": "min_words",
        "blockDup": "block_dup",
        "block_dup": "block_dup",
        "giftEnabled": "gift_enabled",
        "gift_enabled": "gift_enabled",
        "giftMult": "gift_mult",
        "gift_mult": "gift_mult",
        "giftKutyMin": "gift_kuty_min",
        "gift_kuty_min": "gift_kuty_min",
        "giftKutyMax": "gift_kuty_max",
        "gift_kuty_max": "gift_kuty_max",
        "giftExtraKutyOn": "gift_extra_kuty_on",
        "gift_extra_kuty_on": "gift_extra_kuty_on",
        "giftExtraKutyChance": "gift_extra_kuty_chance",
        "gift_extra_kuty_chance": "gift_extra_kuty_chance",
        "giftExtraKutyMin": "gift_extra_kuty_min",
        "gift_extra_kuty_min": "gift_extra_kuty_min",
        "giftExtraKutyMax": "gift_extra_kuty_max",
        "gift_extra_kuty_max": "gift_extra_kuty_max",
        "giftItemOn": "gift_item_on",
        "gift_item_on": "gift_item_on",
        "giftItemChance": "gift_item_chance",
        "gift_item_chance": "gift_item_chance",
        "giftItemCount": "gift_item_count",
        "gift_item_count": "gift_item_count",
        "giftFallbackPct": "gift_fallback_pct",
        "gift_fallback_pct": "gift_fallback_pct",
        "restoreEnabled": "restore_enabled",
        "restore_enabled": "restore_enabled",
        "restoreDays": "restore_days",
        "restore_days": "restore_days",
        "restoreKuty": "restore_kuty",
        "restore_kuty": "restore_kuty",
        "restoreItem": "restore_item",
        "restore_item": "restore_item",
        "restoreItemCount": "restore_item_count",
        "restore_item_count": "restore_item_count",
    }
    for src, dst in mapping.items():
        if src in body:
            conf[dst] = body[src]
    cells = body.get("giftCellEmojis", body.get("gift_cell_emojis"))
    if cells:
        from flame_bonus_plus import canon_board_cells
        conf["gift_cell_emojis"] = canon_board_cells(cells)
    clean = _row_settings(conf)
    await pool.execute(
        """
        INSERT INTO flame_settings (
            id, enabled, base_messages,
            warm_enabled, warm_min_day, warm_every, warm_cap, warm_from, warm_to,
            status_enabled, profit_enabled, profit_hour, min_words, block_dup,
            gift_enabled, gift_mult, gift_kuty_min, gift_kuty_max,
            gift_extra_kuty_on, gift_extra_kuty_chance, gift_extra_kuty_min, gift_extra_kuty_max,
            gift_item_on, gift_item_chance, gift_item_count, gift_fallback_pct,
            restore_enabled, restore_days, restore_kuty, restore_item, restore_item_count,
            gift_cell_emojis
        ) VALUES (
            1, $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
            $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31
        )
        ON CONFLICT (id) DO UPDATE SET
            enabled = EXCLUDED.enabled,
            base_messages = EXCLUDED.base_messages,
            warm_enabled = EXCLUDED.warm_enabled,
            warm_min_day = EXCLUDED.warm_min_day,
            warm_every = EXCLUDED.warm_every,
            warm_cap = EXCLUDED.warm_cap,
            warm_from = EXCLUDED.warm_from,
            warm_to = EXCLUDED.warm_to,
            status_enabled = EXCLUDED.status_enabled,
            profit_enabled = EXCLUDED.profit_enabled,
            profit_hour = EXCLUDED.profit_hour,
            min_words = EXCLUDED.min_words,
            block_dup = EXCLUDED.block_dup,
            gift_enabled = EXCLUDED.gift_enabled,
            gift_mult = EXCLUDED.gift_mult,
            gift_kuty_min = EXCLUDED.gift_kuty_min,
            gift_kuty_max = EXCLUDED.gift_kuty_max,
            gift_extra_kuty_on = EXCLUDED.gift_extra_kuty_on,
            gift_extra_kuty_chance = EXCLUDED.gift_extra_kuty_chance,
            gift_extra_kuty_min = EXCLUDED.gift_extra_kuty_min,
            gift_extra_kuty_max = EXCLUDED.gift_extra_kuty_max,
            gift_item_on = EXCLUDED.gift_item_on,
            gift_item_chance = EXCLUDED.gift_item_chance,
            gift_item_count = EXCLUDED.gift_item_count,
            gift_fallback_pct = EXCLUDED.gift_fallback_pct,
            restore_enabled = EXCLUDED.restore_enabled,
            restore_days = EXCLUDED.restore_days,
            restore_kuty = EXCLUDED.restore_kuty,
            restore_item = EXCLUDED.restore_item,
            restore_item_count = EXCLUDED.restore_item_count,
            gift_cell_emojis = EXCLUDED.gift_cell_emojis
        """,
        clean["enabled"],
        clean["base_messages"],
        clean["warm_enabled"],
        clean["warm_min_day"],
        clean["warm_every"],
        clean["warm_cap"],
        clean["warm_from"],
        clean["warm_to"],
        clean["status_enabled"],
        clean["profit_enabled"],
        clean["profit_hour"],
        clean["min_words"],
        clean["block_dup"],
        clean["gift_enabled"],
        clean["gift_mult"],
        clean["gift_kuty_min"],
        clean["gift_kuty_max"],
        clean["gift_extra_kuty_on"],
        clean["gift_extra_kuty_chance"],
        clean["gift_extra_kuty_min"],
        clean["gift_extra_kuty_max"],
        clean["gift_item_on"],
        clean["gift_item_chance"],
        clean["gift_item_count"],
        clean["gift_fallback_pct"],
        clean["restore_enabled"],
        clean["restore_days"],
        clean["restore_kuty"],
        clean["restore_item"],
        clean["restore_item_count"],
        clean["gift_cell_emojis"],
    )


async def save_steps(pool, steps: list[dict]) -> None:
    await ensure_tables(pool)
    clean = []
    seen = set()
    for step in steps or []:
        start = int(step.get("fromDay") or step.get("from_day") or 0)
        messages = int(step.get("messages") or 0)
        if start < 1 or messages < 1 or messages > 100_000 or start > 100_000 or start in seen:
            continue
        seen.add(start)
        clean.append((start, messages))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM flame_steps")
            if clean:
                await conn.executemany(
                    "INSERT INTO flame_steps (from_day, messages) VALUES ($1, $2)",
                    clean,
                )


async def save_rewards(pool, rewards: list[dict]) -> None:
    await ensure_tables(pool)
    clean = []
    for row in rewards or []:
        day = int(row.get("day") or 0)
        kind = str(row.get("kind") or "")
        amount = int(row.get("amount") or 1)
        item = str(row.get("itemName") or row.get("item_name") or "").strip()[:80]
        if day < 1 or day > 100_000 or kind not in KINDS or amount < 1 or amount > 1_000_000:
            continue
        if kind == "item" and not item:
            continue
        if kind != "item":
            item = ""
        clean.append((day, kind, amount, item))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM flame_rewards")
            await conn.execute("DELETE FROM flame_grants")
            for day, kind, amount, item in clean:
                await conn.execute(
                    """
                    INSERT INTO flame_rewards (day, kind, amount, item_name)
                    VALUES ($1, $2, $3, $4)
                    """,
                    day, kind, amount, item,
                )


async def save_titles(pool, titles: list[dict]) -> None:
    await ensure_tables(pool)
    clean = []
    seen = set()
    for row in titles or []:
        start = int(row.get("fromDay") or row.get("from_day") or 0)
        title = str(row.get("title") or "").strip()[:60]
        emoji = str(row.get("emojiId") or row.get("emoji_id") or STATUS_EMOJI).strip()[:40]
        if start < 1 or start > 100_000 or not title or start in seen:
            continue
        seen.add(start)
        clean.append((start, title, emoji or STATUS_EMOJI))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM flame_titles")
            if clean:
                await conn.executemany(
                    "INSERT INTO flame_titles (from_day, title, emoji_id) VALUES ($1, $2, $3)",
                    clean,
                )


async def save_warm_rewards(pool, rewards: list[dict]) -> None:
    await ensure_tables(pool)
    clean = []
    for row in rewards or []:
        kind = str(row.get("kind") or "")
        amount = int(row.get("amount") or 1)
        item = str(row.get("itemName") or row.get("item_name") or "").strip()[:80]
        weight = int(row.get("weight") or 1)
        if kind not in WARM_KINDS or amount < 1 or amount > 1_000_000 or weight < 1 or weight > 10_000:
            continue
        if kind == "item" and not item:
            continue
        if kind != "item":
            item = ""
        clean.append((kind, amount, item, weight))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM flame_warm_rewards")
            for kind, amount, item, weight in clean:
                await conn.execute(
                    """
                    INSERT INTO flame_warm_rewards (kind, amount, item_name, weight)
                    VALUES ($1, $2, $3, $4)
                    """,
                    kind, amount, item, weight,
                )


async def save_gift_drops(pool, drops: list[dict]) -> None:
    await ensure_tables(pool)
    clean = []
    for row in drops or []:
        kind = str(row.get("kind") or "")
        weight = int(row.get("weight") or 1)
        a = int(row.get("amountMin") or row.get("amount_min") or 1)
        b = int(row.get("amountMax") or row.get("amount_max") or a)
        item = str(row.get("itemName") or row.get("item_name") or "").strip()[:80]
        show = bool(row.get("showPreview") if "showPreview" in row else row.get("show_preview"))
        if kind not in GIFT_KINDS or weight < 1 or weight > 10_000:
            continue
        if kind == "item":
            if not item:
                continue
            a = b = max(1, a)
        else:
            item = ""
            a = max(1, min(a, 1_000_000))
            b = max(a, min(b, 1_000_000))
            show = False
        clean.append((kind, a, b, item, weight, show))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM flame_gift_drops")
            for kind, a, b, item, weight, show in clean:
                await conn.execute(
                    """
                    INSERT INTO flame_gift_drops
                        (kind, amount_min, amount_max, item_name, weight, show_preview)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    kind, a, b, item, weight, show,
                )


async def shop_catalog(pool) -> list[dict]:
    """Предметы для выбора в панели: имя, эмодзи, id."""
    try:
        rows = await pool.fetch(
            """
            SELECT id, name, name1, emoji, COALESCE(price, 0) AS price
            FROM dex
            WHERE name IS NOT NULL AND BTRIM(name) <> ''
            ORDER BY name ASC NULLS LAST, id ASC
            LIMIT 1200
            """
        )
    except Exception:
        return []
    out = []
    seen = set()
    for row in rows:
        name = str(row["name"] or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "id": str(row["id"]),
            "name": name,
            "name1": str(row["name1"] or "").strip(),
            "emoji": str(row["emoji"] or "").strip() or "📦",
            "price": int(row["price"] or 0),
        })
    return out


async def shop_names(pool) -> list[str]:
    return [row["name"] for row in await shop_catalog(pool)]


async def leaderboard(pool, limit: int = 15, titles: list[dict] | None = None) -> list[dict]:
    await ensure_tables(pool)
    rows = await pool.fetch(
        """
        SELECT f.user_id, f.streak_days, f.best_days,
               COALESCE(u.first_name, '') AS first_name,
               COALESCE(u.username, '') AS username
        FROM flame_users f
        LEFT JOIN users u ON u.user_id = f.user_id
        WHERE GREATEST(f.streak_days, f.best_days) > 0
        ORDER BY f.streak_days DESC, f.best_days DESC, f.user_id
        LIMIT $1
        """,
        max(1, min(int(limit), 30)),
    )
    people = []
    for row in rows:
        streak = int(row["streak_days"] or 0)
        best = int(row["best_days"] or 0)
        days = streak if streak else best
        badge = title_for(days, titles or [])
        people.append({
            "userId": int(row["user_id"]),
            "name": (row["first_name"] or "").strip() or "Без имени",
            "username": (row["username"] or "").strip(),
            "streak": streak,
            "best": best,
            "label": span_label(days),
            "record": streak <= 0,
            "title": badge["title"] if badge else "",
        })
    return people


async def recent_loot(pool, limit: int = 40) -> list[dict]:
    await ensure_tables(pool)
    rows = await pool.fetch(
        """
        SELECT l.id, l.user_id, l.source, l.kind, l.amount, l.item_name, l.label, l.created_at,
               COALESCE(u.first_name, '') AS first_name
        FROM flame_loot l
        LEFT JOIN users u ON u.user_id = l.user_id
        ORDER BY l.id DESC
        LIMIT $1
        """,
        max(1, min(int(limit), 100)),
    )
    out = []
    for row in rows:
        out.append({
            "id": int(row["id"]),
            "userId": int(row["user_id"]),
            "name": (row["first_name"] or "").strip() or "Игрок",
            "source": row["source"],
            "kind": row["kind"],
            "amount": int(row["amount"] or 1),
            "itemName": row["item_name"] or "",
            "label": row["label"] or "",
            "at": row["created_at"].isoformat() if row["created_at"] else "",
        })
    return out


async def log_loot(pool, user_id: int, source: str, kind: str, amount: int = 1, item_name: str = "", label: str = "") -> None:
    await ensure_tables(pool)
    words = label or _kind_words(kind, amount, item_name)
    await pool.execute(
        """
        INSERT INTO flame_loot (user_id, source, kind, amount, item_name, label)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        int(user_id),
        str(source)[:20],
        str(kind)[:20],
        max(1, int(amount or 1)),
        str(item_name or "")[:80],
        str(words or "")[:120],
    )


async def streak_of(pool, user_id: int) -> int:
    await ensure_tables(pool)
    value = await pool.fetchval(
        "SELECT streak_days FROM flame_users WHERE user_id = $1",
        int(user_id),
    )
    return int(value or 0)


async def titles_list(pool) -> list[dict]:
    await ensure_tables(pool)
    return [
        {
            "from_day": int(row["from_day"]),
            "title": row["title"],
            "emoji_id": row["emoji_id"] or STATUS_EMOJI,
        }
        for row in await pool.fetch(
            "SELECT from_day, title, emoji_id FROM flame_titles ORDER BY from_day"
        )
    ]


async def bonus_tokens(pool, user_id: int) -> tuple[int, int]:
    await ensure_tables(pool)
    row = await pool.fetchrow(
        "SELECT bonus_opens, bonus_x2 FROM flame_users WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        return 0, 0
    return int(row["bonus_opens"] or 0), int(row["bonus_x2"] or 0)


async def consume_bonus(pool, user_id: int) -> str:
    await ensure_tables(pool)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT bonus_opens, bonus_x2 FROM flame_users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            if not row:
                return ""
            x2 = int(row["bonus_x2"] or 0)
            opens = int(row["bonus_opens"] or 0)
            if x2 > 0:
                await conn.execute(
                    "UPDATE flame_users SET bonus_x2 = bonus_x2 - 1 WHERE user_id = $1",
                    int(user_id),
                )
                return "x2"
            if opens > 0:
                await conn.execute(
                    "UPDATE flame_users SET bonus_opens = bonus_opens - 1 WHERE user_id = $1",
                    int(user_id),
                )
                return "open"
    return ""


async def messages_on(pool, user_id: int, day: date, chat_ids: list[int]) -> int:
    ids = [int(chat) for chat in chat_ids if int(chat) != 0]
    if not ids:
        return 0
    value = await pool.fetchval(
        """
        SELECT COALESCE(SUM(text), 0)
        FROM chatchange
        WHERE user_id = $1 AND date = $2 AND chat_id = ANY($3::bigint[])
        """,
        int(user_id),
        day,
        ids,
    )
    return int(value or 0)


async def restore_state(pool, user_id: int, today: date | None = None) -> dict:
    """Карточка «вернуть огонёк» без оплаты."""
    await ensure_tables(pool)
    day = today or msk_today()
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    row = await pool.fetchrow(
        "SELECT streak_days, lost_streak, lost_on FROM flame_users WHERE user_id = $1",
        int(user_id),
    )
    return restore_view(
        int(row["streak_days"] or 0) if row else 0,
        int(row["lost_streak"] or 0) if row else 0,
        row["lost_on"] if row else None,
        settings,
        day,
    )


async def rollover(pool, today: date | None = None) -> int:
    await ensure_tables(pool)
    day = today or msk_today()
    await ensure_warm_hour(pool, day)
    status = await pool.execute(
        """
        UPDATE flame_users
        SET best_days = GREATEST(best_days, streak_days),
            lost_streak = streak_days,
            lost_on = $2,
            streak_days = 0
        WHERE streak_days > 0
          AND (last_kept IS NULL OR last_kept < $1)
        """,
        day - timedelta(days=1),
        day,
    )
    try:
        return int(str(status).split()[-1])
    except Exception:
        return 0


def _pick_weighted(rows: list[dict]) -> dict | None:
    bag = []
    for row in rows or []:
        weight = max(0, int(row.get("weight") or 0))
        if weight <= 0:
            continue
        bag.extend([row] * weight)
    if not bag:
        return None
    return random.choice(bag)


async def try_warm_hit(pool, user_id: int) -> dict | None:
    """Одно сообщение в тёплый час: прогресс и, возможно, награда."""
    await ensure_tables(pool)
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    if not settings["enabled"] or not settings["warm_enabled"]:
        return None
    now = msk_now()
    day = now.date()
    hour = await ensure_warm_hour(pool, day, settings)
    if hour is None or now.hour != hour:
        return None
    rewards = [
        {
            "kind": row["kind"],
            "amount": int(row["amount"] or 1),
            "item_name": row["item_name"] or "",
            "weight": int(row["weight"] or 1),
        }
        for row in await pool.fetch(
            "SELECT kind, amount, item_name, weight FROM flame_warm_rewards"
        )
    ]
    if not rewards:
        return None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT streak_days, last_kept, warm_day, warm_count, warm_hits,
                       bonus_opens, bonus_x2
                FROM flame_users WHERE user_id = $1 FOR UPDATE
                """,
                int(user_id),
            )
            if not row:
                return None
            streak = int(row["streak_days"] or 0)
            if streak < settings["warm_min_day"]:
                return None
            if row["last_kept"] is not None and row["last_kept"] < day - timedelta(days=1):
                return None
            warm_day = row["warm_day"]
            count = int(row["warm_count"] or 0)
            hits = int(row["warm_hits"] or 0)
            if warm_day != day:
                count = 0
                hits = 0
                warm_day = day
            if hits >= settings["warm_cap"]:
                return None
            count += 1
            grant = None
            if count % settings["warm_every"] == 0:
                picked = _pick_weighted(rewards)
                if picked:
                    hits += 1
                    kind = picked["kind"]
                    amount = int(picked["amount"] or 1)
                    item = picked.get("item_name") or ""
                    if kind == "bonus":
                        await conn.execute(
                            "UPDATE flame_users SET bonus_opens = COALESCE(bonus_opens,0) + $2 WHERE user_id = $1",
                            int(user_id), amount,
                        )
                    elif kind == "bonus_x2":
                        await conn.execute(
                            "UPDATE flame_users SET bonus_x2 = COALESCE(bonus_x2,0) + $2 WHERE user_id = $1",
                            int(user_id), amount,
                        )
                    grant = {
                        "kind": kind,
                        "amount": amount,
                        "item_name": item,
                        "label": _kind_words(kind, amount, item),
                    }
            await conn.execute(
                """
                UPDATE flame_users
                SET warm_day = $2, warm_count = $3, warm_hits = $4
                WHERE user_id = $1
                """,
                int(user_id), warm_day, count, hits,
            )
    if grant:
        await log_loot(pool, user_id, "warm", grant["kind"], grant["amount"], grant["item_name"], grant["label"])
        return grant
    return None


async def gift_config(pool) -> dict:
    await ensure_tables(pool)
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    drops = [
        {
            "kind": row["kind"],
            "amount_min": int(row["amount_min"] or 1),
            "amount_max": int(row["amount_max"] or 1),
            "item_name": row["item_name"] or "",
            "weight": int(row["weight"] or 1),
            "show_preview": bool(row["show_preview"]) if "show_preview" in row.keys() else False,
        }
        for row in await pool.fetch(
            """
            SELECT kind, amount_min, amount_max, item_name, weight,
                   COALESCE(show_preview, FALSE) AS show_preview
            FROM flame_gift_drops
            """
        )
    ]
    return {
        "enabled": settings["gift_enabled"],
        "mult": settings["gift_mult"],
        "kuty_min": settings["gift_kuty_min"],
        "kuty_max": settings["gift_kuty_max"],
        "extra_kuty_on": settings["gift_extra_kuty_on"],
        "extra_kuty_chance": settings["gift_extra_kuty_chance"],
        "extra_kuty_min": settings["gift_extra_kuty_min"],
        "extra_kuty_max": settings["gift_extra_kuty_max"],
        "item_on": settings["gift_item_on"],
        "item_chance": settings["gift_item_chance"],
        "item_count": settings["gift_item_count"],
        "fallback_pct": settings["gift_fallback_pct"],
        "cell_emojis": _board_cells(settings),
        "drops": drops,
        "preview": gift_preview(
            drops,
            settings["gift_mult"],
            settings["gift_kuty_min"],
            settings["gift_kuty_max"],
            item_count=settings["gift_item_count"],
        ),
    }


def roll_gift_stake(conf: dict) -> int:
    lo = max(1, int(conf.get("kuty_min") or 1))
    hi = max(lo, int(conf.get("kuty_max") or lo))
    return random.randint(lo, hi)


def roll_gift_extra(conf: dict) -> dict | None:
    picked = _pick_weighted(conf.get("drops") or [])
    if not picked:
        return None
    kind = picked.get("kind")
    if kind == "item":
        name = str(picked.get("item_name") or "").strip()
        if not name:
            return None
        return {"kind": "item", "amount": 1, "item_name": name, "label": name}
    if kind == "kuty":
        a = max(1, int(picked.get("amount_min") or 1))
        b = max(a, int(picked.get("amount_max") or a))
        amount = random.randint(a, b)
        return {"kind": "kuty", "amount": amount, "item_name": "", "label": f"{amount} кут"}
    return None


async def profit_targets(pool) -> list[dict]:
    """Кому слать вечернюю карточку прямо сейчас."""
    await ensure_tables(pool)
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    if not settings["enabled"] or not settings["profit_enabled"]:
        return []
    now = msk_now()
    if now.hour != settings["profit_hour"]:
        return []
    day = now.date()
    rows = await pool.fetch(
        """
        SELECT user_id, streak_days, last_kept
        FROM flame_users
        WHERE streak_days > 0
          AND (profit_day IS NULL OR profit_day < $1)
        ORDER BY streak_days DESC
        LIMIT 200
        """,
        day,
    )
    titles = await titles_list(pool) if settings.get("status_enabled") else []
    rewards = [
        {"day": int(r["day"]), "kind": r["kind"], "amount": int(r["amount"] or 1), "item_name": r["item_name"] or ""}
        for r in await pool.fetch("SELECT day, kind, amount, item_name FROM flame_rewards ORDER BY day")
    ]
    out = []
    for row in rows:
        uid = int(row["user_id"])
        streak = int(row["streak_days"] or 0)
        await pool.execute("UPDATE flame_users SET profit_day = $2 WHERE user_id = $1", uid, day)
        next_reward = None
        for reward in rewards:
            if int(reward["day"]) > streak:
                next_reward = reward
                break
        loot = await pool.fetch(
            """
            SELECT label, source FROM flame_loot
            WHERE user_id = $1 AND created_at::date = $2
            ORDER BY id DESC LIMIT 8
            """,
            uid,
            day,
        )
        rank = await pool.fetchval(
            """
            SELECT 1 + COUNT(*) FROM flame_users
            WHERE streak_days > $1 OR (streak_days = $1 AND user_id < $2)
            """,
            streak,
            uid,
        )
        out.append({
            "userId": uid,
            "streak": streak,
            "label": span_label(streak),
            "title": (title_for(streak, titles) or {}).get("title") or "",
            "rank": int(rank or 1),
            "next": next_reward,
            "loot": [{"label": r["label"], "source": r["source"]} for r in loot],
            "keptToday": row["last_kept"] == day,
            "hour": settings["profit_hour"],
        })
    return out


async def advance(pool, user_id: int, chat_ids: list[int], today: date | None = None) -> dict | None:
    await ensure_tables(pool)
    day = today or msk_today()
    settings = _row_settings(await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    if not settings["enabled"]:
        return None
    count = await messages_on(pool, user_id, day, chat_ids)
    steps = [
        {"from_day": int(row["from_day"]), "messages": int(row["messages"])}
        for row in await pool.fetch("SELECT from_day, messages FROM flame_steps")
    ]
    titles = await titles_list(pool) if settings.get("status_enabled") else []
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT streak_days, best_days, last_kept, bonus_opens, bonus_x2
                FROM flame_users WHERE user_id = $1 FOR UPDATE
                """,
                int(user_id),
            )
            streak = int(row["streak_days"] or 0) if row else 0
            best = int(row["best_days"] or 0) if row else 0
            last = row["last_kept"] if row else None
            if last == day:
                return None
            if gap_starts_new_series(last, day):
                streak = 0
            target = streak + 1
            if count < need_for(target, settings["base_messages"], steps):
                return None
            best = max(best, target)
            if row:
                await conn.execute(
                    """
                    UPDATE flame_users
                    SET streak_days = $2, best_days = $3, last_kept = $4,
                        lost_streak = 0, lost_on = NULL
                    WHERE user_id = $1
                    """,
                    int(user_id), target, best, day,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO flame_users (user_id, streak_days, best_days, last_kept)
                    VALUES ($1, $2, $3, $4)
                    """,
                    int(user_id), target, best, day,
                )
            rewards = await conn.fetch(
                """
                SELECT id, day, kind, amount, item_name
                FROM flame_rewards
                WHERE day = $1
                  AND NOT EXISTS (
                    SELECT 1 FROM flame_grants g
                    WHERE g.user_id = $2 AND g.reward_id = flame_rewards.id
                  )
                ORDER BY id
                """,
                target,
                int(user_id),
            )
            granted = []
            for reward in rewards:
                await conn.execute(
                    "INSERT INTO flame_grants (user_id, reward_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    int(user_id),
                    int(reward["id"]),
                )
                kind = reward["kind"]
                amount = int(reward["amount"] or 1)
                item = reward["item_name"] or ""
                if kind == "bonus":
                    await conn.execute(
                        "UPDATE flame_users SET bonus_opens = bonus_opens + $2 WHERE user_id = $1",
                        int(user_id), amount,
                    )
                elif kind == "bonus_x2":
                    await conn.execute(
                        "UPDATE flame_users SET bonus_x2 = bonus_x2 + $2 WHERE user_id = $1",
                        int(user_id), amount,
                    )
                granted.append({
                    "id": int(reward["id"]),
                    "day": target,
                    "kind": kind,
                    "amount": amount,
                    "item_name": item,
                    "label": _kind_words(kind, amount, item),
                })
    for gift in granted:
        await log_loot(pool, user_id, "streak", gift["kind"], gift["amount"], gift["item_name"], gift["label"])
    badge = title_for(target, titles)
    return {
        "streak": target,
        "label": span_label(target),
        "title": badge["title"] if badge else "",
        "rewards": granted,
    }
