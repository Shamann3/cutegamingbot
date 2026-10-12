# -*- coding: utf-8 -*-
"""Вход в задания: короткая подсказка и ссылка, которая открывает меню."""
from __future__ import annotations

TASKS_URL = "https://t.me/CuteGamingBot?start=tasks"
TASKS_ICON = "5462902520215002477"
TASKS_START = "tasks"

_ASKS = {
    "задания",
    "задание",
    "хелп задания",
    "задания хелп",
    "задание хелп",
    "хелп задание",
    "челленжи",
    "челленджи",
    "челленж",
    "челлендж",
    "хелп челленжи",
    "челленжи хелп",
    "хелп челленджи",
    "челленджи хелп",
}


def is_tasks_ask(text: str) -> bool:
    raw = " ".join(str(text or "").replace("ё", "е").split()).casefold()
    return raw in _ASKS


def tasks_prompt_text() -> str:
    return (
        f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> "
        "<b>Для начала, нажмите на кнопку снизу</b>"
    )


def is_tasks_start(payload: str) -> bool:
    return str(payload or "").strip().casefold() == TASKS_START
