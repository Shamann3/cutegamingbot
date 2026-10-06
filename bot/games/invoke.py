"""Одинаковый вызов любой игры.

Регистр, лишние пробелы и неразрывный пробел не важны.
«футбол10» — то же самое, что «футбол 10».
«игра хелп» не стартует партию.
Чужая фраза не считается командой: «руслан» не рулетка, «шарф» не шарик.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Collection, Iterable, Optional, Sequence, Tuple

HELP_TAILS = frozenset({"хелп", "помощь", "инструкция", "help", "хепл", "hepl"})

GAME_FIRST = frozenset({
    "шарик", "шар",
    "спин", "слоты", "слот", "барабан",
    "дарт", "дартс",
    "баскет", "баскетбал", "баскетбол", "баскетболл",
    "куб", "кубик",
    "боулинг", "боул",
    "футбол", "фут",
    "трейд",
    "башня", "башни", "башню",
    "рулетка", "рул",
    "мемори",
    "провода", "провод",
    "мины",
    "бомбы", "бомба",
    "риск",
    "плиты", "плита",
    "пуля3412",
    "кн",
    "кости",
    "кнб",
    "орел", "орёл", "решка",
    "дуэль", "дуель", "дуэли",
    "слово", "слова",
    "бинго",
    "шашки", "шахи",
    "фортуна",
})

GAME_PHRASES = (
    "найди пару",
    "найти пару",
    "крестики нолики",
    "нолики крестики",
    "камень ножницы бумага",
    "камень бумага ножницы",
    "бумага камень ножницы",
    "бумага ножницы камень",
    "ножницы бумага камень",
    "ножницы камень бумага",
    "орел или решка",
    "решка или орел",
    "решка и орел",
    "орел и решка",
    "орёл и решка",
    "решка и орёл",
    "орёл или решка",
    "решка или орёл",
)

KNB_PHRASES = (
    "камень ножницы бумага",
    "камень бумага ножницы",
    "бумага камень ножницы",
    "бумага ножницы камень",
    "ножницы бумага камень",
    "ножницы камень бумага",
)

OREL_PHRASES = (
    "орел или решка",
    "решка или орел",
    "решка и орел",
    "орел и решка",
    "орёл и решка",
    "решка и орёл",
    "орёл или решка",
    "решка или орёл",
)

TTT_PHRASES = (
    "крестики нолики",
    "нолики крестики",
)

MEMORY_PHRASES = (
    "найди пару",
    "найти пару",
)

_FIRST_LONG = tuple(sorted(GAME_FIRST, key=len, reverse=True))
_STAKE_GROUP = re.compile(r"\d{1,3}(?:[.,]\d{3})+")


def fold(token: str) -> str:
    raw = "".join(
        ch for ch in (token or "")
        if unicodedata.category(ch) != "Cf"
    )
    return raw.strip().lower().replace("ё", "е")


def command_line(text: str) -> str:
    """Команда как её сравнивает диспетчер: регистр, ё и невидимые символы не важны."""
    return " ".join(fold(text or "").split())


def format_line(example: str) -> str:
    return (
        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
        f"<b>Формат:</b> <code>{example}</code>"
    )


def stake_token(token: str) -> Optional[int]:
    """Целая ставка. «1.000» и «1,000» — тысяча. «10,5» — не ставка."""
    raw = fold(token).replace(" ", "")
    if not raw or len(raw) > 18:
        return None
    if raw.isdigit():
        return int(raw)
    if _STAKE_GROUP.fullmatch(raw):
        return int(re.sub(r"[.,]", "", raw))
    return None


def _name_map(names: Iterable[str]) -> Tuple[str, ...]:
    folded = {fold(name) for name in names if fold(name)}
    return tuple(sorted(folded, key=len, reverse=True))


def open_command(text: str, names: Collection[str]) -> Tuple[str, list]:
    """('ignore'|'help'|'ready', слова).

    ready: первое слово — команда, слитая ставка уже отдельным словом.
    """
    parts = (text or "").strip().split()
    if not parts:
        return "ignore", []
    ordered = _name_map(names)
    if not ordered:
        return "ignore", []
    first = fold(parts[0])
    matched = None
    glued = None
    if first in ordered:
        matched = first
    else:
        for name in ordered:
            if not first.startswith(name):
                continue
            tail = first[len(name):]
            if tail.isdigit() and tail:
                matched = name
                glued = tail
                break
    if matched is None:
        return "ignore", []
    tokens = [matched]
    if glued is not None:
        tokens.append(glued)
    tokens.extend(fold(part) for part in parts[1:])
    if len(tokens) >= 2 and tokens[1] in HELP_TAILS:
        return "help", tokens
    return "ready", tokens


def open_phrase(text: str, phrases: Sequence[str]) -> Tuple[str, list, int]:
    """('ignore'|'help'|'ready', слова, сколько слов заняла фраза)."""
    words = [fold(part) for part in (text or "").strip().split()]
    if not words:
        return "ignore", [], 0
    folded = " ".join(words)
    ordered = sorted({fold(phrase) for phrase in phrases if fold(phrase)}, key=len, reverse=True)
    for phrase in ordered:
        count = len(phrase.split())
        if folded == phrase:
            return "ready", phrase.split(), count
        prefix = phrase + " "
        if folded.startswith(prefix):
            tail = folded[len(prefix):].split()
            tokens = phrase.split() + tail
            if tail and tail[0] in HELP_TAILS:
                return "help", tokens, count
            return "ready", tokens, count
    return "ignore", [], 0


def _stake_from_tail(tokens: Sequence[str], *, required: bool) -> Tuple[str, Optional[int]]:
    tail = list(tokens)
    if not tail:
        if required:
            return "bad", None
        return "play", 0
    if len(tail) == 1:
        bet = stake_token(tail[0])
        if bet is None:
            return "bad", None
        if required and bet <= 0:
            return "bad", None
        if bet < 0:
            return "bad", None
        return "play", bet
    return "bad", None


def parse_required_stake(text: str, names: Collection[str]) -> Tuple[str, Optional[int]]:
    kind, tokens = open_command(text, names)
    if kind != "ready":
        return kind, None
    return _stake_from_tail(tokens[1:], required=True)


def parse_optional_stake(text: str, names: Collection[str]) -> Tuple[str, Optional[int]]:
    kind, tokens = open_command(text, names)
    if kind != "ready":
        return kind, None
    return _stake_from_tail(tokens[1:], required=False)


def parse_phrase_stake(text: str, phrases: Sequence[str], *, required: bool = False) -> Tuple[str, Optional[int]]:
    kind, tokens, count = open_phrase(text, phrases)
    if kind != "ready":
        return kind, None
    return _stake_from_tail(tokens[count:], required=required)


def orel_side(text: str) -> str:
    """Сторона монеты по первому слову: «решка или орел» → решка, «решка10» → решка."""
    kind, tokens, _count = open_phrase(text, OREL_PHRASES)
    if kind == "ignore":
        kind, tokens = open_command(text, ("решка", "орел"))
    head = tokens[0] if kind != "ignore" and tokens else ""
    if head == "решка":
        return "решка"
    return "орел"


def parse_embedded_stake(text: str, names: Collection[str]) -> Tuple[str, Optional[int]]:
    """Команда и число где угодно после неё: «риск ставка 10», «бомбы на 20»."""
    kind, tokens = open_command(text, names)
    if kind != "ready":
        return kind, None
    direct = _stake_from_tail(tokens[1:], required=True)
    if direct[0] == "play":
        return direct
    if len(tokens) == 2 and re.search(r"\d", tokens[1] or ""):
        return "bad", None
    match = re.search(r"\d{1,18}", " ".join(tokens[1:]))
    if match:
        bet = int(match.group(0))
        if bet > 0:
            return "play", bet
    return "bad", None


def command_filter(names: Collection[str]):
    """Фильтр aiogram: команда этой игры, в любом регистре и со слитой ставкой."""
    picked = tuple(names)

    def _check(message) -> bool:
        text = getattr(message, "text", None)
        if not isinstance(text, str) or not text.strip():
            return False
        return open_command(text, picked)[0] != "ignore"

    return _check


def roulette_help_text() -> str:
    return (
        "💭 <b>Неверный формат команды!</b>\n"
        "<blockquote><i><b>Примеры:</b>\n"
        "<code>рулетка 10 красное</code>\n"
        "<code>рулетка 10 черное</code>\n"
        "<code>рулетка 10 чет</code>\n"
        "<code>рулетка 10 нечет</code>\n"
        "<code>рулетка 10 7</code>\n"
        "<code>рулетка 10 0</code>\n"
        "<code>рулетка 10 1 6</code>\n"
        "<code>рулетка 10 6 12</code></i></blockquote>"
    )


def looks_like_game_command(text: str) -> bool:
    folded = " ".join(fold(part) for part in (text or "").strip().split())
    if not folded:
        return False
    for phrase in GAME_PHRASES:
        phrase_folded = fold(phrase)
        if folded == phrase_folded or folded.startswith(phrase_folded + " "):
            return True
    first = folded.split(" ", 1)[0]
    for name in _FIRST_LONG:
        name_folded = fold(name)
        if first == name_folded:
            return True
        rest = first[len(name_folded):]
        if first.startswith(name_folded) and rest.isdigit() and rest:
            return True
    return False
