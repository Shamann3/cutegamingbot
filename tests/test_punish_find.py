# -*- coding: utf-8 -*-
"""Нарушитель не из Кута: упоминание, ссылка, @username — всё доходит до Telegram.

Без базы, без main.py и без настоящего Telegram: юзербот и Bot API подменены.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.admins.punish_clause import handle_from_url, swap_people


def _mention(offset, length, uid, first="Вася", username=None):
    user = SimpleNamespace(id=uid, first_name=first, last_name="", username=username, is_bot=False)
    return SimpleNamespace(type="text_mention", offset=offset, length=length, user=user)


def test_mention_without_username_becomes_an_id_even_after_an_emoji():
    text = "бан 😀 Вася Пупкин спам"
    # «😀» в UTF-16 занимает две позиции, поэтому имя начинается с 7, а не с 6.
    swapped, people = swap_people(text, [_mention(7, 11, 8858841901)])
    assert swapped.split() == ["бан", "😀", "@8858841901", "спам"]
    assert people[8858841901].first_name == "Вася"


def test_profile_links_inside_the_text_become_handles():
    text = "мут Лена 1ч"
    link = SimpleNamespace(type="text_link", offset=4, length=4, url="tg://user?id=123456789")
    swapped, people = swap_people(text, [link])
    assert swapped.split() == ["мут", "@123456789", "1ч"]
    assert people == {}

    assert handle_from_url("https://t.me/Prayz00") == "@Prayz00"
    assert handle_from_url("t.me/Prayz00?start=1") == "@Prayz00"
    assert handle_from_url("tg://resolve?domain=Prayz00") == "@Prayz00"
    assert handle_from_url("https://t.me/+AbCdEf") == ""
    assert handle_from_url("https://example.com/Prayz00") == ""


def test_text_without_people_stays_as_it_was():
    assert swap_people("бан @Prayz00 дп", [SimpleNamespace(type="mention", offset=4, length=8)]) == (
        "бан @Prayz00 дп",
        {},
    )


class _Reply:
    id = 7
    first_name = "Ann"
    full_name = "Ann"
    username = "ann"
    is_bot = False
    last_name = None


def test_a_reason_word_does_not_steal_the_reply_target():
    asyncio.run(_reason_word_does_not_steal_the_reply_target())


async def _reason_word_does_not_steal_the_reply_target():
    from bot.admins.mute import read_punish_clause

    asked = []

    async def lookup(token, source_chat_id=None, telegram=True):
        asked.append(token)
        return 99, "Someone", "flood"

    with patch("bot.admins.mute._lookup_target_by_token", lookup), patch(
        "bot.admins.punish_validate.ensure_punishment_profile",
        AsyncMock(return_value=(7, "Ann", "ann")),
    ):
        clause = await read_punish_clause(["навсегда", "flood"], reply_user=_Reply())
    assert clause.target_id == 7
    assert clause.reason == "flood"
    assert asked == []


def test_a_latin_word_in_the_middle_is_only_a_kut_player():
    asyncio.run(_latin_word_in_the_middle_is_only_a_kut_player())


async def _latin_word_in_the_middle_is_only_a_kut_player():
    from bot.admins.mute import read_punish_clause

    asked = []

    async def lookup(token, source_chat_id=None, telegram=True):
        asked.append((token, telegram))
        if token == "Вася":
            return 5, "Вася", None
        return None, None, None

    with patch("bot.admins.mute._lookup_target_by_token", lookup):
        clause = await read_punish_clause(["Вася", "flood"])
    assert clause.target_id == 5
    assert clause.reason == "flood"
    assert ("flood", False) in asked

    asked.clear()

    async def first(token, source_chat_id=None, telegram=True):
        asked.append((token, telegram))
        return 77, "Prayz", "Prayz00"

    with patch("bot.admins.mute._lookup_target_by_token", first):
        clause = await read_punish_clause(["Prayz00", "дп"])
    assert clause.target_id == 77
    assert clause.reason == "дп"
    assert asked == [("Prayz00", True)]


class _SilentBot:
    async def get_chat(self, _chat_id):
        raise RuntimeError("Bad Request: chat not found")


@pytest.fixture
def fresh_budget(monkeypatch):
    from bot.funcs import who_lookup as who

    budget = who.UsernameBudget()
    monkeypatch.setattr(who, "USERNAME_BUDGET", budget)
    monkeypatch.setattr("bot.admins.punish_validate._bot", lambda: _SilentBot())
    return budget


def _userbot(answer):
    from bot.funcs import who_lookup as who

    resolve = AsyncMock(return_value=answer)
    return (
        patch.object(who, "find_userbot", return_value=object()),
        patch.object(who, "resolve_with_userbot", resolve),
        resolve,
    )


def test_username_outside_kut_is_found_in_telegram(fresh_budget):
    from bot.admins import punish_validate as pv
    from bot.funcs.who_lookup import TgPerson

    person = TgPerson(user_id=8827084733, first_name="Prayz", username="Prayz00")
    found, resolve, mock = _userbot(("person", person))
    with found, resolve:
        kind, saved = asyncio.run(pv.find_telegram_username("@Prayz00"))
        again = asyncio.run(pv.find_telegram_username("prayz00"))
    assert kind == "person"
    assert saved == {"user_id": 8827084733, "first_name": "Prayz", "username": "Prayz00"}
    assert again[0] == "person"
    assert mock.await_count == 1, "второй раз ответ берётся из кэша"


def test_each_miss_explains_itself(fresh_budget):
    from bot.admins import punish_validate as pv
    from bot.funcs.who_lookup import TgPerson, TgPlace

    cases = [
        ("missing", None, "nobodyhere1", "В Telegram нет такого username"),
        ("place", TgPlace("channel", "Новости", "newsroom1"), "newsroom1", "это канал, а не человек"),
        ("person", TgPerson(user_id=5, first_name="Bot", username="helperbot", is_bot=True),
         "helperbot", "это бот"),
    ]
    for kind, value, username, words in cases:
        found, resolve, _ = _userbot((kind, value))
        with found, resolve:
            result = asyncio.run(pv.find_telegram_username(username))
        assert result[1] is None, username
        assert words in pv.username_miss_html(username, "fallback"), username


def test_silent_telegram_is_not_called_not_found(fresh_budget):
    from bot.admins import punish_validate as pv
    from bot.funcs import who_lookup as who

    with patch.object(who, "find_userbot", return_value=None):
        kind, person = asyncio.run(pv.find_telegram_username("quietuser1"))
    assert (kind, person) == ("unknown", None)
    assert "Не получилось проверить" in pv.username_miss_html("quietuser1", "fallback")
    assert pv.username_miss_html("neverasked1", "fallback") == "fallback"


def test_flood_wait_pauses_the_next_question(fresh_budget):
    from bot.admins import punish_validate as pv

    found, resolve, mock = _userbot(("flood", 120))
    with found, resolve:
        assert asyncio.run(pv.find_telegram_username("floodcheck1"))[0] == "flood"
        assert asyncio.run(pv.find_telegram_username("floodcheck2"))[0] == "flood"
    assert mock.await_count == 1
    assert "подождать 2 мин" in pv.username_miss_html("floodcheck1", "fallback")


def test_username_person_gets_a_kut_row_before_the_punishment(fresh_budget):
    from bot.admins import punish_validate as pv
    from bot.funcs.who_lookup import TgPerson

    person = TgPerson(user_id=8827084733, first_name="Prayz", username="Prayz00")
    found, resolve, _ = _userbot(("person", person))
    adopt = AsyncMock()
    with found, resolve, patch.object(pv, "_stored_user", AsyncMock(return_value=(False, "", None))), patch.object(
        pv, "_adopt_person", adopt,
    ):
        result = asyncio.run(pv.ensure_punishment_profile(0, username="Prayz00", source_chat_id=-100))
    assert result == (8827084733, "Prayz", "Prayz00")
    adopt.assert_awaited_once()
    assert adopt.await_args.args[0]["user_id"] == 8827084733
