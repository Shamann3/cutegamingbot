import inspect


def test_a_senior_can_hold_a_junior_seat():
    from group_realm import should_pause_seat

    assert should_pause_seat(actor_rank=4, target_rank=1, actor_is_staff=False) is True
    assert should_pause_seat(actor_rank=None, target_rank=0, actor_is_staff=True) is True
    assert should_pause_seat(actor_rank=2, target_rank=2, actor_is_staff=True) is False
    assert should_pause_seat(actor_rank=1, target_rank=3, actor_is_staff=False) is False
    assert should_pause_seat(actor_rank=5, target_rank=5, actor_is_staff=True) is False
    assert should_pause_seat(actor_rank=4, target_rank=None, actor_is_staff=True) is False


def test_warnings_keep_the_seat_and_a_long_ban_does_not():
    from group_realm import HOLD_FOREVER_SECONDS, seat_hold_plan, seat_reissue_block

    for action in ("warn", "warnall", "warnfull", "kick", "kickall", "voice"):
        assert seat_hold_plan(action, 3600) == "keep"
        assert seat_hold_plan(action, None) == "keep"
        assert seat_hold_plan(action, HOLD_FOREVER_SECONDS) == "keep"
    assert seat_hold_plan("mute", 3600) == "pause"
    assert seat_hold_plan("muteall", HOLD_FOREVER_SECONDS) == "pause"
    assert seat_hold_plan("mute", None) == "pause"
    assert seat_hold_plan("ban", HOLD_FOREVER_SECONDS - 1) == "pause"
    assert seat_hold_plan("ban", HOLD_FOREVER_SECONDS) == "strip"
    assert seat_hold_plan("banall", 7 * 24 * 3600) == "pause"
    assert seat_hold_plan("banall", HOLD_FOREVER_SECONDS) == "strip"
    assert seat_hold_plan("ban", None) == "strip"
    assert seat_hold_plan("ban", 0) == "strip"
    assert seat_hold_plan("banfull", 60) == "strip"
    note = "Должность снята навсегда. Вернуть её может только создатель."
    assert seat_reissue_block(is_creator=False, chat_locked=True, project_locked=False) == note
    assert seat_reissue_block(is_creator=False, chat_locked=False, project_locked=True) == note
    assert seat_reissue_block(is_creator=True, chat_locked=True, project_locked=True) is None
    assert seat_reissue_block(is_creator=False, chat_locked=False, project_locked=False) is None


def test_a_permanent_hold_is_not_returned_when_the_term_ends():
    from group_realm import release_finished_holds, restore_paused_seat

    assert "permanent" in inspect.getsource(restore_paused_seat)
    assert "permanent = FALSE" in inspect.getsource(release_finished_holds)


def test_hold_actions_are_only_lift_and_restore():
    from group_realm import hold_action

    assert hold_action("unmute") == "unmute"
    assert hold_action(" unban ") == "unban"
    assert hold_action("restore") == "restore"
    assert hold_action("ban") is None
    assert hold_action("mute") is None


def test_appoint_can_cover_every_official_group():
    from group_realm import AppointBody

    one = AppointBody(chat_id=1, user_id=2, position_id=3)
    every = AppointBody(chat_id=1, user_id=2, position_id=3, everywhere=True)
    assert one.everywhere is False
    assert every.everywhere is True
