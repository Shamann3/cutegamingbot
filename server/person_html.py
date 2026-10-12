"""Имя человека в тексте, который бот отправляет из API.

С юзернеймом — ссылка https://t.me/username, текстом ссылки служит имя.
Без юзернейма — то же имя обычным текстом, без tg://user.
"""

from __future__ import annotations

import html
import re

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


def person_name_html(name, username=None, *, empty: str = "Без имени") -> str:
    handle = str(username or "").strip().lstrip("@")
    if not _USERNAME.fullmatch(handle):
        handle = ""
    label = " ".join(str(name or "").split())
    if not label:
        label = handle or empty or "Без имени"
    safe = html.escape(label, quote=False)
    if not handle:
        return safe
    return f'<a href="https://t.me/{handle}">{safe}</a>'
