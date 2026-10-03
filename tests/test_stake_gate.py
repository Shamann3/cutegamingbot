"""Ставка пускается только если настоящий баланс её покрывает."""
import asyncio
from pathlib import Path

from bot.funcs.stake_gate import paid_stake_ok, read_stake_balance, stake_covers


def test_zero_balance_does_not_cover_a_stake():
    assert stake_covers(0, 2) is False
    assert stake_covers(1, 2) is False
    assert stake_covers(2, 2) is True
    assert stake_covers(5, 2) is True


def test_zero_or_broken_stake_is_not_a_paid_cover():
    assert stake_covers(5, 0) is False
    assert stake_covers(5, -1) is False
    assert stake_covers("нет", 2) is False
    assert stake_covers(None, 2) is False
    assert stake_covers(2, None) is False
    assert stake_covers("2", "2") is True


def test_free_entry_does_not_ask_the_wallet():
    assert asyncio.run(paid_stake_ok(1, 0)) is True
    assert asyncio.run(paid_stake_ok(1, "нет")) is False


def test_unreadable_user_closes_the_gate():
    assert asyncio.run(read_stake_balance("нет")) == 0
    assert asyncio.run(read_stake_balance(None)) == 0


def test_demo_cannot_skip_the_real_wallet_on_paid_dice():
    root = Path(__file__).resolve().parents[1]
    games = (
        root / "bot" / "tggames" / "bowling.py",
        root / "bot" / "tggames" / "soccer.py",
        root / "bot" / "tggames" / "darts.py",
        root / "bot" / "tggames" / "basket.py",
        root / "bot" / "tggames" / "slots.py",
        root / "bot" / "tggames" / "kube.py",
    )
    skipped = "not using_demo and not using_0demo and bet_int > balance"
    for path in games:
        text = path.read_text(encoding="utf-8")
        assert skipped not in text, path.name
        assert "read_stake_balance" in text, path.name
