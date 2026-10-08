"""Одни правила наказания для бота, кабинета группы и панели сотрудника."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import punish_rights
from group_realm import ACTION_RIGHT, rights_allow, rights_for_kind


COLUMNS = (
    "mute", "muteall", "unmute", "kick", "kickall",
    "warn", "warnall", "warnfull", "ban", "banall", "banfull",
)


def test_chat_rights_match_the_group_cabinet():
    for action, right in ACTION_RIGHT.items():
        assert punish_rights.seat_need(action) == right
        assert punish_rights.seat_allows(["punish_warn"], action) is rights_allow(["punish_warn"], action)


def test_rank_five_holds_chat_punishments_but_not_wide_switches():
    rights = punish_rights.seat_rights(["punish_mute"], 5)
    assert punish_rights.seat_allows(rights, "ban")
    assert punish_rights.seat_allows(rights, "kick")
    assert not punish_rights.seat_allows(rights, "banfull")
    marked = punish_rights.seat_rights(["banfull", "punish_mute"], 4)
    assert punish_rights.seat_allows(marked, "mute")
    assert punish_rights.seat_allows(marked, "banfull")
    assert not punish_rights.seat_allows(marked, "ban")
    cabinet = set(rights_for_kind("post", 4, ["punish_mute", "banfull"], creator=False))
    assert "punish_mute" in cabinet and "banfull" in cabinet and "punish_ban" not in cabinet


def test_staff_with_the_same_right_outranks_the_group_admin():
    member = punish_rights.covers_target(
        staff_grant=True, seat_allows=False,
        actor_rank=-1, target_rank=-1,
        same_person=False, target_staff=False,
    )
    admin = punish_rights.covers_target(
        staff_grant=True, seat_allows=False,
        actor_rank=-1, target_rank=4,
        same_person=False, target_staff=False,
    )
    assert member is None
    assert admin is None
    seat_only = punish_rights.covers_target(
        staff_grant=False, seat_allows=True,
        actor_rank=4, target_rank=4,
        same_person=False, target_staff=False,
    )
    assert seat_only == punish_rights.RANK_BLOCK
    staff_is_protected = punish_rights.covers_target(
        staff_grant=False, seat_allows=True,
        actor_rank=4, target_rank=-1,
        same_person=False, target_staff=True,
    )
    assert staff_is_protected == punish_rights.STAFF_TARGET_BLOCK


def test_lower_or_equal_rank_and_self_are_refused():
    assert punish_rights.may_punish_rank(4, 3, same_person=False) is None
    assert punish_rights.may_punish_rank(4, 4, same_person=False)
    assert punish_rights.may_punish_rank(4, -1, same_person=True) == punish_rights.SELF_BLOCK
    blocked = punish_rights.seat_target_block(
        actor_rank=4, target_rank=2, same_person=False, target_staff=True,
    )
    assert blocked == punish_rights.STAFF_TARGET_BLOCK
    wide = punish_rights.seat_target_block(
        actor_rank=3, target_rank=3, same_person=False, target_staff=False, wide=True,
    )
    assert wide == punish_rights.RANK_BLOCK_WIDE
    lifted = punish_rights.seat_target_block(
        actor_rank=4, target_rank=4, same_person=True, target_staff=False, lift=True,
    )
    assert lifted == punish_rights.SELF_LIFT_BLOCK


def test_staff_column_follows_the_bot_chain_and_stops_on_a_real_column():
    assert punish_rights.staff_column("banall", COLUMNS) == "banall"
    assert punish_rights.staff_column("unban", COLUMNS) == "ban"
    assert punish_rights.staff_column("kickall", ("mute", "kick")) == "kick"
    assert punish_rights.staff_column("banfull", ("mute",)) == "mute"
    perms = {"mute": True, "ban": False, "banall": False, "banfull": False}
    assert punish_rights.staff_allows(perms, "mute", COLUMNS)
    assert not punish_rights.staff_allows(perms, "ban", COLUMNS)
    assert not punish_rights.staff_allows(perms, "banfull", COLUMNS)
    shown = {item["id"] for item in punish_rights.staff_panel_actions(perms, COLUMNS)}
    assert shown == {"mute"}
    # Столбца unmute нет — бот смотрит на mute, и панель показывает снятие.
    assert punish_rights.staff_allows({"mute": True}, "unmute", ("mute", "ban"))
    creator = {item["id"] for item in punish_rights.staff_panel_actions({}, COLUMNS, creator=True)}
    assert creator == {item["id"] for item in punish_rights.STAFF_PANEL_ACTIONS}


def test_chat_unban_does_not_lift_a_wider_ban_without_the_switch():
    assert punish_rights.wide_ban_switch({"timed_full": True}) == "banfull"
    assert punish_rights.wide_ban_switch({"timed_wide": True}) == "banall"
    assert punish_rights.wide_ban_switch({"all_at": 2, "lifted_at": 5}) is None
    assert punish_rights.wide_ban_switch({"full_at": 8, "lifted_at": 3}) == "banfull"
    assert punish_rights.switch_covers(["banfull"], "banall")
    assert not punish_rights.switch_covers(["banall"], "banfull")
    assert punish_rights.switch_covers(["punish_ban"], None)
    assert punish_rights.wide_mute_on({"rows_all": True})
    assert punish_rights.wide_mute_on({"mute_until": datetime.now() + timedelta(hours=1)})
    assert not punish_rights.wide_mute_on({"mute_until": datetime.now() - timedelta(hours=1)})


def test_kick_and_warn_ask_the_seat_not_only_the_staff_account():
    root = Path(__file__).resolve().parents[2]
    for name in ("kick.py", "warn.py", "ban.py"):
        text = (root / "bot" / "admins" / name).read_text(encoding="utf-8")
        assert "check_punish_permission(" in text
        assert "check_staff_permission(" not in text
        assert "guard_seat_target(" in text
    kick = (root / "bot" / "admins" / "kick.py").read_text(encoding="utf-8")
    assert '_kick_permission_action' in kick
    assert 'return "kickall"' in kick


def test_each_punishment_keeps_its_own_column():
    assert punish_rights.punish_action("ban", "full") == "banfull"
    assert punish_rights.punish_action("ban", "all") == "banall"
    assert punish_rights.punish_action("ban", "chat") == "ban"
    assert punish_rights.punish_action("warn", "full") == "warnfull"
    assert punish_rights.punish_action("warn", "all") == "warnall"
    assert punish_rights.punish_action("mute", "all") == "muteall"
    assert punish_rights.punish_action("kick", "all") == "kickall"
    assert punish_rights.punish_action("mute", "later") == "mute"
    perms = {"mute": True, "ban": True, "banall": True, "banfull": False}
    assert not punish_rights.staff_allows(
        perms, punish_rights.punish_action("ban", "full"), COLUMNS,
    )
    assert punish_rights.staff_allows(
        perms, punish_rights.punish_action("ban", "all"), COLUMNS,
    )


def test_project_staff_reaches_another_official_group_without_a_local_seat():
    assert punish_rights.outside_seat_block(staff_grant=True, official=True) is None
    assert (
        punish_rights.outside_seat_block(staff_grant=True, official=False)
        == "Эта группа не отмечена официальной"
    )
    assert (
        punish_rights.outside_seat_block(staff_grant=False, official=True)
        == "В этой группе у вас нет должности"
    )


def test_photo_step_rechecks_the_right_and_the_live_group_list():
    root = Path(__file__).resolve().parents[2]
    for name in ("mute.py", "kick.py", "ban.py", "warn.py"):
        text = (root / "bot" / "admins" / name).read_text(encoding="utf-8")
        assert "refuse_stale_grant(" in text
        assert "official_chats_now(" in text
        assert "proof_in_origin(" in text
        assert "warm_official_chats(" in text


def test_protected_creators_are_the_same_pair_the_bot_refuses():
    assert punish_rights.PROTECTED_CREATOR_IDS == frozenset({6488580935, 6801702632})
    assert not punish_rights.is_staff_account("applicant", "active")
    assert not punish_rights.is_staff_account("moderator", "suspended")
    assert punish_rights.is_staff_account("moderator", "active")
    assert punish_rights.is_lift("unban")
    assert punish_rights.is_wide("banfull")
    assert not punish_rights.is_wide("ban")
