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

def test_hold_keeps_seconds_and_lifts_a_telegram_short_span():
    from group_realm import telegram_hold_seconds

    assert telegram_hold_seconds(10) == 35
    assert telegram_hold_seconds(90) == 90
    assert telegram_hold_seconds(3600) == 3600
    assert telegram_hold_seconds(0) == 0
    assert telegram_hold_seconds(None) == 0


def test_wide_issue_follows_the_position_switch():
    from group_realm import position_wide, wide_actions_for

    only_full = [item["id"] for item in wide_actions_for(["banfull"])]
    assert only_full == ["banfull"]
    assert wide_actions_for(["punish_ban", "ban"]) == []
    assert [item["id"] for item in position_wide(["punish_ban", "punish_mute"])] == []
    assert [item["id"] for item in position_wide(["banfull", "muteall"])] == ["muteall", "banfull"]
    creator = [item["id"] for item in wide_actions_for([], creator=True)]
    assert creator[0] == "muteall"
    assert "banfull" in creator
    assert "unbanall" not in creator


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
    assert may_punish_rank(0, -1, same_person=False) is None
    assert may_punish_rank(0, 0, same_person=False)
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


def test_rank_zero_keeps_every_requested_right():
    from group_realm import (
        KIND_MEMBER,
        KIND_SPAMBLOCK,
        MEMBER_RIGHTS,
        _promote_body,
        assigned_rights,
        initial_rights,
        rights_for_kind,
        send_permissions,
        stored_rank,
        term_bounds,
    )

    kept = rights_for_kind(
        KIND_SPAMBLOCK,
        0,
        ["punish_ban", "can_restrict_members", "banfull"],
        creator=True,
    )
    assert kept == ["punish_ban", "can_restrict_members", "banfull"]
    assert stored_rank(KIND_SPAMBLOCK, 3) == 0
    assert stored_rank(KIND_MEMBER, 2) == 0
    fresh = initial_rights(KIND_MEMBER, 0, ["view_members"])
    assert fresh[:len(MEMBER_RIGHTS)] == list(MEMBER_RIGHTS)
    assert "view_members" in fresh
    assert "punish_ban" not in fresh
    rank0 = rights_for_kind(
        "post",
        0,
        ["punish_ban", "view_members", "can_delete_messages", "banfull"],
        creator=True,
    )
    assert rank0 == ["punish_ban", "view_members", "can_delete_messages", "banfull"]
    assert "banfull" not in rights_for_kind("post", 0, ["punish_ban"], creator=True)
    junior = assigned_rights(
        "post",
        0,
        ["punish_warn", "banfull", "muteall"],
        creator=False,
        stored=["banfull", "manage_positions"],
    )
    assert "banfull" in junior
    assert "manage_positions" in junior
    assert "muteall" not in junior
    assert "punish_warn" in junior
    opened = send_permissions(None)
    assert opened["can_send_messages"] is True
    assert send_permissions(["can_send_messages"])["can_send_photos"] is False
    start, end, err = term_bounds("2026-09-01", "2026-09-30")
    assert err is None and start < end
    _start, _end, missing = term_bounds("", "")
    assert missing
    _start, _end, backwards = term_bounds("2026-10-02", "2026-10-01")
    assert backwards
    present = _promote_body(-100, 5, [])
    assert present["can_manage_chat"] is True
    assert present["can_restrict_members"] is False
    assert present["can_delete_messages"] is False
    assert present["can_promote_members"] is False
    titled = _promote_body(-100, 5, ["can_delete_messages", "punish_mute"])
    assert titled["can_delete_messages"] is True
    assert titled["can_restrict_members"] is False
    gone = _promote_body(-100, 5, None)
    assert all(value is False for key, value in gone.items() if key.startswith("can_"))
    from group_realm import chat_title
    assert chat_title("post", "Модератор", "", "") == ("Модератор", None)
    assert chat_title("spamblock", "Спам блок", "", "") == ("спам блок", None)
    assert chat_title("member", "Обычный пользователь", "участник", "хелпер") == ("", None)
    assert chat_title("post", "Модератор", "мод", "") == ("мод", None)


def test_staff_post_key_stays_on_the_same_title():
    from staff_posts import role_key

    assert role_key("Ночной модератор") == role_key("  ночной   модератор ")
    assert role_key("Ночной модератор").startswith("custom_")
    assert role_key("А") != role_key("Б")


def test_cabinet_pages_follow_the_two_lists():
    assert cabinet_pages(["view_archive"]) == ["overview", "work", "archive", "more"]
    people = cabinet_pages(["punish_mute"])
    assert "activity" in people
    assert "archive" not in people
    assert "work" not in people
    assert "rights" not in people
    assert "analytics" not in people
    assert "activity" in cabinet_pages(["view_analytics"])
    full = ["overview", "work", "activity", "archive", "rights", "more"]
    assert cabinet_pages([], creator=True) == full
    assert cabinet_pages(ALL_RIGHTS) == full
    assert cabinet_pages(["view_archive"], pages=["pay"]) == ["overview", "pay", "more"]
    assert cabinet_pages(["view_archive"], pages=[]) == ["overview", "more"]
    assert "work" in cabinet_pages([], rank=5)
    assert cabinet_pages([], pages=["archive"], rank=5) == ["overview", "archive", "more"]
    assert cabinet_pages(["view_archive"], pages=["work"], rank=0) == ["overview", "work", "more"]


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


def test_person_counts_skip_zeros_and_keep_every_kind():
    from group_realm import fold_person_counts

    rows = fold_person_counts([
        ("banfull", 2),
        ("bot_ban", 1),
        ("unmute", 0),
        ("unban", 3),
        ("warnfull", 1),
        ("mute", 4),
        ("", 5),
    ])
    by_action = {row["action"]: row["count"] for row in rows}
    assert by_action["banfull"] == 3
    assert "unmute" not in by_action
    assert by_action["unban"] == 3
    assert by_action["warnfull"] == 1
    assert by_action["mute"] == 4
    assert [row["action"] for row in rows] == ["banfull", "unban", "mute", "warnfull"]
    assert rows[0]["hint"] == "весь проект"


def test_person_history_keeps_this_chat_and_wide_punishments():
    from group_realm import person_history_where

    sql = person_history_where()
    assert "s.target_player_id = $2" in sql
    assert "s.chat_id = $1" in sql
    assert "'all', 'full'" in sql
    assert "banfull" in sql
    assert "warnall" in sql


def test_only_creator_can_purge_and_not_himself():
    assert purge_allowed(actor_is_creator=True, target_is_creator=False) is None
    assert purge_allowed(actor_is_creator=False, target_is_creator=False)
    assert purge_allowed(actor_is_creator=True, target_is_creator=True)


def test_drag_puts_the_top_post_above_rank_one():
    from group_realm import ladder_places

    assert ladder_places([10]) == [(10, 4, 0)]
    assert ladder_places([10, 11, 12]) == [(10, 4, 0), (11, 3, 1), (12, 2, 2)]
    assert [rank for _pid, rank, _i in ladder_places([1, 2, 3, 4, 5])] == [4, 3, 2, 1, 1]
    assert ladder_places([3, 3, 0, "x"]) == [(3, 4, 0)]


def test_delete_position_unseats_before_drop_and_keeps_creator():
    import inspect

    from group_realm import delete_position

    source = inspect.getsource(delete_position)
    assert ">= 5" in source
    assert "Должность создателя группы удалить нельзя" in source
    seats = source.index("DELETE FROM epsilon_seats")
    applications = source.index("epsilon_group_applications")
    drop = source.index("DELETE FROM epsilon_positions")
    assert seats < applications < drop
    assert "_apply_chat_title" in source
    assert "rights=None" in source
