"""Розыгрыши: чистые функции для вычисления вкладки (bucket) и отображаемого
имени игрока — без обращения к БД, легко покрываются юнит-тестами.
"""
from __future__ import annotations

from datetime import datetime


def giveaway_bucket(status: str, starts_at: datetime | None, now: datetime) -> str:
    """active | upcoming | past — куда попадает розыгрыш в списке игрока.

    cancelled сюда никогда не передаётся — такие розыгрыши уже отфильтрованы
    в SQL (WHERE status != 'cancelled') на уровне get_giveaways_state/history,
    игроку не показываются вовсе.
    """
    if status == "completed":
        return "past"
    if starts_at is not None and starts_at > now:
        return "upcoming"
    return "active"


def display_name(username: str | None, first_name: str | None) -> str:
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    return "Игрок"
