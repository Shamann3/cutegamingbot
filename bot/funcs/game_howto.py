"""Ответ на «как играть в …» — та же справка, что по «хелп …»."""
from __future__ import annotations

import re
import time
from typing import Dict, Optional, Tuple

from bot.games.howto import HowTo
from bot.games.rules import DEFAULT_BOT, LOBBY_DEFAULTS, RULE_KEYS, Table, rules_html

# Справки одиночных игр живут в balance(): открываем их той же командой, что и игрок.
SOLO_HELP: Dict[str, str] = {
    "fortuna_solo": "рулетка хелп",
    "kube": "куб хелп",
    "darts": "дартс хелп",
    "soccer": "футбол хелп",
    "bowling": "боулинг хелп",
    "basket": "баскет хелп",
    "slots": "слоты хелп",
    "provoda": "провода хелп",
    "bombs": "бомбы хелп",
    "risk": "риск хелп",
    "plate": "плиты хелп",
    "tank": "башня хелп",
    "balls": "шар хелп",
    "trade": "хелп трейд",
}
START_TEXT = "🚀 Как играть?"
MENU_TEXT = "хелп игры"

REPEAT_SECONDS = 10.0
_asked_at: Dict[Tuple[int, int, str], float] = {}
_TG_EMOJI = re.compile(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", re.S)


def _repeat(chat_id: int, user_id: int, topic: str, now: float) -> bool:
    """True — тот же человек только что спросил то же самое в этом чате."""
    mark = (chat_id, user_id, topic)
    seen = _asked_at.get(mark)
    if seen is not None and now - seen < REPEAT_SECONDS:
        return True
    if len(_asked_at) > 512:
        for old in [k for k, at in _asked_at.items() if now - at >= REPEAT_SECONDS]:
            _asked_at.pop(old, None)
    _asked_at[mark] = now
    return False


def _with_text(message, text: str):
    return message.model_copy(update={"text": text, "entities": None})


async def _bot_name(bot) -> str:
    try:
        me = await bot.me()
    except Exception:
        return DEFAULT_BOT
    return getattr(me, "username", None) or DEFAULT_BOT


async def _table(key: str, bot) -> Tuple[Table, str]:
    name = await _bot_name(bot)
    try:
        from bot.runtime.game_desk import live as desk

        try:
            await desk.refresh()
        except Exception:
            pass
        low, high = desk.bets(key)
        players = desk.max_players(key, LOBBY_DEFAULTS[key]) if key in LOBBY_DEFAULTS else 0
        commission_from: Optional[int] = None
        if key != "words" and desk.commission_on() and desk.commission_mult(key) > 0:
            commission_from = desk.commission_min_pot()
        if desk.is_maintenance(key):
            state = desk.MAINT_PLAY_HTML
        elif not desk.is_on(key):
            state = desk.closed_html(key)
        else:
            state = ""
    except Exception:
        return Table(players=LOBBY_DEFAULTS.get(key, 0), bot=name), ""
    return Table(min_bet=low, max_bet=high, players=players, commission_from=commission_from, bot=name), state


async def _reply(message, html: str) -> None:
    failure = None
    for text in (html, _TG_EMOJI.sub(r"\1", html)):
        try:
            await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
            return
        except Exception as exc:
            failure = exc
    print(f"[HOWTO] reply failed: {failure!r}")


async def _answer(message, topic: str) -> None:
    if topic in ("start", "menu"):
        from bot.funcs.help import help as send_help

        await send_help(_with_text(message, START_TEXT if topic == "start" else MENU_TEXT))
        return
    phrase = SOLO_HELP.get(topic)
    if phrase:
        from bot.funcs.balance import balance

        await balance(_with_text(message, phrase))
        return
    table, state = await _table(topic, getattr(message, "bot", None))
    await _reply(message, rules_html(topic, table, state=state) or "")


async def answer_howto(message, ask: HowTo) -> bool:
    """Отвечает справкой. False — ответить нечем, сообщение идёт дальше по диспетчеру."""
    if ask.kind in ("start", "menu"):
        topics = [ask.kind]
    elif ask.kind == "game":
        topics = [key for key in (ask.key, *ask.more) if key in SOLO_HELP or key in RULE_KEYS]
    else:
        topics = []
    if not topics:
        return False

    if ask.asked:
        chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
        user_id = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
        now = time.monotonic()
        topics = [topic for topic in topics if not _repeat(chat_id, user_id, topic, now)]

    for topic in topics:
        await _answer(message, topic)
    return True
