# -*- coding: utf-8 -*-
from bot.config.config import TECHNICAL_CHAT_IDS as CONFIG_TECHNICAL_CHAT_IDS
from bot.funcs.technical_chats import (
    TECHNICAL_CHAT_IDS,
    filter_public_chats,
    is_public_chat,
    is_technical_chat,
    is_technical_row,
)

PROFIT_JAR = -1004238101266
BACKGROUND_EARNINGS = -1004318525471
BLACK_MARKET = -1003855337972
GAME_COMMISSIONS = -1004324787050
TEST_GROUP = -1002135149822
PUBLIC_GROUP = -1001921925861


class FakeRecord:
    """asyncpg.Record ведёт себя так: keys() + доступ по ключу, без .get()."""

    def __init__(self, **fields):
        self._fields = dict(fields)

    def keys(self):
        return self._fields.keys()

    def __getitem__(self, key):
        return self._fields[key]


def test_all_technical_groups_are_listed():
    assert TECHNICAL_CHAT_IDS == {
        PROFIT_JAR,
        BACKGROUND_EARNINGS,
        BLACK_MARKET,
        GAME_COMMISSIONS,
        TEST_GROUP,
    }
    assert len(CONFIG_TECHNICAL_CHAT_IDS) == len(TECHNICAL_CHAT_IDS)


def test_is_technical_chat_by_id():
    for chat_id in TECHNICAL_CHAT_IDS:
        assert is_technical_chat(chat_id)
        assert is_technical_chat(str(chat_id))
    assert not is_technical_chat(PUBLIC_GROUP)
    assert not is_technical_chat(None)
    assert not is_technical_chat("")
    assert not is_technical_chat("не число")


def test_db_flag_hides_group_even_if_id_is_unknown():
    row = {"chat_id": PUBLIC_GROUP, "is_technical": True}
    assert is_technical_row(row)
    assert not is_public_chat(row)


def test_config_list_hides_group_when_column_not_seeded_yet():
    # Колонка есть, но строку ещё не разметили: спасает список из конфига.
    assert not is_public_chat({"chat_id": BLACK_MARKET, "is_technical": False})
    # Колонки в выборке нет вовсе (старая схема).
    assert not is_public_chat({"chat_id": BLACK_MARKET})


def test_public_group_stays_visible():
    assert is_public_chat({"chat_id": PUBLIC_GROUP, "is_technical": False})
    assert is_public_chat({"chat_id": PUBLIC_GROUP})


def test_works_with_record_like_rows():
    assert not is_public_chat(FakeRecord(chat_id=TEST_GROUP, chatbalance=100))
    assert is_public_chat(FakeRecord(chat_id=PUBLIC_GROUP, chatbalance=100))
    assert is_public_chat(FakeRecord(chatbalance=100))


def test_filter_public_chats_keeps_order_and_drops_technical():
    rows = [
        {"chat_id": PUBLIC_GROUP, "chatbalance": 10},
        {"chat_id": GAME_COMMISSIONS, "chatbalance": 999999},
        {"chat_id": -1009999999999, "chatbalance": 5},
        {"chat_id": TEST_GROUP, "chatbalance": 7},
    ]
    assert [r["chat_id"] for r in filter_public_chats(rows)] == [PUBLIC_GROUP, -1009999999999]
    assert filter_public_chats(None) == []
    assert filter_public_chats([]) == []


def test_gbl_achievement_title_hides_technical_group():
    from bot.funcs.achievements import build_gbl_title_html

    public = build_gbl_title_html(
        "Спонсор группы",
        chat_id=PUBLIC_GROUP,
        chat_title="Cute Chat",
        chat_url="https://t.me/CuteChat3",
    )
    assert "Cute Chat" in public
    assert "CuteChat3" in public

    hidden = build_gbl_title_html(
        "Спонсор группы",
        chat_id=BLACK_MARKET,
        chat_title="Чёрный рынок",
        chat_url="https://t.me/secret_market",
    )
    assert hidden == "Спонсор группы"
    assert "рынок" not in hidden
    assert "secret_market" not in hidden


def test_legacy_achievement_title_is_stripped_on_render():
    from bot.funcs.achievements import public_title_html

    legacy = {
        "title_html": 'Спонсор группы · <a href="https://t.me/secret_market">Чёрный рынок</a>',
        "meta": {"chat_id": BLACK_MARKET, "level": 3},
    }
    rendered = public_title_html(legacy)
    assert rendered == "Спонсор группы"
    assert "secret_market" not in rendered

    kept = {
        "title_html": 'Спонсор группы · <a href="https://t.me/CuteChat3">Cute Chat</a>',
        "meta": {"chat_id": PUBLIC_GROUP, "level": 3},
    }
    assert public_title_html(kept) == kept["title_html"]
