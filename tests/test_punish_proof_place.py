"""Куда можно прислать фото-доказательство и какая подпись ещё считается доказательством."""
from bot.admins.mute import revoke_button_belongs_to
from bot.admins.punish_proof import proof_caption_ok, proof_place_ok


def test_proof_stays_in_the_official_group_where_the_command_was_typed():
    origin = -1001612636292
    assert proof_place_ok(origin, origin, True)
    assert not proof_place_ok(origin, -1001921925861, True)
    assert not proof_place_ok(origin, origin, False)
    assert not proof_place_ok(12345, 12345, True)
    assert not proof_place_ok("нет", origin, True)
    assert not proof_place_ok(None, None, True)


def test_revoke_button_belongs_only_to_the_issuer():
    card = "warn:revoke:111:8262368640:chat"
    assert revoke_button_belongs_to(card, 111)
    assert not revoke_button_belongs_to(card, 8408304179)
    assert revoke_button_belongs_to("mute:revoke:111:5", 111)
    assert revoke_button_belongs_to("ban:revoke:111:5:chat", 111)
    assert not revoke_button_belongs_to("warn:cancel:111:5", 111)
    assert not revoke_button_belongs_to("warn:revoke:nope:5", 111)


def test_warn_card_names_its_own_record():
    from bot.admins.warn import warn_revoke_record
    assert warn_revoke_record("warn:revoke:111:5:chat:77") == 77
    assert warn_revoke_record("warn:revoke:111:5:chat") is None
    assert warn_revoke_record("mute:revoke:111:5:chat:77") is None


def test_a_caption_is_still_proof_until_it_is_a_new_command():
    assert proof_caption_ok("", command=False)
    assert proof_caption_ok("   ", command=False)
    assert proof_caption_ok("скрин нарушения", command=False)
    assert not proof_caption_ok("банфулл 123 спам", command=True)
    assert not proof_caption_ok("мут 10с", command=True)
