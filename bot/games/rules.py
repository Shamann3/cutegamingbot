"""Правила игр на двоих и на компанию. Тот же вид, что у «хелп бомбы».

Одиночные игры здесь не описаны: их справка живёт в balance() и открывается своей командой.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

DEFAULT_BOT = "CuteGamingBot"

_PEN = "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji>"
_PLANE = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji>"
_COINS = "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji>"
_STAR = "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji>"

_DUO_JOIN = "Соперник нажимает <b>«Присоединиться»</b>, вы - <b>«Начать игру»</b>."

LOBBY_DEFAULTS = {"bingo": 10, "fortuna_lobby": 5, "kosti": 12}


@dataclass(frozen=True)
class Table:
    """Живые настройки стола из пульта."""

    min_bet: int = 0
    max_bet: int = 0
    players: int = 0
    commission_from: Optional[int] = None  # None — комиссии нет
    bot: str = DEFAULT_BOT

    @property
    def free(self) -> bool:
        return self.min_bet <= 0


def _icon(emoji_id: str, char: str) -> str:
    return f"<tg-emoji emoji-id='{emoji_id}'>{char}</tg-emoji>"


def _num(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def _head(icon: str, title: str) -> List[str]:
    return [f"{icon} <b>Игра «{title}»</b>", ""]


def _start(commands: Sequence[str], table: Table, *, free: str, join: str) -> List[str]:
    lines = [f"{_PEN} <b>Как начать</b>", "Напишите в группе:"]
    lines.extend(f"• {command}" for command in commands)
    if table.free:
        lines.append(f"• {free}")
    lines.extend([join, ""])
    return lines


def _lobby_join(players: int) -> str:
    return (
        f"Игроки нажимают <b>«Присоединиться»</b> - от <b>2</b> до <b>{players}</b> человек. "
        "Когда все в сборе, нажмите <b>«Начать игру»</b>."
    )


def _duo_payout(*, draw: bool, prize: str = "") -> List[str]:
    lines = [
        f"{_COINS} <b>Выигрыш</b>",
        f"Победитель получает ставку соперника{prize}.",
        "Куты списываются только в конце партии - у проигравшего.",
    ]
    if draw:
        lines.append("При ничьей никто ничего не теряет.")
    lines.append("")
    return lines


def _lobby_payout() -> List[str]:
    return [
        f"{_COINS} <b>Выигрыш</b>",
        "Ставка у всех одинаковая. Победитель забирает ставки остальных игроков.",
        "Куты списываются только в конце игры - у проигравших.",
        "",
    ]


def _commission(threshold: int) -> str:
    if threshold > 1:
        return f"• С выигрыша от <b>{_num(threshold)}</b> кут удерживается комиссия - <code>хелп комиссия</code>"
    return "• С выигрыша удерживается комиссия - <code>хелп комиссия</code>"


def _important(table: Table, *, duo: bool, inline: str = "") -> List[str]:
    lines = [
        f"{_STAR} <b>Важно</b>",
        "• Командой - только в группах" if inline else "• Играть можно только в группах",
        "• У обоих на балансе должна быть сумма ставки" if duo
        else "• У каждого игрока на балансе должна быть сумма ставки",
        "• Ставка - только целым числом",
    ]
    if table.min_bet > 0:
        lines.append(f"• Минимальная ставка : <b>{_num(table.min_bet)}</b>")
    if table.max_bet > 0:
        lines.append(f"• Максимальная ставка : <b>{_num(table.max_bet)}</b>")
    if table.commission_from is not None:
        lines.append(_commission(table.commission_from))
    if inline:
        lines.append(f"• В любом чате - через инлайн: <code>@{table.bot} {inline}</code>")
    return lines


def _scah(t: Table) -> List[str]:
    return [
        *_head(_icon("5424687267014801006", "♟"), "Шашки"),
        *_start(
            ("<code>шашки (ставка)</code> - партия на куты",), t,
            free="<code>шашки</code> - без ставки, просто так", join=_DUO_JOIN,
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Доска <b>8 × 8</b>, у каждого по <b>12</b> шашек. Создатель играет белыми и ходит первым.",
        "Нажмите на свою шашку, а затем на клетку, куда хотите сходить.",
        "Дошли до последнего ряда - шашка становится дамкой.",
        "",
        "До старта создатель выбирает режим:",
        "• <b>Реализм</b> - бить обязательно, одной шашкой можно бить несколько раз подряд",
        "• <b>Аркада</b> - бить не обязательно, после взятия ход сразу у соперника",
        "",
        "Побеждает тот, кто побьёт все шашки соперника.",
        "• <b>«Сдаться»</b> - победа уходит сопернику",
        "• <b>«Закончить ничьей»</b> - ничья, если нажали оба",
        "",
        *_duo_payout(draw=True, prize=" и предмет <b>«Фигурка шашки»</b>"),
        *_important(t, duo=True, inline="шашки"),
    ]


def _memory(t: Table) -> List[str]:
    return [
        *_head(_icon("5188239353045868629", "🪵"), "Найди пару"),
        *_start(
            ("<code>мемори (ставка)</code> или <code>найди пару (ставка)</code>",), t,
            free="<code>мемори</code> - без ставки, просто так", join=_DUO_JOIN,
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "На поле <b>20</b> закрытых карточек - это <b>10</b> пар одинаковых эмодзи.",
        "За ход откройте две карточки:",
        "• совпали - пара ваша, <b>+1</b> очко и ещё один ход",
        "• не совпали - карточки закроются, ход у соперника",
        "Первым ходит создатель игры.",
        "",
        "Когда открыты все пары, побеждает тот, у кого их больше. При счёте <b>5 : 5</b> - ничья.",
        "",
        *_duo_payout(draw=True),
        *_important(t, duo=True, inline="мемори"),
    ]


def _tic_tac_toe(t: Table) -> List[str]:
    return [
        *_head(_icon("5226660202035554522", "☑️"), "Крестики-нолики"),
        *_start(
            ("<code>кн (ставка)</code> или <code>крестики нолики (ставка)</code>",), t,
            free="<code>кн</code> - без ставки, просто так",
            join="Выберите поле, соперник нажимает <b>«Присоединиться»</b>, вы - <b>«Начать игру»</b>.",
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Ходите по очереди: каждый ставит свой знак в свободную клетку. Первым ходит создатель.",
        "Соберите ряд по горизонтали, вертикали или диагонали:",
        "• поле <b>3 × 3</b> - <b>3</b> в ряд",
        "• поле <b>5 × 5</b> - <b>4</b> в ряд",
        "• поле <b>7 × 7</b> - <b>6</b> в ряд",
        "",
        "Поле заполнилось, а ряда нет - ничья. <b>«Сдаться»</b> - победа уходит сопернику.",
        "",
        *_duo_payout(draw=True),
        *_important(t, duo=True, inline="кн"),
    ]


def _bingo(t: Table) -> List[str]:
    return [
        *_head(_icon("5370783443175086955", "🍪"), "Бинго"),
        *_start(
            ("<code>бинго (ставка)</code>",), t,
            free="<code>бинго</code> - без ставки, просто так", join=_lobby_join(t.players or 10),
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Каждый получает своё число от <b>1</b> до <b>30</b>: нажмите кнопку "
        "или подождите <b>5</b> секунд - бот выдаст число сам.",
        "Затем бот называет победное число. У кого оно - тот и победил.",
        "",
        *_lobby_payout(),
        *_important(t, duo=False),
    ]


def _fortuna(t: Table) -> List[str]:
    return [
        *_head(_icon("5226711870492126219", "🎡"), "Фортуна"),
        *_start(
            ("<code>фортуна (ставка)</code>",), t,
            free="<code>фортуна</code> - без ставки, просто так", join=_lobby_join(t.players or 5),
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Каждому игроку достаётся свой цвет на колесе.",
        "Колесо крутится один раз - чей цвет выпал, тот и победил.",
        "",
        *_lobby_payout(),
        *_important(t, duo=False),
    ]


def _kosti(t: Table) -> List[str]:
    return [
        *_head(_icon("5890971177484029249", "🎲"), "Кости"),
        *_start(
            ("<code>кости (ставка)</code>",), t,
            free="<code>кости</code> - без ставки, просто так", join=_lobby_join(t.players or 12),
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Каждый получает своё число от <b>1</b> до <b>12</b>: нажмите кнопку "
        "или подождите <b>5</b> секунд - бот бросит сам.",
        "Побеждает самое большое число.",
        "",
        *_lobby_payout(),
        *_important(t, duo=False),
    ]


def _duel(t: Table) -> List[str]:
    return [
        *_head(_icon("5222486447306602688", "🔫"), "Дуэль"),
        *_start(
            ("<code>дуэль (ставка)</code>",), t,
            free="<code>дуэль</code> - без ставки, просто так", join=_DUO_JOIN,
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "После старта у обоих появляется кнопка <b>«Выстрелить»</b>. "
        "У каждого один выстрел: попадание или холостой.",
        "Кто первым попал - тот и победил. Оба выстрелили холостыми - ничья.",
        "",
        *_duo_payout(draw=True),
        *_important(t, duo=True, inline="дуэль"),
    ]


def _orel(t: Table) -> List[str]:
    return [
        *_head(_icon("5269254848703902904", "🦅"), "Орёл или решка"),
        *_start(
            ("<code>орел (ставка)</code> - вы за орла", "<code>решка (ставка)</code> - вы за решку"), t,
            free="<code>орел</code> или <code>решка</code> без числа - без ставки, просто так",
            join="Сопернику достаётся другая сторона. Он нажимает <b>«Присоединиться»</b>, "
                 "вы - <b>«Начать игру»</b>.",
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Оба нажимают <b>«Подбросить монетку»</b>. На чью сторону упала монета - тот и победил.",
        "Ничьих не бывает.",
        "",
        *_duo_payout(draw=False),
        *_important(t, duo=True, inline="орел"),
    ]


def _knb(t: Table) -> List[str]:
    return [
        *_head(_icon("5237808360882977239", "✂️"), "Камень-ножницы-бумага"),
        *_start(
            ("<code>кнб (ставка)</code> или <code>камень ножницы бумага (ставка)</code>",), t,
            free="<code>кнб</code> - без ставки, просто так", join=_DUO_JOIN,
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Каждый тайно выбирает: камень, ножницы или бумагу. "
        "Выбор соперника видно, только когда сходили оба.",
        "• камень бьёт ножницы",
        "• ножницы режут бумагу",
        "• бумага накрывает камень",
        "Один раунд. Одинаковый выбор - ничья.",
        "",
        *_duo_payout(draw=True),
        *_important(t, duo=True, inline="кнб"),
    ]


def _mines(t: Table) -> List[str]:
    return [
        *_head(_icon("5469913852462242978", "🧨"), "Мины"),
        *_start(
            ("<code>мины (ставка)</code>",), t,
            free="<code>мины</code> - без ставки, просто так", join=_DUO_JOIN,
        ),
        f"{_PLANE} <b>Суть игры</b>",
        "Поле <b>5 × 5</b>, под клетками спрятаны <b>4</b> мины. Ходите по очереди, первым - создатель.",
        "Открывайте по одной клетке. Кто наступит на мину - проиграл.",
        "",
        *_duo_payout(draw=False),
        *_important(t, duo=True, inline="мины"),
    ]


def _words(t: Table) -> List[str]:
    return [
        *_head(_icon("5249238643247179904", "⭐️"), "Слова"),
        f"{_PEN} <b>Как начать</b>",
        "Игра создаётся через инлайн. Наберите в поле сообщения:",
        f"• <code>@{t.bot} слова (ставка) (слово) (подсказка)</code>",
        f"Например: <code>@{t.bot} слова 10 кот пушистый питомец</code>",
        "Нажмите <b>«Создать игру»</b> - карточка игры появится в чате.",
        "",
        f"{_PLANE} <b>Суть игры</b>",
        "Создатель загадывает слово, остальные отгадывают - просто пишут слово в этот чат.",
        "Кто первым напишет загаданное слово - тот и победил. Регистр букв не важен.",
        "",
        f"{_COINS} <b>Выигрыш</b>",
        "Ставка создателя - это приз. Её целиком получает тот, кто первым отгадает слово.",
        "Ставка не обязательна, но без неё нужна подсказка.",
        "",
        f"{_STAR} <b>Важно</b>",
        "• Своё слово создатель отгадывать не может",
        "• Отменить игру может только создатель - кнопкой <b>«Отмена»</b>",
        "• Ставка - только целым числом",
    ]


_BUILDERS: Dict[str, Callable[[Table], List[str]]] = {
    "scah": _scah,
    "memory": _memory,
    "tic_tac_toe": _tic_tac_toe,
    "bingo": _bingo,
    "fortuna_lobby": _fortuna,
    "kosti": _kosti,
    "duel": _duel,
    "orel": _orel,
    "knb": _knb,
    "mines": _mines,
    "words": _words,
}

RULE_KEYS = frozenset(_BUILDERS)


def rules_html(key: str, table: Optional[Table] = None, *, state: str = "") -> Optional[str]:
    """Справка игры. state — строка про техработы или выключенную игру, встаёт первой."""
    build = _BUILDERS.get(key)
    if build is None:
        return None
    lines = build(table or Table())
    if state:
        lines = [state, "", *lines]
    return "\n".join(lines).strip()
