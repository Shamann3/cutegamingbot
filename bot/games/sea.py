# -*- coding: utf-8 -*-
"""Морской бой в группе.

Вызов тот же: сообщение «морской бой» или «морской бой 10».
Сроки, поле и флот — в блоке ниже. Вызов только сообщением в группе.

Общий стол видят все: только выстрелы. Корабли открываются скрытым
сообщением в этом же чате и только тому, кто нажал «Моё море».
Личка — запасной путь, если скрытое сообщение не ушло.
"""
from __future__ import annotations

import asyncio
import contextvars
import html
import json
import random
import time
from collections import Counter
from itertools import count
from pathlib import Path

from aiogram import Router
from aiogram.types import (
    EphemeralMessageParameters,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# --- настройки партии. Меняются здесь, бот читает их при запуске. ---

SIZE = 8
COLS = "ABCDEFGH"            # не короче SIZE. Буквы слева направо, верх поля
# Наборы выбирает создатель до старта. Число в названии — клетки кораблей, поле 8×8.
# Больше клеток — проще попадать. Лёгкий до 16.
# 1 — катер, 2 — крейсер, 3 — эсминец, 4 — линкор.
LEVELS = (
    (
        "easy",
        "Лёгкий 16",
        (4, 3, 3, 2, 2, 1, 1),
        "Лёгкий. Линкор, два эсминца, два крейсера и два катера.",
    ),
    (
        "mid",
        "Средний 12",
        (4, 3, 2, 2, 1),
        "Средний. Линкор, эсминец, два крейсера и катер.",
    ),
    (
        "hard",
        "Сложный 8",
        (3, 2, 2, 1),
        "Сложный. Эсминец, два крейсера и катер.",
    ),
)
_LEVEL = {item[0]: item for item in LEVELS}
FLEET = _LEVEL["easy"][2]
# Название типа: (им. ед., род. ед., род. мн.)
SHIP_KIND = {
    1: ("катер", "катера", "катеров"),
    2: ("крейсер", "крейсера", "крейсеров"),
    3: ("эсминец", "эсминца", "эсминцев"),
    4: ("линкор", "линкора", "линкоров"),
}
SHIP_TITLE = {
    1: "Катер",
    2: "Крейсер",
    3: "Эсминец",
    4: "Линкор",
}
PLACE_SECONDS = 300          # расстановка. Кто не успел — партия снимается, куты на месте
LOBBY_SECONDS = 7200         # стол без старта сам закрывается через 2 часа
TURN_SECONDS = 60            # минута на выстрел
MISS_LIMIT = 3               # столько пропущенных минут — и игрок сдаётся
PAGE = 5                     # столбцов на экране кнопок. Слева ещё цифра, в ряду не больше 8
CLICK_GAP = 0.0              # без паузы: кнопки отвечают сразу
WORDS = ("морскойбой", "battleship")
PHRASES = ("морской бой", "морская битва")

_IDS = count(1)
TABLES: dict[int, dict] = {}
INLINE: dict[int, dict] = {}
_LOCKS: dict[int, asyncio.Lock] = {}
_OPEN_AT: dict[int, float] = {}
_PACE_AT: dict[tuple[int, int], float] = {}
_WARN_AT: dict[tuple[int, int], float] = {}
_LIVE = Path(__file__).with_name("sea_live.json")
EMPTY = InlineKeyboardMarkup(inline_keyboard=[])
_PLACE_WHY = {
    "edge": "Корабль выходит за край. Выберите клетку левее или выше.",
    "touch": "Слишком близко. Между кораблями нужна пустая клетка, даже углом.",
    "count": "Такой корабль уже стоит. Нажмите другую длину.",
    "length": "Нет такого корабля.",
}
_TOAST = {
    "miss": "Мимо. Ход соперника.",
    "hit": "Попадание. Стреляйте ещё.",
    "sunk": "Корабль потоплен. Стреляйте ещё.",
    "win": "Победа.",
    "repeat": "Уже стрелял.",
    "halo": "Тут пусто.",
}
# Как выглядит игра. В кавычки ставится id премиум-эмодзи.
# Пустые кавычки "" — остаётся обычный знак, он написан в комментарии.
# Id берутся из твоего набора. Чужие сюда не подставляются.
#
# Корабль на кнопках собирается из клеток:
#   горизонтальный    левая · середина · середина · правая
#   вертикальный      верх, потом середина, потом низ
#   одна клетка       отдельный знак
#
# Если слот «выбран», «ранен» или «потоплен» пустой,
# берётся обычная часть корабля. Выбранный корабль ещё подсвечивается.
FACE = {
    # --- море (со своей стороны на скрытом поле) ---
    "water": "",                          # пустая клетка, знак ㅤ
    "miss": "5348132683304156113",        # я попал мимо
    "foe_miss": "5341779022219059533",    # соперник попал мимо по мне
    "halo": "5350475991691052862",        # обводка вокруг корабля
    "hit": "5469785308386041323",         # соперник пробил мой корабль
    "kill": "5276032951342088188",        # соперник потопил мой корабль
    "aim_hit": "5228784961011607179",     # я пробил корабль противника
    "aim_kill": "5458539816989760062",    # я потопил корабль противника
    # совместимость со старыми вызовами / общим полем прицела
    "wound": "5228784961011607179",
    "sunk": "5458539816989760062",
    "zone": "5381975814415866082",        # монета в строке ставки

    # --- целый корабль. Пусто = рисунок корабля из знаков ниже ---
    "ship_one": "",
    "ship_left": "",
    "ship_mid_h": "",
    "ship_right": "",
    "ship_top": "",
    "ship_mid_v": "",
    "ship_bot": "",

    # --- выбранный корабль. Пусто = тот же рисунок, кнопка подсвечена ---
    "pick_one": "",
    "pick_left": "",
    "pick_mid_h": "",
    "pick_right": "",
    "pick_top": "",
    "pick_mid_v": "",
    "pick_bot": "",

    # --- надпись «Морской бой» ---
    "title": "6001395499628762723",

    # --- кнопки ---
    "again": "5882207227997066107",       # Авто
    "ready": "6114060708075277880",       # Готово, кнопка зелёная
    "join": "",                           # Присоединиться, без эмодзи
    "start": "",                          # Начать, без эмодзи
    "sea": "5415803062738504079",         # Моё море
    "mine": "6334614094837974604",        # Мои корабли
    "left": "5805509901048356965",
    "right": "5807453545548487345",
    "down": "5807557921843715576",
    "up": "5807601906603792598",
    "turn": "5807492110059838726",
    "give": "5408921017596781520",        # Сдаться
    "leave": "",                          # Выйти, без эмодзи
}
_WATER = "\u3164"
_GUIDE = {
    "lobby": "«Присоединиться», затем «Начать». Сложность выбирает создатель.",
    "place": "«Авто» ставит само. «Выставить вручную» — клетка за клеткой: катер, крейсер, эсминец, линкор. Затем «Готово».",
    "fight": "Нажмите клетку. «Мои корабли» — ваши.",
}
_PACE = "Пожалуйста, не торопитесь"
_LEFT_WORD = {
    1: "один",
    2: "два",
    3: "три",
    4: "четыре",
    5: "пять",
    6: "шесть",
    7: "семь",
    8: "восемь",
}


def letters() -> str:
    return (COLS + "ABCDEFGHIJKLMNOPQRSTUVWXYZ")[:SIZE]


def fleet_phrase(fleet=None) -> str:
    """Кратко: «линкор ×1, эсминец ×2, …»."""
    parts = []
    for length, _got, want in fleet_progress([], fleet):
        if want <= 0:
            continue
        parts.append(f"{SHIP_TITLE.get(length, 'корабль').lower()} ×{want}")
    return ", ".join(parts) if parts else ", ".join(str(int(n)) for n in FLEET)


def span_text(seconds: int) -> str:
    seconds = int(seconds)
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60} мин"
    return f"{max(0, seconds)} с"


def _times(n: int) -> str:
    n = abs(int(n))
    tail = n % 10
    hundred = n % 100
    if tail == 1 and hundred != 11:
        return f"{n} раз"
    if tail in (2, 3, 4) and hundred not in (12, 13, 14):
        return f"{n} раза"
    return f"{n} раз"


def _num(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def page_width() -> int:
    """Столбцов на одном экране. Плюс цифра слева — Telegram принимает до 8 кнопок в ряду."""
    return max(1, min(int(PAGE), 7))


def page_count() -> int:
    width = page_width()
    return (SIZE + width - 1) // width


def page_columns(page: int) -> list:
    width = page_width()
    start = int(page) * width
    return list(range(start, min(SIZE, start + width)))


def page_label(page: int) -> str:
    cols = page_columns(page)
    if not cols:
        return "—"
    names = letters()
    return f"{names[cols[0]]}–{names[cols[-1]]}"


def ship_at(ships, r: int, c: int):
    cell = (r, c)
    for ship in ships:
        if cell in ship:
            return ship
    return None


def shape(ship, r: int, c: int) -> str:
    """Фигура корабля на схеме. Один символ, чтобы столбцы не поплыли."""
    cells = set(ship)
    left = (r, c - 1) in cells
    right = (r, c + 1) in cells
    up = (r - 1, c) in cells
    down = (r + 1, c) in cells
    if left and right:
        return "="
    if up and down:
        return "|"
    if right and not left:
        return "<"
    if left and not right:
        return ">"
    if down and not up:
        return "^"
    if up and not down:
        return "v"
    return "#"


def button_char(glyph: str) -> str:
    return {
        ".": "·",
        "o": "○",
        "x": "✕",
        "+": "▫",
        "=": "═",
        "|": "║",
        "<": "◀",
        ">": "▶",
        "^": "▲",
        "v": "▼",
        "#": "●",
    }.get(glyph, "·")


def _spec(fleet=None):
    return Counter(tuple(int(n) for n in (FLEET if fleet is None else fleet)))


def place_ship(ships, length: int, r: int, c: int, across: bool, fleet=None):
    """Нос в (r, c), дальше вправо или вниз. Касание даже углом не проходит."""
    need = _spec(fleet)
    if int(length) not in need:
        return False, ships, "length"
    cells = []
    for step in range(int(length)):
        rr, cc = (r, c + step) if across else (r + step, c)
        if not (0 <= rr < SIZE and 0 <= cc < SIZE):
            return False, ships, "edge"
        cells.append((rr, cc))
    blocked = set()
    for ship in ships:
        for sr, sc in ship:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    blocked.add((sr + dr, sc + dc))
    if any(cell in blocked for cell in cells):
        return False, ships, "touch"
    have = Counter(len(ship) for ship in ships)
    if have[int(length)] >= need[int(length)]:
        return False, ships, "count"
    return True, [*ships, tuple(cells)], ""


HAND_CAP = 4  # линкор — самый длинный


def cells_used(ships) -> int:
    return sum(len(ship) for ship in ships)


def hand_budget(fleet=None) -> int:
    return sum(_spec(fleet).elements())


def hand_cap(fleet=None) -> int:
    """Самый длинный корабль выбранного набора — дальше вручную не растёт."""
    lengths = [int(n) for n in (FLEET if fleet is None else fleet)]
    if not lengths:
        return 3
    return min(HAND_CAP, max(lengths))


def ship_word(length: int, count: int = 1) -> str:
    """Согласованное слово: 1 катер, 2 катера, 5 катеров."""
    forms = SHIP_KIND.get(int(length))
    if not forms:
        return "корабль" if abs(int(count)) == 1 else "корабля"
    one, few, many = forms
    n = abs(int(count))
    tail = n % 10
    hundred = n % 100
    if tail == 1 and hundred != 11:
        return one
    if tail in (2, 3, 4) and hundred not in (12, 13, 14):
        return few
    return many


def ship_count_label(length: int, count: int) -> str:
    n = abs(int(count))
    return f"{n} {ship_word(length, n)}"


def ship_max_alert(length: int, fleet=None) -> str:
    """Текст show_alert, когда лимит типа уже выбран."""
    want = int(_spec(fleet)[int(length)])
    if want <= 0:
        return "Такого корабля в наборе нет."
    forms = SHIP_KIND.get(int(length))
    many = forms[2] if forms else "кораблей"
    return (
        f"Максимум {many} уже выставлен.\n"
        f"В наборе: {ship_count_label(int(length), want)}."
    )


def fleet_feasible(ships, fleet=None) -> bool:
    """Текущие корабли ещё могут дорасти до набора сложности."""
    slots = sorted((int(n) for n in (FLEET if fleet is None else fleet)), reverse=True)
    lens = sorted((len(ship) for ship in ships), reverse=True)
    if len(lens) > len(slots):
        return False
    return all(length <= slots[index] for index, length in enumerate(lens))


def _can_start_ship(ships, fleet) -> bool:
    """Можно ли начать новый катер: есть слот «1» или ещё не начат более длинный."""
    need = _spec(fleet)
    have = Counter(len(ship) for ship in ships)
    total = sum(need.values())
    if len(ships) >= total:
        return False
    if have[1] < need[1]:
        return True
    larger_need = sum(count for length, count in need.items() if length > 1)
    larger_have = sum(1 for ship in ships if len(ship) > 1)
    growing = max(0, have[1] - need[1])
    return larger_have + growing < larger_need


def fleet_progress(ships, fleet=None) -> list[tuple[int, int, int]]:
    """[(длина, стоит, нужно), ...] от линкора к катеру."""
    need = _spec(fleet)
    have = Counter(len(ship) for ship in ships)
    return [
        (length, int(have[length]), int(need[length]))
        for length in sorted(need, reverse=True)
    ]


def _straight(ship) -> bool:
    cells = tuple(ship)
    if len(cells) <= 1:
        return True
    rows = {r for r, _ in cells}
    cols = {c for _, c in cells}
    if len(rows) == 1:
        line = sorted(c for _, c in cells)
        return line[-1] - line[0] == len(cells) - 1 and len(line) == len(cells)
    if len(cols) == 1:
        line = sorted(r for r, _ in cells)
        return line[-1] - line[0] == len(cells) - 1 and len(line) == len(cells)
    return False


def _ends(ship):
    cells = tuple(ship)
    if not cells or not _straight(cells):
        return []
    if len(cells) == 1:
        r, c = cells[0]
        return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    rows = {r for r, _ in cells}
    if len(rows) == 1:
        r = next(iter(rows))
        line = sorted(c for _, c in cells)
        return [(r, line[0] - 1), (r, line[-1] + 1)]
    c = next(c for _, c in cells)
    line = sorted(r for r, _ in cells)
    return [(line[0] - 1, c), (line[-1] + 1, c)]


def _order_ship(cells):
    cells = list(cells)
    cells.sort(key=lambda item: (item[0], item[1]))
    return tuple(cells)


def _diagonal(ships, r: int, c: int) -> bool:
    for ship in ships:
        for sr, sc in ship:
            if abs(sr - r) == 1 and abs(sc - c) == 1:
                return True
    return False


def hand_put(ships, r: int, c: int, budget: int, fleet=None):
    """Клетка становится кораблём или удлиняет его по прямой. Диагональ не проходит.

    Код ``count:N`` — лимит кораблей длины N уже выбран (для show_alert).
    """
    cell = (int(r), int(c))
    cap = hand_cap(fleet)
    need_total = sum(_spec(fleet).values()) if fleet is not None else None
    if not (0 <= cell[0] < SIZE and 0 <= cell[1] < SIZE):
        return False, ships, "edge"
    if ship_at(ships, cell[0], cell[1]) is not None:
        return False, ships, "ship"
    if cells_used(ships) >= int(budget):
        return False, ships, "full"
    growers = [index for index, ship in enumerate(ships) if cell in _ends(ship)]
    if len(growers) > 1:
        return False, ships, "touch"
    if len(growers) == 1:
        index = growers[0]
        ship = ships[index]
        if len(ship) >= cap:
            return False, ships, "long"
        nxt = _order_ship([*ship, cell])
        if not _straight(nxt) or not _fits(_without(ships, index), nxt):
            return False, ships, "touch"
        out = list(ships)
        out[index] = nxt
        if fleet is not None and not fleet_feasible(out, fleet):
            return False, ships, f"count:{len(nxt)}"
        return True, out, "grow"
    if fleet is not None and not _can_start_ship(ships, fleet):
        have = Counter(len(ship) for ship in ships)
        need = _spec(fleet)
        if have[1] >= need[1]:
            return False, ships, "count:1"
        return False, ships, "slots"
    if need_total is not None and len(ships) >= need_total:
        return False, ships, "slots"
    if _diagonal(ships, cell[0], cell[1]):
        return False, ships, "diag"
    if not _fits(ships, (cell,)):
        return False, ships, "touch"
    trial = [*ships, (cell,)]
    if fleet is not None and not fleet_feasible(trial, fleet):
        return False, ships, "count:1"
    return True, trial, "new"


def hand_ready(ships, budget: int, fleet=None) -> bool:
    """Вручную нужен ровно набор выбранной сложности."""
    if fleet is not None:
        if cells_used(ships) != int(budget):
            return False
        if not fleet_ready(ships, fleet):
            return False
    elif cells_used(ships) != int(budget):
        return False
    cap = hand_cap(fleet)
    if any(len(ship) < 1 or len(ship) > cap or not _straight(ship) for ship in ships):
        return False
    for index, ship in enumerate(ships):
        if not _fits(_without(ships, index), ship):
            return False
    return True


_HAND_NOTE = {
    "full": "Клетки набора уже заняты.",
    "long": "Корабль длиннее, чем позволяет набор.",
    "diag": "По диагонали нельзя.",
    "touch": "Сюда нельзя — слишком близко к другому кораблю.",
    "edge": "Сюда нельзя.",
    "slots": "Все корабли набора уже начаты.",
    "grow": "Корабль стал длиннее.",
    "new": "Катер поставлен. Удлините по прямой или начните другой.",
}


def hand_fail_text(code: str, fleet=None) -> str:
    raw = str(code or "")
    if raw.startswith("count:"):
        try:
            length = int(raw.split(":", 1)[1])
        except (TypeError, ValueError, IndexError):
            length = 1
        return ship_max_alert(length, fleet)
    if raw == "slots":
        return "Все корабли набора уже начаты. Удлините существующие или нажмите «Готово»."
    if raw == "long":
        cap = hand_cap(fleet)
        title = SHIP_TITLE.get(cap, "Корабль")
        return f"Дальше нельзя: в наборе самый длинный — {title.lower()} ({cap})."
    return _HAND_NOTE.get(raw, "Сюда нельзя")


def fleet_ready(ships, fleet=None) -> bool:
    return Counter(len(ship) for ship in ships) == _spec(fleet)


def game_fleet(game) -> tuple:
    """Набор этой партии. У старого стола без записи берём то, что уже стоит."""
    raw = (game or {}).get("fleet")
    if raw:
        return tuple(int(n) for n in raw)
    for board in ((game or {}).get("boards") or {}).values():
        ships = (board or {}).get("ships") or []
        if ships:
            return tuple(sorted((len(ship) for ship in ships), reverse=True))
    return tuple(int(n) for n in FLEET)


def _fits(others, cells) -> bool:
    cells = tuple(cells)
    if not cells or len(cells) != len(set(cells)):
        return False
    if any(r < 0 or c < 0 or r >= SIZE or c >= SIZE for r, c in cells):
        return False
    blocked = set()
    for ship in others:
        for sr, sc in ship:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    blocked.add((sr + dr, sc + dc))
    return not any(cell in blocked for cell in cells)


def ship_index(ships, r: int, c: int):
    for index, ship in enumerate(ships):
        if (r, c) in ship:
            return index
    return None


def _without(ships, index: int) -> list:
    return [ship for pos, ship in enumerate(ships) if pos != index]


def shift_ship(ships, index: int, dr: int, dc: int):
    if index < 0 or index >= len(ships):
        return False, ships
    nxt = tuple((r + dr, c + dc) for r, c in ships[index])
    if not _fits(_without(ships, index), nxt):
        return False, ships
    out = list(ships)
    out[index] = nxt
    return True, out


def turn_ship(ships, index: int):
    """Поворот. Нос старается остаться на месте, если так не встаёт — пробуем другие точки."""
    if index < 0 or index >= len(ships):
        return False, ships
    ship = ships[index]
    if len(ship) < 2:
        return False, ships
    horizontal = ship[0][0] == ship[-1][0]
    others = _without(ships, index)
    anchors = (ship[0], ship[len(ship) // 2], ship[-1])
    for ar, ac in anchors:
        options = []
        if horizontal:
            options.append(tuple((ar + i, ac) for i in range(len(ship))))
            options.append(tuple((ar - i, ac) for i in range(len(ship))))
        else:
            options.append(tuple((ar, ac + i) for i in range(len(ship))))
            options.append(tuple((ar, ac - i) for i in range(len(ship))))
        for nxt in options:
            if nxt != ship and _fits(others, nxt):
                out = list(ships)
                out[index] = nxt
                return True, out
    return False, ships


_PLANS = {
    # Сложный 8
    (3, 2, 2, 1): (
        (3, 0, 0, True),
        (2, 2, 0, True),
        (2, 2, 3, True),
        (1, 4, 0, True),
    ),
    # Средний 12
    (4, 3, 2, 2, 1): (
        (4, 0, 0, True),
        (3, 0, 5, True),
        (2, 2, 0, True),
        (2, 2, 3, True),
        (1, 4, 0, True),
    ),
    # Лёгкий 16
    (4, 3, 3, 2, 2, 1, 1): (
        (4, 0, 0, True),
        (3, 0, 5, True),
        (3, 2, 0, True),
        (2, 2, 4, True),
        (2, 4, 0, True),
        (1, 4, 3, True),
        (1, 4, 5, True),
    ),
}


def _fallback_fleet(fleet=None) -> list:
    spec = tuple(int(n) for n in (FLEET if fleet is None else fleet))
    ships = []
    for length, r, c, across in _PLANS.get(spec, ()):
        ok, ships, _code = place_ship(ships, length, r, c, across, spec)
        if not ok:
            return []
    return ships


def scatter(rng=None, fleet=None) -> list:
    """Новая случайная расстановка. Каждый вызов — другой рисунок."""
    rng = rng or random.Random()
    spec = tuple(int(n) for n in (FLEET if fleet is None else fleet))
    fleet = list(spec)
    for _ in range(40):
        blocked = set()
        ships = []
        order = fleet[:]
        rng.shuffle(order)
        failed = False
        for length in order:
            spots = []
            span = int(length)
            for across in (True, False):
                r_max = SIZE if across else SIZE - span + 1
                c_max = SIZE - span + 1 if across else SIZE
                for r in range(r_max):
                    for c in range(c_max):
                        cells = tuple(
                            (r, c + step) if across else (r + step, c)
                            for step in range(span)
                        )
                        if not any(cell in blocked for cell in cells):
                            spots.append(cells)
            if not spots:
                failed = True
                break
            cells = rng.choice(spots)
            ships.append(cells)
            for sr, sc in cells:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        blocked.add((sr + dr, sc + dc))
        if not failed and fleet_ready(ships, spec):
            return ships
    return _fallback_fleet(spec)


def next_length(ships, prefer=None, fleet=None):
    """Какой корабль ставить дальше. Текущий остаётся, пока такие ещё есть."""
    have = Counter(len(ship) for ship in ships)
    need = _spec(fleet)
    if prefer is not None and need[int(prefer)] - have[int(prefer)] > 0:
        return int(prefer)
    for length in sorted(need, reverse=True):
        if need[length] - have[length] > 0:
            return int(length)
    return None


def guide_text(phase: str) -> str:
    return _GUIDE.get(phase or "", _GUIDE["lobby"])


def label_hint(kind: str) -> str:
    if kind == "a":
        return "Это буква столбца. Клетки — под ней."
    if kind == "n":
        return "Это номер ряда. Клетки — справа от цифры."
    if kind == "d":
        return "Нажмите на корабль. Стрелки его двигают, поворот разворачивает."
    return "Буквы сверху, цифры слева."


def ship_face(length: int, left: int, chosen: bool) -> str:
    if int(length) == 1:
        core = "1 ●"
    else:
        core = f"{int(length)} {'▬' * int(length)}"
    if int(left) > 1:
        core = f"{core} ×{int(left)}"
    if chosen:
        return "✓ " + core
    return core


def remain_line(ships, fleet=None) -> str:
    bits = []
    for length, got, want in fleet_progress(ships, fleet):
        left = want - got
        if left > 0:
            bits.append(ship_count_label(length, left))
    if not bits:
        return "Все корабли на воде."
    if len(bits) == 1:
        return "Осталось: " + bits[0] + "."
    return "Осталось: " + ", ".join(bits[:-1]) + " и " + bits[-1] + "."


def sunk_ships(ships, hits):
    hits = set(hits)
    return [ship for ship in ships if ship and all(cell in hits for cell in ship)]


def halo_cells(ships, hits) -> set:
    """Клетки вокруг потопленных. Это обводка, по ней уже не стреляют."""
    hull = {cell for ship in ships for cell in ship}
    ring = set()
    for ship in sunk_ships(ships, hits):
        for r, c in ship:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < SIZE and 0 <= cc < SIZE and (rr, cc) not in hull:
                        ring.add((rr, cc))
    return ring


def apply_shot(ships, hits, misses, r: int, c: int):
    hits = set(hits)
    misses = set(misses)
    cell = (r, c)
    if cell in hits or cell in misses:
        return "repeat", hits, misses
    if cell in halo_cells(ships, hits):
        return "halo", hits, misses
    target = ship_at(ships, r, c)
    if target is None:
        misses.add(cell)
        return "miss", hits, misses
    hits.add(cell)
    if all(all(part in hits for part in ship) for ship in ships):
        return "win", hits, misses
    if all(part in hits for part in target):
        return "sunk", hits, misses
    return "hit", hits, misses


def public_marks(ships, hits, misses) -> dict:
    """Чужое море: целый корабль не виден. Потопленный остаётся фигурой и в обводке."""
    marks = {}
    sunk = {cell for ship in sunk_ships(ships, hits) for cell in ship}
    for cell in halo_cells(ships, hits):
        marks[cell] = "+"
    for r, c in hits:
        if (r, c) in sunk:
            marks[(r, c)] = shape(ship_at(ships, r, c), r, c)
        else:
            marks[(r, c)] = "x"
    for cell in misses:
        if cell not in marks:
            marks[cell] = "o"
    return marks


def own_marks(ships, hits, misses) -> dict:
    marks = {}
    hits = set(hits)
    for cell in halo_cells(ships, hits):
        marks[cell] = "+"
    for ship in ships:
        sunk = bool(ship) and all(cell in hits for cell in ship)
        for r, c in ship:
            if (r, c) in hits and not sunk:
                marks[(r, c)] = "x"
            else:
                marks[(r, c)] = shape(ship, r, c)
    for cell in misses:
        if cell not in marks:
            marks[cell] = "o"
    return marks


def chart(marks: dict) -> str:
    names = letters()
    lines = ["   " + " ".join(names)]
    for r in range(SIZE):
        cells = []
        for c in range(SIZE):
            glyph = marks.get((r, c), ".")
            cells.append(glyph if len(glyph) == 1 else ".")
        lines.append(f"{r + 1:2} " + " ".join(cells))
    return "\n".join(lines)


def chart_html(marks: dict) -> str:
    return "<pre>" + html.escape(chart(marks)) + "</pre>"


def parse_sea(text: str):
    from bot.games.invoke import parse_optional_stake, parse_phrase_stake

    kind, bet = parse_phrase_stake(text, PHRASES)
    if kind == "ignore":
        kind, bet = parse_optional_stake(text, WORDS)
    if kind == "play":
        return "play", int(bet or 0)
    if kind in {"help", "bad"}:
        return kind, None
    return "ignore", None


def sea_command(text: str) -> bool:
    return parse_sea(text)[0] in {"play", "bad"}


def _fold_mine(text: str) -> str:
    return " ".join(str(text or "").lower().replace("ё", "е").split())


def sea_mine_command(text: str) -> bool:
    """Сообщение «мои корабли» / «моё море» — открыть скрытое поле."""
    folded = _fold_mine(text)
    return folded in {"мои корабли", "мое море", "моикорабли", "моеморе"}


def _face(key: str) -> str:
    return str(FACE.get(key) or "").strip()


def _tag(key: str, fallback: str) -> str:
    eid = _face(key)
    if not eid:
        return fallback
    return f"<tg-emoji emoji-id='{html.escape(eid, quote=True)}'>{fallback}</tg-emoji>"


def _btn(text: str, data: str, style: str | None = None, icon: str = "", icon_only: bool = False) -> InlineKeyboardButton:
    eid = _face(icon) if icon else ""
    label = " " if eid and icon_only else (text or " ")
    kwargs = {"text": label, "callback_data": data}
    if eid:
        kwargs["icon_custom_emoji_id"] = eid
    if style:
        kwargs["style"] = style
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        try:
            return InlineKeyboardButton(**kwargs)
        except TypeError:
            return InlineKeyboardButton(text=text or " ", callback_data=data)


def chat_message_url(chat_id: int, message_id: int, username: str = "") -> str:
    """Ссылка на сообщение в группе/канале."""
    mid = int(message_id or 0)
    cid = int(chat_id or 0)
    if mid <= 0 or not cid:
        return ""
    uname = str(username or "").strip().lstrip("@")
    if uname and all(ch.isalnum() or ch == "_" for ch in uname):
        return f"https://t.me/{uname}/{mid}"
    s = str(cid)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{mid}"
    if cid < 0:
        return f"https://t.me/c/{abs(cid)}/{mid}"
    return ""


def game_message_url(game) -> str:
    """Ссылка на общее сообщение партии (t.me/…/id или t.me/c/…/id)."""
    return chat_message_url(
        int((game or {}).get("chat_id") or 0),
        int((game or {}).get("message_id") or 0),
        str((game or {}).get("chat_username") or ""),
    )


def hidden_message_url(game, uid: int) -> str:
    """Ссылка на скрытое поле кораблей этого игрока."""
    board = ((game or {}).get("boards") or {}).get(int(uid)) or {}
    mid = int(board.get("message_id") or 0)
    chat_id = int(board.get("chat_id") or 0) or int((game or {}).get("chat_id") or 0)
    if mid <= 0:
        return ""
    return chat_message_url(chat_id, mid, str((game or {}).get("chat_username") or ""))


def _url_btn(text: str, url: str, icon: str = "") -> InlineKeyboardButton:
    eid = _face(icon) if icon else ""
    label = " " if eid else (text or "К партии")
    kwargs = {"text": label, "url": str(url)}
    if eid:
        kwargs["icon_custom_emoji_id"] = eid
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text=text or "К партии", url=str(url))


def _with_game_link(rows: list, game, uid: int | None = None) -> InlineKeyboardMarkup:
    out = [list(row) for row in (rows or [])]
    footer = []
    ships_link = hidden_message_url(game, int(uid)) if uid is not None else ""
    party_link = game_message_url(game)
    if ships_link:
        footer.append(_url_btn("К кораблям", ships_link, icon="mine"))
    if party_link:
        footer.append(_url_btn("К партии", party_link, icon="title"))
    if footer:
        out.append(footer)
    return InlineKeyboardMarkup(inline_keyboard=out)


def _pack(buttons, width: int = 8) -> list:
    return [buttons[i:i + width] for i in range(0, len(buttons), width)]


_PART_OF = {
    "#": "one",
    "<": "left",
    "=": "mid_h",
    ">": "right",
    "^": "top",
    "|": "mid_v",
    "v": "bot",
}
_PART_TEXT = {
    "one": "◻️",
    "left": "◻️",
    "mid_h": "◻️",
    "right": "◻️",
    "top": "◻️",
    "mid_v": "◻️",
    "bot": "◻️",
}


def _icon(*keys: str) -> str:
    for key in keys:
        if _face(key):
            return key
    return ""


def _mark(data: str, fallback: str, icon_key: str, style: str | None = None) -> InlineKeyboardButton:
    icon = _icon(icon_key)
    return _btn(fallback, data, style, icon=icon, icon_only=bool(icon))


def _keepout(ships) -> set:
    hull = {cell for ship in ships for cell in ship}
    ring = set()
    for r, c in hull:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cell = (r + dr, c + dc)
                if cell in hull:
                    continue
                if 0 <= cell[0] < SIZE and 0 <= cell[1] < SIZE:
                    ring.add(cell)
    return ring


def _foe_shot_mark(
    data: str, foe_ships, aim_hits: set, foe_halo: set, r: int, c: int,
) -> InlineKeyboardButton | None:
    """Мои выстрелы по противнику: aim_hit / aim_kill / обводка."""
    cell = (r, c)
    foe = ship_at(foe_ships, r, c)
    if foe is not None and cell in aim_hits:
        if all(part in aim_hits for part in foe):
            return _mark(data, "🔥", "aim_kill")
        return _mark(data, "🎇", "aim_hit")
    if cell in aim_hits:
        return _mark(data, "🎇", "aim_hit")
    if cell in foe_halo:
        return _mark(data, "✨", "halo")
    return None


def _cell_button(
    data: str, ships, hits: set, misses: set, halo: set, picked: set,
    blocked: set, r: int, c: int, reveal: bool, aim_hits: set = frozenset(),
    foe_ships=(), foe_halo: set = frozenset(), foe_misses: set = frozenset(),
    *, defense: bool = False,
) -> InlineKeyboardButton:
    """
    defense=True — свои корабли на скрытом поле (урон по мне: hit/kill).
    defense=False — прицел / чужие корабли (мои выстрелы: aim_hit/aim_kill).
    """
    cell = (r, c)
    ship = ship_at(ships, r, c)
    sunk = bool(ship) and all(part in hits for part in ship)
    if ship is not None and (reveal or sunk or cell in hits):
        part = _PART_OF[shape(ship, r, c)]
        text = _PART_TEXT[part]
        if sunk:
            return _mark(data, "💥" if defense else "🔥", "kill" if defense else "aim_kill")
        if cell in hits:
            return _mark(data, "💥" if defense else "🎇", "hit" if defense else "aim_hit")
        if cell in picked:
            icon = _icon(f"pick_{part}", f"ship_{part}")
            return _btn(text, data, "primary", icon=icon, icon_only=bool(icon))
        icon = _icon(f"ship_{part}")
        return _btn(text, data, icon=icon, icon_only=bool(icon))
    if cell in blocked:
        return _mark(data, "✨", "halo")
    if cell in foe_misses:
        return _mark(data, "🤷‍♂️", "foe_miss")
    if cell in misses:
        return _mark(data, "👎", "miss")
    foe_mark = _foe_shot_mark(data, foe_ships, aim_hits, foe_halo, r, c)
    if foe_mark is not None:
        return foe_mark
    if cell in halo:
        return _mark(data, "✨", "halo")
    return _mark(data, _WATER, "water")


def _grid(
    prefix: str, gid: int, page: int, ships, hits=(), misses=(), chosen=(),
    reveal: bool = False, frozen: bool = False, blocked=None, aim_hits=(),
    foe_ships=(), foe_misses=(), *, defense: bool = False,
) -> list:
    hits = set(hits or ())
    misses = set(misses or ())
    aim_hits = set(aim_hits or ())
    foe_misses = set(foe_misses or ())
    foe_ships = list(foe_ships or ())
    picked = set(chosen or ())
    halo = halo_cells(ships, hits)
    foe_halo = halo_cells(foe_ships, aim_hits) if foe_ships and aim_hits else set()
    blocked = set(blocked or ())
    if SIZE <= 8:
        cols = list(range(SIZE))
    else:
        cols = page_columns(page)
    rows = []
    for r in range(SIZE):
        row = []
        for c in cols:
            data = "sea:x:0" if frozen else f"{prefix}c:{gid}:{r * SIZE + c}"
            row.append(_cell_button(
                data, ships, hits, misses, halo, picked, blocked, r, c, reveal,
                aim_hits=aim_hits, foe_ships=foe_ships, foe_halo=foe_halo,
                foe_misses=foe_misses, defense=defense,
            ))
        rows.append(row)
    return rows


def _page_buttons(prefix: str, gid: int, page: int) -> list:
    buttons = []
    last = page_count() - 1
    for item in range(page_count()):
        label = page_label(item)
        if item == page:
            label = "● " + label
        elif item < page:
            label = "← " + label
        elif item == last:
            label = label + " →"
        buttons.append(_btn(label, f"{prefix}p:{gid}:{item}", "primary" if item == page else None))
    return buttons


def _length_buttons(prefix: str, gid: int, ships, pick, fleet=None) -> list:
    have = Counter(len(ship) for ship in ships)
    need = _spec(fleet)
    buttons = []
    for length in sorted(need, reverse=True):
        left = need[length] - have[length]
        if left <= 0:
            continue
        chosen = pick == length
        buttons.append(_btn(
            ship_face(length, left, chosen),
            f"{prefix}l:{gid}:{length}",
            "primary" if chosen else None,
        ))
    return buttons


def _help_row(prefix: str, gid: int, leave: str) -> list:
    return [
        _btn("Как играть", f"{prefix}q:{gid}"),
        _btn(leave, f"{prefix}g:{gid}"),
    ]


def _nav_row(prefix: str, gid: int) -> list:
    return [
        _btn("⬅️", f"{prefix}m:{gid}:l", icon="left", icon_only=True),
        _btn("⬆️", f"{prefix}m:{gid}:u", icon="up", icon_only=True),
        _btn("⬇️", f"{prefix}m:{gid}:d", icon="down", icon_only=True),
        _btn("➡️", f"{prefix}m:{gid}:r", icon="right", icon_only=True),
        _btn("↻", f"{prefix}m:{gid}:t", icon="turn", icon_only=True),
    ]


def _tool_row(prefix: str, gid: int, ships, tool, fleet=None) -> list:
    have = Counter(len(ship) for ship in ships)
    need = _spec(fleet)
    buttons = []
    for length in sorted(need, reverse=True):
        left = need[length] - have[length]
        face = "◻️" * int(length)
        for _ in range(max(0, left)):
            buttons.append(_btn(
                face,
                f"{prefix}l:{gid}:{int(length)}",
                "primary" if int(tool or 0) == int(length) else None,
            ))
    buttons.append(_btn("↻", f"{prefix}m:{gid}:t", icon="turn", icon_only=True))
    return _pack(buttons, 8)


def place_markup(prefix: str, gid: int, ships, page: int, hold=None, hand: bool = False, tool=None, fleet=None) -> InlineKeyboardMarkup:
    chosen = ()
    if not hand and hold is not None and 0 <= int(hold) < len(ships):
        chosen = ships[int(hold)]
    ready_row = [
        _btn("Авто", f"{prefix}a:{gid}", icon="again"),
        _btn("Готово", f"{prefix}r:{gid}", "success", icon="ready"),
    ]
    if hand:
        rows = [ready_row]
        blocked = _keepout(ships)
    else:
        rows = [ready_row, _nav_row(prefix, gid)]
        blocked = _keepout(ships) if ships else (_keepout([chosen]) if chosen else None)
    rows.extend(_grid(
        prefix, gid, page, ships, chosen=chosen, reveal=True, blocked=blocked,
    ))
    if SIZE > 8:
        rows.extend(_pack(_page_buttons(prefix, gid, page)))
    if not hand:
        rows.append([_btn("Выставить вручную", f"{prefix}b:{gid}")])
    rows.append([_btn("Выйти", f"{prefix}g:{gid}", icon="leave")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def aim_markup(prefix: str, gid: int, page: int, ships=(), hits=(), misses=()) -> InlineKeyboardMarkup:
    rows = _grid(prefix, gid, page, ships, hits, misses, reveal=False)
    if SIZE > 8:
        rows.extend(_pack(_page_buttons(prefix, gid, page)))
    rows.append([
        _btn("Мои корабли", f"{prefix}f:{gid}", icon="mine"),
        _btn("Сдаться", f"{prefix}g:{gid}", icon="give"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fleet_markup(prefix: str, gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Как играть", f"{prefix}q:{gid}")]])


def lobby_markup(game) -> InlineKeyboardMarkup:
    prefix = game["prefix"]
    gid = game["id"]
    current = str(game.get("level") or "easy")
    levels = [
        _btn(title, f"{prefix}k:{gid}:{key}", "primary" if key == current else None)
        for key, title, _fleet, _note in LEVELS
    ]
    rows = [levels]
    if len(game["participants"]) < 2:
        rows.append([_btn("Присоединиться", f"{prefix}j:{gid}", "primary")])
    else:
        rows.append([_btn("Начать", f"{prefix}s:{gid}", "success")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def place_public_markup(game) -> InlineKeyboardMarkup:
    prefix = game["prefix"]
    gid = game["id"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Моё море", f"{prefix}d:{gid}", "primary", icon="sea")],
    ])


def _bold(name) -> str:
    """Имя уже может быть ссылкой t.me — как в топе, оборачиваем целиком в <b>."""
    text = str(name or "Игрок")
    if text.startswith("<b>") and text.endswith("</b>"):
        return text
    return f"<b>{text}</b>"


def stake_line(bet: int) -> str:
    if int(bet) <= 0:
        return ""
    eid = html.escape(_face("zone") or "5381975814415866082", quote=True)
    return f"<tg-emoji emoji-id='{eid}'>🪙</tg-emoji> Ставка - {_num(int(bet))} кут"


def lobby_text(game) -> str:
    lines = [f"{_tag('title', '🛥')} <b>Морской бой</b>"]
    stake = stake_line(int(game["bet"]))
    if stake:
        lines.append(stake)
    for uid in game["participants"]:
        lines.append("• " + _bold(game["links"].get(uid, "Игрок")))
    return "\n".join(lines)


def invite_text(bet: int) -> str:
    lines = [f"{_tag('title', '🛥')} <b>Морской бой</b>"]
    stake = stake_line(int(bet))
    if stake:
        lines.append(stake)
    return "\n".join(lines)


def place_text(game) -> str:
    lines = [f"{_tag('title', '🛥')} <b>Морской бой</b>"]
    for uid in game["players"]:
        state = "готов" if game["boards"][uid]["ready"] else "расставляет"
        lines.append(f"{_bold(game['links'].get(uid, 'Игрок'))} — {state}")
    return "\n".join(lines)


def _other(game, uid: int) -> int:
    for person in game.get("players") or []:
        if int(person) != int(uid):
            return int(person)
    return int(uid)


def _incoming(game, uid: int):
    box = (game.get("shots") or {}).get(_other(game, uid)) or {}
    return set(box.get("hit") or ()), set(box.get("miss") or ())


def _outgoing(game, uid: int):
    """Выстрелы самого игрока по чужому морю — для скрытого поля."""
    box = (game.get("shots") or {}).get(int(uid)) or {}
    return set(box.get("hit") or ()), set(box.get("miss") or ())


def _public_chart(game, uid: int) -> str:
    hits, misses = _incoming(game, uid)
    return chart_html(public_marks(game["boards"][uid]["ships"], hits, misses))


def _final_chart(game, uid: int) -> str:
    """После конца партии море можно показать целиком."""
    hits, misses = _incoming(game, uid)
    return chart_html(own_marks(game["boards"][uid]["ships"], hits, misses))


def fight_text(game) -> str:
    links = game["links"]
    turn = int(game["turn"])
    lines = [
        f"{_tag('title', '🛥')} <b>Морской бой</b>",
        f"Ход: {_bold(links.get(turn, 'игрок'))}",
    ]
    if game.get("note"):
        lines.append(str(game["note"]))
    return "\n".join(lines)


def secret_place_text(board, budget: int = 0, fleet=None) -> str:
    title = f"{_tag('title', '🛥')} <b>Ваше море</b>"
    if not board.get("hand"):
        return title
    ships = board.get("ships") or []
    used = cells_used(ships)
    left = max(0, int(budget) - used)
    cap = hand_cap(fleet)
    rows = []
    for length, got, want in fleet_progress(ships, fleet):
        mark = "✓" if got >= want else "·"
        name = SHIP_TITLE.get(length, "Корабль")
        rows.append(f"{mark} {name} — <b>{got}</b> из <b>{want}</b>")
    roster = "\n".join(rows)
    tip = (
        "Пустая клетка — новый катер. Соседняя по прямой — удлинение.\n"
        f"Самый длинный в наборе — {SHIP_TITLE.get(cap, 'корабль').lower()} ({cap})."
    )
    return (
        f"{title}\n"
        f"<blockquote>{roster}</blockquote>\n"
        f"Клеток: <b>{used}</b> из <b>{int(budget)}</b> · ещё <b>{left}</b>\n"
        f"<i>{tip}</i>"
    )


def secret_fight_text(ships, hits, misses) -> str:
    return f"{_tag('title', '🛥')} <b>Ваши корабли</b>"


def _secret_view(game, uid: int):
    board = game["boards"][uid]
    prefix = game["prefix"]
    gid = game["id"]
    if game["phase"] == "place":
        fleet = game_fleet(game)
        text = secret_place_text(board, hand_budget(fleet), fleet)
        markup = place_markup(
            prefix, gid, board["ships"], board["page"], board.get("hold"),
            hand=bool(board.get("hand")), tool=board.get("tool"), fleet=fleet,
        )
        return text, _with_game_link(markup.inline_keyboard, game, uid)
    if game.get("phase") == "over":
        return end_text(
            game,
            int(game.get("winner") or 0),
            str(game.get("end_how") or "Партия закончена."),
            int(game.get("net") or 0),
        ), EMPTY
    hits, misses = _incoming(game, uid)
    aim_hits, aim_misses = _outgoing(game, uid)
    foe = _other(game, uid)
    foe_ships = (game.get("boards") or {}).get(foe, {}).get("ships") or []
    # Своя сторона: hit/kill/foe_miss. Чужие выстрелы: aim_hit/aim_kill/miss.
    text = secret_fight_text(board["ships"], hits, misses)
    rows = _grid(
        prefix, gid, board.get("page", 0), board["ships"], hits,
        aim_misses, reveal=True, aim_hits=aim_hits,
        foe_ships=foe_ships, foe_misses=misses, defense=True,
    )
    if game["phase"] == "fight":
        rows.append([_btn("Сдаться", f"{prefix}g:{gid}", icon="give")])
        return text, _with_game_link(rows, game, uid)
    return text, EMPTY


def end_text(game, winner: int, how: str, net: int) -> str:
    name = str((game.get("links") or {}).get(winner, "Игрок"))
    lines = [
        f"{_tag('title', '🛥')} Морской бой",
        f"<tg-emoji emoji-id='5469967260380612012'>🏆</tg-emoji> <b>{name} - победитель!</b>",
    ]
    if int(game.get("bet") or 0) > 0:
        lines.append(f"{_tag('zone', '🪙')} <b>Выигрыш - {_num(net)} кут</b>")
    lines.append(f"<i>{how}</i>")
    return "\n".join(lines)


def end_markup(game, winner: int, gfund):
    return _commission_markup(gfund)


def _blank_board() -> dict:
    return {
        "ships": [],
        "page": 0,
        "across": True,
        "pick": None,
        "hold": None,
        "hand": False,
        "tool": None,
        "ready": False,
        "ephemeral_id": 0,
        "mode": "none",
        "chat_id": 0,
        "message_id": 0,
    }


def _fresh(gid: int, chat_id: int, message_id: int, owner: int, bet: int, prefix: str) -> dict:
    return {
        "id": int(gid),
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "bet": int(bet),
        "creator": int(owner),
        "level": "easy",
        "fleet": tuple(int(n) for n in FLEET),
        "prefix": prefix,
        "participants": [int(owner)],
        "players": [],
        "phase": "lobby",
        "boards": {},
        "shots": {},
        "skips": {},
        "turn": 0,
        "first": 0,
        "aim_page": 0,
        "links": {},
        "touch": {},
        "note": "",
        "confirm": None,
        "place_deadline": 0,
        "turn_deadline": 0,
        "lobby_deadline": 0,
        "inline_id": "",
        "chat_username": "",
        "place_token": 0,
        "turn_token": 0,
        "lobby_token": 0,
        "place_task": None,
        "turn_task": None,
        "lobby_task": None,
        "bot": None,
    }


def _split(data: str):
    if data.startswith("seai:"):
        body = data[5:]
    elif data.startswith("sea:"):
        body = data[4:]
    else:
        return "", []
    parts = body.split(":")
    if not parts or not parts[0]:
        return "", []
    return parts[0], parts[1:]


def _lock(gid: int) -> asyncio.Lock:
    lock = _LOCKS.get(int(gid))
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[int(gid)] = lock
    return lock


def _drop_task(game, key: str) -> None:
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    task = game.get(key)
    if task is not None and task is not current and not task.done():
        task.cancel()
    game[key] = None


def _pace(gid: int, uid: int, *, stamp: bool) -> str:
    """Пусто — нажатие принято. При CLICK_GAP > 0: alert / quiet для слишком быстрых тапов."""
    if float(CLICK_GAP) <= 0:
        return ""
    now = time.monotonic()
    key = (int(gid), int(uid))
    if now - _PACE_AT.get(key, 0.0) < float(CLICK_GAP):
        if now - _WARN_AT.get(key, 0.0) >= float(CLICK_GAP):
            _WARN_AT[key] = now
            return "alert"
        return "quiet"
    if stamp:
        _PACE_AT[key] = now
        _WARN_AT.pop(key, None)
    return ""


def _drop_pace(gid: int) -> None:
    prefix = int(gid)
    for box in (_PACE_AT, _WARN_AT):
        for key in [item for item in box if item[0] == prefix]:
            box.pop(key, None)


def _too_soon(game, uid: int, *, stamp: bool) -> bool:
    return False


def _ready_touch(game, uid: int) -> bool:
    return True


def _surface(query, game) -> str:
    inline_id = str(getattr(query, "inline_message_id", "") or "")
    game_inline = str(game.get("inline_id") or "")
    if inline_id and game_inline and inline_id == game_inline:
        return "public"
    msg = getattr(query, "message", None)
    if msg is not None and getattr(msg, "ephemeral_message_id", None):
        return "ephemeral"
    if msg is None or getattr(msg, "chat", None) is None:
        return "none"
    chat_id = int(getattr(msg.chat, "id", 0) or 0)
    message_id = int(getattr(msg, "message_id", 0) or 0)
    if chat_id == int(game["chat_id"]) and message_id == int(game["message_id"]):
        return "public"
    if str(getattr(msg.chat, "type", "") or "") == "private":
        return "dm"
    return "ephemeral"


def _is_public_target(chat_id, message_id, game) -> bool:
    if not int(chat_id) or not int(message_id):
        return False
    return int(chat_id) == int(game["chat_id"]) and int(message_id) == int(game["message_id"])


def _aim(game):
    foe = _other(game, int(game["turn"]))
    hits, misses = _incoming(game, foe)
    return aim_markup(
        game["prefix"], game["id"], int(game["aim_page"]),
        game["boards"][foe]["ships"], hits, misses,
    )


_JOBS: contextvars.ContextVar = contextvars.ContextVar("sea_jobs", default=None)
_TAILS: dict[int, asyncio.Task] = {}


def _queue(item) -> bool:
    jobs = _JOBS.get()
    if jobs is None:
        return False
    if item[0] == "ack" and any(job[0] == "ack" for job in jobs):
        return True
    jobs.append(item)
    return True


async def _ack_now(query, text: str = "", alert: bool = False) -> None:
    try:
        if text and alert:
            await query.answer(text[:200], show_alert=True)
        elif text:
            await query.answer(text[:200])
        else:
            await query.answer()
    except Exception:
        pass


async def _ack_jump(query, url: str) -> bool:
    """Перекинуть клиента на сообщение по ссылке. True — url принят."""
    if query is None or not url:
        return False
    try:
        await query.answer(url=str(url))
        return True
    except Exception as exc:
        print(f"[SEA] jump {type(exc).__name__}")
        return False


async def _ack(query, text: str = "", alert: bool = False) -> None:
    if query is None:
        return
    if _queue(("ack", query, text, alert)):
        return
    await _ack_now(query, text, alert)


async def _edit(bot, chat_id, message_id, text, markup) -> bool:
    if _queue(("edit", bot, chat_id, message_id, text, markup)):
        return True
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return True
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return True
        print(f"[SEA] edit {type(exc).__name__}")
        return False


async def _markup_only(bot, chat_id, message_id, markup) -> bool:
    if _queue(("markup", bot, chat_id, message_id, markup)):
        return True
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
        return True
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return True
        print(f"[SEA] markup {type(exc).__name__}")
        return False


def public_channel(game) -> str:
    """Куда писать общий стол: инлайн-карточка или обычное сообщение."""
    if str(game.get("inline_id") or ""):
        return "inline"
    if int(game.get("chat_id") or 0) and int(game.get("message_id") or 0):
        return "chat"
    return "none"


def _public_targets(game) -> list:
    targets = []
    inline_id = str(game.get("inline_id") or "")
    if inline_id:
        targets.append({"inline_message_id": inline_id})
    chat_id = int(game.get("chat_id") or 0)
    message_id = int(game.get("message_id") or 0)
    if chat_id and message_id:
        targets.append({"chat_id": chat_id, "message_id": message_id})
    return targets


async def _touch_targets(bot, targets, kwargs) -> bool:
    last = None
    for target in targets:
        try:
            await bot.edit_message_text(**target, **kwargs)
            return True
        except Exception as exc:
            if "not modified" in str(exc).lower():
                return True
            last = exc
    print(f"[SEA] edit {type(last).__name__ if last else 'none'}")
    return False


async def _touch_public(bot, game, **kwargs) -> bool:
    if bot is None:
        return False
    targets = _public_targets(game)
    if not targets:
        return False
    if _queue(("touch", bot, targets, kwargs)):
        return True
    return await _touch_targets(bot, targets, kwargs)


async def _show(bot, game, text, markup) -> bool:
    return await _touch_public(
        bot,
        game,
        text=text,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _show_markup(bot, game, markup) -> bool:
    if bot is None:
        return False
    targets = _public_targets(game)
    if not targets:
        return False
    if _queue(("markpub", bot, targets, markup)):
        return True
    last = None
    for target in targets:
        try:
            await bot.edit_message_reply_markup(**target, reply_markup=markup)
            return True
        except Exception as exc:
            if "not modified" in str(exc).lower():
                return True
            last = exc
    print(f"[SEA] markup {type(last).__name__ if last else 'none'}")
    return False


async def _dm(bot, uid: int, text: str, markup):
    try:
        return await bot.send_message(
            chat_id=int(uid),
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"[SEA] dm {type(exc).__name__}")
        return None


def _remember_hidden(board, sent) -> None:
    if sent is None:
        return
    eid = int(getattr(sent, "ephemeral_message_id", 0) or 0)
    mid = int(getattr(sent, "message_id", 0) or 0)
    chat = getattr(sent, "chat", None)
    if eid and chat is not None:
        board["mode"] = "ephemeral"
        board["ephemeral_id"] = eid
        board["chat_id"] = int(chat.id)
        # message_id нужен для ссылки «перейти к кораблям»
        if mid:
            board["message_id"] = mid
        return
    if mid and chat is not None:
        board["mode"] = "dm"
        board["chat_id"] = int(chat.id)
        board["message_id"] = mid
        board["ephemeral_id"] = 0


async def _eph_edit_now(bot, chat_id: int, uid: int, eid: int, text: str, markup, only_markup: bool) -> bool:
    if bot is None or not eid or not chat_id:
        return False
    try:
        if only_markup:
            await bot.edit_ephemeral_message_reply_markup(
                chat_id=chat_id,
                receiver_user_id=int(uid),
                ephemeral_message_id=eid,
                reply_markup=markup,
            )
        else:
            await bot.edit_ephemeral_message_text(
                chat_id=chat_id,
                receiver_user_id=int(uid),
                ephemeral_message_id=eid,
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        return True
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return True
        print(f"[SEA] ephemeral edit {type(exc).__name__}")
        return False


async def _edit_hidden(bot, board, uid: int, text: str, markup, only_markup: bool = False) -> bool:
    eid = int(board.get("ephemeral_id") or 0)
    chat_id = int(board.get("chat_id") or 0)
    if bot is None or not eid or not chat_id:
        return False
    if _queue(("eph_edit", bot, chat_id, int(uid), eid, text, markup, bool(only_markup))):
        return True
    return await _eph_edit_now(bot, chat_id, int(uid), eid, text, markup, bool(only_markup))


def _clear_board_link(board) -> None:
    if not isinstance(board, dict):
        return
    board["mode"] = "none"
    board["ephemeral_id"] = 0
    board["message_id"] = 0


async def _drop_hidden(bot, game, uid: int) -> None:
    """Убирает скрытое море одного игрока: ephemeral или запасная личка."""
    board = (game.get("boards") or {}).get(int(uid))
    if not isinstance(board, dict):
        return
    mode = str(board.get("mode") or "")
    chat_id = int(board.get("chat_id") or 0)
    if bot is not None and mode == "ephemeral":
        eid = int(board.get("ephemeral_id") or 0)
        if eid and chat_id:
            try:
                await bot.delete_ephemeral_message(
                    chat_id=chat_id,
                    receiver_user_id=int(uid),
                    ephemeral_message_id=eid,
                )
            except Exception as exc:
                print(f"[SEA] eph del {type(exc).__name__}")
    elif bot is not None and mode == "dm":
        mid = int(board.get("message_id") or 0)
        if mid and chat_id and not _is_public_target(chat_id, mid, game):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as exc:
                print(f"[SEA] dm del {type(exc).__name__}")
    _clear_board_link(board)


async def _drop_all_hidden(bot, game) -> None:
    """Скрытые моря всех игроков. Нужно при выходе и при снятии партии."""
    for uid in list((game.get("boards") or {}).keys()):
        await _drop_hidden(bot, game, int(uid))


async def _ephemeral(bot, query, uid: int, text: str, markup, bind_callback: bool = True):
    """Первое скрытое море. Правки потом идут через editEphemeralMessageText."""
    msg = getattr(query, "message", None)
    if msg is None or getattr(msg, "chat", None) is None:
        return None
    if getattr(msg, "ephemeral_message_id", None):
        return None
    params = {"receiver_user_id": int(uid), "replace_callback_query_message": False}
    if bind_callback:
        params["callback_query_id"] = str(query.id)
    try:
        return await bot.send_message(
            chat_id=msg.chat.id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
            ephemeral_message_parameters=EphemeralMessageParameters(**params),
        )
    except Exception as exc:
        print(f"[SEA] ephemeral {type(exc).__name__}")
        return None


async def _paint_secret(bot, game, uid: int, query=None, toast: str = "", only_markup: bool = False, quiet: bool = False, bind_callback: bool = True) -> None:
    """Море с кораблями. В общее сообщение партии оно не пишется."""
    text, markup = _secret_view(game, uid)
    board = game["boards"].setdefault(uid, _blank_board())
    surface = _surface(query, game) if query is not None else "none"

    async def _save(chat_id, message_id) -> bool:
        if _is_public_target(chat_id, message_id, game):
            return False
        if only_markup:
            return await _markup_only(bot, chat_id, message_id, markup)
        return await _edit(bot, chat_id, message_id, text, markup)

    async def _tell(text: str = "", alert: bool = False) -> None:
        if quiet or query is None:
            return
        await _ack(query, text, alert=alert)

    if surface == "dm":
        msg = query.message
        await _tell(toast)
        if await _save(msg.chat.id, msg.message_id):
            board["mode"] = "dm"
            board["chat_id"] = int(msg.chat.id)
            board["message_id"] = int(msg.message_id)
            return
        sent = await _dm(bot, uid, text, markup)
        if sent is not None and not _is_public_target(sent.chat.id, sent.message_id, game):
            board["mode"] = "dm"
            board["chat_id"] = int(sent.chat.id)
            board["message_id"] = int(sent.message_id)
        return

    if surface == "ephemeral":
        msg = query.message
        eid = int(getattr(msg, "ephemeral_message_id", 0) or 0)
        if eid:
            board["mode"] = "ephemeral"
            board["ephemeral_id"] = eid
            board["chat_id"] = int(msg.chat.id)
        await _tell(toast)
        if await _edit_hidden(bot, board, uid, text, markup, only_markup):
            return
        await _tell("Нажмите ещё раз.")
        return

    if surface == "public" and query is not None:
        if board.get("mode") == "ephemeral" and board.get("ephemeral_id"):
            await _tell(toast)
            await _edit_hidden(bot, board, uid, text, markup, only_markup)
            return
        if _queue(("eph_new", bot, query, uid, text, markup, board, toast or "Ваше море", bind_callback)):
            return
        sent = await _ephemeral(bot, query, uid, text, markup, bind_callback)
        if sent is not None:
            _remember_hidden(board, sent)
            await _tell(toast or "Ваше море")
            return

    if board.get("mode") == "ephemeral" and board.get("ephemeral_id"):
        if await _edit_hidden(bot, board, uid, text, markup, only_markup):
            await _tell(toast)
            return
        board["mode"] = "none"

    if board.get("mode") == "dm" and board.get("message_id"):
        if await _save(board["chat_id"], board["message_id"]):
            await _tell(toast or "Море обновлено")
            return
        board["mode"] = "none"

    if query is None:
        return

    sent = await _dm(bot, uid, text, markup)
    if sent is not None and not _is_public_target(sent.chat.id, sent.message_id, game):
        board["mode"] = "dm"
        board["chat_id"] = int(sent.chat.id)
        board["message_id"] = int(sent.message_id)
        await _tell("Море открыто в личке: в этом чате скрытое сообщение не ушло.")
        return
    await _tell("Напишите боту /start и нажмите «Моё море» ещё раз.", alert=True)


def _plain_name(user) -> str:
    """Имя как в топе: кликабельная ссылка t.me при наличии username."""
    from bot.funcs.person_html import person_name_html

    first = getattr(user, "first_name", None) if user is not None else None
    username = getattr(user, "username", None) if user is not None else None
    return person_name_html(first, username, empty="Игрок")


async def _banned(uid: int) -> bool:
    try:
        from main import db
        return bool(await db.is_user_banned(uid))
    except Exception:
        return False


async def _desk_reason(bet: int) -> str:
    try:
        from bot.runtime.game_desk.live import bets, is_maintenance, is_on
    except Exception:
        return ""
    if is_maintenance("sea"):
        return "Морской бой на паузе."
    if not is_on("sea"):
        return "Морской бой выключен."
    if int(bet) > 0:
        low, high = bets("sea")
        if int(bet) < int(low):
            return f"Минимальная ставка {_num(low)}."
        if int(high) > 0 and int(bet) > int(high):
            return f"Максимальная ставка {_num(high)}."
    return ""


async def _door_blocks(message) -> bool:
    if message is None:
        return False
    try:
        from bot.funcs.group_door import guard_action
        return bool(await guard_action(message, "play"))
    except Exception as exc:
        print(f"[SEA] door {type(exc).__name__}")
        return False


async def _farm(uid: int, participants) -> str:
    try:
        from datetime import datetime
        from main import _format_hms, _pair_seconds_left, db
    except Exception as exc:
        print(f"[SEA] farm import {type(exc).__name__}")
        return ""
    try:
        people = {int(item) for item in participants}
        try:
            inviter = await db.get_refferer_id_or_error(uid)
        except LookupError:
            inviter = None
        if inviter and int(inviter) in people:
            secs = await _pair_seconds_left(db, uid, int(inviter), now=datetime.now())
            if secs > 0:
                return f"Пока нельзя сесть с тем, кто пригласил вас в Кут. Осталось {_format_hms(secs)}"
        invitees = await db.get_invitees_in(inviter_id=uid, candidates=people)
        left = None
        for invitee in invitees or []:
            secs = await _pair_seconds_left(db, uid, int(invitee), now=datetime.now())
            if secs > 0:
                left = secs if left is None else min(left, secs)
        if left is not None:
            return f"Пока нельзя сесть с тем, кого вы пригласили в Кут. Осталось {_format_hms(left)}"
    except Exception as exc:
        print(f"[SEA] farm {type(exc).__name__}")
    return ""


async def _pay(winner: int, loser: int, stake: int):
    stake = int(stake)
    net = stake
    gfund = None
    if stake <= 0:
        try:
            from main import bot1, db, ref_coin
            await db.update_user_wins(int(winner), 1, bot1, ref_coin)
            await db.update_user_loose(int(loser), 1, bot1, ref_coin)
            await db.update_game_last_activity(int(winner))
            await db.update_game_last_activity(int(loser))
        except Exception as exc:
            print(f"[SEA] score {type(exc).__name__}")
        return 0, None
    try:
        from main import bot1, db
        from bot.funcs.growth_fund import apply_commission_pvp
        gfund = await apply_commission_pvp(
            db, bot1, game="sea", pot=stake,
            winner_id=int(winner), loser_ids=[int(loser)],
        )
        if gfund:
            net = max(0, stake - int(gfund["commission"]))
    except Exception as exc:
        print(f"[SEA] commission {type(exc).__name__}")
        gfund = None
        net = stake
    try:
        from main import bot1, check_bet_and_set_item, db, ref_coin
        await db.update_user_balance(int(winner), f"+{int(net)}")
        await db.update_user_balance(int(loser), f"-{int(stake)}")
        await db.update_user_winamount(int(winner), int(net))
        await db.update_user_wins(int(winner), 1, bot1, ref_coin)
        await db.update_user_loose(int(loser), 1, bot1, ref_coin)
        await db.update_game_last_activity(int(winner))
        await db.update_game_last_activity(int(loser))
        await db.cutehistory_plus(int(winner), int(net), "+ морской бой")
        await db.cutehistory_minus(int(loser), int(stake), "- морской бой")
        await check_bet_and_set_item(int(winner), int(stake))
    except Exception as exc:
        print(f"[SEA] pay {type(exc).__name__}")
    return net, gfund


def _commission_markup(gfund):
    if not gfund:
        return EMPTY
    try:
        from bot.funcs.growth_fund import build_commission_button
        return InlineKeyboardMarkup(inline_keyboard=[[build_commission_button(gfund)]])
    except Exception as exc:
        print(f"[SEA] commission button {type(exc).__name__}")
        return EMPTY


def _soften_deadline(game, key: str, seconds: float, *, fresh: bool) -> None:
    """После рестарта не закрываем стол из‑за простоя бота."""
    now = time.time()
    if fresh:
        game[key] = now + float(seconds)
        return
    try:
        deadline = float(game.get(key) or 0)
    except (TypeError, ValueError):
        deadline = 0.0
    # Просроченный или почти истёкший срок — полный интервал заново.
    if deadline <= now + 3.0:
        game[key] = now + float(seconds)


def _arm_place(store, game, fresh: bool = True) -> None:
    current = None
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    old = game.get("place_task")
    if old is not None and old is not current and not old.done():
        old.cancel()
    _soften_deadline(game, "place_deadline", PLACE_SECONDS, fresh=fresh)
    game["place_token"] = int(game.get("place_token", 0)) + 1
    token = game["place_token"]
    game["place_task"] = asyncio.create_task(_place_deadline(store, game["id"], token))


def _arm_lobby(store, game, fresh: bool = True) -> None:
    current = None
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    old = game.get("lobby_task")
    if old is not None and old is not current and not old.done():
        old.cancel()
    _soften_deadline(game, "lobby_deadline", LOBBY_SECONDS, fresh=fresh)
    game["lobby_token"] = int(game.get("lobby_token", 0)) + 1
    token = game["lobby_token"]
    game["lobby_task"] = asyncio.create_task(_lobby_deadline(store, game["id"], token))


def _arm_turn(store, game, fresh: bool = True) -> None:
    current = None
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    old = game.get("turn_task")
    if old is not None and old is not current and not old.done():
        old.cancel()
    _soften_deadline(game, "turn_deadline", TURN_SECONDS, fresh=fresh)
    game["turn_token"] = int(game.get("turn_token", 0)) + 1
    token = game["turn_token"]
    game["turn_task"] = asyncio.create_task(_turn_deadline(store, game["id"], token))


async def _close_quiet(store, game, text: str) -> None:
    if game.get("phase") == "over":
        return
    game["phase"] = "over"
    _drop_task(game, "lobby_task")
    _drop_task(game, "place_task")
    _drop_task(game, "turn_task")
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, text, EMPTY)
    await _drop_all_hidden(bot, game)
    gid = int(game["id"])
    store.pop(gid, None)
    _LOCKS.pop(gid, None)
    _drop_pace(gid)
    _keep()


async def _finish(store, game, winner: int, reason: str) -> None:
    if game.get("phase") == "over":
        return
    game["phase"] = "over"
    _drop_task(game, "lobby_task")
    _drop_task(game, "place_task")
    _drop_task(game, "turn_task")
    loser = _other(game, winner)
    how = {
        "ships": "Все корабли соперника потоплены.",
        "give": "Соперник сдался.",
        "skip": "Соперник пропустил три хода.",
    }.get(reason, "Партия закончена.")
    net, gfund = await _pay(winner, loser, int(game["bet"]))
    game["winner"] = int(winner)
    game["end_how"] = how
    game["net"] = int(net)
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, end_text(game, winner, how, net), end_markup(game, winner, gfund))
    await _drop_all_hidden(bot, game)
    gid = int(game["id"])
    store.pop(gid, None)
    _LOCKS.pop(gid, None)
    _drop_pace(gid)
    _keep()


async def _begin_place(store, game) -> None:
    _drop_task(game, "lobby_task")
    players = [int(item) for item in game["participants"][:2]]
    game["players"] = players
    game["phase"] = "place"
    game["boards"] = {}
    spec = game_fleet(game)
    for uid in players:
        board = _blank_board()
        board["ships"] = scatter(fleet=spec)
        game["boards"][uid] = board
    game["shots"] = {uid: {"hit": set(), "miss": set()} for uid in players}
    game["skips"] = {uid: 0 for uid in players}
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, place_text(game), place_public_markup(game))
    _arm_place(store, game)


async def _begin_fight(store, game) -> None:
    _drop_task(game, "place_task")
    players = [int(item) for item in game["players"]]
    first = random.choice(players)
    game["phase"] = "fight"
    game["turn"] = first
    game["first"] = first
    game["aim_page"] = 0
    game["note"] = ""
    game["shots"] = {uid: {"hit": set(), "miss": set()} for uid in players}
    game["skips"] = {uid: 0 for uid in players}
    bot = game.get("bot")
    if bot is not None:
        if not await _show(bot, game, fight_text(game), _aim(game)):
            await _show(bot, game, fight_text(game), _aim(game))
        await asyncio.gather(*(
            _paint_secret(bot, game, uid, query=None) for uid in players
        ))
    _arm_turn(store, game)


async def _lobby_deadline(store, gid: int, token: int) -> None:
    try:
        game = store.get(gid)
        left = float(game.get("lobby_deadline") or 0) - time.time() if game else 0
        if left > 0:
            await asyncio.sleep(left)
    except asyncio.CancelledError:
        return
    try:
        async with _lock(gid):
            game = store.get(gid)
            if not game or game.get("phase") != "lobby" or int(game.get("lobby_token", 0)) != int(token):
                return
            await _close_quiet(
                store, game,
                "🚢 <b>Морской бой</b>\nВремя ожидания вышло.\nПартия закрыта, куты на месте.",
            )
    except asyncio.CancelledError:
        return
    except Exception as exc:
        print(f"[SEA] lobby timer {type(exc).__name__}")


async def _place_deadline(store, gid: int, token: int) -> None:
    try:
        game = store.get(gid)
        left = float(game.get("place_deadline") or 0) - time.time() if game else 0
        if left > 0:
            await asyncio.sleep(left)
    except asyncio.CancelledError:
        return
    try:
        async with _lock(gid):
            game = store.get(gid)
            if not game or game.get("phase") != "place" or int(game.get("place_token", 0)) != int(token):
                return
            ready = game.get("players") and all(game["boards"][uid]["ready"] for uid in game["players"])
            if ready:
                return
            await _close_quiet(
                store, game,
                "🚢 <b>Морской бой</b>\nВремя вышло. Не все корабли на воде.\nПартия снята, куты на месте.",
            )
    except asyncio.CancelledError:
        return
    except Exception as exc:
        print(f"[SEA] place timer {type(exc).__name__}")


async def _turn_deadline(store, gid: int, token: int) -> None:
    try:
        game = store.get(gid)
        left = float(game.get("turn_deadline") or 0) - time.time() if game else 0
        if left > 0:
            await asyncio.sleep(left)
    except asyncio.CancelledError:
        return
    try:
        async with _lock(gid):
            game = store.get(gid)
            if not game or game.get("phase") != "fight" or int(game.get("turn_token", 0)) != int(token):
                return
            uid = int(game["turn"])
            game["skips"][uid] = int(game["skips"].get(uid, 0)) + 1
            if game["skips"][uid] >= int(MISS_LIMIT):
                await _finish(store, game, _other(game, uid), "skip")
                return
            game["turn"] = _other(game, uid)
            game["note"] = "Прошлый ход пропущен."
            bot = game.get("bot")
            if bot is not None:
                await _show(bot, game, fight_text(game), _aim(game))
            _arm_turn(store, game)
            _keep()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        print(f"[SEA] turn timer {type(exc).__name__}")


async def _join(query, game, uid: int) -> None:
    if game["phase"] != "lobby":
        await _ack(query, "Партия уже началась.")
        return
    if uid == int(game["creator"]) or uid in game["participants"]:
        await _ack(query, "Вы уже в этой партии.", alert=True)
        return
    if len(game["participants"]) >= 2:
        await _ack(query, "Мест нет.")
        return
    if await _banned(uid):
        await _ack(query, "Игра для вас закрыта.", alert=True)
        return
    bet = int(game["bet"])
    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        have = await read_stake_balance(uid)
        if int(have or 0) < bet:
            await _ack(query, "Недостаточно кут.", alert=True)
            return
    reason = await _farm(uid, game["participants"])
    if reason:
        await _ack(query, reason, alert=True)
        return
    game["participants"].append(uid)
    game["links"][uid] = _plain_name(getattr(query, "from_user", None))
    await _ack(query, "Вы в партии")
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, lobby_text(game), lobby_markup(game))


async def _start(query, store, game, uid: int) -> None:
    if game["phase"] != "lobby":
        await _ack(query, "Партия уже началась.")
        return
    if uid != int(game["creator"]):
        await _ack(query, "Начинает тот, кто открыл партию.", alert=True)
        return
    if len(game["participants"]) < 2:
        await _ack(query, "Нужен второй игрок.", alert=True)
        return
    if await _door_blocks(getattr(query, "message", None)):
        await _ack(query)
        return
    reason = await _desk_reason(int(game["bet"]))
    if reason:
        await _ack(query, reason, alert=True)
        return
    bet = int(game["bet"])
    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        for person in game["participants"]:
            have = await read_stake_balance(person)
            if int(have or 0) < bet:
                await _ack(query, "У кого-то из игроков не хватает кут.", alert=True)
                return
    await _ack(query)
    await _begin_place(store, game)


async def _give_up(query, store, game, uid: int) -> None:
    phase = game.get("phase")
    if phase == "over":
        await _ack(query, "Партия уже закрыта")
        return
    armed = game.get("confirm") == ("g", uid)
    if phase == "lobby":
        people = [int(item) for item in game.get("participants") or []]
        if uid not in people:
            await _ack(query, "Вы не за этим столом.")
            return
        if not armed:
            game["confirm"] = ("g", uid)
            game.setdefault("touch", {})[uid] = time.monotonic()
            if uid == int(game["creator"]):
                await _ack(query, "Стол закроется, куты останутся. Нажмите ещё раз.", alert=True)
            else:
                await _ack(query, "Вы выйдете из стола. Нажмите ещё раз.", alert=True)
            return
        game["confirm"] = None
        if uid == int(game["creator"]):
            await _ack(query, "Стол закрыт")
            await _close_quiet(store, game, "🚢 <b>Морской бой</b>\nСтол закрыт. Куты на месте.")
            return
        game["participants"] = [item for item in people if item != uid]
        await _ack(query, "Вы вышли из стола")
        bot = game.get("bot")
        if bot is not None:
            await _show(bot, game, lobby_text(game), lobby_markup(game))
        return
    if uid not in [int(item) for item in game.get("players") or []]:
        await _ack(query, "Вы не в этой партии.")
        return
    if not armed:
        game["confirm"] = ("g", uid)
        game.setdefault("touch", {})[uid] = time.monotonic()
        if phase == "fight":
            await _ack(query, "Победа уйдёт сопернику. Нажмите «Сдаться» ещё раз.", alert=True)
        else:
            await _ack(query, "Партия снимется, куты останутся. Нажмите «Выйти» ещё раз.", alert=True)
        return
    game["confirm"] = None
    if phase == "place":
        await _ack(query, "Партия снята")
        who = _bold(game["links"].get(uid, "Игрок"))
        await _close_quiet(store, game, f"🚢 <b>Морской бой</b>\n{who} вышел.\nПартия снята, куты на месте.")
        return
    if phase == "fight":
        await _ack(query, "Вы сдались")
        await _finish(store, game, _other(game, uid), "give")
        return
    await _ack(query, "Партия уже закрыта")


_FLEET_ALERT = "Ваши корабли"


async def _pin_ships_link(bot, game, uid: int) -> None:
    """После отправки карты дописать url-кнопку «К кораблям», если есть message_id."""
    if not hidden_message_url(game, uid):
        return
    board = (game.get("boards") or {}).get(int(uid))
    if not isinstance(board, dict) or bot is None:
        return
    text, markup = _secret_view(game, uid)
    if board.get("mode") == "ephemeral" and board.get("ephemeral_id"):
        await _eph_edit_now(
            bot, int(board["chat_id"]), int(uid), int(board["ephemeral_id"]),
            text, markup, False,
        )
    elif board.get("mode") == "dm" and board.get("message_id"):
        try:
            await bot.edit_message_text(
                chat_id=int(board["chat_id"]),
                message_id=int(board["message_id"]),
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            if "not modified" not in str(exc).lower():
                print(f"[SEA] pin link {type(exc).__name__}")


async def _reveal_ships(query, game, uid: int, *, toast: str) -> None:
    """
    Показать скрытую карту кораблей.

    Важно: t.me/c/... в answerCallbackQuery Telegram обычно отклоняет.
    Надёжный путь — новое ephemeral с callback_query_id (bind): клиент
    сам открывает скрытое сообщение после нажатия «Мои корабли».
    """
    bot = game.get("bot")
    board = game["boards"].setdefault(uid, _blank_board())
    text, markup = _secret_view(game, uid)

    # Старую карту убираем и шлём новую с bind — так карта реально всплывает.
    await _drop_hidden(bot, game, uid)
    sent = await _ephemeral(bot, query, uid, text, markup, bind_callback=True)
    if sent is not None:
        _remember_hidden(board, sent)
        await _pin_ships_link(bot, game, uid)
        _keep()
        return

    # Без bind: пробуем отправить и прыгнуть по ссылке (если клиент примет).
    sent = await _ephemeral(bot, query, uid, text, markup, bind_callback=False)
    if sent is not None:
        _remember_hidden(board, sent)
        await _pin_ships_link(bot, game, uid)
        jump = hidden_message_url(game, uid)
        if jump and await _ack_jump(query, jump):
            _keep()
            return
        await _ack_now(query, toast)
        _keep()
        return

    sent = await _dm(bot, uid, text, markup)
    if sent is not None and not _is_public_target(sent.chat.id, sent.message_id, game):
        _remember_hidden(board, sent)
        await _pin_ships_link(bot, game, uid)
        jump = hidden_message_url(game, uid)
        if jump and await _ack_jump(query, jump):
            _keep()
            return
        await _ack_now(query, "Корабли открыты в личке")
        _keep()
        return
    await _ack_now(query, "Напишите боту /start и нажмите ещё раз.", alert=True)


async def _open_sea(query, game, uid: int) -> None:
    if uid not in game.get("boards", {}):
        await _ack(query, "Вы не в этой партии.")
        return
    if game.get("phase") not in {"place", "fight"}:
        await _ack(query, "Море откроется, когда партия начнётся.")
        return
    await _reveal_ships(query, game, uid, toast="Ваше море")


async def _open_fleet(query, game, uid: int) -> None:
    if uid not in game.get("boards", {}):
        await _ack(query, "Вы не в этой партии.")
        return
    if game.get("phase") not in {"place", "fight"}:
        await _ack(query, "Море откроется, когда партия начнётся.")
        return
    await _reveal_ships(query, game, uid, toast=_FLEET_ALERT)


async def _turn_page(query, game, uid: int, page: int) -> None:
    if page < 0 or page >= page_count():
        await _ack(query, "Кнопка устарела")
        return
    surface = _surface(query, game)
    if game.get("phase") == "fight" and surface == "public":
        if page == int(game["aim_page"]):
            await _ack(query)
            return
        game["aim_page"] = page
        await _ack(query)
        bot = game.get("bot")
        if bot is not None and not await _show_markup(bot, game, _aim(game)):
            await _show(bot, game, fight_text(game), _aim(game))
        return
    if game.get("phase") == "place" and uid in game.get("boards", {}) and surface != "public":
        board = game["boards"][uid]
        if page == int(board["page"]):
            await _ack(query)
            return
        board["page"] = page
        await _paint_secret(game.get("bot"), game, uid, query, only_markup=True)
        return
    await _ack(query)


async def _pick_length(query, game, uid: int, length: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    if int(length) not in _spec(game_fleet(game)):
        await _ack(query, "Нет такого корабля.")
        return
    board = game["boards"][uid]
    if board["ready"]:
        await _ack(query, "Корабли уже готовы. Ожидаем соперника.", alert=True)
        return
    board["hand"] = True
    board["tool"] = int(length)
    board["hold"] = None
    board["ready"] = False
    await _paint_secret(game.get("bot"), game, uid, query)


async def _flip(query, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    board["across"] = not board["across"]
    way = "вправо" if board["across"] else "вниз"
    await _paint_secret(game.get("bot"), game, uid, query, toast=f"Нос пойдёт {way}.")


async def _undo(query, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    if not board["ships"]:
        await _ack(query, "Убирать нечего.")
        return
    was = board["ready"]
    board["ships"] = board["ships"][:-1]
    board["ready"] = False
    board["pick"] = next_length(board["ships"], board["pick"], game_fleet(game))
    await _paint_secret(game.get("bot"), game, uid, query, toast="Последний корабль убран.")
    if was:
        bot = game.get("bot")
        if bot is not None:
            await _show(bot, game, place_text(game), place_public_markup(game))


async def _ready(query, store, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    fleet = game_fleet(game)
    budget = hand_budget(fleet)
    if board.get("hand"):
        if not hand_ready(board["ships"], budget, fleet):
            left = budget - cells_used(board["ships"])
            if left > 0:
                note = f"Осталось занять клеток: {max(0, left)}.\n{remain_line(board['ships'], fleet)}"
            elif not fleet_ready(board["ships"], fleet):
                note = remain_line(board["ships"], fleet)
                if note == "Все корабли на воде.":
                    note = "Проверьте длины кораблей — нужен точный набор сложности."
            else:
                note = "Проверьте корабли."
            await _ack(query, note, alert=True)
            return
    elif not fleet_ready(board["ships"], fleet):
        await _ack(query, remain_line(board["ships"], fleet), alert=True)
        return
    board["ready"] = True
    if all(game["boards"][person]["ready"] for person in game["players"]):
        surface = _surface(query, game)
        if surface == "ephemeral":
            await _begin_fight(store, game)
            await _paint_secret(game.get("bot"), game, uid, query, toast="Бой начался. Стреляйте в общем сообщении.")
            return
        await _ack(query, "Бой начался. Стреляйте в общем сообщении.")
        await _begin_fight(store, game)
        return
    # show_alert: игрок явно видит, что готов и ждёт соперника.
    await _ack(
        query,
        "Вы готовы к бою, осталось подождать пока противник выставит свои корабли",
        alert=True,
    )
    await _paint_secret(game.get("bot"), game, uid, query, quiet=True)
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, place_text(game), place_public_markup(game))


async def _place_cell(query, game, uid: int, r: int, c: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query, "Сейчас корабли не ставят.")
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море».", alert=True)
        return
    board = game["boards"][uid]
    if board["ready"]:
        await _ack(query, "Ожидаем соперника.")
        return
    if board.get("hand"):
        await _place_hand(query, game, uid, r, c)
        return
    index = ship_index(board["ships"], r, c)
    if index is None:
        await _ack(query, "Нажмите на корабль.")
        return
    board["hold"] = index
    board["ready"] = False
    await _paint_secret(game.get("bot"), game, uid, query, toast="Двигайте стрелками.")


async def _place_hand(query, game, uid: int, r: int, c: int) -> None:
    board = game["boards"][uid]
    index = ship_index(board["ships"], r, c)
    if index is not None:
        length = len(board["ships"][index])
        board["ships"] = _without(board["ships"], index)
        board["ready"] = False
        title = SHIP_TITLE.get(length, "Корабль")
        await _paint_secret(game.get("bot"), game, uid, query, toast=f"{title} убран.")
        return
    fleet = game_fleet(game)
    before = list(board["ships"])
    ok, ships, code = hand_put(before, r, c, hand_budget(fleet), fleet)
    if not ok:
        await _ack(query, hand_fail_text(code, fleet), alert=True)
        return
    board["ships"] = ships
    board["ready"] = False
    # Какой корабль изменился — для тоста.
    toast = _HAND_NOTE.get(code, "Корабль поставлен.")
    if code == "new":
        toast = "Катер поставлен. Удлините по прямой или начните другой."
    elif code == "grow":
        grown = None
        before_lens = Counter(len(ship) for ship in before)
        after_lens = Counter(len(ship) for ship in ships)
        for length in sorted(after_lens, reverse=True):
            if after_lens[length] > before_lens[length]:
                grown = length
                break
        if grown:
            toast = f"Теперь это {SHIP_TITLE.get(grown, 'корабль').lower()}."
        else:
            toast = "Корабль стал длиннее."
    await _paint_secret(game.get("bot"), game, uid, query, toast=toast)


async def _auto(query, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море».", alert=True)
        return
    board = game["boards"][uid]
    board["ships"] = scatter(fleet=game_fleet(game))
    board["hold"] = None
    board["hand"] = False
    board["tool"] = None
    board["ready"] = False
    await _paint_secret(game.get("bot"), game, uid, query, toast="Новые корабли.")


async def _by_hand(query, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море».", alert=True)
        return
    board = game["boards"][uid]
    if board["ready"]:
        await _ack(query, "Ожидаем соперника.")
        return
    if not board.get("hand"):
        board["ships"] = []
    board["hand"] = True
    board["hold"] = None
    board["tool"] = None
    board["ready"] = False
    await _paint_secret(game.get("bot"), game, uid, query, toast="Нажмите свободную клетку.")


_STEPS = {"u": (-1, 0), "d": (1, 0), "l": (0, -1), "r": (0, 1)}


async def _nudge(query, game, uid: int, way: str) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море».", alert=True)
        return
    board = game["boards"][uid]
    if board.get("hand") and way == "t":
        board["across"] = not bool(board.get("across", True))
        await _paint_secret(game.get("bot"), game, uid, query, toast="→" if board["across"] else "↓")
        return
    hold = board.get("hold")
    if hold is None:
        await _ack(query, "Сначала нажмите на корабль.")
        return
    if way == "t":
        ok, ships = turn_ship(board["ships"], int(hold))
        toast = "Корабль повёрнут." if ok else "Так не поворачивается."
    else:
        step = _STEPS.get(way)
        if step is None:
            await _ack(query, "Кнопка устарела")
            return
        ok, ships = shift_ship(board["ships"], int(hold), step[0], step[1])
        toast = "Готово." if ok else "Туда нельзя."
    if ok:
        board["ships"] = ships
        board["ready"] = False
    await _paint_secret(game.get("bot"), game, uid, query, toast=toast)


async def _shoot(query, store, game, uid: int, r: int, c: int) -> None:
    if game.get("phase") != "fight":
        await _ack(query, "Сейчас корабли ещё ставят.")
        return
    if _surface(query, game) != "public":
        await _ack(query, "Стреляйте кнопками в общем сообщении.")
        return
    if uid not in [int(item) for item in game.get("players") or []]:
        await _ack(query, "Вы не в этой партии.")
        return
    if uid != int(game["turn"]):
        await _ack(query, "Сейчас ход соперника. «Мои корабли» откроет ваше море.")
        return
    foe = _other(game, uid)
    box = game["shots"][uid]
    kind, hits, misses = apply_shot(game["boards"][foe]["ships"], box["hit"], box["miss"], r, c)
    if kind in {"repeat", "halo"}:
        await _ack(query, _TOAST[kind])
        return
    box["hit"] = hits
    box["miss"] = misses
    game["note"] = ""
    await _ack(query, _TOAST[kind])
    if kind == "win":
        await _finish(store, game, uid, "ships")
        return
    if kind == "miss":
        game["turn"] = foe
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, fight_text(game), _aim(game))
        # Соперник видит попадание/мимо по своим кораблям;
        # стрелявший — сразу то же «мимо» на своём скрытом поле.
        await _paint_secret(bot, game, foe, query=None)
        await _paint_secret(bot, game, uid, query=None)
    _arm_turn(store, game)


async def _level(query, game, uid: int, key: str) -> None:
    if game.get("phase") != "lobby":
        await _ack(query, "Сложность выбирается до начала партии.")
        return
    spec = _LEVEL.get(str(key or ""))
    if not spec:
        await _ack(query, "Кнопка устарела")
        return
    _key, _title, fleet, note = spec
    if uid != int(game.get("creator") or 0):
        await _ack(query, "Сложность выбирает создатель партии.", alert=True)
        return
    game["level"] = _key
    game["fleet"] = tuple(int(n) for n in fleet)
    await _ack(query, note, alert=True)
    bot = game.get("bot")
    if bot is not None:
        await _show(bot, game, lobby_text(game), lobby_markup(game))


async def _route(query, store, game, action: str, parts, uid: int) -> None:
    if action not in {"g", "q"}:
        game["confirm"] = None
    if action == "k":
        await _level(query, game, uid, parts[1] if len(parts) > 1 else "")
        return
    if action == "q":
        await _ack(query, guide_text(str(game.get("phase") or "")), alert=True)
        return
    if action == "j":
        await _join(query, game, uid)
        return
    if action == "s":
        await _start(query, store, game, uid)
        return
    if action == "g":
        await _give_up(query, store, game, uid)
        return
    if action == "f":
        await _open_fleet(query, game, uid)
        return
    if action == "d":
        await _open_sea(query, game, uid)
        return
    if action == "p":
        try:
            page = int(parts[1])
        except (IndexError, ValueError):
            await _ack(query, "Кнопка устарела")
            return
        await _turn_page(query, game, uid, page)
        return
    if action == "l":
        try:
            length = int(parts[1])
        except (IndexError, ValueError):
            await _ack(query, "Кнопка устарела")
            return
        await _pick_length(query, game, uid, length)
        return
    if action == "o":
        await _flip(query, game, uid)
        return
    if action == "u":
        await _undo(query, game, uid)
        return
    if action == "a":
        await _auto(query, game, uid)
        return
    if action == "b":
        await _by_hand(query, game, uid)
        return
    if action == "m":
        await _nudge(query, game, uid, parts[1] if len(parts) > 1 else "")
        return
    if action == "r":
        await _ready(query, store, game, uid)
        return
    if action == "c":
        try:
            idx = int(parts[1])
        except (IndexError, ValueError):
            await _ack(query, "Кнопка устарела")
            return
        r, c = divmod(idx, SIZE)
        if not (0 <= r < SIZE and 0 <= c < SIZE):
            await _ack(query, "Кнопка устарела")
            return
        if game.get("phase") == "place":
            await _place_cell(query, game, uid, r, c)
        else:
            await _shoot(query, store, game, uid, r, c)
        return
    await _ack(query)


async def _inline_new(query, store, uid: int, parts) -> None:
    try:
        owner = int(parts[0])
        bet = int(parts[1])
    except (IndexError, ValueError):
        await _ack(query, "Кнопка устарела")
        return
    if uid != owner or bet < 0:
        await _ack(query, "Эту партию открывает тот, кто её вызвал.", alert=True)
        return
    msg = getattr(query, "message", None)
    inline_id = str(getattr(query, "inline_message_id", "") or "")
    chat_id = 0
    message_id = 0
    if msg is not None and getattr(msg, "chat", None) is not None:
        chat_id = int(msg.chat.id)
        message_id = int(getattr(msg, "message_id", 0) or 0)
    if not inline_id and not message_id:
        _OPEN_AT.pop(uid, None)
        await _ack(query, "Сообщение уже не найти.", alert=True)
        return
    reason = await _desk_reason(bet)
    if reason:
        _OPEN_AT.pop(uid, None)
        await _ack(query, reason, alert=True)
        return
    if msg is not None and await _door_blocks(msg):
        _OPEN_AT.pop(uid, None)
        await _ack(query)
        return
    if await _banned(uid):
        _OPEN_AT.pop(uid, None)
        await _ack(query, "Игра для вас закрыта.", alert=True)
        return
    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        have = await read_stake_balance(uid)
        if int(have or 0) < bet:
            _OPEN_AT.pop(uid, None)
            if msg is not None:
                await _need_funds(msg, uid, bet)
                await _ack(query)
            else:
                await _ack(query, "Недостаточно кут.", alert=True)
            return
    gid = next(_IDS)
    game = _fresh(gid, chat_id, message_id, uid, bet, "seai:")
    game["inline_id"] = inline_id
    game["bot"] = getattr(query, "bot", None)
    game["links"][uid] = _plain_name(getattr(query, "from_user", None))
    store[gid] = game
    ok = await _show(game["bot"], game, lobby_text(game), lobby_markup(game))
    if not ok:
        store.pop(gid, None)
        _OPEN_AT.pop(uid, None)
        await _ack(query, "Не вышло открыть партию. Нажмите ещё раз.", alert=True)
        return
    _arm_lobby(store, game)
    await _ack(query, "Партия открыта")


async def _apply(job) -> None:
    kind = job[0]
    try:
        if kind == "ack":
            await _ack_now(job[1], job[2], job[3])
        elif kind == "edit":
            await _edit(job[1], job[2], job[3], job[4], job[5])
        elif kind == "markup":
            await _markup_only(job[1], job[2], job[3], job[4])
        elif kind == "touch":
            await _touch_targets(job[1], job[2], job[3])
        elif kind == "markpub":
            bot, targets, markup = job[1], job[2], job[3]
            for target in targets:
                try:
                    await bot.edit_message_reply_markup(**target, reply_markup=markup)
                    return
                except Exception as exc:
                    if "not modified" in str(exc).lower():
                        return
        elif kind == "eph_edit":
            await _eph_edit_now(job[1], job[2], job[3], job[4], job[5], job[6], job[7])
        elif kind == "eph_new":
            _bot, query, uid, text, markup, board, toast = job[1:8]
            bind = job[8] if len(job) > 8 else True
            sent = await _ephemeral(_bot, query, uid, text, markup, bind)
            if sent is not None:
                _remember_hidden(board, sent)
                if toast:
                    await _ack_now(query, toast)
                return
            sent = await _dm(_bot, uid, text, markup)
            if sent is not None:
                _remember_hidden(board, sent)
                await _ack_now(query, "Море в личке")
                return
            await _ack_now(query, "Напишите боту /start", alert=True)
    except Exception as exc:
        print(f"[SEA] apply {type(exc).__name__}")


def _follow(gid: int, jobs: list):
    if not jobs:
        return None
    prev = _TAILS.pop(int(gid), None)
    if prev is not None and not prev.done():
        prev.cancel()

    async def run():
        opening = [
            job for job in jobs
            if job[0] == "eph_new" and (len(job) < 9 or job[8])
        ]
        acks = [job for job in jobs if job[0] == "ack"]
        rest = [job for job in jobs if job not in opening and job[0] != "ack"]
        try:
            for job in opening:
                await _apply(job)
            for job in acks:
                await _apply(job)
            for job in rest:
                await _apply(job)
        except asyncio.CancelledError:
            return

    task = asyncio.create_task(run())
    _TAILS[int(gid)] = task
    return task


async def _flush_jobs(gid: int, jobs: list) -> None:
    """Кружок на кнопке гаснет сразу. Правки поля уходят следом отдельной задачей."""
    if not jobs:
        return
    bind_open = [
        job for job in jobs
        if job[0] == "eph_new" and (len(job) < 9 or job[8])
    ]
    if bind_open:
        _follow(gid, jobs)
        return
    for job in jobs:
        if job[0] == "ack":
            await _ack_now(job[1], job[2], job[3])
    rest = [job for job in jobs if job[0] != "ack"]
    _follow(gid, rest)


async def _press(query, store) -> None:
    data = str(getattr(query, "data", "") or "")
    action, parts = _split(data)
    if not action or action == "x":
        await _ack_now(query)
        return
    if action == "h":
        kind = parts[1] if len(parts) > 1 else ""
        await _ack_now(query, label_hint(kind))
        return
    user = getattr(query, "from_user", None)
    if user is None or not getattr(user, "id", None):
        await _ack_now(query, "Напишите от своего имени.")
        return
    uid = int(user.id)
    if action == "n":
        if not data.startswith("seai:"):
            await _ack_now(query)
            return
        await _inline_new(query, store, uid, parts)
        return
    try:
        gid = int(parts[0])
    except (IndexError, ValueError):
        await _ack_now(query, "Кнопка устарела")
        return
    jobs = []
    token = _JOBS.set(jobs)
    try:
        async with _lock(gid):
            game = store.get(gid)
            if not game or game.get("phase") in {"over", "dead"}:
                await _ack(query, "Партия уже закрыта")
            else:
                bot = getattr(query, "bot", None)
                if bot is not None:
                    game["bot"] = bot
                await _route(query, store, game, action, parts, uid)
                if action != "q":
                    _touch_save()
    finally:
        _JOBS.reset(token)
    await _flush_jobs(gid, jobs)


def _jsonify(value):
    if isinstance(value, set):
        return ["__set__", [_jsonify(item) for item in value]]
    if isinstance(value, tuple):
        return ["__tuple__", [_jsonify(item) for item in value]]
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def _revive(value):
    if isinstance(value, list) and len(value) == 2 and value[0] == "__set__":
        return {_revive(item) for item in value[1]}
    if isinstance(value, list) and len(value) == 2 and value[0] == "__tuple__":
        return tuple(_revive(item) for item in value[1])
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            name = int(key) if str(key).lstrip("-").isdigit() else key
            out[name] = _revive(item)
        return out
    if isinstance(value, list):
        return [_revive(item) for item in value]
    return value


def _pack_game(game) -> dict:
    skip = {"bot", "place_task", "turn_task", "lobby_task"}
    return {key: _jsonify(value) for key, value in game.items() if key not in skip}


def _prepare_restored(game) -> dict:
    game["bot"] = None
    game["place_task"] = None
    game["turn_task"] = None
    game["lobby_task"] = None
    phase = str(game.get("phase") or "")
    if phase == "lobby":
        _soften_deadline(game, "lobby_deadline", LOBBY_SECONDS, fresh=False)
    elif phase == "place":
        _soften_deadline(game, "place_deadline", PLACE_SECONDS, fresh=False)
    elif phase == "fight":
        _soften_deadline(game, "turn_deadline", TURN_SECONDS, fresh=False)
    return game


_SEA_TABLES_STORE = None
_SEA_INLINE_STORE = None
_SEA_STORE_FAIL = False
_SAVE_TASK = None


def _redis_stores():
    """Redis GameStore — тот же слой, что у шашек; переживает рестарт процесса."""
    global _SEA_TABLES_STORE, _SEA_INLINE_STORE, _SEA_STORE_FAIL
    if _SEA_STORE_FAIL:
        return None, None
    if _SEA_TABLES_STORE is not None and _SEA_INLINE_STORE is not None:
        return _SEA_TABLES_STORE, _SEA_INLINE_STORE
    try:
        from bot.db_create.pklcode import LazyGameStore
        _SEA_TABLES_STORE = LazyGameStore("games_sea")
        _SEA_INLINE_STORE = LazyGameStore("inline_games_sea")
    except Exception as exc:
        _SEA_STORE_FAIL = True
        print(f"[SEA] redis store {type(exc).__name__}")
        return None, None
    return _SEA_TABLES_STORE, _SEA_INLINE_STORE


def _touch_save() -> None:
    global _SAVE_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _keep()
        return
    if _SAVE_TASK is not None and not _SAVE_TASK.done():
        return
    _SAVE_TASK = loop.create_task(_save_later())


async def _save_later() -> None:
    try:
        await asyncio.sleep(0.15)
        _keep()
    except Exception as exc:
        print(f"[SEA] save {type(exc).__name__}")


def _live_map(store: dict) -> dict:
    return {
        int(key): game
        for key, game in store.items()
        if isinstance(game, dict) and game.get("phase") not in {"over", "dead"}
    }


def _sync_redis(store, live: dict) -> None:
    if store is None:
        return
    keep = {str(gid) for gid in live}
    try:
        for key in list(store.keys()):
            if str(key) not in keep:
                try:
                    del store[key]
                except Exception:
                    pass
        for gid, game in live.items():
            store[str(gid)] = _pack_game(game)
        store.save()
    except Exception as exc:
        print(f"[SEA] redis save {type(exc).__name__}")


def _keep() -> None:
    tables = _live_map(TABLES)
    inline = _live_map(INLINE)
    redis_tables, redis_inline = _redis_stores()
    _sync_redis(redis_tables, tables)
    _sync_redis(redis_inline, inline)
    try:
        blob = {
            "tables": {str(key): _pack_game(game) for key, game in tables.items()},
            "inline": {str(key): _pack_game(game) for key, game in inline.items()},
        }
        raw = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
        tmp = _LIVE.with_suffix(".tmp")
        tmp.write_text(raw, encoding="utf-8")
        tmp.replace(_LIVE)
    except Exception as exc:
        print(f"[SEA] file save {type(exc).__name__}")


def _ingest(raw_store, target: dict) -> int:
    count = 0
    if raw_store is None:
        return 0
    try:
        items = list(raw_store.items())
    except Exception:
        return 0
    for key, raw in items:
        game = _revive(raw)
        if not isinstance(game, dict):
            continue
        if game.get("phase") in {"over", "dead"}:
            continue
        try:
            gid = int(game.get("id") or key)
        except (TypeError, ValueError):
            continue
        game["id"] = gid
        target[gid] = _prepare_restored(game)
        count += 1
    return count


def _load_file_blob() -> dict:
    if not _LIVE.exists():
        return {}
    try:
        blob = json.loads(_LIVE.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else {}
    except Exception as exc:
        print(f"[SEA] file load {type(exc).__name__}")
        return {}


def _load() -> None:
    global _IDS
    redis_tables, redis_inline = _redis_stores()
    got = 0
    got += _ingest(redis_tables, TABLES)
    got += _ingest(redis_inline, INLINE)
    if not TABLES and not INLINE:
        blob = _load_file_blob()
        got += _ingest(blob.get("tables") or {}, TABLES)
        got += _ingest(blob.get("inline") or {}, INLINE)
        if TABLES or INLINE:
            # Старый JSON переносим в Redis, чтобы следующий рестарт уже шёл оттуда.
            _keep()
    used = [*TABLES.keys(), *INLINE.keys()]
    _IDS = count((max(used) + 1) if used else 1)
    if got:
        print(f"[SEA] restored {got} live game(s)")


_AWAKE: set = set()


def _wake(store) -> None:
    if id(store) in _AWAKE:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    _AWAKE.add(id(store))
    for game in list(store.values()):
        phase = game.get("phase")
        if phase == "lobby" and (game.get("lobby_task") is None or game["lobby_task"].done()):
            _arm_lobby(store, game, fresh=False)
        elif phase == "place" and (game.get("place_task") is None or game["place_task"].done()):
            _arm_place(store, game, fresh=False)
        elif phase == "fight" and (game.get("turn_task") is None or game["turn_task"].done()):
            _arm_turn(store, game, fresh=False)
    _keep()


async def press(query, store) -> None:
    try:
        _wake(store)
        await _press(query, store)
    except Exception as exc:
        print(f"[SEA] press {type(exc).__name__}")
        await _ack(query, "Не вышло. Нажмите ещё раз.")


async def _need_funds(message, uid: int, bet: int) -> None:
    """То же окно, что у шашек: купить куты или узнать, как их заработать."""
    try:
        from bot.config.config import TOKEN, donate_bet, timeoutdonate
        from main import get_bot_username_by_token, pending_context, send_invoice_to_user
    except Exception as exc:
        print(f"[SEA] funds import {type(exc).__name__}")
        try:
            await message.reply("Недостаточно кут для этой ставки.")
        except Exception:
            pass
        return
    try:
        bot_username = await get_bot_username_by_token(TOKEN)
    except Exception:
        bot_username = None
    bot_username = bot_username or "CuteGamingBot"
    result = int(bet) * donate_bet
    if isinstance(result, float) and result.is_integer():
        stars = str(int(result))
    else:
        stars = str(int(result)) if isinstance(result, int) else str(result)
    pending_context[int(uid)] = {"stars_amount": stars, "sent": False}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💫 Купить {_num(int(bet))} кут 💰",
            url=f"https://t.me/{bot_username}?start=insert_{stars}_+",
        )],
        [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
    ])
    try:
        await message.reply(
            "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"[SEA] funds {type(exc).__name__}")
        return

    async def _later() -> None:
        try:
            await asyncio.sleep(float(timeoutdonate))
            ctx = pending_context.get(int(uid))
            if not ctx or ctx.get("sent"):
                return
            invoice = await send_invoice_to_user(message, stars)
            if invoice is not None:
                ctx["manual_message_id"] = invoice.message_id
        except Exception as exc:
            print(f"[SEA] invoice {type(exc).__name__}")

    asyncio.create_task(_later())


def _find_player_game(chat_id: int, uid: int):
    found = None
    for game in TABLES.values():
        if int(game.get("chat_id") or 0) != int(chat_id):
            continue
        if game.get("phase") not in {"place", "fight"}:
            continue
        boards = game.get("boards") or {}
        players = {int(item) for item in (game.get("players") or [])}
        if int(uid) not in boards and int(uid) not in players:
            continue
        if found is None or int(game.get("message_id") or 0) >= int(found.get("message_id") or 0):
            found = game
    return found


async def _ephemeral_from_chat(bot, chat_id: int, uid: int, text: str, markup):
    if bot is None or not chat_id:
        return None
    try:
        return await bot.send_message(
            chat_id=int(chat_id),
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=int(uid),
            ),
        )
    except Exception as exc:
        print(f"[SEA] ephemeral chat {type(exc).__name__}")
        return None


async def sea_show_mine(message: Message) -> None:
    """Текст «мои корабли» / «моё море» — показать скрытое поле игрока."""
    if not sea_mine_command(getattr(message, "text", "") or ""):
        return
    user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)
    if user is None or not getattr(user, "id", None):
        return
    chat_type = str(getattr(getattr(chat, "type", None), "value", getattr(chat, "type", "")) or "")
    if chat is None or chat_type not in {"group", "supergroup"}:
        try:
            await message.reply("Напишите это в группе, где идёт ваша партия.")
        except Exception:
            pass
        return
    uid = int(user.id)
    game = _find_player_game(int(chat.id), uid)
    if game is None:
        try:
            await message.reply("В этом чате нет вашей активной партии морского боя.")
        except Exception:
            pass
        return
    bot = getattr(message, "bot", None) or game.get("bot")
    game["bot"] = bot
    uname = str(getattr(chat, "username", None) or "").strip()
    if uname:
        game["chat_username"] = uname
    _wake(TABLES)
    text, markup = _secret_view(game, uid)
    board = game["boards"].setdefault(uid, _blank_board())
    if board.get("mode") == "ephemeral" and board.get("ephemeral_id"):
        if await _edit_hidden(bot, board, uid, text, markup):
            _keep()
            return
        board["mode"] = "none"
    if board.get("mode") == "dm" and board.get("message_id"):
        if await _edit(bot, board["chat_id"], board["message_id"], text, markup):
            _keep()
            return
        board["mode"] = "none"
    sent = await _ephemeral_from_chat(bot, int(chat.id), uid, text, markup)
    if sent is not None:
        _remember_hidden(board, sent)
        _keep()
        return
    sent = await _dm(bot, uid, text, markup)
    if sent is not None and not _is_public_target(sent.chat.id, sent.message_id, game):
        _remember_hidden(board, sent)
        try:
            await message.reply("Карта кораблей открыта в личке с ботом.")
        except Exception:
            pass
        _keep()
        return
    try:
        await message.reply("Не удалось открыть море. Нажмите «Моё море» на сообщении партии.")
    except Exception:
        pass


async def sea_open(message: Message) -> None:
    kind, bet = parse_sea(getattr(message, "text", "") or "")
    if kind in {"ignore", "help"}:
        return
    if kind == "bad":
        try:
            await message.reply(
                "🚢 <b>Морской бой</b>\n"
                "Без ставки: <code>морской бой</code>\n"
                "Со ставкой: <code>морской бой 10</code>",
                parse_mode="HTML",
            )
        except Exception as exc:
            print(f"[SEA] format {type(exc).__name__}")
        return
    bet = int(bet or 0)
    from bot.games.group_only import reject_if_private_game
    if await reject_if_private_game(message, "sea", bet):
        return
    user = getattr(message, "from_user", None)
    if user is None or not getattr(user, "id", None):
        try:
            await message.reply("Напишите от своего имени.")
        except Exception:
            pass
        return
    uid = int(user.id)
    if await _banned(uid):
        try:
            await message.reply("Игра для вас закрыта.")
        except Exception:
            pass
        return
    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        have = await read_stake_balance(uid)
        if int(have or 0) < bet:
            await _need_funds(message, uid, bet)
            return
    gid = next(_IDS)
    chat = getattr(message, "chat", None)
    game = _fresh(gid, getattr(chat, "id", 0) or 0, 0, uid, bet, "sea:")
    game["bot"] = getattr(message, "bot", None)
    game["links"][uid] = _plain_name(user)
    game["chat_username"] = str(getattr(chat, "username", None) or "").strip()
    TABLES[gid] = game
    try:
        sent = await message.reply(
            lobby_text(game),
            reply_markup=lobby_markup(game),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        TABLES.pop(gid, None)
        print(f"[SEA] open {type(exc).__name__}")
        try:
            await message.reply("Стол не открылся. Напишите «морской бой» ещё раз.")
        except Exception:
            pass
        return
    game["chat_id"] = int(sent.chat.id)
    game["message_id"] = int(sent.message_id)
    if getattr(sent.chat, "username", None):
        game["chat_username"] = str(sent.chat.username)
    _arm_lobby(TABLES, game)
    _keep()


_load()

router = Router(name="sea")


@router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("sea:"))
async def sea_press(query):
    await press(query, TABLES)
