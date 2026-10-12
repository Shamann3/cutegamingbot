# -*- coding: utf-8 -*-
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.admins.card_target import offender_from_card, reply_target_user


def _entity(kind, offset, length, **extra):
    return SimpleNamespace(type=kind, offset=offset, length=length, **extra)


def _utf16(text, index):
    return len(text[:index].encode("utf-16-le")) // 2


def test_punishment_card_uses_the_offender_not_the_staff_member():
    text = (
        "🧘 Нарушитель: Лена · 8858841901\n"
        "👮 Модератор: Пётр · 6801702632"
    )
    assert offender_from_card(text) == 8858841901


def test_profile_card_uses_the_single_marked_id():
    text = "🎩 Лена\n👤 @lena\n🆔 8858841901\nБаланс 12.500 кут"
    assert offender_from_card(text) == 8858841901


def test_code_entity_after_an_emoji_is_still_the_person():
    text = "🧘 Лена · 8858841901"
    start = text.rindex("8858841901")
    entity = _entity("code", _utf16(text, start), _utf16("8858841901", len("8858841901")))
    assert offender_from_card(text, [entity]) == 8858841901


def test_text_link_on_the_offender_line_wins():
    text = "Нарушитель: Лена\nМодератор: Пётр"
    link = _entity("text_link", 0, 4, url="tg://user?id=8858841901")
    other = _entity("text_link", _utf16(text, text.index("Пётр")), 4, url="tg://user?id=6801702632")
    assert offender_from_card(text, [link, other]) == 8858841901


def test_statistics_and_lists_do_not_pick_anyone():
    top = "Топ чата\n1. Анна 111111111\n2. Боря 222222222\n3. Вера 333333333"
    assert offender_from_card(top) is None
    joined = "Зашли сейчас\nАнна — 111111111\nБоря — 222222222"
    assert offender_from_card(joined) is None
    missing = "Не нашёл пользователя с ID 8858841901"
    assert offender_from_card(missing) is None


def test_reply_to_a_person_stays_that_person_and_a_bot_card_does_not_pick_the_bot():
    human = SimpleNamespace(id=7, is_bot=False, first_name="Анна")
    assert reply_target_user(SimpleNamespace(from_user=human, text="привет", entities=())) is human

    bot = SimpleNamespace(id=1, is_bot=True, first_name="Кут")
    card = SimpleNamespace(
        from_user=bot,
        text="🆔 8858841901",
        entities=(),
        caption=None,
    )
    person = reply_target_user(card)
    assert person.id == 8858841901
    assert person.is_bot is False

    stats = SimpleNamespace(
        from_user=bot,
        text="Статистика чата\n1. 111111111\n2. 222222222\n3. 333333333",
        entities=(),
        caption=None,
    )
    assert reply_target_user(stats) is None


def test_punish_command_uses_the_person_from_the_bot_card():
    asyncio.run(_punish_command_uses_the_person_from_the_bot_card())


async def _punish_command_uses_the_person_from_the_bot_card():
    from bot.admins.mute import read_punish_clause

    bot = SimpleNamespace(id=1, is_bot=True, first_name="Кут")
    card = SimpleNamespace(
        from_user=bot,
        text="Нарушитель: Лена · 8858841901\nМодератор: Пётр · 6801702632",
        entities=(),
        caption=None,
    )
    person = reply_target_user(card)
    with patch(
        "bot.admins.punish_validate.ensure_punishment_profile",
        AsyncMock(return_value=(8858841901, "Лена", None)),
    ):
        clause = await read_punish_clause(["навсегда", "спам"], reply_user=person)
    assert clause.error is None
    assert clause.target_id == 8858841901
    assert clause.duration_text == "навсегда"
    assert clause.reason == "спам"

    named = SimpleNamespace(id=42, is_bot=False, first_name="Свой", full_name="Свой", username="own", last_name=None)
    assert reply_target_user(SimpleNamespace(from_user=named, text="🆔 8858841901", entities=())) is named


def test_reply_to_a_join_picks_the_person_who_entered():
    inviter = SimpleNamespace(id=1, is_bot=False, first_name="Админ")
    joiner = SimpleNamespace(id=8858841901, is_bot=False, first_name="Новый", last_name="", username="newone")
    message = SimpleNamespace(from_user=inviter, new_chat_members=[joiner], text="", entities=())
    person = reply_target_user(message)
    assert person.id == 8858841901
    assert person.username == "newone"


def test_several_people_entering_together_are_not_the_inviter():
    inviter = SimpleNamespace(id=1, is_bot=False, first_name="Админ")
    first = SimpleNamespace(id=8858841901, is_bot=False, first_name="А", last_name="", username="aone")
    second = SimpleNamespace(id=8858841902, is_bot=False, first_name="Б", last_name="", username="btwo")
    message = SimpleNamespace(from_user=inviter, new_chat_members=[first, second], text="")
    assert reply_target_user(message) is None
