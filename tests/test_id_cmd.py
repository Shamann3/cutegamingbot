from bot.funcs.id_cmd import parse_id_command, username_of


def test_dot_id_is_the_command_and_a_word_is_not():
    assert parse_id_command(".id") == ""
    assert parse_id_command(".id   ") == ""
    assert parse_id_command(".id @XBlerka") == "@XBlerka"
    assert parse_id_command(".idea") is None
    assert parse_id_command("id") is None


def test_username_comes_from_a_mention_or_a_public_link():
    assert username_of("@durov") == "durov"
    assert username_of("https://t.me/durov") == "durov"
    assert username_of("t.me/durov/123") == "durov"
    assert username_of("https://t.me/c/123/4") == ""
    assert username_of("Иван") == ""
