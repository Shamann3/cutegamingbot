# -*- coding: utf-8 -*-
"""Ссылки Mini App, которые открываются и в группе, и в личке.

Telegram принимает web_app-кнопки только в private chat. В группе такая
кнопка выглядит живой, но не открывается. Обычная url-кнопка
https://t.me/bot/app?startapp=... открывает тот же Mini App везде.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

try:
    from bot.config.config import APP_NAME, BOT_USERNAME123412
except Exception:  # pragma: no cover
    BOT_USERNAME123412 = "CuteGamingBot"
    APP_NAME = "cute"

FARM_ICON_ID = "5208464835079082371"

_STARTAPP_HINTS = (
    ("farm", ("farm", "ферм")),
    ("market", ("market", "бирж", "рынок", "маркет")),
    ("shop", ("shop", "магазин", "шоп")),
    ("craft", ("craft", "крафт")),
    ("inventory", ("inventory", "инвентар")),
)


def bot_username() -> str:
    return str(BOT_USERNAME123412 or "CuteGamingBot").lstrip("@")


def app_short_name() -> str:
    return str(APP_NAME or "cute").strip() or "cute"


def mini_app_url(startapp: str = "") -> str:
    link = f"https://t.me/{bot_username()}/{app_short_name()}"
    start = (startapp or "").strip()
    if start:
        link += f"?startapp={start}"
    return link


def farm_url() -> str:
    return mini_app_url("farm")


def infer_startapp(url: str = "", text: str = "") -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    for key in ("startapp", "tgWebAppStartParam"):
        values = qs.get(key) or []
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    blob = f"{parsed.path} {text}".lower()
    for startapp, hints in _STARTAPP_HINTS:
        if any(hint in blob for hint in hints):
            return startapp
    return ""


def is_telegram_deep_link(url: str) -> bool:
    low = (url or "").strip().lower()
    return low.startswith("tg:") or "t.me/" in low


def is_our_mini_app(url: str) -> bool:
    low = (url or "").strip().lower()
    if not low:
        return False
    if f"t.me/{bot_username().lower()}/" in low:
        return True
    return "cutegaming" in low


def group_safe_url(url: str, text: str = "", *, as_web_app: bool = False) -> str:
    """URL, который можно поставить на кнопку в группе.

    Наш Mini App → t.me/bot/app?startapp=...
    Уже t.me / внешняя ссылка → как есть.
    """
    raw = (url or "").strip()
    if not raw:
        return raw
    if is_telegram_deep_link(raw) and not as_web_app:
        return raw
    if as_web_app or is_our_mini_app(raw):
        return mini_app_url(infer_startapp(raw, text))
    return raw
