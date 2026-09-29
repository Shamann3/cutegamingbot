"""Одинаковый вызов игр: регистр, пробелы, слитая ставка, чужие слова."""
from bot.games.invoke import (
    command_filter,
    looks_like_game_command,
    open_command,
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
    assert command_filter(("футбол", "фут"))(_Msg("Футбол10"))
    assert not command_filter(("футбол", "фут"))(_Msg("футболка"))
