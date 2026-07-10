"""Кодирование и декодирование JSON-предметов как в PostgreSQL (кириллица → \\uXXXX)."""

from __future__ import annotations

import json
from typing import Any

_FILE_ID_PREFIXES = ("CAAC", "AgAC", "BQAC", "CgAC")
_FILE_ID_MARKERS = ("AAxkB", "xkB", "palochka")


def is_telegram_file_id(text: str) -> bool:
    value = (text or "").strip()
    if len(value) < 20:
        return False
    if value.startswith(_FILE_ID_PREFIXES):
        return True
    return any(marker in value for marker in _FILE_ID_MARKERS)


def _normalize_counts(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        return {}
    result: dict[str, int] = {}
    for key, value in data.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        result[str(key)] = count
    return result


def _parse_candidates(text: str) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    def add(value: str) -> None:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)

    add(text)
    if '""' in text:
        add(text.replace('""', '"'))

    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        inner = stripped[1:-1]
        add(inner)
        if '""' in inner:
            add(inner.replace('""', '"'))

    return candidates


def decode_json_payload(raw: Any) -> dict[str, int]:
    """Расшифровка JSON из БД: dict, строка, двойные кавычки, \\uXXXX."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return _normalize_counts(raw)

    if isinstance(raw, str):
        text = raw.strip()
        if not text or is_telegram_file_id(text):
            return {}

        for candidate in _parse_candidates(text):
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict):
                return _normalize_counts(data)
            if isinstance(data, str):
                try:
                    nested = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(nested, dict):
                    return _normalize_counts(nested)
        return {}

    return {}


def encode_json_payload(items: dict, *, name_map: dict[str, str] | None = None) -> str:
    """Сериализация users.items → единый чистый JSON (кириллица → \\uXXXX).

    Формат — стандартный JSON-объект {имя_предмета: количество}, полностью
    совместимый с основным ботом (который использует json.dumps/json.loads):
      {"\\u041a\\u043b\\u044e\\u0447": 7, "\\u0412\\u043e\\u0434\\u0430": 98}

    Ключи — имена предметов из dex (русские символы экранируются в \\uXXXX,
    как это делает json.dumps по умолчанию, чтобы TEXT в БД оставался ASCII).

    name_map: {str(id) -> имя} — подаётся из user_items.items_to_db, чтобы
    привести ключи к dex.name. Если id не найден в name_map — ключ
    сохраняется как есть (безопасный fallback).

    Примечание: старый «обёрнутый» формат ("{""...""}") больше не пишется, но
    по-прежнему корректно читается через decode_json_payload — при первом
    старте сервера migrate_all_users_items нормализует такие записи.
    """
    normalized = _normalize_counts(items)

    if name_map:
        named: dict[str, int] = {}
        for key, count in normalized.items():
            display_key = name_map.get(str(key), str(key))
            named[display_key] = named.get(display_key, 0) + count
        normalized = named

    # Стандартный JSON с теми же разделителями, что и у json.dumps в боте.
    return json.dumps(normalized, ensure_ascii=True, separators=(", ", ": "))


def format_payload_text(items: dict[str, int]) -> str:
    if not items:
        return ""
    return ", ".join(f"{name} ×{count}" for name, count in items.items())
