"""Топ лучших игроков: сколько игр сыграно, без разницы победа это или проигрыш.

Считается так же, как «Богачи»: место вызвавшего и десятка сверху.
Победы и проигрыши складываются. «За всё время» берёт users.wins + users.loose.
Сегодня, неделя, месяц и год копятся в user_games_day с момента, когда игра
прошла через update_user_wins / update_user_loose.
"""
from __future__ import annotations

import html
import locale
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.games.invoke import command_line

BEST_PLAYERS_EMOJI_ID = "5469967260380612012"
BEST_PLAYERS_PLACE_EMOJI_ID = "5474417568053745249"

BEST_PLAYERS_COMMANDS = frozenset({
    "стата игр",
    "стата игры",
    "стата игра",
    "стата игроков",
    "стата игроки",
    "стата лучших игроков",
    "стата лучшие игроки",
    "стата по играм",
    "стата сыгранных игр",
    "статистика игр",
    "статистика игры",
    "статистика игроков",
    "статистика игроки",
    "статистика лучших игроков",
    "статистика лучшие игроки",
    "статистика по играм",
    "лучшие игроки",
    "лучший игрок",
    "лучшие игроки проекта",
    "топ лучших игроков",
    "топ лучшие игроки",
    "топ лучший игрок",
    "топ лучших игроков проекта",
    "топ игроков",
    "топ игроки",
    "топ игроков проекта",
    "топ игр",
    "топ игры",
    "топ по играм",
    "топ сыгранных игр",
    "игры топ",
    "игроки топ",
    "игровой топ",
    "рейтинг игроков",
    "рейтинг игр",
    "кто больше играет",
    "кто больше всего играет",
    "кто больше всего играет в игры",
    "кто больше всех играет",
    "кто играет больше всех",
    "сыгранные игры",
})

PERIODS = ("day", "week", "month", "year", "all")
SOURCES = ("menu", "text")

_PERIOD_BUTTONS = (
    ("day", "За сегодня", "5424987025667293801"),
    ("week", "За неделю", "5438529285184847871"),
    ("month", "За месяц", "5436371618169389408"),
    ("year", "За год", "5249233098444399524"),
    ("all", "За всё время", "5303138782004924588"),
)

_EMPTY_BY_PERIOD = {
    "day": "За сегодня игр пока нет.",
    "week": "За неделю игр пока нет.",
    "month": "За месяц игр пока нет.",
    "year": "За год игр пока нет.",
    "all": "Игр пока нет.",
}

_MSK = timezone(timedelta(hours=3))


def is_best_players_command(text: str | None) -> bool:
    return command_line(text or "") in BEST_PLAYERS_COMMANDS


def msk_today(now: datetime | None = None) -> date:
    moment = now or datetime.now(_MSK)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_MSK)
    return moment.astimezone(_MSK).date()


def period_bounds(period: str, today: date) -> Optional[Tuple[date, date]]:
    """Границы текущего периода по московской дате. None — за всё время."""
    kind = str(period or "all").strip().lower()
    if kind == "day":
        return today, today
    if kind == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if kind == "month":
        start = today.replace(day=1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start, end
    if kind == "year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return None


def parse_best_players_callback(data: str | None) -> Optional[Tuple[str, str]]:
    raw = str(data or "")
    if raw == "bestplayers":
        return "all", "menu"
    if not raw.startswith("bestplay:"):
        return None
    parts = raw.split(":")
    if len(parts) != 3:
        return None
    _, period, source = parts
    if period not in PERIODS or source not in SOURCES:
        return None
    return period, source


def format_place(place) -> str:
    try:
        number = int(place)
    except (TypeError, ValueError):
        return "н/a"
    if number <= 0:
        return "н/a"
    return "{:,.0f}".format(number).replace(",", ".")


def format_games(games) -> str:
    try:
        number = int(games or 0)
    except (TypeError, ValueError):
        number = 0
    if number < 0:
        number = 0
    return locale.format_string("%d", number, grouping=True).replace(",", ".")


def user_link(user_id: int, first_name: str | None, username: str | None) -> str:
    nick = str(username or "").strip().lstrip("@")
    name = str(first_name or "").strip()
    if nick:
        label = html.escape(name or nick)
        return f"<a href='https://t.me/{html.escape(nick)}'>{label}</a>"
    if name:
        return html.escape(name)
    return "У пользователя нет имени."


def render_best_players_text(
    place,
    rows: Sequence[Tuple[int, int]],
    names: dict,
    period: str = "all",
    empty_line: str | None = None,
    lead: str | None = None,
) -> str:
    place_text = format_place(place)
    text = (
        f"<tg-emoji emoji-id='{BEST_PLAYERS_EMOJI_ID}'>🏆</tg-emoji> "
        "<b>Статистика лучших игроков проекта\n"
        f"<tg-emoji emoji-id='{BEST_PLAYERS_PLACE_EMOJI_ID}'>🌱</tg-emoji> "
        f"Ваше место в топе : <i>{place_text}</i></b>\n\n"
    )
    if lead:
        text += f"{lead}\n\n"
    if not rows:
        text += empty_line or _EMPTY_BY_PERIOD.get(period, _EMPTY_BY_PERIOD["all"])
        return text
    for rank, (user_id, games) in enumerate(rows, start=1):
        first_name, username = names.get(int(user_id), (None, None))
        link = user_link(int(user_id), first_name, username)
        games_text = format_games(games)
        if rank <= 3:
            text += f"<b>{rank}. {link} ─ {games_text} сыгранных игр</b>\n\n"
        else:
            text += f"{rank}. {link} ─ <b>{games_text}</b> сыгранных игр\n\n"
    return text


def best_players_keyboard(active: str = "all", source: str = "menu") -> InlineKeyboardMarkup:
    period = active if active in PERIODS else "all"
    origin = source if source in SOURCES else "menu"

    def button(key: str, label: str, icon: str) -> InlineKeyboardButton:
        title = f"✔️ {label}" if key == period else label
        return InlineKeyboardButton(
            text=title,
            callback_data=f"bestplay:{key}:{origin}",
            style="default",
            icon_custom_emoji_id=icon,
        )

    day, week, month, year, whole = (
        button(key, label, icon) for key, label, icon in _PERIOD_BUTTONS
    )
    rows = [
        [day],
        [week, month, year],
        [whole],
    ]
    if origin == "text":
        rows.append([
            InlineKeyboardButton(
                text="Скрыть",
                callback_data="deletehelp0101",
                style="default",
                icon_custom_emoji_id="5226660202035554522",
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="Назад",
                callback_data="backtop",
                style="default",
                icon_custom_emoji_id="5255703720078879038",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_best_players_view(db, viewer_id: int, period: str = "all", source: str = "menu"):
    kind = period if period in PERIODS else "all"
    origin = source if source in SOURCES else "menu"
    bounds = period_bounds(kind, msk_today())
    board = await db.get_best_players_board(
        period=kind,
        viewer_id=int(viewer_id),
        start=None if bounds is None else bounds[0],
        end=None if bounds is None else bounds[1],
        limit=10,
    )
    rows = list(board.get("rows") or [])
    names = await db.get_names_bulk(uid for uid, _ in rows)
    empty_line = None
    lead = None
    if board.get("copyHidden") and kind == "all":
        when = board.get("liftLabel") or "выбранной даты"
        lead = f"До {when} топ за всё время скрыт."
        if not rows:
            empty_line = (
                f"С {when} здесь будет сумма общей статистики и игр после копии. "
                "День, неделя, месяц и год считаются как обычно."
            )
    text = render_best_players_text(board.get("place"), rows, names or {}, kind, empty_line, lead)
    keyboard = best_players_keyboard(kind, origin)
    return text, keyboard
