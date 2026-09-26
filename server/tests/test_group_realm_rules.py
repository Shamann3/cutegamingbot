from group_realm import action_right, editable_rights, may_edit_position, may_punish_rank, rights_allow
from staff_panel_rights import column_granted, purge_allowed

def test_local_actions_map_to_one_right():
    assert action_right("ban") == "punish_ban"
    assert action_right("mute") == "punish_mute"
    assert action_right("banfull") is None


def test_lower_role_cannot_ban():
    assert rights_allow(["punish_warn", "view_members"], "warn")
    assert not rights_allow(["punish_warn", "view_members"], "ban")
    assert not rights_allow(["punish_mute"], "banfull")


def test_punish_only_junior_rank():
    assert may_punish_rank(3, 1, same_person=False) is None
    assert may_punish_rank(1, 0, same_person=False) is None
    assert may_punish_rank(3, 3, same_person=False)
    assert may_punish_rank(2, 5, same_person=False)
    assert may_punish_rank(5, 1, same_person=True)


def test_players_ban_needs_explicit_banfull():
    assert column_granted({"banfull": True, "mute": False}, "banfull")
    assert column_granted({"BanFull": 1}, "banfull")
    assert not column_granted({"ban": True, "mute": True}, "banfull")
    assert not column_granted({"banfull": False}, "banfull")
    assert not column_granted(None, "banfull")


def test_position_edit_stays_below_actor():
    assert may_edit_position(5, 5, creator=True)
    assert not may_edit_position(3, 3, creator=False)
    assert may_edit_position(3, 1, creator=False)
    assert editable_rights(5, ["punish_warn"], creator=False)[0] == "view_members"
    assert "manage_positions" not in editable_rights(2, ["manage_positions", "punish_warn"], creator=False)
    assert "manage_positions" in editable_rights(2, ["manage_positions", "punish_warn"], creator=True)


def test_only_creator_can_purge_and_not_himself():
    assert purge_allowed(actor_is_creator=True, target_is_creator=False) is None
    assert purge_allowed(actor_is_creator=False, target_is_creator=False)
    assert purge_allowed(actor_is_creator=True, target_is_creator=True)
