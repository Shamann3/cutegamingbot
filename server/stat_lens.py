"""Как люди видят топ после копии статистики.

До окна — число из базы.
Внутри окна — ноль.
После окна — копия плюс всё, что прибавилось с момента копии.
"""
from __future__ import annotations

from datetime import date, timedelta

PERIODS = ("day", "week", "month", "year", "all")


def period_bounds(kind: str, today: date) -> tuple[date, date] | None:
    """Границы срока по московской дате. None — за всё время."""
    name = str(kind or "all").strip().lower()
    if name == "day":
        return today, today
    if name == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if name == "month":
        start = today.replace(day=1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start, end
    if name == "year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return None


def anchor_day(kind: str, today: date) -> date:
    """Куда ложится разница, когда создатель задаёт сумму за срок."""
    bounds = period_bounds(kind, today)
    if bounds is None:
        return today
    start, end = bounds
    if start <= today <= end:
        return today
    return end


def phase(today: date, zero_from: date | None, zero_until: date | None) -> str:
    if zero_from is None or zero_until is None:
        return "off"
    if today < zero_from:
        return "before"
    if today <= zero_until:
        return "zero"
    return "after"


def seen_number(raw: int, copied: int | None, stage: str) -> int:
    number = int(raw or 0)
    if stage == "zero":
        return 0
    if stage == "after":
        base = int(copied or 0)
        return base + (number - base)
    return number


def gained(raw: int, copied: int | None) -> int:
    return int(raw or 0) - int(copied or 0)


def games_people_see(raw: int, copied: int | None) -> int:
    """В топе игр после копии видно только то, что сыграли позже копии."""
    number = int(raw or 0)
    if copied is None:
        return number
    left = number - int(copied or 0)
    return left if left > 0 else 0


def hide_pair(wins: int, losses: int, played_since: int | None) -> tuple[int, int]:
    """Сколько побед и проигрышей остаётся в копии и не входит в топ за всё время.

    played_since is None — срез на сейчас, прячется весь текущий итог.
    Иначе played_since — игры с выбранного дня, они остаются в топе.
    """
    wins_n = int(wins or 0)
    losses_n = int(losses or 0)
    if wins_n < 0:
        wins_n = 0
    if losses_n < 0:
        losses_n = 0
    if played_since is None:
        return wins_n, losses_n
    since = int(played_since or 0)
    if since < 0:
        since = 0
    hide = wins_n + losses_n - since
    if hide < 0:
        hide = 0
    hide_wins = wins_n if hide > wins_n else hide
    return hide_wins, hide - hide_wins


def plan_period_total(days: list[tuple[date, int]], anchor: date, target: int) -> list[tuple[date, int]]:
    """Новые значения по дням, чтобы сумма срока стала target. Не уходит ниже нуля."""
    if target < 0:
        raise ValueError("Число не может быть меньше нуля")
    bucket = {day: int(amount) for day, amount in days}
    bucket.setdefault(anchor, 0)
    current = sum(bucket.values())
    delta = int(target) - current
    if delta == 0:
        return []
    if delta > 0:
        return [(anchor, bucket[anchor] + delta)]
    ordered = sorted(bucket, reverse=True)
    if anchor in ordered:
        ordered.remove(anchor)
        ordered.insert(0, anchor)
    left = -delta
    changes: list[tuple[date, int]] = []
    for day in ordered:
        have = bucket[day]
        if have <= 0:
            continue
        take = min(have, left)
        changes.append((day, have - take))
        left -= take
        if left == 0:
            break
    if left:
        raise ValueError("Ниже нуля за этот срок не опустить")
    return changes
