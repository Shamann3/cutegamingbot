"""Кратковременный кэш ответа биржи (без баланса пользователя)."""

from __future__ import annotations

import copy
import time
from typing import Any


def _clone_for_read(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow clone — enough for read-only API responses; avoids deepcopy on every hit."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, list):
            out[key] = [
                dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, dict):
            out[key] = dict(value)
        else:
            out[key] = value
    return out


class ShopCatalogCache:
    def __init__(self, ttl_seconds: int = 45) -> None:
        self.ttl_seconds = max(0, int(ttl_seconds))
        self._entries: dict[str, tuple[float, dict[str, Any]]] = {}

    def _key(
        self,
        category_id: str,
        page: int,
        search_q: str,
        price_filter: str,
        sort_by: str,
        sort_order: str,
        page_size: int,
    ) -> str:
        return "|".join(
            (
                category_id,
                str(page),
                search_q,
                price_filter,
                sort_by,
                sort_order,
                str(page_size),
            )
        )

    def get(
        self,
        category_id: str,
        page: int,
        search_q: str,
        price_filter: str,
        sort_by: str,
        sort_order: str,
        page_size: int,
    ) -> dict[str, Any] | None:
        if self.ttl_seconds <= 0:
            return None

        key = self._key(
            category_id, page, search_q, price_filter, sort_by, sort_order, page_size
        )
        entry = self._entries.get(key)
        if not entry:
            return None

        saved_at, payload = entry
        if time.monotonic() - saved_at > self.ttl_seconds:
            self._entries.pop(key, None)
            return None

        return _clone_for_read(payload)

    def set(
        self,
        category_id: str,
        page: int,
        search_q: str,
        price_filter: str,
        sort_by: str,
        sort_order: str,
        page_size: int,
        payload: dict[str, Any],
    ) -> None:
        if self.ttl_seconds <= 0:
            return

        key = self._key(
            category_id, page, search_q, price_filter, sort_by, sort_order, page_size
        )
        stored = {k: v for k, v in payload.items() if k != "kut"}
        self._entries[key] = (time.monotonic(), copy.deepcopy(stored))

    def clear(self) -> None:
        self._entries.clear()


def build_shop_catalog_cache(ttl_seconds: int) -> ShopCatalogCache:
    return ShopCatalogCache(ttl_seconds=ttl_seconds)
