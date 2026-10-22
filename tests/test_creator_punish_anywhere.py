"""Создатель проекта наказывает в любой группе, где есть бот."""
from bot.admins.mute import (
    _actor_may_punish_here,
    _creator_punish_grant,
    _mute_record_chat_ids,
)
from bot.funcs.creator_join import PROJECT_CREATOR_ID

CREATOR = 6801702632
OTHER_CREATOR = 6488580935
GROUP = -1004242424242


def test_the_grant_is_this_person_and_only_punishments():
    assert PROJECT_CREATOR_ID == CREATOR
    for action in (
        "mute", "muteall", "unmute",
        "ban", "banall", "banfull",
        "kick", "kickall",
        "warn", "warnall", "warnfull",
        "cancel_mute", "cancel_ban", "cancel_kick", "cancel_warn", "cancel_pending",
        "unban", "unbanall", "unbanfull",
        "unwarn", "clearwarns",
    ):
        assert _creator_punish_grant(CREATOR, action), action
    assert not _creator_punish_grant(CREATOR, "roster")
    assert not _creator_punish_grant(CREATOR, "")
    assert not _creator_punish_grant(OTHER_CREATOR, "mute")
    assert not _creator_punish_grant(1, "banfull")


def test_any_group_counts_and_a_private_chat_does_not(monkeypatch):
    from bot.admins import mute

    monkeypatch.setattr(mute, "_is_staff_chat", lambda _cid: False)
    assert _actor_may_punish_here(GROUP, CREATOR)
    assert not _actor_may_punish_here(CREATOR, CREATOR)
    assert not _actor_may_punish_here(0, CREATOR)
    assert not _actor_may_punish_here(GROUP, OTHER_CREATOR)
    assert not _actor_may_punish_here(GROUP, None)
    assert not _actor_may_punish_here("нет", CREATOR)

    assert _mute_record_chat_ids("chat", GROUP, CREATOR) == [GROUP]
    assert _mute_record_chat_ids("chat", GROUP, 1) == []
    assert _mute_record_chat_ids("all", GROUP, CREATOR) == [0]


def test_an_official_group_stays_open_for_everyone_else(monkeypatch):
    from bot.admins import mute

    monkeypatch.setattr(mute, "_is_staff_chat", lambda cid: int(cid) == GROUP)
    assert _actor_may_punish_here(GROUP, 1)
    assert not _actor_may_punish_here(-1001, 1)
    assert _mute_record_chat_ids("chat", GROUP, 1) == [GROUP]
