# -*- coding: utf-8 -*-
from bot.funcs.whisper_open import alert_text, whisper_body, whisper_page


def test_whisper_keeps_the_letters_after_the_word():
    assert whisper_body("прошептать Привет, Вася") == "Привет, Вася"
    assert whisper_body("Шепнуть  Тихо") == "Тихо"
    assert whisper_body("баланс") is None
    assert whisper_body("прошептать") == ""


def test_whisper_page_names_the_sender_and_escapes():
    page = whisper_page("Аня", "привет <b>тут</b>")
    assert page.startswith("<b>Шёпот</b>")
    assert "от Аня" in page
    assert "привет &lt;b&gt;тут&lt;/b&gt;" in page
    assert "<b>тут</b>" not in page.split("\n\n", 1)[1]


def test_alert_stays_inside_the_telegram_limit():
    assert alert_text("коротко") == "коротко"
    long = alert_text("я" * 250)
    assert len(long) == 200
    assert long.endswith("…")
