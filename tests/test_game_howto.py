"""«Как играть в …» своими словами: какая игра, что ответить, без ложных срабатываний."""
import asyncio
import re
import sys
import types
from pathlib import Path

from bot.funcs import game_howto
from bot.games.howto import HowTo, read_howto
from bot.games.rules import RULE_KEYS, Table, rules_html
from bot.runtime.game_desk.catalog import GAMES

ROOT = Path(__file__).resolve().parents[1]


def _key(text):
    ask = read_howto(text)
    assert ask is not None and ask.kind == "game", text
    return ask.key


def test_every_game_answers_a_plain_question():
    asked = {
        "как играть в бомбы": "bombs",
        "как играть в шашки?": "scah",
        "Как играть в Шашки": "scah",
        "а как в шашки играть?": "scah",
        "как в шашки": "scah",
        "как играть в мемори": "memory",
        "как играть в найди пару": "memory",
        "как играть в бинго": "bingo",
        "как играть в фортуну": "fortuna_lobby",
        "как играть в колесо фортуны": "fortuna_lobby",
        "как играть в кости": "kosti",
        "как играть в дуэль": "duel",
        "как играть в дуэли": "duel",
        "как играть в орла и решку": "orel",
        "как играть в орел или решка": "orel",
        "как играть в кнб": "knb",
        "как играть в камень ножницы бумага": "knb",
        "как играть в мины": "mines",
        "как играть в крестики-нолики": "tic_tac_toe",
        "как играть в кн": "tic_tac_toe",
        "как играть в слова": "words",
        "как играть в башню": "tank",
        "как играть в риск": "risk",
        "как играть в плиты": "plate",
        "как играть в трейд": "trade",
        "как играть в шарик": "balls",
        "как играть в провода": "provoda",
        "как играть в слоты": "slots",
        "как играть в баскетбол": "basket",
        "как играть в футбол": "soccer",
        "как играть в боулинг": "bowling",
        "как играть в дартс": "darts",
        "как играть в кубик": "kube",
        "как играть в рулетку (игра)": "fortuna_solo",
    }
    for text, key in asked.items():
        assert _key(text) == key, text


def test_free_wording_finds_the_game():
    asked = {
        "Кут, подскажите пожалуйста как играть в бомбы?": "bombs",
        "не понимаю как играть в рулетку": "fortuna_solo",
        "я не знаю как играть в шашки": "scah",
        "не умею играть в шашки": "scah",
        "объясни бомбы": "bombs",
        "расскажите про риск": "risk",
        "что такое риск": "risk",
        "что за игра мины": "mines",
        "правила кнб": "knb",
        "правила игры в слова": "words",
        "какие правила в костях": "kosti",
        "как ходить в шашках": "scah",
        "как бить в шашках?": "scah",
        "как стать дамкой в шашках": "scah",
        "как сделать ставку в рулетке": "fortuna_solo",
        "как забрать выигрыш в башне": "tank",
        "как работает трейд": "trade",
        "что делать в бомбах": "bombs",
        "сколько можно поставить в рулетке": "fortuna_solo",
        "где можно поиграть в шашки": "scah",
        "что значит дамка в шашках": "scah",
        "можно ли рубить назад в шашках": "scah",
        "сколько мин в бомбах": "bombs",
        "сколько игроков в бинго": "bingo",
        "какая максимальная ставка в рулетке": "fortuna_solo",
        "как отменить игру в слова": "words",
        "как обыграть бота в шашки": "scah",
        "кто первый ходит в шашках": "scah",
        "как угадать слово": "words",
        "как бросить кости": "kosti",
        "бомбы как играть": "bombs",
        "кто знает как играть в мемори?": "memory",
        "хочу научиться играть в шашки": "scah",
        "КАК ИГРАТЬ В БОМБЫ!!!": "bombs",
        "как играть в орёл": "orel",
        "how to play bombs": "bombs",
        "как играть в бомбы 10": "bombs",
    }
    for text, key in asked.items():
        assert _key(text) == key, text


def test_ordinary_chat_is_not_a_rules_question():
    quiet = (
        "Шашки 10",
        "шашки",
        "бомбы 10",
        "рулетка 10 красное",
        "кут орел или решка",
        "кто сыграет в шашки?",
        "давай в бомбы",
        "как-нибудь сыграем в шашки",
        "я знаю как играть в шашки",
        "понял как играть в бомбы, спасибо",
        "как же круто играть в шашки",
        "как часто вы играете в шашки",
        "как давно ты играешь в бомбы",
        "как играть в футболке",
        "как играть в шахматы",
        "как играть без риска",
        "как играть на гитаре",
        "как играть в кубик рубика",
        "как бомбы?",
        "что-то бомбы сломались",
        "сколько ты выиграл в бомбах",
        "сколько раз ты играл в шашки",
        "какой ты молодец в шашках",
        "кто играет в шашки",
        "кто хочет в шашки",
        "кто хочет начать в шашки",
        "кто выиграл в шашки",
        "я играю в шашки каждый день",
        "хелп",
        "хелп игры",
        "кут игры",
        "правила",
        "правила чата",
        "как дела",
        "слова",
        "как играть в пулю",
        "",
    )
    for text in quiet:
        assert read_howto(text) is None, text


def test_help_command_is_direct_and_a_question_is_asked():
    assert read_howto("бомбы хелп") == HowTo("game", "bombs", False)
    assert read_howto("хелп шашки") == HowTo("game", "scah", False)
    assert read_howto("правила игры бомбы") == HowTo("game", "bombs", False)
    assert read_howto("как играть в бомбы") == HowTo("game", "bombs", True)


def test_two_games_get_two_answers_and_more_get_the_list():
    assert read_howto("как играть в кости или в кубик") == HowTo("game", "kosti", True, ("kube",))
    assert read_howto("хелп бомбы шашки") == HowTo("game", "bombs", False, ("scah",))
    assert read_howto("как играть в шашки? шашки это сложно") is None
    assert read_howto("как играть в бомбы, мины и башню") == HowTo("menu")
    assert read_howto("как играть в шашки, а в шашку как ходить") == HowTo("game", "scah", True)


def test_newcomer_without_a_game_gets_the_start_or_the_list():
    for text in (
        "как играть?", "🚀 Как играть?", "а как тут играть", "не понимаю как играть",
        "как пользоваться ботом", "где играть?",
    ):
        assert read_howto(text) == HowTo("start"), text
    for text in ("какие есть игры", "во что можно поиграть?", "что тут есть поиграть", "список игр"):
        assert read_howto(text) == HowTo("menu"), text
    assert read_howto("как пользоваться") is None
    assert read_howto("какие игры ты любишь") is None


def test_every_public_game_has_an_answer():
    for game in GAMES:
        if game["key"] == "bullet":
            continue
        assert game["key"] in game_howto.SOLO_HELP or game["key"] in RULE_KEYS, game["key"]


def test_solo_help_phrases_exist_in_balance():
    source = (ROOT / "bot" / "funcs" / "balance.py").read_text(encoding="utf-8")
    for phrase in game_howto.SOLO_HELP.values():
        assert f'"{phrase}"' in source, phrase


def test_games_menu_lines_open_their_help():
    source = (ROOT / "bot" / "funcs" / "help.py").read_text(encoding="utf-8")
    lines = re.findall(r"<code>((?:как|Как) играть в [^<]+)</code>", source)
    assert len(lines) >= 14
    for line in lines:
        ask = read_howto(line)
        assert ask is not None and ask.key in game_howto.SOLO_HELP, line


def _balanced(html):
    for tag in ("b", "code", "tg-emoji"):
        assert html.count(f"<{tag}") == html.count(f"</{tag}>"), tag


def test_rules_read_cleanly_for_every_game():
    for key in RULE_KEYS:
        html = rules_html(key, Table(max_bet=500_000, players=7, commission_from=10, bot="CuteGamingBot"))
        assert html and "None" not in html, key
        assert "Как начать" in html and "Суть игры" in html and "Выигрыш" in html and "Важно" in html, key
        _balanced(html)
    assert rules_html("bullet") is None
    assert rules_html("bombs") is None


def test_rules_follow_the_live_table():
    free = rules_html("scah", Table(max_bet=500_000, commission_from=10))
    assert "<code>шашки</code> - без ставки" in free
    assert "Максимальная ставка : <b>500.000</b>" in free
    assert "от <b>10</b> кут удерживается комиссия" in free
    assert "@CuteGamingBot шашки" in free

    paid = rules_html("scah", Table(min_bet=50, max_bet=1000))
    assert "без ставки" not in paid
    assert "Минимальная ставка : <b>50</b>" in paid
    assert "комиссия" not in paid

    assert "до <b>7</b> человек" in rules_html("bingo", Table(players=7))
    assert "@TestBot слова" in rules_html("words", Table(bot="TestBot"))
    assert rules_html("mines", Table(), state="🛠 Тех работы").startswith("🛠 Тех работы\n\n")


class _Chat:
    id = -100500


class _User:
    id = 42


class _Bot:
    async def me(self):
        return types.SimpleNamespace(username="CuteGamingBot")


class _Message:
    def __init__(self, text="как играть в шашки"):
        self.text = text
        self.chat = _Chat()
        self.from_user = _User()
        self.bot = _Bot()
        self.replies = []

    def model_copy(self, update):
        twin = _Message(update.get("text", self.text))
        twin.replies = self.replies
        return twin

    async def reply(self, text, **kwargs):
        self.replies.append(text)


def _fresh_memory(monkeypatch):
    monkeypatch.setattr(game_howto, "_asked_at", {})


def test_answer_sends_pvp_rules_once_per_question(monkeypatch):
    _fresh_memory(monkeypatch)

    async def table(key, bot):
        return Table(max_bet=500_000, bot="CuteGamingBot"), ""

    monkeypatch.setattr(game_howto, "_table", table)
    message = _Message()
    ask = HowTo("game", "scah", True)
    assert asyncio.run(game_howto.answer_howto(message, ask))
    assert asyncio.run(game_howto.answer_howto(message, ask))
    assert len(message.replies) == 1
    assert "Игра «Шашки»" in message.replies[0]

    direct = HowTo("game", "scah", False)
    asyncio.run(game_howto.answer_howto(message, direct))
    asyncio.run(game_howto.answer_howto(message, direct))
    assert len(message.replies) == 3


def test_answer_covers_both_games_of_one_question(monkeypatch):
    _fresh_memory(monkeypatch)
    seen = []

    async def balance(message):
        seen.append(message.text)

    async def table(key, bot):
        return Table(bot="CuteGamingBot"), ""

    monkeypatch.setitem(sys.modules, "bot.funcs.balance", types.SimpleNamespace(balance=balance))
    monkeypatch.setattr(game_howto, "_table", table)
    message = _Message("как играть в бомбы и мины")
    assert asyncio.run(game_howto.answer_howto(message, HowTo("game", "bombs", True, ("mines",))))
    assert seen == ["бомбы хелп"]
    assert len(message.replies) == 1 and "Игра «Мины»" in message.replies[0]
    assert not asyncio.run(game_howto.answer_howto(message, HowTo("game", "bullet", True)))


def test_answer_reuses_the_solo_help_command(monkeypatch):
    _fresh_memory(monkeypatch)
    seen = []

    async def balance(message):
        seen.append(message.text)

    monkeypatch.setitem(sys.modules, "bot.funcs.balance", types.SimpleNamespace(balance=balance))
    assert asyncio.run(game_howto.answer_howto(_Message("как играть в бомбы"), HowTo("game", "bombs", True)))
    assert seen == ["бомбы хелп"]


def test_answer_for_a_newcomer_uses_the_existing_help(monkeypatch):
    _fresh_memory(monkeypatch)
    seen = []

    async def send_help(message):
        seen.append(message.text)

    monkeypatch.setitem(sys.modules, "bot.funcs.help", types.SimpleNamespace(help=send_help))
    asyncio.run(game_howto.answer_howto(_Message("как играть?"), HowTo("start")))
    asyncio.run(game_howto.answer_howto(_Message("какие есть игры"), HowTo("menu")))
    assert seen == [game_howto.START_TEXT, game_howto.MENU_TEXT]


def test_live_table_reads_the_desk(monkeypatch):
    from bot.runtime.game_desk import live

    async def no_refresh(db=None):
        return live.snapshot()

    monkeypatch.setattr(live, "refresh", no_refresh)
    table, state = asyncio.run(game_howto._table("bingo", _Bot()))
    assert table.max_bet == 500_000 and table.min_bet == 0
    assert table.players == 10
    assert table.commission_from == live.commission_min_pot()
    assert table.bot == "CuteGamingBot"
    assert state == ""
    words, _ = asyncio.run(game_howto._table("words", _Bot()))
    assert words.commission_from is None
