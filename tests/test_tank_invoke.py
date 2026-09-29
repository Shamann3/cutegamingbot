"""Одинаковый вызов игр: регистр, пробелы, слитая ставка, чужие слова."""
from bot.games.invoke import (
    command_filter,
    command_line,
    format_line,
    howto_reply,
    looks_like_game_command,
    open_command,
    orel_side,
    parse_embedded_stake,
    parse_optional_stake,
    parse_phrase_stake,
    parse_required_stake,
    stake_token,
)


class _Msg:
    def __init__(self, text):
        self.text = text


def test_stake_token_thousands_not_decimals():
    assert stake_token("10") == 10
    assert stake_token("1.000") == 1000
    assert stake_token("1,000") == 1000
    assert stake_token("10,5") is None
    assert stake_token("10.5") is None


def test_every_simple_game_accepts_case_spaces_and_glued_bet():
    samples = (
        (("башня", "башни", "башню"), "Башня 10", "башня10", "башня\u00a010"),
        (("шар", "шарик"), "Шарик 10", "шар10", "шар  10"),
        (("плита", "плиты"), "Плита 10", "плиты10", "ПЛИТА 10"),
        (("провода", "провод"), "Провода 10", "провод10", "провода\u00a010"),
        (("футбол", "фут"), "Футбол 10", "фут10", "ФУТБОЛ 10"),
        (("спин", "слоты", "слот", "барабан"), "Слоты 10", "слот10", "Барабан 10"),
        (("дарт", "дартс"), "Дартс 10", "дарт10", "ДАРТС 10"),
        (("баскет", "баскетбол", "баскетболл", "баскетбал"), "Баскет 10", "баскетбол10", "БАСКЕТ 10"),
        (("боулинг", "боул"), "Боулинг 10", "боул10", "БОУЛИНГ 10"),
    )
    for names, spaced, glued, extra in samples:
        for text in (spaced, glued, extra):
            kind, bet = parse_required_stake(text, names)
            assert kind == "play", text
            assert bet == 10, text


def test_optional_lobby_games_and_help_do_not_start():
    for names, alone, glued in (
        (("мины",), "Мины", "мины10"),
        (("кости",), "Кости", "кости10"),
        (("бинго",), "Бинго", "бинго10"),
        (("дуэль", "дуель", "дуэли"), "Дуэль", "дуэль10"),
        (("шашки", "шахи"), "Шахи", "шашки10"),
        (("мемори",), "Мемори", "мемори10"),
        (("кн",), "Кн", "кн10"),
        (("кнб",), "Кнб", "кнб10"),
        (("орел", "орёл", "решка"), "Орёл", "решка10"),
    ):
        kind, bet = parse_optional_stake(alone, names)
        assert kind == "play" and bet == 0, alone
        kind, bet = parse_optional_stake(glued, names)
        assert kind == "play" and bet == 10, glued
        kind, _bet = parse_optional_stake(alone + " хелп", names)
        assert kind == "help", alone


def test_phrases_and_reversed_order():
    kind, bet = parse_phrase_stake("Найди пару 10", ("найди пару", "найти пару"))
    assert kind == "play" and bet == 10
    kind, bet = parse_phrase_stake("найти пару", ("найди пару", "найти пару"))
    assert kind == "play" and bet == 0
    kind, bet = parse_phrase_stake("Нолики крестики 5", ("крестики нолики", "нолики крестики"))
    assert kind == "play" and bet == 5
    kind, bet = parse_phrase_stake("Орёл или решка 7", ("орёл или решка", "решка или орёл"))
    assert kind == "play" and bet == 7
    kind, bet = parse_phrase_stake("Камень ножницы бумага 15", ("камень ножницы бумага",))
    assert kind == "play" and bet == 15


def test_kube_trade_roulette_keep_their_arguments():
    kind, tokens = open_command("Куб10 4", ("куб", "кубик"))
    assert kind == "ready" and tokens == ["куб", "10", "4"]
    kind, tokens = open_command("Трейд10 вверх", ("трейд",))
    assert kind == "ready" and tokens == ["трейд", "10", "вверх"]
    kind, tokens = open_command("Рулетка10 красное", ("рул", "рулетка"))
    assert kind == "ready" and tokens == ["рулетка", "10", "красное"]
    kind, tokens = open_command("рул 10 чёрное", ("рул", "рулетка"))
    assert tokens[2] == "черное"


def test_menu_howto_replies_with_the_play_line():
    menu = {
        "как играть в Башни": "башня 10",
        "Как играть в Риск": "риск 10",
        "Как играть в Плиты": "плита 10",
        "Как играть в Бомбы": "бомбы 10",
        "Как играть в Трейд": "трейд вверх 10",
        "Как играть в Шарик": "шарик 10",
        "Как играть в Провода": "провода 10",
        "Как играть в слоты": "слоты 10",
        "Как играть в Баскет": "баскет 10",
        "Как играть в Футбол": "футбол 10",
        "Как играть в Боулинг": "боулинг 10",
        "Как играть в Дартс": "дартс 10",
        "Как играть в Куб": "куб 10 4",
    }
    for phrase, example in menu.items():
        assert howto_reply(phrase) == format_line(example), phrase
    roulette = howto_reply("Как играть в Рулетку")
    assert "рулетка 10 красное" in roulette
    assert "рулетка 10 7" in roulette
    assert howto_reply("Шашки 10") is None
    assert howto_reply("как играть в футболке") is None


def test_fortuna_lobby_accepts_the_menu_stake():
    kind, bet = parse_optional_stake("Фортуна", ("фортуна",))
    assert kind == "play" and bet == 0
    kind, bet = parse_optional_stake("Фортуна 10", ("фортуна",))
    assert kind == "play" and bet == 10
    kind, bet = parse_optional_stake("фортуна10", ("фортуна",))
    assert kind == "play" and bet == 10
    kind, bet = parse_optional_stake("Фортуна 1.000", ("фортуна",))
    assert kind == "play" and bet == 1000
    assert parse_optional_stake("Фортуна 10,5", ("фортуна",))[0] == "bad"


def test_bombs_and_coin_ignore_letter_case():
    for text in (
        "бомбы 10", "Бомбы 10", "БОМБЫ 10", "бомба 10", "Бомба10", "бомбы10",
        "\u200bбомбы 10", "  бомбы 10",
    ):
        assert parse_embedded_stake(text, ("бомба", "бомбы")) == ("play", 10), text
        assert command_line(text).startswith(("бомбы", "бомба")), text
    assert parse_embedded_stake("бомбы", ("бомба", "бомбы")) == ("bad", None)
    assert command_line("Бомбы") == command_line("бомбы") == "бомбы"
    assert orel_side("орел или решка") == "орел"
    assert orel_side("Орел или решка 10") == "орел"
    assert orel_side("решка или орел") == "решка"
    assert orel_side("Решка") == "решка"
    assert orel_side("решка10") == "решка"
    assert orel_side("орёл") == "орел"
    assert command_line("Орёл или решка").startswith("орел")


def test_foreign_words_are_not_games():
    assert parse_required_stake("футболка 10", ("футбол", "фут"))[0] == "ignore"
    assert parse_required_stake("шарф 10", ("шар", "шарик"))[0] == "ignore"
    assert parse_required_stake("рулон 10 красное", ("рул", "рулетка"))[0] == "ignore"
    assert parse_optional_stake("книга", ("кн",))[0] == "ignore"
    assert parse_embedded_stake("рискну 10", ("риск",))[0] == "ignore"
    assert parse_embedded_stake("риск 10,5", ("риск",))[0] == "bad"
    assert parse_embedded_stake("бомбы на 20", ("бомба", "бомбы")) == ("play", 20)
    assert not looks_like_game_command("Руслан")
    assert looks_like_game_command("Башня 10")
    assert looks_like_game_command("Фортуна 10")
    assert command_filter(("футбол", "фут"))(_Msg("Футбол10"))
    assert not command_filter(("футбол", "фут"))(_Msg("футболка"))
