# -*- coding: utf-8 -*-
"""Ссылки Mini App, которые открываются и в группе, и в личке.

Telegram принимает web_app-кнопки только в private chat. В группе такая
кнопка выглядит живой, но не открывается. Обычная url-кнопка
https://t.me/bot/app?startapp=... открывает тот же Mini App везде.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, parse_qs, urlencode, urlsplit, urlparse, urlunsplit

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
    """Ссылка на основное приложение, не на короткое имя /cute.

    Короткое имя всё ещё привязано к удалённому хосту
    cutegaming-mobet.ondigitalocean.app, поэтому t.me/бот/cute не открывается.
    t.me/бот?startapp=... открывает кнопку меню, а у неё живой адрес.
    """
    link = f"https://t.me/{bot_username()}"
    start = (startapp or "").strip()
    if start:
        link += f"?startapp={start}"
    return link


def farm_url() -> str:
    return mini_app_url("farm")


_PROD_WEBAPP_URL = "https://cutegaming-ridbh.ondigitalocean.app/"
# Старый адрес приложения: домен снят, DNS его больше не находит.
_DEAD_HOSTS = frozenset({"cutegaming-mobet.ondigitalocean.app"})


def webapp_page_url(startapp: str = "") -> str:
    """Адрес Mini App с разделом в query. Его открывает кнопка web_app в личке."""
    base = (os.getenv("WEBAPP_URL") or "").strip()
    host = (urlsplit(base).hostname or "").lower()
    if not base.startswith("https://") or "ngrok" in base.lower() or host in _DEAD_HOSTS:
        base = _PROD_WEBAPP_URL
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    start = (startapp or "").strip()
    if start:
        query["startapp"] = start
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), ""))


def section_button_fields(text: str, startapp: str, *, private: bool, icon: str = "") -> dict:
    """Поля кнопки «открыть раздел».

    В личке — web_app, он открывает приложение сразу.
    В группе web_app не работает, поэтому обычная ссылка t.me.
    """
    fields = {"text": text, "style": "default"}
    if icon:
        fields["icon_custom_emoji_id"] = icon
    if private:
        fields["web_app_url"] = webapp_page_url(startapp)
    else:
        fields["url"] = mini_app_url(startapp)
    return fields


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
    raw = (url or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if f"t.me/{bot_username().lower()}/" in low:
        return True
    host = (urlparse(raw).hostname or "").lower()
    return bool(host) and ("cutegaming" in host or host.endswith("ondigitalocean.app"))


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
        return mini_app_url(infer_startapp(raw, text) or "farm")
    return raw
