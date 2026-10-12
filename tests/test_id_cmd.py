from bot.funcs.id_cmd import numeric_target, parse_id_command, username_of


def test_dot_id_is_the_command_and_a_word_is_not():
    assert parse_id_command(".id") == ""
    assert parse_id_command(".id   ") == ""
    assert parse_id_command(".id @XBlerka") == "@XBlerka"
    assert parse_id_command(".idea") is None
    assert parse_id_command("id") is None


def test_a_number_is_an_id_and_a_name_is_not():
    assert numeric_target("8827084733") == 8827084733
    assert numeric_target("-1001921925861") == -1001921925861
    assert numeric_target("@durov") is None
    assert numeric_target("Иван") is None


def test_username_comes_from_a_mention_or_a_public_link():
    assert username_of("@durov") == "durov"
    assert username_of("https://t.me/durov") == "durov"
    assert username_of("t.me/durov/123") == "durov"
    assert username_of("https://t.me/c/123/4") == ""
    assert username_of("Иван") == ""
