# -*- coding: utf-8 -*-
"""Срок и нарушитель читаются в любом порядке. Без базы и без Telegram."""
import asyncio
from unittest.mock import AsyncMock, patch

from bot.admins.punish_clause import (
    find_duration_span,
    is_forever_token,
    is_strong_user_token,
    mention_id,
)


def _parse(text):
    raw = " ".join((text or "").split()).casefold()
    if is_forever_token(raw):
        return ("forever",)
    import re
    if re.fullmatch(
        r"\d+\s*(сек|секунд|мин|минут|минуты|час|часа|часов|день|дня|дней|д|ч|м)",
        raw,
    ):
        return ("time",)
    return None


def test_forever_words():
    assert is_forever_token("навсегда")
    assert is_forever_token("Навсегда")
    assert is_forever_token("навсегда.")
    assert is_forever_token("forever")
    assert not is_forever_token("Рк")
    assert not is_forever_token("10")


def test_mention_id_is_not_a_username():
    assert mention_id("@8858841901") == "8858841901"
    assert mention_id("8858841901") == "8858841901"
    assert mention_id("@sharlout") is None
    assert mention_id("10") is None


def test_iris_phrase_finds_forever_before_the_id():
    parts = ["навсегда", "@8858841901", "Рк"]
    span = find_duration_span(parts, _parse)
    assert span == (0, 1, "навсегда")
    assert is_strong_user_token("@8858841901")
    assert not is_strong_user_token("Рк")
    assert not is_strong_user_token("навсегда")


def test_duration_can_sit_at_the_end():
    parts = ["@8858841901", "Рк", "навсегда"]
    span = find_duration_span(parts, _parse)
    assert span[0] == 2
    assert span[2] == "навсегда"


def test_ten_seconds_is_a_span_not_a_user():
    parts = ["10", "сек", "@user", "привет"]
    span = find_duration_span(parts, _parse)
    assert span == (0, 2, "10 сек")
    assert not is_strong_user_token("10")


def test_long_id_is_not_eaten_as_a_duration():
    parts = ["8858841901", "навсегда", "Рк"]
    span = find_duration_span(parts, _parse)
    assert span[0] == 1
    assert is_strong_user_token("8858841901")


def test_read_clause_accepts_iris_order_and_the_swap():
    asyncio.run(_read_clause_accepts_iris_order_and_the_swap())


async def _read_clause_accepts_iris_order_and_the_swap():
    from bot.admins.mute import parse_duration, read_punish_clause

    parsed = parse_duration("навсегда")
    assert parsed is not None
    _delta, minutes = parsed
    assert minutes > 100000

    async def lookup(token, source_chat_id=None):
        bare = str(token).lstrip("@")
        if bare.isdigit() and len(bare) >= 5:
            return int(bare), "Lena", None
        if bare.lower() in {"user", "sharlout"}:
            return 42, "User", bare
        return None, None, None

    orders = [
        ["навсегда", "@8858841901", "Рк"],
        ["@8858841901", "навсегда", "Рк"],
        ["@8858841901", "Рк", "навсегда"],
        ["Рк", "@8858841901", "навсегда"],
        ["8858841901", "навсегда", "Рк"],
    ]
    with patch("bot.admins.mute._lookup_target_by_token", lookup):
        for parts in orders:
            clause = await read_punish_clause(parts)
            assert clause.error is None, parts
            assert clause.target_id == 8858841901, parts
            assert clause.duration_text == "навсегда", parts
            assert clause.reason == "Рк", parts

        swapped = await read_punish_clause(["10", "сек", "@user", "спам"])
        assert swapped.target_id == 42
        assert swapped.duration_text == "10 сек"
        assert swapped.reason == "спам"

        tail = await read_punish_clause(["@user", "спам", "1", "день"])
        assert tail.target_id == 42
        assert tail.duration_text == "1 день"
        assert tail.reason == "спам"


def test_reply_keeps_the_author_when_only_the_term_is_written():
    asyncio.run(_reply_keeps_the_author_when_only_the_term_is_written())


async def _reply_keeps_the_author_when_only_the_term_is_written():
    from bot.admins.mute import read_punish_clause

    class Reply:
        id = 7
        first_name = "Ann"
        full_name = "Ann"
        username = "ann"
        is_bot = False
        last_name = None

    with patch(
        "bot.admins.punish_validate.ensure_punishment_profile",
        AsyncMock(return_value=(7, "Ann", "ann")),
    ):
        clause = await read_punish_clause(["навсегда", "Рк"], reply_user=Reply())
    assert clause.error is None
    assert clause.target_id == 7
    assert clause.duration_text == "навсегда"
    assert clause.reason == "Рк"


def test_telegram_errors_split_a_fake_id_from_an_unseen_one():
    from bot.admins.punish_validate import (
        is_invalid_telegram_user_error,
        is_user_not_participant_error,
    )

    class TelegramError(Exception):
        pass

    assert not is_invalid_telegram_user_error(TelegramError("Bad Request: PARTICIPANT_ID_INVALID"))
    assert is_user_not_participant_error(TelegramError("Bad Request: PARTICIPANT_ID_INVALID"))
    assert is_invalid_telegram_user_error(TelegramError("USER_ID_INVALID"))
    assert is_invalid_telegram_user_error(TelegramError("PEER_ID_INVALID"))
    assert is_user_not_participant_error(TelegramError("Bad Request: user not found"))
    assert is_user_not_participant_error(TelegramError("USER_NOT_PARTICIPANT"))
    assert not is_user_not_participant_error(TelegramError("Bad Request: chat not found"))
    assert not is_invalid_telegram_user_error(TelegramError("Bad Request: chat not found"))


def test_unseen_account_is_created_and_a_fake_id_is_not():
    asyncio.run(_unseen_account_is_created_and_a_fake_id_is_not())


async def _unseen_account_is_created_and_a_fake_id_is_not():
    from bot.admins.punish_validate import describe_telegram_user, verify_telegram_user_exists

    class Bot:
        def __init__(self, fail):
            self.fail = fail

        async def get_chat(self, user_id):
            raise RuntimeError(self.fail)

    class Member:
        class User:
            id = 8827084733
            first_name = "Ира"
            last_name = ""
            username = "ira_k"
            is_bot = False

        user = User()

    silent = patch("bot.admins.punish_validate._bot", return_value=Bot("Bad Request: chat not found"))
    no_chats = patch("bot.admins.punish_validate.probe_chat_ids", return_value=())
    unknown = patch(
        "bot.admins.punish_validate._ask_userbot",
        AsyncMock(return_value=("unknown", None)),
    )
    with silent, no_chats, unknown:
        person = await describe_telegram_user(8827084733, source_chat_id=1)
        assert person["user_id"] == 8827084733
        assert person["first_name"] == "8827084733"
        assert await describe_telegram_user(10, source_chat_id=1) is None
        assert await verify_telegram_user_exists(8827084733, probe_chat_ids=()) is True
        assert await verify_telegram_user_exists(10, probe_chat_ids=()) is False

    not_here = patch(
        "bot.admins.punish_validate._bot",
        return_value=Bot("Bad Request: PARTICIPANT_ID_INVALID"),
    )
    with not_here, no_chats, unknown:
        person = await describe_telegram_user(8827084733, source_chat_id=-100)
        assert person["user_id"] == 8827084733
        assert await verify_telegram_user_exists(8827084733, probe_chat_ids=(-100,)) is True

    with patch("bot.admins.punish_validate._bot", return_value=Bot("USER_ID_INVALID")), no_chats:
        assert await describe_telegram_user(8827084733, source_chat_id=-100) is None
        assert await verify_telegram_user_exists(8827084733, probe_chat_ids=()) is False

    with patch(
        "bot.admins.punish_validate._ask_userbot",
        AsyncMock(return_value=("missing", None)),
    ), patch("bot.admins.punish_validate._bot", return_value=Bot("Bad Request: chat not found")), patch(
        "bot.admins.punish_validate.probe_chat_ids", return_value=(),
    ):
        assert await describe_telegram_user(8827084733, source_chat_id=-100) is None
        assert await verify_telegram_user_exists(8827084733, probe_chat_ids=()) is False

    async def member(_cid, _uid):
        return Member(), None

    with patch("bot.admins.punish_validate._bot", return_value=Bot("Bad Request: chat not found")), patch(
        "bot.admins.punish_validate.probe_chat_ids", return_value=(-100,),
    ), patch("bot.admins.punish_validate.inspect_chat_member", member):
        named = await describe_telegram_user(8827084733, source_chat_id=-100)
    assert named["first_name"] == "Ира"
    assert named["username"] == "ira_k"
