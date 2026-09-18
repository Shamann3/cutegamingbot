# -*- coding: utf-8 -*-
"""Технические группы: один предикат «показывать это игроку или нет».

Зачем. Копилка прибыли, фоновые заработки, чёрный рынок / дом в играх,
комиссии игр и тестовая группа - служебные кошельки. В публичных списках
(топы групп по балансу, достижения в профиле) их быть не должно.

Как. Источник истины - колонка chat.is_technical (DDL и сид:
Database.ensure_technical_chat_schema, server/schema.sql). Список id из
bot/config/config.py - сид этой колонки и страховка: если строка чата ещё не
размечена (свежая группа, БД без миграции), предикат всё равно скроет её.
Поэтому флаг и список складываются по ИЛИ, а не заменяют друг друга.

Чего тут нет. Владелец и админка фильтр не применяют - они должны видеть
техгруппы целиком, так что ни server/admin_groups.py, ни админские агрегаты
через этот модуль не проходят.
"""

from typing import Any, Iterable, List, Mapping, Optional

from bot.config.config import TECHNICAL_CHAT_IDS as _CONFIG_TECHNICAL_CHAT_IDS


def _as_chat_id(value: Any) -> Optional[int]:
    """chat_id из БД/TG приходит и int, и str, и None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


TECHNICAL_CHAT_IDS: frozenset = frozenset(
    cid for cid in (_as_chat_id(raw) for raw in _CONFIG_TECHNICAL_CHAT_IDS) if cid is not None
)


def _row_field(row: Any, name: str) -> Any:
    """Значение поля из asyncpg.Record / dict / обычного объекта."""
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(name)
    keys = getattr(row, "keys", None)
    if callable(keys):
        try:
            if name in keys():
                return row[name]
        except (TypeError, KeyError):
            return None
        return None
    return getattr(row, name, None)


def is_technical_chat(chat_id: Any) -> bool:
    """Техническая ли группа по одному id (без обращения к БД)."""
    cid = _as_chat_id(chat_id)
    return cid is not None and cid in TECHNICAL_CHAT_IDS


def is_technical_row(row: Any) -> bool:
    """Строка chat: флаг из БД, а если его ещё нет - список из конфига."""
    if bool(_row_field(row, "is_technical")):
        return True
    return is_technical_chat(_row_field(row, "chat_id"))


def is_public_chat(row: Any) -> bool:
    """Можно ли показать эту строку chat обычному игроку."""
    return not is_technical_row(row)


def filter_public_chats(rows: Optional[Iterable[Any]]) -> List[Any]:
    """Отсеять технические группы из выборки, сохранив порядок."""
    return [row for row in (rows or ()) if is_public_chat(row)]
