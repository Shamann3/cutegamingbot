# -*- coding: utf-8 -*-
"""+ в технических кошельках — без живой Telegram и без БД."""

import pathlib
import sys

from bot.config.config import (
    BACKGROUND_EARNINGS_CHAT_ID,
    GAME_COMMISSION_CHAT_ID,
    PROFIT_JAR_CHAT_ID,
    TECH_CHAT_ID,
    test_id,
)
from bot.funcs.tech_plus import (
    BLACK_MARKET_CHAT_ID,
    PLUS_CHAT_IDS,
    format_tech_plus,
    should_announce_plus,
)


_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_plus_skips_black_market_and_test_group():
    assert BLACK_MARKET_CHAT_ID == TECH_CHAT_ID
    assert not should_announce_plus(TECH_CHAT_ID)
    assert not should_announce_plus(test_id)
    assert not should_announce_plus(None)
    assert not should_announce_plus("не число")


def test_plus_covers_the_three_money_wallets():
    assert PLUS_CHAT_IDS == {
        GAME_COMMISSION_CHAT_ID,
        BACKGROUND_EARNINGS_CHAT_ID,
        PROFIT_JAR_CHAT_ID,
    }
    for chat_id in PLUS_CHAT_IDS:
        assert should_announce_plus(chat_id)
        assert should_announce_plus(str(chat_id))


def test_plus_message_is_short_and_matches_black_market_numbers():
    assert format_tech_plus(1234) == "<blockquote><b>+ 1.234</b></blockquote>"
    assert format_tech_plus(0) == "<blockquote><b>+ 0</b></blockquote>"
    assert "\n" not in format_tech_plus(50)


def test_bot_and_server_formats_match():
    sys.path.insert(0, str(_ROOT / "server"))
    from tech_plus import format_tech_plus as server_fmt
    from tech_plus import should_announce_plus as server_should

    assert server_fmt(1234) == format_tech_plus(1234)
    assert server_should(TECH_CHAT_ID) is False
    assert server_should(BACKGROUND_EARNINGS_CHAT_ID) is True


def test_credits_are_wired():
    shop = _read("bot", "funcs", "shop.py")
    assert shop.count("_announce_shop_plus(") == 4
    fund = _read("bot", "funcs", "growth_fund.py")
    assert "announce_tech_plus" in fund
    engine = _read("bot", "runtime", "nika", "engine.py")
    assert "announce_tech_plus" in engine
    market = _read("server", "db.py")
    assert "schedule_tech_plus" in market
    assert "BACKGROUND_EARNINGS_CHAT_ID, commission" in market
