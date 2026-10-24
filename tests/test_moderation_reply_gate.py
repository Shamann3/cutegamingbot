# -*- coding: utf-8 -*-
"""Справка модерации только без ответа на сообщение."""
from types import SimpleNamespace

from bot.admins.mute import (
    _get_reply_target_message,
    _message_has_reply_context,
    _reply_person,
)
from bot.funcs.reply_origin import note_bot_reply, note_human, reset_reply_origin


def test_reply_context_from_reply_to_message():
    msg = SimpleNamespace(
        reply_to_message=SimpleNamespace(message_id=1),
        external_reply=None,
        reply_parameters=None,
    )
    assert _message_has_reply_context(msg)


def test_reply_context_from_external_reply_without_user():
    msg = SimpleNamespace(
        reply_to_message=None,
        external_reply=SimpleNamespace(origin=None, message_id=99),
        reply_parameters=None,
    )
    assert _message_has_reply_context(msg)
    assert _get_reply_target_message(msg) is None


def test_external_reply_origin_user_becomes_target():
    human = SimpleNamespace(id=42, is_bot=False, first_name="Ann", username="ann")
    origin = SimpleNamespace(sender_user=human)
    ext = SimpleNamespace(origin=origin, chat=SimpleNamespace(id=-100), message_id=7)
    msg = SimpleNamespace(reply_to_message=None, external_reply=ext, reply_parameters=None)
    stub = _get_reply_target_message(msg)
    assert stub is not None
    assert _reply_person(stub).id == 42


def test_bot_reply_chain_resolves_person():
    reset_reply_origin()
    note_human(-100, 15, 88)
    note_bot_reply(-100, 40, 15)
    bot_msg = SimpleNamespace(
        message_id=40,
        chat=SimpleNamespace(id=-100),
        from_user=SimpleNamespace(id=999, is_bot=True),
        reply_to_message=None,
        text="",
        entities=(),
    )
    person = _reply_person(bot_msg)
    assert person is not None
    assert person.id == 88
