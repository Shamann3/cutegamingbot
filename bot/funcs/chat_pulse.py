# -*- coding: utf-8 -*-
"""Счёт сообщений человека в том чате, где открыт профиль.

Цифры — из суточных строк chatchange (уже пишутся на каждое сообщение).
Один запрос на четыре окна. Формат строк живёт отдельно от базы.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any, Optional

DOVE = "<tg-emoji emoji-id='5174659134607328175'>🕊</tg-emoji>"
BOOK = "<tg-emoji emoji-id='5472410705929971383'>📖</tg-emoji>"

_MSK = timezone(timedelta(hours=3))
_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def compact_count(value: Any) -> str:
    """Короткое число для строки профиля: 242, 2,3k, 61k."""
    try:
        n = max(0, int(value or 0))
    except (TypeError, ValueError):
        n = 0
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        scaled = n / 1000
        if scaled >= 100 or abs(scaled - round(scaled)) < 0.05:
            return f"{int(round(scaled))}k"
        return f"{scaled:.1f}".replace(".", ",") + "k"
    scaled = n / 1_000_000
    if abs(scaled - round(scaled)) < 0.05:
        return f"{int(round(scaled))} млн"
    return f"{scaled:.1f}".replace(".", ",") + " млн"


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _day_label(day: date, today: date) -> str:
    """День словами, а старше недели — числом: «12 сентября», «31.12.2025»."""
    delta = (today - day).days
    if delta <= 0:
        return "сегодня"
    if delta == 1:
        return "вчера"
    if delta < 7:
        return f"{delta} дн. назад"
    if day.year == today.year:
        return f"{day.day} {_MONTHS[day.month - 1]}"
    return day.strftime("%d.%m.%Y")


def last_seen_label(
    *,
    seen_unix: Optional[float],
    last_day: Optional[date],
    now_unix: float,
    today: date,
) -> str:
    """Когда человек последний раз писал в этом чате.

    Пока бот сам видел сообщение — минуты и часы; дальше — по дню из базы.
    """
    day = _as_date(last_day)
    if seen_unix is not None:
        sec = max(0, int(now_unix - float(seen_unix)))
        if sec < 45:
            return "только что"
        if sec < 3600:
            return f"{max(1, sec // 60)} мин назад"
        if sec < 86400:
            return f"{max(1, sec // 3600)} ч назад"
        seen_day = datetime.fromtimestamp(float(seen_unix), _MSK).date()
        if day is None or seen_day > day:
            day = seen_day
    if day is not None:
        return _day_label(day, today)
    return "ещё не было"


def pulse_block(last: str, day: int, week: int, month: int, total: int) -> str:
    """Две строки под фондом. Пустые строки вокруг добавляет профиль.

    Первая строка говорит, о чём речь (эта группа), вторая — что считается
    (сообщения), чтобы цифры были понятны и без подсказки.
    """
    when = escape(str(last))
    return (
        f"{DOVE} <b>Последнее сообщение в этой группе : {when}</b>\n"
        f"{BOOK} <b>Сообщений : сегодня {compact_count(day)} · неделя {compact_count(week)}"
        f" · месяц {compact_count(month)} · всего {compact_count(total)}</b>"
    )


def pending_today(buffer: Any, user_id: int, chat_id: int, today: date) -> int:
    """Сообщения, которые уже в памяти и ещё не доехали до chatchange."""
    if not isinstance(buffer, dict):
        return 0
    uid, cid = int(user_id), int(chat_id)
    total = 0
    for key, raw in buffer.items():
        try:
            if not isinstance(key, tuple):
                continue
            if len(key) >= 3:
                p_uid, p_cid, p_day = key[0], key[1], key[2]
                if p_day != today:
                    continue
            elif len(key) == 2:
                p_uid, p_cid = key[0], key[1]
            else:
                continue
            if int(p_uid) != uid or int(p_cid) != cid:
                continue
            total += max(0, int(raw or 0))
        except (TypeError, ValueError):
            continue
    return total


def windows(today: date) -> tuple[date, date, date]:
    """Сегодня, начало скользящей недели, первое число месяца — всё по MSK-дате."""
    return today, today - timedelta(days=6), today.replace(day=1)
