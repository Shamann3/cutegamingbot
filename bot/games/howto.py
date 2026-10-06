"""Вопрос «как играть в …» своими словами.

«как играть в бомбы», «а как в шашки играть?», «правила кнб», «что за игра мины»,
«не понимаю как играть в рулетку», «бомбы хелп» — справка этой игры.
«как играть в бомбы и мины» — обе справки, три игры и больше — список игр.
«как играть?», «во что тут поиграть» — справка для новичка и список игр.
«как играть в футболке», «кто сыграет в шашки?», «без риска» — не вопрос о правилах.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import permutations
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from bot.games.invoke import fold

MAX_WORDS = 16
MAX_CHARS = 200


@dataclass(frozen=True)
class HowTo:
    kind: str           # "game" — справка игры, "start" — как начать, "menu" — список игр
    key: str = ""       # ключ игры из каталога пульта
    asked: bool = True  # спросили своими словами; False — команда вроде «бомбы хелп»
    more: Tuple[str, ...] = ()  # вторая игра из того же вопроса


# Слово значит только игру.
_STRONG: Dict[str, Tuple[str, ...]] = {
    "scah": ("шашки", "шашку", "шашках", "шашек", "шашкам", "шашками", "checkers"),
    "memory": ("мемори", "memory"),
    "bingo": ("бинго", "bingo"),
    "duel": ("дуэль", "дуэли", "дуэлях", "дуэлью", "дуэлей", "дуэлям", "дуель", "дуели", "duel"),
    "knb": ("кнб",),
    "bombs": ("бомбы", "бомбах", "бомбами", "бомбам", "bombs"),
    "slots": ("слоты", "слотах", "слотов", "слотами", "слотам", "slots"),
    "basket": (
        "баскетбол", "баскетболе", "баскетбола", "баскетболу", "баскетболл", "баскетбал",
        "баскет", "баскете", "баскету", "basketball",
    ),
    "soccer": ("футбол", "футболе", "футбола", "футболу", "football", "soccer"),
    "bowling": ("боулинг", "боулинге", "боулинга", "боулингу", "bowling"),
    "darts": ("дартс", "дартсе", "дартса", "дартсу", "darts"),
    "fortuna_solo": ("рулетка", "рулетку", "рулетке", "рулеткой", "рулетки", "roulette"),
}

# Обычные слова: «риск», «слова», «шар». Игрой считаются только на месте игры —
# «в риск», «игра слова», «риск хелп», «что такое риск».
_WEAK: Dict[str, Tuple[str, ...]] = {
    "scah": ("шашка", "шашке", "шашкой", "шахи"),
    "fortuna_lobby": ("фортуна", "фортуну", "фортуне", "фортуной", "фортуны", "fortuna"),
    "kosti": ("кости", "костях", "костей", "костям", "кость"),
    "orel": (
        "орел", "орла", "орле", "орлу", "орлом", "решка", "решку", "решке", "решкой",
        "орлянка", "орлянку", "монетка", "монетку", "монетке",
    ),
    "mines": ("мины", "мину", "минах", "минам", "минами", "сапер", "сапера", "mines"),
    "tic_tac_toe": ("кн", "крестики", "нолики", "крестиках", "ноликах", "крестикам"),
    "words": ("слова", "слово", "словах", "словам", "слов"),
    "tank": ("башня", "башни", "башню", "башне", "башней", "башням", "tower"),
    "risk": ("риск", "риска", "риске", "риску", "риском", "risk"),
    "plate": ("плиты", "плита", "плиту", "плитах", "плитам", "плит", "плитами", "плите"),
    "bombs": ("бомба", "бомбу", "бомбой", "бомбе", "бомб"),
    "trade": ("трейд", "трейде", "трейда", "трейду", "трейдом", "трейдинг", "трейдинге", "trade"),
    "balls": (
        "шарик", "шарика", "шарике", "шарику", "шариком", "шарики",
        "шар", "шара", "шаре", "шару", "шаром", "наперстки", "наперсток",
    ),
    "provoda": ("провода", "провод", "проводах", "проводам", "проводов", "проводами", "проводе"),
    "slots": ("слот", "слоте", "спин", "спины", "барабан", "барабане"),
    "soccer": ("фут",),
    "bowling": ("боул",),
    "darts": ("дарт",),
    "kube": ("куб", "кубик", "кубе", "кубике", "кубику", "кубика", "кубики", "кубиках", "кубиком"),
    "fortuna_solo": ("рул",),
}

_PHRASES: Tuple[Tuple[Tuple[str, ...], str], ...] = tuple(sorted(
    (
        *((order, "knb") for order in permutations(("камень", "ножницы", "бумага"))),
        *((order, "knb") for order in permutations(("камень", "ножницы", "бумагу"))),
        (("найди", "пару"), "memory"),
        (("найти", "пару"), "memory"),
        (("найди", "пары"), "memory"),
        (("крестики", "нолики"), "tic_tac_toe"),
        (("нолики", "крестики"), "tic_tac_toe"),
        (("крестиках", "ноликах"), "tic_tac_toe"),
        (("крестиков", "ноликов"), "tic_tac_toe"),
        (("tic", "tac", "toe"), "tic_tac_toe"),
        (("орел", "или", "решка"), "orel"),
        (("решка", "или", "орел"), "orel"),
        (("орел", "и", "решка"), "orel"),
        (("решка", "и", "орел"), "orel"),
        (("орла", "и", "решку"), "orel"),
        (("орла", "или", "решку"), "orel"),
        (("колесо", "фортуны"), "fortuna_lobby"),
    ),
    key=lambda item: -len(item[0]),
))

# «кубик рубика» — головоломка, а не игра бота.
_NOT_A_GAME = frozenset({("кубик", "рубика"), ("куб", "рубика"), ("кубика", "рубика")})

_HELP = frozenset({
    "хелп", "хелпа", "хелпу", "помощь", "help", "хепл", "hepl",
    "инструкция", "инструкцию", "инструкции", "гайд", "гайды", "мануал", "туториал",
    "правила", "правило", "правилах", "правилам", "правил", "справка", "справку", "справки",
    "rules", "guide", "tutorial", "faq",
})
_ASK = frozenset({"как", "how", "сколько", "где"})
# «как часто вы играете в шашки» — вопрос, но не о правилах.
_HOW_MUCH = frozenset({"часто", "долго", "давно", "много", "мало", "редко", "обычно", "сильно", "often", "long"})
_VERBS = frozenset({
    "play", "win",
    "начать", "начинать", "начинается", "запустить", "запускать", "запускается",
    "создать", "создавать", "создается", "открыть",
    "работает", "работают", "работать", "устроена", "устроено", "устроен", "устроены",
    "проходит", "происходит",
    "выиграть", "выигрывать", "выигрывают", "выиграю", "победить", "побеждать", "побеждает",
    "побеждают", "стать",
    "ставить", "поставить", "ставится", "ставят", "ставку", "ставки", "ставка",
    "делать", "сделать", "пользоваться",
    "ходить", "походить", "сходить", "ходит", "ходят", "ход", "ходы", "ходом",
    "бить", "побить", "рубить",
    "забрать", "забирать", "вывести", "остановить", "закончить", "выйти", "сдаться",
    "присоединиться", "присоединяться", "зайти", "войти", "вступить", "участвовать",
    "выбрать", "выбирать", "угадать", "угадывать", "отгадать", "отгадывать",
    "загадать", "загадывать", "нажать", "нажимать", "нажимают", "тыкать",
    "бросить", "бросать", "бросают", "кидать", "кинуть", "крутить", "крутят", "крутится",
    "стрелять", "выстрелить", "считается", "считать", "получить", "получать",
    "отменить", "отменять", "закрыть", "прекратить", "пригласить", "позвать",
    "поменять", "сменить", "подбросить", "перевернуть", "переворачивать", "открывать",
    "съесть", "двигать", "передвигать", "найти", "собрать", "набрать",
    "обыграть", "проиграть", "проигрывать", "выигрывает",
})
# «сколько мин в бомбах», «какая максимальная ставка в рулетке».
_WHICH = frozenset({
    "сколько", "какая", "какой", "какие", "какое", "какую", "каким", "какими",
    "каков", "какова", "каковы", "which",
})
_COUNT = frozenset({
    "мин", "бомб", "игроков", "человек", "людей", "участников", "ходов", "клеток", "карт", "карточек",
    "раундов", "шагов", "уровней", "этажей", "максимум", "минимум", "максимальная", "минимальная",
    "лимит", "лимиты", "ставок", "множитель", "множители", "коэффициент", "шанс", "шансы", "комиссия",
})
_PLAY = re.compile(
    r"(?:по)?игра(?:ть|ться|ют|ет|ешь|ем|ете|ю|й|йте|ется|ются)"
    r"|сыгра(?:ть|ю|ем|ешь|ет|ете|ют|й|йте)"
)
_PLAY_TYPOS = frozenset({"игарть", "играьт", "иргать", "игратб", "играт", "игрть"})
_EXPLAIN = frozenset({
    "объясни", "объясните", "обьясни", "обьясните", "расскажи", "расскажите",
    "подскажи", "подскажите", "научи", "научите", "поясни", "поясните",
    "покажи", "покажите", "растолкуй", "растолкуйте", "научиться", "понять",
    "разобраться", "узнать", "explain",
})
_WHAT = frozenset({"что", "че", "чо", "what"})
_WHAT_TAIL = frozenset({"такое", "за", "это", "значит", "означает", "означают", "is"})
# «я знаю как играть в шашки» — рассказ, а не вопрос. С «не» — вопрос.
_KNOW = frozenset({
    "знаю", "умею", "понял", "поняла", "поняли", "понимаю", "разобрался", "разобралась",
    "разобрались", "научился", "научилась", "научились", "освоил", "освоила",
})
_LOST = _KNOW | frozenset({"понятно", "догоняю", "вкурил", "въехал", "врубаюсь", "шарю", "разбираюсь"})
_LOST_JOINED = frozenset({"непонятно", "непонимаю", "незнаю", "неумею", "непонял", "непоняла", "непойму"})
# «кто сыграет в шашки?», «давай в бомбы» — зовут играть, правила не нужны.
_INVITE = frozenset({
    "давай", "давайте", "го", "погнали", "сыграем", "поиграем", "сыграешь", "поиграешь",
    "сыграет", "поиграет", "сыграете", "поиграете", "вызываю", "хочет", "хочешь", "хотите",
})
# «как же круто играть в шашки» — восклицание.
_MOOD = frozenset({
    "круто", "весело", "скучно", "классно", "кайфово", "кайф", "здорово", "прикольно",
    "сложно", "легко", "трудно", "нудно", "лень", "бесит", "надоело", "устал", "устала",
    "обожаю", "люблю", "нравится", "ненавижу", "страшно", "обидно", "жаль", "жалко",
    "хорошо", "плохо", "ужасно", "отлично",
})
_GLUE = frozenset({
    "а", "и", "ну", "вот", "так", "же", "ж", "ведь", "вообще", "все", "всем", "еще", "уже", "тоже", "также",
    "мне", "нам", "меня", "нас", "тебя", "вас", "я", "мы", "ты", "вы", "он", "она", "они",
    "тут", "здесь", "там", "в", "во", "на", "с", "со", "по", "про", "о", "об", "для",
    "к", "ко", "у", "из", "от", "до", "при",
    "эту", "это", "этой", "этот", "эта", "эти", "этим", "этого", "этом",
    "игру", "игра", "игры", "игре", "игрой", "игр", "играх", "игрушку", "игрушка",
    "ваш", "вашу", "вашей", "вашем", "ваша", "наш", "нашу", "нашей",
    "бот", "бота", "боте", "ботом", "ботик", "кут", "кута", "куте", "кутом", "кьют", "cute",
    "пожалуйста", "пж", "пжл", "плиз", "плз", "pls", "plz", "please",
    "нормально", "правильно", "именно", "хоть", "кто", "нибудь", "ктонибудь", "ктото",
    "можете", "можешь", "может", "то", "знает", "знаете", "знаешь",
    "люди", "народ", "ребят", "ребята", "парни", "девочки", "друзья",
    "привет", "прив", "хай", "эй", "алло", "слушай", "слушайте", "скажи", "скажите",
    "помоги", "помогите", "напиши", "напишите", "хочу", "хотел", "хотела", "хотим", "бы",
    "надо", "нужно", "чтобы", "чтоб", "если", "ли", "или", "либо", "есть",
    "значит", "суть", "смысл", "сначала", "вначале", "первый", "раз", "впервые",
    "новенький", "новенькая", "новичок", "новичку", "новичкам",
    "подробно", "подробнее", "коротко", "кратко", "вкратце", "просто", "сейчас", "щас", "теперь",
    "the", "to", "in", "a", "an", "do", "i", "you", "can", "me", "this", "game",
})
_SLOT_BEFORE = frozenset({
    "в", "во", "игра", "игру", "игры", "игре", "игрой", "игрушку",
    "про", "о", "об", "по", "такое", "за",
    "работает", "работают", "устроена", "устроен", "устроено", "устроены",
}) | _HELP | _EXPLAIN
_SLOT_AFTER = frozenset({"как", "это", "игра", "игру", "игры", "игре"}) | _HELP
_DIRECT_OK = _HELP | frozenset({"игра", "игры", "игру"})
_LIST_GLUE = frozenset({"и", "или", "либо", "а", "в", "во"})
_BOT = frozenset({"бот", "бота", "боте", "ботом", "ботик", "кут", "кута", "куте", "кутом", "кьют", "cute"})
_SHORT_OK = frozenset({"а", "как", "в", "во", "ну", "и", "тут", "здесь", "мне", "нам", "кут", "бот"})
_KNOWN = (
    _GLUE | _HELP | _ASK | _VERBS | _EXPLAIN | _WHAT | _WHAT_TAIL | _LOST | _LOST_JOINED
    | _SLOT_BEFORE | _WHICH | _COUNT | frozenset({"не", "можно"})
)
_GENERIC_OK = _GLUE | _EXPLAIN | _LOST | _LOST_JOINED | frozenset({
    "как", "how", "где", "не", "играть", "поиграть", "сыграть", "пользоваться", "начать", "play",
    "какие", "что", "во", "список", "игр", "игры", "можно",
})
_MERGE = {
    ("как", "нибудь"): "какнибудь",
    ("как", "то"): "както",
    ("как", "бы"): "какбы",
    ("так", "как"): "таккак",
    ("кто", "нибудь"): "ктонибудь",
    ("кто", "то"): "ктото",
    ("что", "нибудь"): "чтонибудь",
    ("что", "то"): "чтото",
}
_TOKEN = re.compile(r"[0-9a-zа-я]+")


def _forms() -> Dict[str, Tuple[str, bool]]:
    table: Dict[str, Tuple[str, bool]] = {}
    for key, forms in _WEAK.items():
        for form in forms:
            table[form] = (key, False)
    for key, forms in _STRONG.items():
        for form in forms:
            table[form] = (key, True)
    return table


_FORMS = _forms()


def words_of(text: str) -> List[str]:
    """Слова сообщения: регистр, ё, знаки и эмодзи не важны."""
    raw = _TOKEN.findall(fold(text or ""))
    out: List[str] = []
    for token in raw:
        if out and (out[-1], token) in _MERGE:
            out[-1] = _MERGE[(out[-1], token)]
            continue
        out.append(token)
    return out


@dataclass(frozen=True)
class _Mention:
    key: str
    start: int
    end: int
    strong: bool


def _mentions(tokens: Sequence[str]) -> List[_Mention]:
    found: List[_Mention] = []
    i = 0
    while i < len(tokens):
        hit = None
        for phrase, key in _PHRASES:
            if tuple(tokens[i:i + len(phrase)]) == phrase:
                hit = _Mention(key, i, i + len(phrase), True)
                break
        if hit is None and tokens[i] in _FORMS:
            key, strong = _FORMS[tokens[i]]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if (tokens[i], nxt) not in _NOT_A_GAME:
                hit = _Mention(key, i, i + 1, strong)
        if hit is None:
            i += 1
            continue
        found.append(hit)
        i = hit.end
    return found


def _in_place(tokens: Sequence[str], mention: _Mention) -> bool:
    if mention.strong:
        return True
    before = tokens[mention.start - 1] if mention.start > 0 else ""
    after = tokens[mention.end] if mention.end < len(tokens) else ""
    return before in _SLOT_BEFORE or after in _SLOT_AFTER or _is_verb(before)


def _placed(tokens: Sequence[str], mentions: Sequence[_Mention]) -> List[_Mention]:
    """Игры на своём месте. «в бомбы, мины и башню» — перечисление тоже на месте."""
    placed: List[_Mention] = []
    for mention in mentions:
        listed = False
        if placed:
            gap = tokens[placed[-1].end:mention.start]
            listed = len(gap) <= 2 and all(token in _LIST_GLUE for token in gap)
        if listed or _in_place(tokens, mention):
            placed.append(mention)
    return placed


def _is_verb(token: str) -> bool:
    return token in _VERBS or token in _PLAY_TYPOS or bool(_PLAY.fullmatch(token))


def _known(token: str) -> bool:
    return token in _KNOWN or token.isdigit() or token.endswith("bot") or _is_verb(token)


def _asks_how(tokens: Sequence[str]) -> bool:
    """«как» рядом с действием: «как играть», «как в шашки ходить», «бомбы как работают»."""
    asks = [
        i for i, token in enumerate(tokens)
        if token in _ASK and (i + 1 >= len(tokens) or tokens[i + 1] not in _HOW_MUCH)
    ]
    verbs = [i for i, token in enumerate(tokens) if _is_verb(token)]
    return any(abs(a - v) <= 4 for a in asks for v in verbs)


def _statement(words: FrozenSet[str]) -> bool:
    if words & _INVITE or words & _MOOD:
        return True
    return bool(words & _KNOW) and "не" not in words


def _game_intent(tokens: Sequence[str], rest: Sequence[str]) -> Optional[bool]:
    """None — не вопрос о правилах. Иначе HowTo.asked."""
    words = frozenset(rest)
    if _statement(words):
        return None
    unknown = sum(1 for token in rest if not _known(token))
    if words & _HELP:
        if unknown > 1:
            return None
        direct = len(rest) <= 2 and words <= _DIRECT_OK
        return not direct
    if unknown > 2:
        return None
    if words & _EXPLAIN:
        return True
    if words & _WHAT and (words & _WHAT_TAIL or any(_is_verb(token) for token in rest)):
        return True
    if ("не" in words and words & _LOST) or words & _LOST_JOINED:
        return True
    if _asks_how(tokens):
        return True
    has_verb = any(_is_verb(token) for token in rest)
    if words & _WHICH and (words & _COUNT or has_verb):
        return True
    if "ли" in words and words & {"можно", "нужно", "надо", "обязательно"} and has_verb:
        return True
    if "кто" in words and any(token in _VERBS for token in rest):
        return True
    if "как" in words and words & {"в", "во"} and words <= _SHORT_OK:
        return True
    return None


def _generic(tokens: Sequence[str]) -> Optional[str]:
    words = frozenset(tokens)
    if _statement(words):
        return None
    if any(not (token in _GENERIC_OK or token.endswith("bot")) for token in tokens):
        return None
    if words & {"как", "how", "где"} and words & {"играть", "поиграть", "play"}:
        return "start"
    if "как" in words and "пользоваться" in words and (words & _BOT or any(t.endswith("bot") for t in tokens)):
        return "start"
    if "какие" in words and words & {"игры", "игр"}:
        return "menu"
    if "что" in words and words & {"поиграть", "играть", "сыграть"}:
        return "menu"
    if "список" in words and words & {"игры", "игр"}:
        return "menu"
    return None


def read_howto(text: str) -> Optional[HowTo]:
    """Какую справку ждёт человек. None — сообщение не про правила."""
    if not text or len(text) > MAX_CHARS:
        return None
    tokens = words_of(text)
    if not tokens or len(tokens) > MAX_WORDS:
        return None
    found = _placed(tokens, _mentions(tokens))
    keys = list(dict.fromkeys(m.key for m in found))
    if not keys:
        kind = _generic(tokens)
        return HowTo(kind) if kind else None
    taken = {i for m in found for i in range(m.start, m.end)}
    rest = [token for i, token in enumerate(tokens) if i not in taken]
    asked = _game_intent(tokens, rest)
    if asked is None:
        return None
    if len(keys) > 2:
        return HowTo("menu", asked=asked)
    return HowTo("game", keys[0], asked, tuple(keys[1:]))
