# -*- coding: utf-8 -*-
"""Панель наказывает человека, которого ещё нет в users."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from offender_profile import (
    BOT,
    DENIED,
    GLANCE_OUTSIDE,
    GLANCE_SILENT,
    NAME_ONLY,
    SAVED_NAMED,
    SAVED_SILENT,
    SHORT,
    UNCHECKED,
    OffenderRefused,
    _seen,
    account_missing_text,
    adopt_query,
    failure_text,
    glance_person,
    parse_offender_query,
    prepare_offender,
    read_telegram_answer,
)


@pytest.fixture(autouse=True)
def fresh_memory():
    _seen.clear()
    yield
    _seen.clear()


def test_links_and_plain_words_split_into_id_username_or_name():
    assert parse_offender_query("8827084733") == {"kind": "id", "user_id": 8827084733}
    assert parse_offender_query("@8827084733") == {"kind": "id", "user_id": 8827084733}
    assert parse_offender_query("tg://user?id=123456789") == {"kind": "id", "user_id": 123456789}
    assert parse_offender_query("https://t.me/Prayz00") == {"kind": "username", "username": "Prayz00"}
    assert parse_offender_query("t.me/Prayz00?start=1") == {"kind": "username", "username": "Prayz00"}
    assert parse_offender_query("https://t.me/c/123/4")["kind"] == "bad"
    assert parse_offender_query("Вася")["kind"] == "name"
    assert parse_offender_query("10") == {"kind": "id", "user_id": 10}


def test_missing_from_this_chat_is_not_a_missing_account():
    denied = read_telegram_answer(5, {"ok": False, "description": "Bad Request: USER_ID_INVALID"}, None)
    assert denied["kind"] == "denied"
    absent = read_telegram_answer(
        8827084733,
        {"ok": False, "description": "Bad Request: chat not found"},
        {"ok": False, "description": "Bad Request: PARTICIPANT_ID_INVALID"},
    )
    assert absent["kind"] == "silent"
    named = read_telegram_answer(
        8827084733,
        {"ok": False, "description": "chat not found"},
        {"ok": True, "result": {"user": {"id": 8827084733, "first_name": "Prayz", "username": "Prayz00"}}},
    )
    assert named["kind"] == "person"
    assert named["person"]["first_name"] == "Prayz"
    bot = read_telegram_answer(4, {"ok": True, "result": {"id": 4, "type": "private", "is_bot": True, "first_name": "Bot"}}, None)
    assert bot["kind"] == "bot"
    place = read_telegram_answer(-100, {"ok": True, "result": {"id": -100, "type": "channel", "title": "Новости"}}, None)
    assert place["kind"] == "place"


def _row(user_id, first_name, username=None):
    return {"user_id": user_id, "first_name": first_name, "username": username, "balance": 0, "banned": False}


def test_a_named_player_already_in_kut_is_not_asked_again():
    import asyncio
    asyncio.run(_named_player_is_not_asked_again())


async def _named_player_is_not_asked_again():
    calls = []

    async def tg(method, **params):
        calls.append(method)
        return {"ok": False}

    async def load(user_id):
        return _row(user_id, "Анна", "anna")

    saved = []

    async def save(person):
        saved.append(person)

    result = await prepare_offender(7, -100, tg_api=tg, load_row=load, save_person=save)
    assert result["ok"] is True
    assert result["created"] is False
    assert result["first_name"] == "Анна"
    assert calls == []
    assert saved == []


def test_username_outside_kut_is_shown_and_saved_only_when_asked():
    import asyncio
    asyncio.run(_username_outside_kut())


async def _username_outside_kut():
    async def tg(method, **params):
        assert params["chat_id"] == "@Prayz00" or params["chat_id"] == 8827084733
        return {"ok": True, "result": {
            "id": 8827084733, "type": "private", "first_name": "Prayz", "username": "Prayz00",
        }}

    async def empty(_value):
        return None

    glance = await glance_person("@Prayz00", tg_api=tg, load_row=empty, load_username=empty)
    assert glance["status"] == "outside"
    assert glance["user"]["userId"] == 8827084733
    assert glance["message"] == GLANCE_OUTSIDE
    assert "ещё нет" in glance["message"]

    saved = []

    async def save(person):
        saved.append(person)

    prepared = await prepare_offender(8827084733, -5, tg_api=tg, load_row=empty, save_person=save)
    assert prepared["ok"] is True
    assert prepared["created"] is True
    assert prepared["message"] == SAVED_NAMED
    assert saved[0]["username"] == "Prayz00"


def test_a_long_unseen_id_is_kept_and_a_fake_one_is_refused():
    import asyncio
    asyncio.run(_long_id_and_fake_id())


async def _long_id_and_fake_id():
    async def silent(method, **_params):
        if method == "getChat":
            return {"ok": False, "description": "Bad Request: chat not found"}
        return {"ok": False, "description": "Bad Request: PARTICIPANT_ID_INVALID"}

    saved = []

    async def save(person):
        saved.append(person)

    async def empty(_value):
        return None

    quiet = await prepare_offender(8827084733, -100, tg_api=silent, load_row=empty, save_person=save)
    assert quiet["ok"] is True
    assert quiet["placeholder"] is True
    assert quiet["message"] == SAVED_SILENT
    assert saved[0]["first_name"] == "8827084733"

    glance = await glance_person("8827084733", -100, tg_api=silent, load_row=empty, load_username=empty)
    assert glance["status"] == "silent"
    assert glance["message"] == GLANCE_SILENT

    async def denied(method, **_params):
        return {"ok": False, "description": "Bad Request: USER_ID_INVALID"}

    refused = await prepare_offender(8827084734, -100, tg_api=denied, load_row=empty, save_person=save)
    assert refused["ok"] is False
    assert refused["refusal"] == DENIED.format(user_id=8827084734)
    assert len(saved) == 1


def test_short_numbers_bots_channels_and_plain_names_do_not_become_players():
    import asyncio
    asyncio.run(_rejects())


async def _rejects():
    async def tg(*_args, **_kwargs):
        raise AssertionError("telegram")

    async def empty(_value):
        return None

    short = await prepare_offender(10, None, tg_api=tg, load_row=empty, save_person=empty)
    assert short["refusal"] == SHORT

    async def bot_chat(method, **_params):
        return {"ok": True, "result": {"id": 500000, "type": "private", "is_bot": True, "first_name": "Helper"}}

    bot = await prepare_offender(500000, None, tg_api=bot_chat, load_row=empty, save_person=empty)
    assert bot["refusal"] == BOT

    glance = await glance_person("Вася Пупкин", tg_api=tg, load_row=empty, load_username=empty)
    assert glance["message"] == NAME_ONLY

    unseen = await glance_person("@quietuser1", tg_api=lambda *a, **k: {"ok": False, "description": "chat not found"}, load_row=empty, load_username=empty)
    assert unseen["status"] == "unchecked"
    assert unseen["message"] == UNCHECKED.format(name="quietuser1")

    with pytest.raises(OffenderRefused) as raised:
        await adopt_query("@quietuser1", tg_api=lambda *a, **k: {"ok": False, "description": "chat not found"})
    assert "не знает ID" in str(raised.value)


def test_a_spoken_refusal_is_shown_as_written():
    assert failure_text({"spoken": SHORT, "telegram": "USER_ID_INVALID"}) == SHORT
    assert account_missing_text("Bad Request: user not found") is True
    assert account_missing_text("PARTICIPANT_ID_INVALID") is False
