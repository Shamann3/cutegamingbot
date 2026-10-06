# -*- coding: utf-8 -*-
"""Состав администраторов одной официальной группы.

Тот же древовидный вид, что у «персонала проекта», но люди и права берутся
с должностей этой группы. Сотрудники проекта сюда не подмешиваются.
"""
from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import Any, Optional

# Те же премиум-эмодзи, что у лестницы персонала: ранг 1 мелкий, ранг 5 корона.
_LEVEL_EMOJI = {
    1: ("🔹", "5393514467394875868"),
    2: ("🔸", "4958900559139570572"),
    3: ("💠", "5402366352042252021"),
    4: ("💎", "5296491512660534111"),
    5: ("👑", "5305629674058061875"),
}
_DIAMOND = ("💎", "5296773795091094130")

# Порядок как у переключателей должности: сначала этот чат, потом шире.
_RIGHTS = (
    ("punish_mute", "Мут", "только этот чат"),
    ("punish_ban", "Бан в чате", "только этот чат"),
    ("punish_kick", "Кик", "только этот чат"),
    ("punish_warn", "Варн", "только этот чат"),
    ("punish_voice", "Голос", "только этот чат"),
    ("muteall", "Муталл", "все официальные группы"),
    ("kickall", "Кикалл", "все официальные группы"),
    ("warnall", "Варналл", "все официальные группы"),
    ("banall", "Баналл", "все официальные группы"),
    ("warnfull", "Варнфулл", "весь проект"),
    ("banfull", "Банфулл", "весь проект"),
)
_CHAT_KEYS = {key for key, _name, place in _RIGHTS if place == "только этот чат"}

BTN_ALL = "Все права"
BTN_STAFF = "Сотрудники проекта"
BTN_GROUP = "Администраторы группы"
BTN_GROUP_BACK = "К администраторам"


def coerce_rights(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return []


def granted_lines(rank: int, rights: Any) -> list[tuple[str, str]]:
    """Что должность реально может выдать. Создатель группы держит наказания этого чата."""
    have = set(coerce_rights(rights))
    if int(rank) >= 5:
        have |= _CHAT_KEYS
    return [(name, place) for key, name, place in _RIGHTS if key in have]


def _emoji(rank: int) -> str:
    level = max(1, min(5, int(rank or 1)))
    plain, custom = _LEVEL_EMOJI[level]
    return f"<tg-emoji emoji-id='{custom}'>{plain}</tg-emoji>"


def _plain_emoji(rank: int) -> str:
    level = max(1, min(5, int(rank or 1)))
    return _LEVEL_EMOJI[level][0]


def _clip(text: str, limit: int = 28) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def highest_vacancy(posts: list[dict]) -> Optional[int]:
    """Индекс самой высокой должности, если на этом ранге ещё никого нет.

    Занятый верхний ранг не трогаем: вакансии ниже остаются вакансиями.
    """
    if not posts:
        return None
    top = max(int(post.get("rank") or 0) for post in posts)
    indexes = [i for i, post in enumerate(posts) if int(post.get("rank") or 0) == top]
    if any(post.get("people") for i, post in enumerate(posts) if i in indexes):
        return None
    return indexes[0]


def stored_owner_name(
    display_name: Any,
    first_name: Any,
    username: Any,
    user_id: int,
) -> tuple[str, str]:
    """Имя создателя группы из уже лежащих в базе полей, без запроса в Telegram."""
    name = " ".join(str(display_name or "").split()) or " ".join(str(first_name or "").split())
    uname = str(username or "").strip().lstrip("@")
    if not name:
        name = f"@{uname}" if uname else str(int(user_id))
    return name, uname


def render_group_roster(group_title: str, posts: list[dict], *, stamp: str = "") -> str:
    """Дерево должностей этой группы. Пустая должность видна как вакансия."""
    diamond, custom = _DIAMOND
    gem = f"<tg-emoji emoji-id='{custom}'>{diamond}</tg-emoji>"
    title = escape(" ".join(str(group_title or "Эта группа").split()) or "Эта группа")
    parts = [
        f"<b>{gem} АДМИНИСТРАТОРЫ ГРУППЫ {gem}</b>",
        f"\n<blockquote><b>{title}</b></blockquote>",
    ]
    shown = 0
    for post in posts or []:
        name = escape(str(post.get("title") or "Должность"))
        rank = int(post.get("rank") or 0)
        parts.append(f"\n\n<code>┏</code> {_emoji(rank)} <b>{name}</b> <i>· ранг {rank}</i>")
        people = list(post.get("people") or [])
        shown += 1
        if not people:
            parts.append("\n<code>┗</code> <i>- вакантно</i>")
            continue
        last = len(people) - 1
        for index, person in enumerate(people):
            end = index == last
            branch = "┗" if end else "┣"
            status = person.get("status") or ""
            member = person.get("html") or escape(str(person.get("name") or "человек"))
            parts.append(f"\n<code>{branch}</code> {status} {member}".rstrip())
            hint = str(person.get("hint") or "").strip()
            if hint:
                rail = " " if end else "┃"
                parts.append(f"\n<code>{rail}</code> <i>{escape(hint)}</i>")
    if shown:
        parts.append(
            "\n\n<i>Нажмите должность — её права в этой группе. "
            "«Сотрудники проекта» меняет это сообщение на персонал проекта. "
            "Кнопки нажимает тот, кто написал «кто админ».</i>"
        )
    else:
        parts.append(
            "\n<blockquote><b><i>В этой группе ещё нет должностей администраторов.</i></b></blockquote>"
            "\n<i>«Сотрудники проекта» откроет персонал проекта. "
            "Кнопку нажимает тот, кто написал «кто админ».</i>"
        )
    clock = stamp or datetime.now().strftime("%H:%M:%S")
    parts.append(
        "\n\n<blockquote><i>"
        "<tg-emoji emoji-id='5339112148175959615'>🟢</tg-emoji> в сети · "
        "<tg-emoji emoji-id='5339082633160703625'>🟡</tg-emoji> недавно · "
        "<tg-emoji emoji-id='5339113303522161846'>⚪️</tg-emoji> не в сети · "
        "<tg-emoji emoji-id='5336936725765700868'>🟠</tg-emoji> не на смене</i>\n"
        f"<i>администраторы этой группы · {escape(clock)}</i></blockquote>"
    )
    return "".join(parts)


def render_group_rights(group_title: str, posts: list[dict], *, only: Optional[int] = None) -> str:
    """Права должностей этой группы. only — номер кнопки, None — все должности."""
    title = escape(" ".join(str(group_title or "Эта группа").split()) or "Эта группа")
    chosen = list(posts or [])
    if only is not None:
        if only < 0 or only >= len(chosen):
            chosen = []
        else:
            chosen = [chosen[only]]
    parts = [
        "<b><tg-emoji emoji-id='5373346752671804066'>👑</tg-emoji> ПРАВА АДМИНИСТРАТОРОВ</b>",
        f"\n<blockquote><b>{title}</b></blockquote>",
        "\n<i>Только то, что включено у должности. Мут чата не включает муталл, бан чата не включает банфулл.</i>",
    ]
    if not chosen:
        parts.append("\n<blockquote><i>Такой должности в этом списке уже нет. Откройте «кто админ» заново.</i></blockquote>")
        return "".join(parts)
    for post in chosen:
        name = escape(str(post.get("title") or "Должность"))
        rank = int(post.get("rank") or 0)
        parts.append(f"\n\n{_emoji(rank)} <b>{name}</b> <i>· ранг {rank}</i>")
        lines = granted_lines(rank, post.get("rights"))
        if not lines:
            parts.append("\n<blockquote><i>Наказания у этой должности выключены.</i></blockquote>")
            continue
        last = len(lines) - 1
        for index, (label, place) in enumerate(lines):
            branch = "┗" if index == last else "┣"
            parts.append(f"\n<code>{branch}</code> <b>{escape(label)}</b> <i>- {escape(place)}</i>")
    parts.append(
        "\n\n<blockquote><i>«Сотрудники проекта» откроет персонал проекта и его права.</i></blockquote>"
    )
    return "".join(parts)


def group_roster_rows(viewer_id: int, posts: list[dict]) -> list[list[tuple[str, str]]]:
    """Кнопки под составом группы. В callback_data зашит тот, кто открыл список."""
    viewer = int(viewer_id)
    rows: list[list[tuple[str, str]]] = []
    row: list[tuple[str, str]] = []
    for index, post in enumerate(posts or []):
        label = _clip(f"{_plain_emoji(int(post.get('rank') or 1))} {post.get('title') or 'Должность'}")
        row.append((label, f"staff:gperm:{viewer}:{index}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if posts:
        rows.append([(BTN_ALL, f"staff:gall:{viewer}")])
    rows.append([(BTN_STAFF, f"staff:gstf:{viewer}")])
    return rows


def group_rights_rows(viewer_id: int) -> list[list[tuple[str, str]]]:
    viewer = int(viewer_id)
    return [
        [(BTN_GROUP_BACK, f"staff:gback:{viewer}")],
        [(BTN_STAFF, f"staff:gstf:{viewer}")],
    ]


def staff_return_row(viewer_id: int) -> list[tuple[str, str]]:
    """Кнопка назад к администраторам группы из сообщения про персонал проекта."""
    return [(BTN_GROUP, f"staff:gadm:{int(viewer_id)}")]
