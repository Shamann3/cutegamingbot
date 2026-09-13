"""Кнопки Mini App в группах должны уходить t.me-ссылкой, не web_app."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_notify import build_inline_keyboard, group_safe_button_url


def test_group_web_app_farm_becomes_deep_link():
    url = group_safe_button_url(
        "https://cutegaming-ridbh.ondigitalocean.app/",
        "Открыть ферму",
        "web_app",
    )
    assert url == "https://t.me/CuteGamingBot/cute?startapp=farm"


def test_group_keyboard_never_emits_web_app():
    raw = build_inline_keyboard(
        [[{"text": "Ферма", "url": "https://cutegaming-ridbh.ondigitalocean.app/", "type": "web_app"}]],
        group_safe=True,
    )
    data = json.loads(raw)
    btn = data["inline_keyboard"][0][0]
    assert "web_app" not in btn
    assert btn["url"] == "https://t.me/CuteGamingBot/cute?startapp=farm"


def test_private_keyboard_keeps_web_app():
    raw = build_inline_keyboard(
        [[{"text": "Ферма", "url": "https://cutegaming-ridbh.ondigitalocean.app/", "type": "web_app"}]],
        group_safe=False,
    )
    data = json.loads(raw)
    btn = data["inline_keyboard"][0][0]
    assert btn["web_app"]["url"] == "https://cutegaming-ridbh.ondigitalocean.app/"


def test_external_url_stays_external():
    url = group_safe_button_url("https://t.me/CuteGamingChat", "Группа", "url")
    assert url == "https://t.me/CuteGamingChat"
