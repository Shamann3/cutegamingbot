# -*- coding: utf-8 -*-
from types import SimpleNamespace

from bot.funcs.reply_origin import (
    note_bot_reply,
    note_human,
    note_outgoing,
    note_update,
    person_behind_bot_message,
    reset_reply_origin,
)


def setup_function():
    reset_reply_origin()


def test_who_on_a_bot_reply_opens_the_person_the_bot_answered():
    note_human(-100, 15, 77)
    note_bot_reply(-100, 40, 15)
    reply = SimpleNamespace(
        message_id=40,
        chat=SimpleNamespace(id=-100),
        from_user=SimpleNamespace(id=999, is_bot=True),
        reply_to_message=None,
    )
    assert person_behind_bot_message(reply) == 77


def test_nested_reply_is_used_when_telegram_sends_it():
    reply = SimpleNamespace(
        message_id=40,
        chat=SimpleNamespace(id=-100),
        from_user=SimpleNamespace(id=999, is_bot=True),
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=77, is_bot=False)),
    )
    assert person_behind_bot_message(reply) == 77


def test_outgoing_send_remembers_the_answered_person():
    note_update(SimpleNamespace(
        message=SimpleNamespace(
            message_id=15,
            chat=SimpleNamespace(id=-100),
            from_user=SimpleNamespace(id=77, is_bot=False),
        ),
    ))
    method = SimpleNamespace(
        chat_id=-100,
        reply_parameters=SimpleNamespace(message_id=15),
    )
    sent = SimpleNamespace(message_id=40, chat=SimpleNamespace(id=-100))
    note_outgoing(method, sent)
    assert person_behind_bot_message(SimpleNamespace(
        message_id=40,
        chat=SimpleNamespace(id=-100),
        reply_to_message=None,
    )) == 77


def test_a_bot_message_without_a_person_stays_unknown():
    assert person_behind_bot_message(SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(id=-100),
        reply_to_message=None,
    )) is None
