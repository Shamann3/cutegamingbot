import inspect


def test_senior_ban_pauses_a_junior_and_mute_does_not():
    from group_realm import should_pause_seat

    assert should_pause_seat(actor_rank=4, target_rank=1, actor_is_staff=False) is True
    assert should_pause_seat(actor_rank=None, target_rank=0, actor_is_staff=True) is True
    assert should_pause_seat(actor_rank=2, target_rank=2, actor_is_staff=True) is False
    assert should_pause_seat(actor_rank=1, target_rank=3, actor_is_staff=False) is False
    assert should_pause_seat(actor_rank=5, target_rank=5, actor_is_staff=True) is False
    assert should_pause_seat(actor_rank=4, target_rank=None, actor_is_staff=True) is False


def test_mute_keeps_the_seat_row():
    from group_realm import park_title_for_mute

    source = inspect.getsource(park_title_for_mute)
    assert "DELETE FROM epsilon_seats" not in source
    assert "title_parked" in source


def test_appoint_can_cover_every_official_group():
    from group_realm import AppointBody

    one = AppointBody(chat_id=1, user_id=2, position_id=3)
    every = AppointBody(chat_id=1, user_id=2, position_id=3, everywhere=True)
    assert one.everywhere is False
    assert every.everywhere is True
