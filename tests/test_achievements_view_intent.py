# -*- coding: utf-8 -*-
from bot.handlers.achievements_view import parse_achievements_intent
from bot.funcs.achievements import plain_title_preview


def test_casual_sentence_is_not_achievements_command():
    assert parse_achievements_intent("к слову, за покупку уровня идет достижение") is None
    assert parse_achievements_intent("кто ты") is None
    assert parse_achievements_intent("кто ты такой") is None


def test_real_commands_still_work():
    assert parse_achievements_intent("достижения") == ("view", "")
    assert parse_achievements_intent("мои достижения") == ("own", "")
    assert parse_achievements_intent("достижения @nab27007") == ("view", "@nab27007")
    assert parse_achievements_intent("вася достижения") == ("view", "вася")


def test_profile_pin_does_not_leak_html_tags():
    raw = "<b><tg-emoji emoji-id='5379764753762704744'>🎁</tg-emoji></b> Первооткрыватель"
    preview = plain_title_preview(raw)
    assert "&lt;b&gt;" not in preview
    assert "<b>" not in preview
    assert "Первооткрыватель" in preview


def test_profile_pin_keeps_premium_emoji_and_bold():
    from bot.funcs.achievements import achievement_profile_pin_html
    pin = achievement_profile_pin_html({
        "title_html": (
            "<b><tg-emoji emoji-id='5379764753762704744'>🎁</tg-emoji></b> "
            "Первооткрыватель купона"
        ),
        "icon_emoji_id": "5379764753762704744",
        "icon_fallback": "🎁",
    })
    assert "<tg-emoji" in pin
    assert "5379764753762704744" in pin
    assert "<b>" in pin
    assert "&lt;b&gt;" not in pin
    assert "Первооткрыватель" in pin


def test_showcase_fit_does_not_drop_vitrina_emoji_first():
    from bot.funcs.achievements import fit_protecting_showcase
    chrome = "".join(
        f"<tg-emoji emoji-id='{10000 + i}'>⭐</tg-emoji>" for i in range(40)
    )
    showcase = (
        "<blockquote><tg-emoji emoji-id='5379764753762704744'>🎁</tg-emoji> "
        "<b>Витрина</b> · 1/5\n"
        "<b><tg-emoji emoji-id='5379764753762704744'>🎁</tg-emoji></b> Титул"
        "</blockquote>"
    )
    fitted = fit_protecting_showcase(
        chrome + "\n" + showcase,
        max_emojis=20,
        max_len=3800,
    )
    assert "Витрина" in fitted
    assert "5379764753762704744" in fitted
