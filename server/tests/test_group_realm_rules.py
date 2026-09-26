from group_realm import action_right, may_punish_rank, rights_allow
from staff_panel_rights import column_granted

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
