# -*- coding: utf-8 -*-
from bot.funcs.whisper_open import (
    alert_text,
    arm_wait,
    ask_text,
    claim_wait,
    group_has_secret,
    split_address,
    whisper_body,
    whisper_page,
)


def test_whisper_keeps_the_letters_after_the_word():
    assert whisper_body("прошептать Привет, Вася") == "Привет, Вася"
    assert whisper_body("Шепнуть  Тихо") == "Тихо"
    assert whisper_body("Шептнуть Тихо") == "Тихо"
    assert whisper_body("баланс") is None
    assert whisper_body("прошептать") == ""


def test_whisper_address_reads_name_link_and_id():
    kind, secret = split_address("@Vasya привет, это секрет", plain=True)
    assert kind == ("username", "Vasya")
    assert secret == "привет, это секрет"
    kind, secret = split_address("https://t.me/Vasya одна строка", plain=False)
    assert kind == ("username", "Vasya")
    assert secret == "одна строка"
    kind, secret = split_address("tg://user?id=555001234 тихо", plain=False)
    assert kind == ("id", "555001234")
    assert secret == "тихо"
    kind, secret = split_address("123456789 текст", plain=False)
    assert kind == ("id", "123456789")
    assert secret == "текст"
    assert split_address("Привет, Вася", plain=False) == (None, "Привет, Вася")
    kind, secret = split_address("vasya секрет", plain=True)
    assert kind == ("username", "vasya")
    assert secret == "секрет"


def test_whisper_page_names_the_sender_and_escapes():
    page = whisper_page("Аня", "привет <b>тут</b>")
    assert page.startswith("<b>Шёпот</b>")
    assert "от Аня" in page
    assert "привет &lt;b&gt;тут&lt;/b&gt;" in page
    assert "<b>тут</b>" not in page.split("\n\n", 1)[1]


def test_a_group_line_does_not_become_the_secret():
    assert group_has_secret("Привет") is True
    assert group_has_secret("") is False
    note = ask_text("Вася", leaked=True)
    assert "Привет" not in note
    assert "недавних действиях" in note
    safe = ask_text("Вася", leaked=False)
    assert "в лич" not in safe
    assert "В группе будет только карточка" in safe
    token = arm_wait(
        sender_id=5,
        receiver_id=7,
        sender_name="Аня",
        receiver_name="Вася",
        chat_id=-100,
    )
    assert claim_wait(5)["token"] == token
    assert claim_wait(5) is None


def test_alert_stays_inside_the_telegram_limit():
    assert alert_text("коротко") == "коротко"
    long = alert_text("я" * 250)
    assert len(long) == 200
    assert long.endswith("…")
