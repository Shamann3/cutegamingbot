"""Приглашение срабатывает один раз и только для первого входа."""
import inspect


def test_a_new_person_can_be_invited_once():
    from bot.funcs.referral_gate import referral_verdict

    assert referral_verdict(
        user_id=2, referrer_id=1, referrer_exists=True, invitee=None,
    ) == "ok"


def test_the_same_link_does_not_count_twice():
    from bot.funcs.referral_gate import referral_verdict

    invitee = {"refferer_id": 1}
    assert referral_verdict(
        user_id=2, referrer_id=1, referrer_exists=True, invitee=invitee,
    ) == "same"


def test_another_link_does_not_replace_the_first():
    from bot.funcs.referral_gate import referral_verdict

    invitee = {"refferer_id": 7}
    assert referral_verdict(
        user_id=2, referrer_id=1, referrer_exists=True, invitee=invitee,
    ) == "taken"
    invitee = {"refcheck_ref_user_id": 7}
    assert referral_verdict(
        user_id=2, referrer_id=1, referrer_exists=True, invitee=invitee,
    ) == "taken"


def test_someone_who_already_opened_the_bot_cannot_be_invited():
    from bot.funcs.referral_gate import referral_verdict

    base = dict(user_id=2, referrer_id=1, referrer_exists=True)
    assert referral_verdict(invitee={"registered_at": "2026-01-01"}, **base) == "used"
    assert referral_verdict(invitee={"bot_first_start_at": "2026-01-01"}, **base) == "used"
    assert referral_verdict(invitee={"usersref": 1}, **base) == "used"
    assert referral_verdict(invitee={"wins": 3}, **base) == "used"
    assert referral_verdict(invitee={"loose": 1}, **base) == "used"
    assert referral_verdict(invitee={"refcheckgame": 1}, **base) == "used"


def test_you_cannot_invite_yourself_or_a_missing_person():
    from bot.funcs.referral_gate import referral_verdict

    assert referral_verdict(
        user_id=1, referrer_id=1, referrer_exists=True, invitee=None,
    ) == "self"
    assert referral_verdict(
        user_id=2, referrer_id=9, referrer_exists=False, invitee=None,
    ) == "no_inviter"
    assert referral_verdict(
        user_id=0, referrer_id=1, referrer_exists=True, invitee=None,
    ) == "bad"


def test_the_card_says_when_the_reward_arrives_and_that_a_repeat_does_not_count():
    from bot.funcs.referral_copy import (
        counted_guest_text,
        counted_inviter_text,
        referral_button_label,
        referral_card,
        referral_share_text,
        visitor_text,
    )

    card = referral_card("https://t.me/CuteGamingBot?start=1", 1)
    assert "первый раз" in card
    assert "одну игру" in card
    assert "1 кут" in card
    assert "25%" in card
    assert "Повторный вход" in card
    assert "уже открывал бота" in card
    assert "1 друг = 1 кут" not in card

    share = referral_share_text(1)
    assert "первый вход" in share
    assert "уже открывали бота" in share
    assert referral_button_label() == "Зайти по приглашению"

    ok = visitor_text("ok", 1)
    assert "одну игру" in ok
    assert "один раз" in ok
    assert "25%" in ok
    assert "Вы будете получать 25%" not in ok

    again = visitor_text("same", 1)
    assert "Второй раз" in again
    used = visitor_text("used", 1)
    assert "первом входе" in used
    assert "прошёл(-ла)" not in counted_inviter_text("Аня", 1)
    assert "Первая игра" in counted_inviter_text("Аня", 1)
    assert "Второй раз" in counted_guest_text(1)


def test_claim_writes_the_inviter_only_while_the_seat_is_empty():
    from bot.db_create.db import Database

    source = inspect.getsource(Database.claim_referral)
    assert "refferer_id IS NULL" in source
    assert "NOT EXISTS" in source
    assert "IS DISTINCT FROM" not in source
    assert "INSERT INTO users (user_id) VALUES" not in source

    guard = inspect.getsource(Database.update_user_wins)
    assert "COALESCE(usersref, 0)" in guard
    assert "приглашение уже было засчитано" in guard
