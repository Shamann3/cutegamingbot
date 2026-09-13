import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from tiktok_earn_logic import (  # noqa: E402
    kut_for_views,
    normalize_nick,
    parse_tiktok_url,
    payout_delta,
    validate_nick,
)


def test_nick_taken_message_is_defined():
    from bot.funcs import tiktok_earn as tt
    src = Path(tt.__file__).read_text(encoding="utf-8")
    assert "Этот ник уже занят другим игроком" in src
    assert "Можно не больше" in src
    assert "Эта пачка ещё на проверке" in src
    assert "Без него скриншоты принять нельзя" in src
    assert "require_nicks" in src


def test_bot_texts_match_plan():
    from bot.funcs.tiktok_earn import help_earnings_block, text_ask_nick, text_hub, text_need_nick
    assert "Тик ток" in text_hub()
    assert "cuteplayer" in text_ask_nick()
    assert "Задания" in help_earnings_block()
    assert "по которому тебя можно найти" in text_need_nick() or "можно найти" in text_need_nick()


def test_shared_url_and_payout():
    assert normalize_nick("@Foo") == "foo"
    assert validate_nick("foo_1") == "foo_1"
    parsed = parse_tiktok_url("www.tiktok.com/@x/video/111")
    assert parsed["canonical"] == "video:111"
    assert kut_for_views(1000) == 30
    assert payout_delta(0, 1000)["kut"] == 30
