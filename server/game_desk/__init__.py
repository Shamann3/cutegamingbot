# -*- coding: utf-8 -*-
"""Стол игр для FastAPI. Пакета bot в api-контейнере нет."""

from .catalog import catalog_public, default_payload
from .schema import ensure_game_desk_schema
from .store import load_payload, merge_payload, save_payload

__all__ = [
    "catalog_public",
    "default_payload",
    "ensure_game_desk_schema",
    "load_payload",
    "merge_payload",
    "save_payload",
]
