"""Единый кодек инвентаря users.items для основного бота.

Инвентарь пользователя хранится в таблице ``users`` в столбце ``items`` как
JSON-объект вида ``{"Ключ": 7, "Вода": 98}`` — ключ это имя предмета из ``dex``
(``dex.name``), значение — целочисленное количество.

Этот модуль — единственная точка (де)сериализации инвентаря в боте. Он
полностью совместим с вебаппом (server/json_db_codec.py):

* :func:`encode_items` пишет чистый JSON (``json.dumps`` с ``ensure_ascii=True``),
  ровно тот же формат, что и вебапп после унификации.
* :func:`decode_items` читает *любой* исторически встречавшийся формат без
  исключений и без потери данных:
    - обычный ``dict`` (asyncpg может отдавать JSON/JSONB сразу словарём);
    - чистый JSON ``{"Ключ": 7}``;
    - старый «обёрнутый» формат вебаппа ``"{""\\u041a..."": 7}"``
      (двойные кавычки + внешние кавычки);
    - дважды закодированный JSON (строка внутри строки);
    - одинарные кавычки / висячие запятые (мягкое авто-лечение).

Главное правило: :func:`decode_items` **никогда не бросает исключение** и при
непонятных данных возвращает ``{}`` — но вызывающий код НЕ должен на основании
пустого результата затирать непустое поле в БД (см. get_user_inventory_use).
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Префиксы/маркеры Telegram file_id — иногда попадают в текстовые поля и точно
# не являются инвентарём. Их не пытаемся парсить как JSON.
_FILE_ID_PREFIXES = ("CAAC", "AgAC", "BQAC", "CgAC")
_FILE_ID_MARKERS = ("AAxkB", "palochka")


def is_telegram_file_id(text: str) -> bool:
    value = (text or "").strip()
    if len(value) < 20:
        return False
    if value.startswith(_FILE_ID_PREFIXES):
        return True
    return any(marker in value for marker in _FILE_ID_MARKERS)


def _coerce_dict(data: Any) -> Dict[str, Any] | None:
    """Приводит распарсенное значение к словарю инвентаря или возвращает None."""
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items()}
    return None


def _parse_candidates(text: str) -> list[str]:
    """Готовит список строк-кандидатов для json.loads с учётом старых форматов."""
    seen: set[str] = set()
    candidates: list[str] = []

    def add(value: str) -> None:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)

    add(text)

    # «Обёрнутый» формат вебаппа: двойные кавычки внутри.
    if '""' in text:
        add(text.replace('""', '"'))

    # Внешние кавычки вокруг всего значения: "...".
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        inner = stripped[1:-1]
        add(inner)
        if '""' in inner:
            add(inner.replace('""', '"'))

    return candidates


def _autoheal(text: str) -> str:
    healed = text.strip()
    # Одинарные кавычки → двойные (только если двойных вообще нет).
    if "'" in healed and '"' not in healed:
        healed = healed.replace("'", '"')
    # Висячие запятые.
    healed = healed.replace(",}", "}").replace(",]", "]")
    return healed


def decode_items(raw: Any) -> Dict[str, Any]:
    """Расшифровка users.items в словарь. Никогда не бросает исключение."""
    if raw is None:
        return {}

    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}

    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8", errors="replace")
        except Exception:
            return {}

    if not isinstance(raw, str):
        return {}

    text = raw.strip()
    if not text or is_telegram_file_id(text):
        return {}

    for candidate in _parse_candidates(text):
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        result = _coerce_dict(data)
        if result is not None:
            return result
        # Дважды закодированный JSON: строка внутри строки.
        if isinstance(data, str):
            try:
                nested = json.loads(data)
            except Exception:
                continue
            result = _coerce_dict(nested)
            if result is not None:
                return result

    # Последняя попытка — мягкое авто-лечение.
    try:
        data = json.loads(_autoheal(text))
        result = _coerce_dict(data)
        if result is not None:
            return result
    except Exception:
        pass

    return {}


def normalize_inventory(items: Dict[str, Any]) -> Dict[str, int]:
    """Оставляет только положительные целочисленные количества (для отображения/санитайза)."""
    result: Dict[str, int] = {}
    if not isinstance(items, dict):
        return result
    for key, value in items.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            result[str(key)] = count
    return result


def encode_items(items: Dict[str, Any]) -> str:
    """Сериализация инвентаря в чистый JSON (совместимо с вебаппом и старым ботом).

    Использует ``ensure_ascii=True`` и стандартные разделители — тот же формат,
    что раньше давал ``json.dumps(inventory)`` в боте, поэтому запись поведенчески
    не меняется, но теперь проходит через единую точку.
    """
    if not isinstance(items, dict):
        items = {}
    return json.dumps(items, ensure_ascii=True, separators=(", ", ": "))
