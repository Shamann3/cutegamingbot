# -*- coding: utf-8 -*-
"""Морской бой в группе.

Все сроки, поле, флот и пауза кнопок — в блоке ниже.
Инлайн живёт отдельно: bot/design/sea_inline.py, правила отсюда не копирует.

Корабли не пишутся в общее сообщение. Игрок ставит их в личке с ботом.
Если бот не может написать первым, то же море уходит скрытым сообщением,
как шёпот: его видит только тот, кто нажал кнопку.
"""
from __future__ import annotations

import asyncio
import html
import random
import time
from collections import Counter
from itertools import count

from aiogram import Router
from aiogram.types import (
    EphemeralMessageParameters,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# --- настройки партии. Меняются здесь, бот читает их при запуске. ---

SIZE = 10
COLS = "ABCDEFGHIJ"          # не короче SIZE. Буквы слева направо, верх поля
FLEET = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)
PLACE_SECONDS = 180          # расстановка. Кто не успел — партия снимается, куты на месте
TURN_SECONDS = 60            # минута на выстрел
MISS_LIMIT = 3               # столько пропущенных минут — и игрок сдаётся
PAGE = 5                     # столбцов на экране кнопок. Слева ещё цифра, в ряду не больше 8
CLICK_GAP = 0.35             # пауза между живыми нажатиями, чтобы поле не копилось в очереди
WORDS = ("морскойбой", "battleship")
PHRASES = ("морской бой", "морская битва")

_IDS = count(1)
TABLES: dict[int, dict] = {}
INLINE: dict[int, dict] = {}
_LOCKS: dict[int, asyncio.Lock] = {}
_OPEN_AT: dict[int, float] = {}
EMPTY = InlineKeyboardMarkup(inline_keyboard=[])
_PLACE_WHY = {
    "edge": "Корабль выходит за край. Выберите клетку левее или выше.",
    "touch": "Слишком близко. Между кораблями нужна пустая клетка, даже углом.",
    "count": "Такой корабль уже стоит. Нажмите другую длину.",
    "length": "Нет такого корабля.",
}
_TOAST = {
    "miss": "Мимо. Ход переходит.",
    "hit": "Попадание. Стреляйте ещё.",
    "sunk": "Потоплен. Вокруг него обводка. Стреляйте ещё.",
    "win": "Все корабли потоплены.",
    "repeat": "Сюда уже стреляли.",
    "halo": "Это обводка потопленного. Тут пусто.",
}
_GUIDE = {
    "lobby": (
        "Второй жмёт «Присоединиться», первый — «Начать». "
        "Корабли ставите у себя, в чат они не попадают. "
        "Потом жмите клетки: попали — ход ваш, мимо — ход другого."
    ),
    "place": (
        "Над полем нажмите корабль. Потом клетку: туда встанет нос. "
        "«Вправо» и «Вниз» меняют сторону. "
        "Между кораблями оставьте пустую клетку. Затем «Готово»."
    ),
    "fight": (
        "Жмите клетку в верхнем море. Попали — стреляйте ещё. Мимо — ход другого. "
        "○ мимо, ✕ ранен, ▫ обводка. «Мои корабли» видны только вам."
    ),
}
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


def fleet_phrase() -> str:
    return ", ".join(str(int(n)) for n in FLEET)


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


def place_ship(ships, length: int, r: int, c: int, across: bool):
    """Нос в (r, c), дальше вправо или вниз. Касание даже углом не проходит."""
    need = Counter(FLEET)
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


def fleet_ready(ships) -> bool:
    return Counter(len(ship) for ship in ships) == Counter(FLEET)


def next_length(ships, prefer=None):
    """Какой корабль ставить дальше. Текущий остаётся, пока такие ещё есть."""
    have = Counter(len(ship) for ship in ships)
    need = Counter(FLEET)
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
        return "Сюда смотрит нос. Сторону меняет кнопка «Вправо» или «Вниз»."
    return "Буквы сверху, цифры слева. Жмите клетку на пересечении."


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


def remain_line(ships) -> str:
    have = Counter(len(ship) for ship in ships)
    need = Counter(FLEET)
    bits = []
    for length in sorted(need, reverse=True):
        left = need[length] - have[length]
        if left > 0:
            bits.append(f"{_LEFT_WORD.get(left, str(left))} на {length}")
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


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    if style:
        try:
            return InlineKeyboardButton(text=text, callback_data=data, style=style)
        except TypeError:
            pass
    return InlineKeyboardButton(text=text, callback_data=data)


def _pack(buttons, width: int = 8) -> list:
    return [buttons[i:i + width] for i in range(0, len(buttons), width)]


def _grid(prefix: str, gid: int, page: int, marks: dict, corner: str = "◎", corner_kind: str = "c") -> list:
    names = letters()
    cols = page_columns(page)
    rows = [[
        _btn(corner, f"{prefix}h:{gid}:{corner_kind}"),
        *(_btn(names[c], f"{prefix}h:{gid}:a") for c in cols),
    ]]
    for r in range(SIZE):
        row = [_btn(str(r + 1), f"{prefix}h:{gid}:n")]
        for c in cols:
            row.append(_btn(button_char(marks.get((r, c), ".")), f"{prefix}c:{gid}:{r * SIZE + c}"))
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


def _length_buttons(prefix: str, gid: int, ships, pick) -> list:
    have = Counter(len(ship) for ship in ships)
    need = Counter(FLEET)
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


def place_markup(prefix: str, gid: int, ships, page: int, across: bool, pick) -> InlineKeyboardMarkup:
    ready = fleet_ready(ships)
    rows = []
    rows.extend(_pack(_length_buttons(prefix, gid, ships, pick)))
    rows.append([
        _btn("➡ Вправо" if across else "⬇ Вниз", f"{prefix}o:{gid}"),
        _btn("↩ Убрать", f"{prefix}u:{gid}"),
        _btn("✓ Готово" if ready else "Готово", f"{prefix}r:{gid}", "primary" if ready else None),
    ])
    rows.extend(_grid(
        prefix, gid, page, own_marks(ships, set(), set()),
        "➡" if across else "⬇", "d",
    ))
    rows.extend(_pack(_page_buttons(prefix, gid, page)))
    rows.append(_help_row(prefix, gid, "Выйти"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def aim_markup(prefix: str, gid: int, page: int, marks: dict) -> InlineKeyboardMarkup:
    rows = _grid(prefix, gid, page, marks, "◎", "c")
    rows.extend(_pack(_page_buttons(prefix, gid, page)))
    rows.append([
        _btn("Мои корабли", f"{prefix}f:{gid}"),
        _btn("Как играть", f"{prefix}q:{gid}"),
        _btn("Сдаться", f"{prefix}g:{gid}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fleet_markup(prefix: str, gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Как играть", f"{prefix}q:{gid}")]])


def lobby_markup(game) -> InlineKeyboardMarkup:
    prefix = game["prefix"]
    gid = game["id"]
    full = len(game["participants"]) >= 2
    rows = [[_btn("Присоединиться", f"{prefix}j:{gid}", None if full else "primary")]]
    if full:
        rows.append([_btn("Начать игру", f"{prefix}s:{gid}", "primary")])
    rows.append(_help_row(prefix, gid, "Отмена"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def place_public_markup(game) -> InlineKeyboardMarkup:
    prefix = game["prefix"]
    gid = game["id"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Моё море", f"{prefix}d:{gid}", "primary")],
        _help_row(prefix, gid, "Выйти"),
    ])


def lobby_text(game) -> str:
    bet = int(game["bet"])
    stake = "Без ставки." if bet <= 0 else f"Ставка {_num(bet)} кут."
    lines = [
        "🚢 <b>Морской бой</b>",
        stake,
        "Куты спишутся в конце у проигравшего.",
        "",
        "1. Второй жмёт «Присоединиться»",
        "2. Первый жмёт «Начать игру»",
        "3. Корабли каждый ставит у себя",
        "4. Потом стреляете по клеткам",
    ]
    if len(game["participants"]) >= 2:
        lines.extend(["", f"{game['links'].get(game['creator'], 'Первый')}, нажмите «Начать игру»."])
    else:
        lines.extend(["", "Ждём второго игрока."])
    for uid in game["participants"]:
        role = "открыл стол" if int(uid) == int(game["creator"]) else "за столом"
        lines.append(f"• {game['links'].get(uid, 'Игрок')} — {role}")
    return "\n".join(lines)


def invite_text(bet: int) -> str:
    stake = "Без ставки." if int(bet) <= 0 else f"Ставка {_num(bet)} кут."
    return "\n".join([
        "🚢 <b>Морской бой</b>",
        stake,
        "Нажмите «Создать игру».",
        "Соперник жмёт «Присоединиться», вы — «Начать».",
        "Корабли будут видны только вам.",
    ])


def place_text(game) -> str:
    lines = [
        "🚢 <b>Морской бой</b>",
        "Нажмите «Моё море». Его видите только вы.",
        f"На расстановку {span_text(PLACE_SECONDS)}.",
    ]
    for uid in game["players"]:
        state = "готов" if game["boards"][uid]["ready"] else "расставляет"
        lines.append(f"• {game['links'].get(uid, 'Игрок')} — {state}")
    lines.append("Когда оба готовы, начнётся стрельба.")
    return "\n".join(lines)


def _other(game, uid: int) -> int:
    for person in game.get("players") or []:
        if int(person) != int(uid):
            return int(person)
    return int(uid)


def _incoming(game, uid: int):
    box = (game.get("shots") or {}).get(_other(game, uid)) or {}
    return set(box.get("hit") or ()), set(box.get("miss") or ())


def _public_chart(game, uid: int) -> str:
    hits, misses = _incoming(game, uid)
    return chart_html(public_marks(game["boards"][uid]["ships"], hits, misses))


def fight_text(game) -> str:
    links = game["links"]
    turn = int(game["turn"])
    foe = _other(game, turn)
    lines = [
        "🚢 <b>Морской бой</b>",
        f"Первый выстрел — {links.get(game['first'], 'игрок')}.",
        f"🎯 Сейчас ходит {links.get(turn, 'игрок')}. Жмите клетку в верхнем море.",
        "Попали — стреляйте ещё. Мимо — ход переходит.",
        f"На ход {span_text(TURN_SECONDS)}. Пропуски: {int(game['skips'].get(turn, 0))} из {MISS_LIMIT}.",
    ]
    if game.get("note"):
        lines.append(str(game["note"]))
    lines.extend([
        "",
        f"🎯 Море {links.get(foe, 'соперника')} — сюда стрелять",
        _public_chart(game, foe),
        "",
        f"🌫 Море {links.get(turn, 'игрока')} — корабли скрыты",
        _public_chart(game, turn),
        "",
        "Кнопки снизу — половина поля. ● отмечает, какая открыта.",
        "· пусто    ○ мимо    ✕ ранен    ▫ обводка потопленного",
    ])
    return "\n".join(lines)


def secret_place_text(board) -> str:
    ships = board["ships"]
    if board["ready"]:
        now = "Ждём соперника. «Убрать» снимет последний корабль."
    elif fleet_ready(ships):
        now = "Все корабли на воде. Нажмите «Готово»."
    elif board["pick"]:
        way = "вправо" if board["across"] else "вниз"
        now = f"Выбран корабль на {board['pick']}. Нажмите клетку: нос встанет туда и пойдёт {way}."
    else:
        now = "Нажмите корабль над полем."
    return "\n".join([
        "🚢 <b>Ваше море</b>",
        "Его видите только вы.",
        chart_html(own_marks(ships, set(), set())),
        remain_line(ships),
        now,
        "Буквы сверху, цифры слева. Другая половина поля — кнопка снизу.",
        "Между кораблями оставьте пустую клетку.",
    ])


def secret_fight_text(ships, hits, misses) -> str:
    return "\n".join([
        "🚢 <b>Ваши корабли</b>",
        "Их видите только вы. Стрелять нужно в общем сообщении.",
        chart_html(own_marks(ships, hits, misses)),
        "✕ — в эту клетку попали. Плюсы вокруг — корабль потоплен.",
        "Буквы сверху, цифры слева.",
    ])


def _secret_view(game, uid: int):
    board = game["boards"][uid]
    prefix = game["prefix"]
    gid = game["id"]
    if game["phase"] == "place":
        return secret_place_text(board), place_markup(
            prefix, gid, board["ships"], board["page"], board["across"], board["pick"],
        )
    hits, misses = _incoming(game, uid)
    text = secret_fight_text(board["ships"], hits, misses)
    if game["phase"] == "fight":
        return text, fleet_markup(prefix, gid)
    return text, EMPTY


def end_text(game, winner: int, how: str, net: int) -> str:
    loser = _other(game, winner)
    links = game["links"]
    lines = [
        "🚢 <b>Морской бой</b>",
        f"{links.get(winner, 'Игрок')} победил.",
        how,
    ]
    if int(game["bet"]) > 0:
        lines.append(f"Выигрыш {_num(net)} кут.")
    lines.append("○ мимо    ✕ ранен    фигура и плюсы — потопленный корабль")
    lines.extend([
        "",
        f"Море {links.get(loser, 'соперника')}",
        _public_chart(game, loser),
        "",
        f"Море {links.get(winner, 'победителя')}",
        _public_chart(game, winner),
    ])
    return "\n".join(lines)


def _blank_board() -> dict:
    return {
        "ships": [],
        "page": 0,
        "across": True,
        "pick": next_length([]),
        "ready": False,
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
        "place_token": 0,
        "turn_token": 0,
        "place_task": None,
        "turn_task": None,
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


def _ready_touch(game, uid: int) -> bool:
    now = time.monotonic()
    last = float(game["touch"].get(int(uid), 0.0))
    if now - last < float(CLICK_GAP):
        return False
    game["touch"][int(uid)] = now
    return True


def _surface(query, game) -> str:
    msg = getattr(query, "message", None)
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
    return int(chat_id) == int(game["chat_id"]) and int(message_id) == int(game["message_id"])


def _aim(game):
    foe = _other(game, int(game["turn"]))
    hits, misses = _incoming(game, foe)
    marks = public_marks(game["boards"][foe]["ships"], hits, misses)
    return aim_markup(game["prefix"], game["id"], int(game["aim_page"]), marks)


async def _ack(query, text: str = "", alert: bool = False) -> None:
    try:
        if text and alert:
            await query.answer(text[:200], show_alert=True)
        elif text:
            await query.answer(text[:200])
        else:
            await query.answer()
    except Exception:
        pass


async def _edit(bot, chat_id, message_id, text, markup) -> bool:
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
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
        return True
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return True
        print(f"[SEA] markup {type(exc).__name__}")
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


async def _ephemeral(bot, query, game, uid: int, text: str, markup, replace: bool) -> bool:
    msg = getattr(query, "message", None)
    if msg is None or getattr(msg, "chat", None) is None:
        return False
    if replace and _surface(query, game) != "ephemeral":
        replace = False
    try:
        await bot.send_message(
            chat_id=msg.chat.id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=int(uid),
                callback_query_id=str(query.id),
                replace_callback_query_message=bool(replace),
            ),
        )
        return True
    except Exception as exc:
        print(f"[SEA] ephemeral {type(exc).__name__}")
        return False


async def _paint_secret(bot, game, uid: int, query=None, toast: str = "", only_markup: bool = False) -> None:
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

    if surface == "dm":
        msg = query.message
        await _ack(query, toast)
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
        if await _ephemeral(bot, query, game, uid, text, markup, True):
            await _ack(query, toast)
        else:
            await _ack(query, "Не вышло обновить море. Нажмите ещё раз.", alert=True)
        return

    if board.get("mode") == "dm" and board.get("message_id"):
        if await _save(board["chat_id"], board["message_id"]):
            if query is not None:
                await _ack(query, toast or "Море в личке с ботом")
            return
        board["mode"] = "none"

    sent = await _dm(bot, uid, text, markup)
    if sent is not None and not _is_public_target(sent.chat.id, sent.message_id, game):
        board["mode"] = "dm"
        board["chat_id"] = int(sent.chat.id)
        board["message_id"] = int(sent.message_id)
        if query is not None:
            await _ack(query, "Море открыто в личке")
        return

    if query is None:
        return
    if await _ephemeral(bot, query, game, uid, text, markup, False):
        await _ack(query, toast)
        return
    await _ack(query, "Напишите боту в личку /start и откройте море ещё раз.", alert=True)


async def _link(uid: int) -> str:
    try:
        from main import create_user_link, db
        first = await db.get_firstname_by_user_id(uid)
        username = await db.get_username_by_user_id(uid)
        return await create_user_link(uid, first or "Игрок", username)
    except Exception as exc:
        print(f"[SEA] link {type(exc).__name__}")
        return "Игрок"


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


def _arm_place(store, game) -> None:
    current = None
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    old = game.get("place_task")
    if old is not None and old is not current and not old.done():
        old.cancel()
    game["place_token"] = int(game.get("place_token", 0)) + 1
    token = game["place_token"]
    game["place_task"] = asyncio.create_task(_place_deadline(store, game["id"], token))


def _arm_turn(store, game) -> None:
    current = None
    try:
        current = asyncio.current_task()
    except RuntimeError:
        current = None
    old = game.get("turn_task")
    if old is not None and old is not current and not old.done():
        old.cancel()
    game["turn_token"] = int(game.get("turn_token", 0)) + 1
    token = game["turn_token"]
    game["turn_task"] = asyncio.create_task(_turn_deadline(store, game["id"], token))


async def _close_quiet(store, game, text: str) -> None:
    if game.get("phase") == "over":
        return
    game["phase"] = "over"
    _drop_task(game, "place_task")
    _drop_task(game, "turn_task")
    bot = game.get("bot")
    if bot is not None:
        await _edit(bot, game["chat_id"], game["message_id"], text, EMPTY)
        for board in list(game.get("boards", {}).values()):
            if board.get("mode") != "dm" or not board.get("message_id"):
                continue
            if _is_public_target(board["chat_id"], board["message_id"], game):
                continue
            await _edit(bot, board["chat_id"], board["message_id"], "🚢 Партия снята.", EMPTY)
    store.pop(game["id"], None)
    _LOCKS.pop(game["id"], None)


async def _finish(store, game, winner: int, reason: str) -> None:
    if game.get("phase") == "over":
        return
    game["phase"] = "over"
    _drop_task(game, "place_task")
    _drop_task(game, "turn_task")
    loser = _other(game, winner)
    how = {
        "ships": "Все корабли соперника потоплены.",
        "give": "Соперник сдался.",
        "skip": f"Соперник пропустил ход {_times(MISS_LIMIT)}.",
    }.get(reason, "Партия закончена.")
    net, gfund = await _pay(winner, loser, int(game["bet"]))
    bot = game.get("bot")
    if bot is not None:
        await _edit(
            bot, game["chat_id"], game["message_id"],
            end_text(game, winner, how, net), _commission_markup(gfund),
        )
        for uid in list(game.get("players") or []):
            await _paint_secret(bot, game, int(uid), query=None)
    store.pop(game["id"], None)
    _LOCKS.pop(game["id"], None)


async def _begin_place(store, game) -> None:
    players = [int(item) for item in game["participants"][:2]]
    game["players"] = players
    game["phase"] = "place"
    game["boards"] = {uid: _blank_board() for uid in players}
    game["shots"] = {uid: {"hit": set(), "miss": set()} for uid in players}
    game["skips"] = {uid: 0 for uid in players}
    bot = game.get("bot")
    if bot is not None:
        await _edit(bot, game["chat_id"], game["message_id"], place_text(game), place_public_markup(game))
        for uid in players:
            await _paint_secret(bot, game, uid, query=None)
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
        if not await _edit(bot, game["chat_id"], game["message_id"], fight_text(game), _aim(game)):
            await _edit(bot, game["chat_id"], game["message_id"], fight_text(game), _aim(game))
        for uid in players:
            await _paint_secret(bot, game, uid, query=None)
    _arm_turn(store, game)


async def _place_deadline(store, gid: int, token: int) -> None:
    try:
        await asyncio.sleep(PLACE_SECONDS)
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
        await asyncio.sleep(TURN_SECONDS)
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
                await _edit(bot, game["chat_id"], game["message_id"], fight_text(game), _aim(game))
            _arm_turn(store, game)
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
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    game["participants"].append(uid)
    game["links"][uid] = await _link(uid)
    await _ack(query, "Вы в партии")
    bot = game.get("bot")
    if bot is not None:
        await _edit(bot, game["chat_id"], game["message_id"], lobby_text(game), lobby_markup(game))


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
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    await _ack(query, "Нажмите «Моё море» и поставьте корабли")
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
                await _ack(query, "Стол закроется, куты останутся. Нажмите «Отмена» ещё раз.", alert=True)
            else:
                await _ack(query, "Вы выйдете из стола. Нажмите «Отмена» ещё раз.", alert=True)
            return
        if not _ready_touch(game, uid):
            await _ack(query, "Нажмите ещё раз.")
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
            await _edit(bot, game["chat_id"], game["message_id"], lobby_text(game), lobby_markup(game))
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
    if not _ready_touch(game, uid):
        await _ack(query, "Нажмите ещё раз.")
        return
    game["confirm"] = None
    if phase == "place":
        await _ack(query, "Партия снята")
        who = game["links"].get(uid, "Игрок")
        await _close_quiet(store, game, f"🚢 <b>Морской бой</b>\n{who} вышел.\nПартия снята, куты на месте.")
        return
    if phase == "fight":
        await _ack(query, "Вы сдались")
        await _finish(store, game, _other(game, uid), "give")
        return
    await _ack(query, "Партия уже закрыта")


async def _open_sea(query, game, uid: int) -> None:
    if uid not in game.get("boards", {}):
        await _ack(query, "Вы не в этой партии.")
        return
    if game.get("phase") not in {"place", "fight"}:
        await _ack(query, "Море откроется, когда партия начнётся.")
        return
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    await _paint_secret(game.get("bot"), game, uid, query)


async def _turn_page(query, game, uid: int, page: int) -> None:
    if page < 0 or page >= page_count():
        await _ack(query, "Кнопка устарела")
        return
    surface = _surface(query, game)
    if game.get("phase") == "fight" and surface == "public":
        if page == int(game["aim_page"]):
            await _ack(query)
            return
        if not _ready_touch(game, uid):
            await _ack(query, "Секунду")
            return
        game["aim_page"] = page
        await _ack(query)
        bot = game.get("bot")
        if bot is not None and not await _markup_only(bot, game["chat_id"], game["message_id"], _aim(game)):
            await _edit(bot, game["chat_id"], game["message_id"], fight_text(game), _aim(game))
        return
    if game.get("phase") == "place" and uid in game.get("boards", {}) and surface != "public":
        board = game["boards"][uid]
        if page == int(board["page"]):
            await _ack(query)
            return
        if not _ready_touch(game, uid):
            await _ack(query, "Секунду")
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
    if int(length) not in Counter(FLEET):
        await _ack(query, "Нет такого корабля.")
        return
    board = game["boards"][uid]
    if board["ready"]:
        await _ack(query, "Ждём соперника. «Убрать» снимет последний корабль.", alert=True)
        return
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    board["pick"] = int(length)
    await _paint_secret(game.get("bot"), game, uid, query, toast=f"Корабль на {int(length)}. Нажмите клетку.")


async def _flip(query, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
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
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    was = board["ready"]
    board["ships"] = board["ships"][:-1]
    board["ready"] = False
    board["pick"] = next_length(board["ships"], board["pick"])
    await _paint_secret(game.get("bot"), game, uid, query, toast="Последний корабль убран.")
    if was:
        bot = game.get("bot")
        if bot is not None:
            await _edit(bot, game["chat_id"], game["message_id"], place_text(game), place_public_markup(game))


async def _ready(query, store, game, uid: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query)
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    if not fleet_ready(board["ships"]):
        await _ack(query, "Ещё не все корабли. Нажмите клетку на поле.", alert=True)
        return
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
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
    await _paint_secret(game.get("bot"), game, uid, query, toast="Ждём соперника")
    bot = game.get("bot")
    if bot is not None:
        await _edit(bot, game["chat_id"], game["message_id"], place_text(game), place_public_markup(game))


async def _place_cell(query, game, uid: int, r: int, c: int) -> None:
    if game.get("phase") != "place" or uid not in game.get("boards", {}):
        await _ack(query, "Сейчас корабли не ставят.")
        return
    if _surface(query, game) == "public":
        await _ack(query, "Нажмите «Моё море» в общем сообщении.", alert=True)
        return
    board = game["boards"][uid]
    if board["ready"]:
        await _ack(query, "Ждём соперника. «Убрать» снимет последний корабль.", alert=True)
        return
    if not board["pick"]:
        if fleet_ready(board["ships"]):
            await _ack(query, "Все корабли стоят. Нажмите «Готово».", alert=True)
        else:
            await _ack(query, "Сначала нажмите корабль над полем.", alert=True)
        return
    ok, ships, code = place_ship(board["ships"], board["pick"], r, c, board["across"])
    if not ok:
        await _ack(query, _PLACE_WHY.get(code, "Сюда не встаёт."), alert=True)
        return
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
        return
    board["ships"] = ships
    board["ready"] = False
    board["pick"] = next_length(ships)
    if board["pick"]:
        toast = f"Стоит. Теперь корабль на {board['pick']}."
    else:
        toast = "Все стоят. Нажмите «Готово»."
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
    if not _ready_touch(game, uid):
        await _ack(query, "Секунду")
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
        await _edit(bot, game["chat_id"], game["message_id"], fight_text(game), _aim(game))
        await _paint_secret(bot, game, foe, query=None)
    _arm_turn(store, game)


async def _route(query, store, game, action: str, parts, uid: int) -> None:
    if action not in {"g", "q"}:
        game["confirm"] = None
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
    if action in {"d", "f"}:
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
    now = time.monotonic()
    if now - float(_OPEN_AT.get(uid, 0.0)) < 2:
        await _ack(query, "Секунду")
        return
    _OPEN_AT[uid] = now
    msg = getattr(query, "message", None)
    if msg is None or getattr(msg, "chat", None) is None:
        _OPEN_AT.pop(uid, None)
        await _ack(query, "Сообщение уже не найти.", alert=True)
        return
    reason = await _desk_reason(bet)
    if reason:
        _OPEN_AT.pop(uid, None)
        await _ack(query, reason, alert=True)
        return
    if await _door_blocks(msg):
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
            await _ack(query, "Недостаточно кут.", alert=True)
            return
    gid = next(_IDS)
    game = _fresh(gid, msg.chat.id, msg.message_id, uid, bet, "seai:")
    game["bot"] = getattr(query, "bot", None)
    game["links"][uid] = await _link(uid)
    store[gid] = game
    ok = False
    if game["bot"] is not None:
        ok = await _edit(game["bot"], msg.chat.id, msg.message_id, lobby_text(game), lobby_markup(game))
    if not ok:
        store.pop(gid, None)
        _OPEN_AT.pop(uid, None)
        await _ack(query, "Не вышло открыть партию. Нажмите ещё раз.", alert=True)
        return
    await _ack(query, "Партия открыта")


async def _press(query, store) -> None:
    data = str(getattr(query, "data", "") or "")
    action, parts = _split(data)
    if not action or action == "x":
        await _ack(query)
        return
    if action == "h":
        kind = parts[1] if len(parts) > 1 else ""
        await _ack(query, label_hint(kind))
        return
    user = getattr(query, "from_user", None)
    if user is None or not getattr(user, "id", None):
        await _ack(query, "Напишите от своего имени.")
        return
    uid = int(user.id)
    if action == "n":
        if not data.startswith("seai:"):
            await _ack(query)
            return
        await _inline_new(query, store, uid, parts)
        return
    try:
        gid = int(parts[0])
    except (IndexError, ValueError):
        await _ack(query, "Кнопка устарела")
        return
    async with _lock(gid):
        game = store.get(gid)
        if not game or game.get("phase") in {"over", "dead"}:
            await _ack(query, "Партия уже закрыта")
            return
        bot = getattr(query, "bot", None)
        if bot is not None:
            game["bot"] = bot
        await _route(query, store, game, action, parts, uid)


async def press(query, store) -> None:
    try:
        await _press(query, store)
    except Exception as exc:
        print(f"[SEA] press {type(exc).__name__}")
        await _ack(query, "Не вышло. Нажмите ещё раз.")


async def sea_open(message: Message) -> None:
    kind, bet = parse_sea(getattr(message, "text", "") or "")
    if kind in {"ignore", "help"}:
        return
    if kind == "bad":
        from bot.games.invoke import format_line
        try:
            await message.reply(format_line("морской бой [ставка]"), parse_mode="HTML")
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
            try:
                await message.reply("Недостаточно кут для этой ставки.")
            except Exception:
                pass
            return
    gid = next(_IDS)
    chat = getattr(message, "chat", None)
    game = _fresh(gid, getattr(chat, "id", 0) or 0, 0, uid, bet, "sea:")
    game["bot"] = getattr(message, "bot", None)
    game["links"][uid] = await _link(uid)
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
        return
    game["chat_id"] = int(sent.chat.id)
    game["message_id"] = int(sent.message_id)


router = Router(name="sea")


@router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("sea:"))
async def sea_press(query):
    await press(query, TABLES)
