"""Куда можно прислать фото-доказательство и какая подпись ещё считается доказательством."""
from bot.admins.punish_proof import proof_caption_ok, proof_place_ok


def test_proof_stays_in_the_official_group_where_the_command_was_typed():
    origin = -1001612636292
    assert proof_place_ok(origin, origin, True)
    assert not proof_place_ok(origin, -1001921925861, True)
    assert not proof_place_ok(origin, origin, False)
    assert not proof_place_ok(12345, 12345, True)
    assert not proof_place_ok("нет", origin, True)
    assert not proof_place_ok(None, None, True)


def test_a_caption_is_still_proof_until_it_is_a_new_command():
    assert proof_caption_ok("", command=False)
    assert proof_caption_ok("   ", command=False)
    assert proof_caption_ok("скрин нарушения", command=False)
    assert not proof_caption_ok("банфулл 123 спам", command=True)
    assert not proof_caption_ok("мут 10с", command=True)
