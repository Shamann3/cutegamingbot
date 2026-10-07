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


def clock_label(seen_unix: float) -> str:
    """Московские часы последнего сообщения: 09:05, 21:00."""
    return datetime.fromtimestamp(float(seen_unix), _MSK).strftime("%H:%M")


def as_seen_unix(value: Any) -> Optional[float]:
    """Момент из памяти или из базы. Наивное время считаем московским."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=_MSK)
        return moment.timestamp()
    return None


def msk_stamp(seen_unix: Optional[float], day: date) -> Optional[datetime]:
    """Наивное московское время для строки этого дня. Чужой день не подписываем."""
    if seen_unix is None:
        return None
    moment = datetime.fromtimestamp(float(seen_unix), _MSK).replace(tzinfo=None)
    if moment.date() != day:
        return None
    return moment


def last_seen_label(
    *,
    seen_unix: Optional[float],
    last_day: Optional[date],
    now_unix: float,
    today: date,
) -> str:
    """Когда человек последний раз писал в этом чате.

    Сегодня — часы и минуты по Москве. Вчера — слово «вчера».
    Часы берутся только если момент действительно сегодняшний:
    вчерашний след не подменяет день, который в базе новее.
    """
    del now_unix  # календарный день важнее «N часов назад»
    day = _as_date(last_day)
    seen_day = None
    if seen_unix is not None:
        seen_day = datetime.fromtimestamp(float(seen_unix), _MSK).date()
        if day is None or seen_day > day:
            day = seen_day
    if day is None:
        return "ещё не было"
    if day >= today:
        if seen_unix is not None and seen_day is not None and seen_day >= today:
            return clock_label(seen_unix)
        return "сегодня"
    if (today - day).days == 1:
        return "вчера"
    return _day_label(day, today)


def _when_html(last: str) -> str:
    """Часы сегодня — моноширинные, как время. Остальные подписи остаются словами."""
    text = str(last)
    if (
        len(text) == 5
        and text[2] == ":"
        and text[:2].isdigit()
        and text[3:].isdigit()
    ):
        return f"{text}"
    return escape(text)


def pulse_block(last: str, day: int, week: int, month: int, total: int) -> str:
    """Две строки под фондом. Пустые строки вокруг добавляет профиль.

    Первая строка говорит, о чём речь (эта группа), вторая — что считается
    (сообщения), чтобы цифры были понятны и без подсказки.
    """
    return (
        f"{DOVE} <b>Последняя активность : {_when_html(last)}</b>\n"
        f"{BOOK} <b>Д {compact_count(day)} | Н {compact_count(week)}"
        f" | М {compact_count(month)} | Все {compact_count(total)} соо</b>"
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
