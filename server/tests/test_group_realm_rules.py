from group_realm import (
    ALL_RIGHTS,
    action_right,
    cabinet_pages,
    editable_rights,
    may_edit_position,
    may_punish_rank,
    rights_allow,
)
from staff_panel_rights import column_granted, purge_allowed

def test_local_actions_map_to_one_right():
    assert action_right("ban") == "punish_ban"
    assert action_right("mute") == "punish_mute"
    assert action_right("voice") == "punish_voice"
    assert action_right("unvoice") == "punish_voice"
    assert action_right("banfull") is None


def test_lower_role_cannot_ban():
    assert rights_allow(["punish_warn", "view_members"], "warn")
    assert not rights_allow(["punish_warn", "view_members"], "ban")
    assert not rights_allow(["punish_mute"], "banfull")
    assert rights_allow(["punish_voice"], "voice")
    assert not rights_allow(["punish_mute"], "voice")


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


def test_cabinet_pages_follow_the_two_lists():
    assert cabinet_pages(["view_archive"]) == ["overview", "archive", "more"]
    people = cabinet_pages(["punish_mute"])
    assert "activity" in people
    assert "archive" not in people
    assert "rights" not in people
    assert "analytics" not in people
    assert "activity" in cabinet_pages(["view_analytics"])
    full = ["overview", "activity", "archive", "rights", "more"]
    assert cabinet_pages([], creator=True) == full
    assert cabinet_pages(ALL_RIGHTS) == full


def test_activity_windows_cover_day_month_and_year():
    from datetime import date

    from group_realm import activity_buckets, activity_window, previous_window

    today = date(2026, 9, 27)
    assert activity_window("day", today) == (today, today, "day")
    start, end, grain = activity_window("month", today)
    assert start == date(2026, 9, 1) and end == today and grain == "day"
    assert len(activity_buckets(start, end, grain)) == 27
    year_start, year_end, year_grain = activity_window("year", today)
    assert year_start == date(2026, 1, 1) and year_grain == "month"
    assert len(activity_buckets(year_start, year_end, year_grain)) == 9
    assert previous_window("day", today, today) == (date(2026, 9, 26), date(2026, 9, 26))


def test_junior_cannot_open_rights_page_by_asking():
    saved = editable_rights(2, ["manage_positions", "view_archive", "punish_ban"], creator=False)
    pages = cabinet_pages(saved)
    assert "archive" in pages
    assert "activity" in pages
    assert "rights" not in pages
    assert "manage_positions" not in saved


def test_only_creator_can_purge_and_not_himself():
    assert purge_allowed(actor_is_creator=True, target_is_creator=False) is None
    assert purge_allowed(actor_is_creator=False, target_is_creator=False)
    assert purge_allowed(actor_is_creator=True, target_is_creator=True)
