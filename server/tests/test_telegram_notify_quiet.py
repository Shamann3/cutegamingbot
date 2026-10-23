# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_notify import (
    PERMANENT_FAILURE_CATEGORIES,
    _classify_error,
    log_each_telegram_error,
)


def test_expected_chat_refusals_are_quiet_and_permanent():
    no_pin = _classify_error(400, "Bad Request: not enough rights to manage pinned messages in the chat")
    no_photo = _classify_error(400, "Bad Request: not enough rights to send photos to the chat")
    moved = _classify_error(400, "Bad Request: group chat was upgraded to a supergroup chat")
    assert no_pin == "no_rights"
    assert no_photo == "no_rights"
    assert moved == "migrated"
    for category in (no_pin, no_photo, moved):
        assert log_each_telegram_error(category) is False
        assert category in PERMANENT_FAILURE_CATEGORIES


def test_a_real_send_mistake_is_still_loud():
    category = _classify_error(400, "Bad Request: can't parse entities")
    assert category == "other"
    assert log_each_telegram_error(category) is True
