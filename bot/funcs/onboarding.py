"""Онбординг новичка: три клика, один следующий шаг на каждом экране.

Ветка «пусто»:
    /start → бесплатный баланс → игра в группе

Ветка «есть куты»:
    /start → выбор игры → запуск

Описание игры перед стартом — только из словаря GAMES:
    rules / board_lead / tip_lead / help_cmd — правьте там, с <tg-emoji …>.

Дом один: show_home(). Площадка: ONBOARDING_CLUB = auto|test|prod.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
import traceback
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from aiogram import F
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)

from main import (
    bot1,
    db,
    dp,
    gc_bot_can_serve_template,
    gc_bot_can_serve_venue,
    gc_get_active_assignment,
    gc_load_templates_for_user,
    gc_mark_templates_venue_status,
)

# ──────────────────────────────────────────────────────────────────────
# Клуб - площадка, куда онбординг ведёт играть по умолчанию
# ──────────────────────────────────────────────────────────────────────
# Меняется одной строкой здесь или переменной окружения ONBOARDING_CLUB:
#   "prod" - боевая группа -1001612636292 (@CuteGamingChat)
#   "test" - тестовая группа -1002135149822
#   "auto" - по DATABASE_MODE из bot/config/config.py (test -> test, main -> prod)
ONBOARDING_CLUB = "auto"  # <<< "auto" | "test" | "prod"

# name  - именительный падеж: «Площадка : …»
# where - предложный падеж:   «играть в …»
# У группы с юзернеймом обе формы - сам юзернейм.
_CLUB_PRESETS: Dict[str, Dict[str, Any]] = {
    "prod": {
        "chat_id": -1001612636292,
        "username": "CuteGamingChat",
        "name": "клуб",
        "where": "клубе",
    },
    "test": {  # приватная группа: ссылки через t.me/c/...
        "chat_id": -1002135149822,
        "username": "",
        "name": "тестовая группа",
        "where": "тестовой группе",
    },
}


def _resolve_club_mode() -> str:
    """Какой пресет клуба: env ONBOARDING_CLUB > константа > режим базы."""
    raw = (os.getenv("ONBOARDING_CLUB") or "").strip().lower()
    if not raw:
        raw = str(ONBOARDING_CLUB or "auto").strip().lower()
    if raw in ("prod", "main", "production"):
        return "prod"
    if raw in ("test", "sandbox"):
        return "test"

    mode = ""
    try:
        from bot.config.config import DATABASE_MODE
        mode = str(DATABASE_MODE or "").strip().lower()
    except Exception as e:
        print(f"[ONBOARDING] DATABASE_MODE недоступен: {e!r}")
    if not mode:
        mode = (os.getenv("APP_MODE") or "").strip().lower()
    return "test" if mode in ("test", "sandbox") else "prod"


def _public_chat_url(chat_id: int, username: str = "") -> str:
    """Ссылка на чат: по юзернейму, иначе внутренняя t.me/c/..."""
    name = str(username or "").strip().lstrip("@")
    if name and name.replace("_", "").isalnum():
        return f"https://t.me/{name}"
    raw = str(int(chat_id))
    return f"https://t.me/c/{raw[4:]}" if raw.startswith("-100") else f"https://t.me/{raw}"


def _club_from_mode(mode: str) -> Tuple[int, str, str, str, str]:
    preset = _CLUB_PRESETS.get(mode) or _CLUB_PRESETS["prod"]
    chat_id = int(preset["chat_id"])
    username = str(preset.get("username") or "").strip().lstrip("@")
    if username:
        name = where = f"@{username}"
    else:
        name = str(preset.get("name") or "клуб")
        where = str(preset.get("where") or "клубе")
    return chat_id, username, _public_chat_url(chat_id, username), name, where


CLUB_MODE = _resolve_club_mode()
CLUB_CHAT_ID, CLUB_USERNAME, CLUB_URL, CLUB_NAME, CLUB_WHERE = _club_from_mode(CLUB_MODE)
BOT_USERNAME = "CuteGamingBot"
BOT_URL = f"https://t.me/{BOT_USERNAME}"

# Ставка по умолчанию для первой игры.
FIRST_BET = 10

# Окно обучающих подсказок после первого /start.
NEWBIE_HINT_DAYS = 2

# Тот же адрес, что у кнопки меню «🌿 Ферма» в main.py.
_PROD_WEBAPP_URL = "https://cutegaming-mobet.ondigitalocean.app/"


def _farm_url() -> str:
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if not url.startswith("https://") or "ngrok" in url.lower():
        return _PROD_WEBAPP_URL
    return url


# Сколько бесплатных заданий на одной странице.
# Навигация появляется только если заданий больше этого числа.
FREE_QUESTS_PER_PAGE = 10

# Безопасная ставка: доля от баланса задания (10% = не сжечь всё сразу).
SAFE_BET_PERCENT = 10

# Быстрый выбор первой ставки на экране игры (инлайн-кнопки).
STAKE_PRESETS: Tuple[int, ...] = (2, 3, 5, 10, 15, 25, 50, 100)

# Длина текстового прогресс-бара.
PROGRESS_SEGMENTS = 10

# Этапы воронки: мягкий ориентир для новичка.
_PATH_STEPS = ("Вход", "Задание", "Игра")


def _path(step: int) -> str:
    """Вход · Задание · Игра - текущий этап жирным."""
    parts = []
    for i, name in enumerate(_PATH_STEPS):
        parts.append(f"<b>{name}</b>" if i == step else name)
    return " · ".join(parts)


def _lines(*parts: str) -> str:
    """Короткие строки экрана: пустые пропускаем, одна пустая = абзац."""
    out: List[str] = []
    blank_pending = False
    for part in parts:
        if part is None:
            continue
        raw = str(part)
        if not raw.strip():
            blank_pending = True
            continue
        if blank_pending and out:
            out.append("")
            blank_pending = False
        out.append(raw.rstrip())
    return "\n".join(out)


def _bq(*parts: str) -> str:
    """blockquote: каждая строка жирная. Для плотных карточек цифр."""
    chunks = [str(p) for p in parts if p is not None and str(p).strip()]
    lines: List[str] = []
    for chunk in chunks:
        for line in chunk.split("\n"):
            if not line.strip():
                continue
            plain = line.replace("<b>", "").replace("</b>", "")
            lines.append(f"<b>{plain}</b>")
    return f"<blockquote>{chr(10).join(lines)}</blockquote>"



def _progress_pct(current: int, target: int) -> int:
    if target <= 0:
        return 0
    return int(max(0, min(100, (current * 100) // target)))


def _progress_bar(current: int, target: int) -> str:
    pct = _progress_pct(current, target)
    filled = int(round(pct * PROGRESS_SEGMENTS / 100))
    filled = max(0, min(PROGRESS_SEGMENTS, filled))
    return "■" * filled + "□" * (PROGRESS_SEGMENTS - filled)


def _progress_line(current: int, target: int) -> str:
    """Живой прогресс до цели задания: [■■■□□□□□□□] 30%."""
    return (
        f"<tg-emoji emoji-id='5321021153219732362'>⚡️</tg-emoji> "
        f"[{_progress_bar(current, target)}] {_progress_pct(current, target)}%"
    )


def _quest_stats(wallet: "Wallet") -> str:
    """Прогресс задания — полный видимый текст с premium emoji.

    Меняйте строки и <tg-emoji …> прямо здесь.
    """
    left = max(0, wallet.target - wallet.amount)
    return (
        f"<tg-emoji emoji-id='5321021153219732362'>⚡️</tg-emoji> [{_progress_bar(wallet.amount, wallet.target)}] {_progress_pct(wallet.amount, wallet.target)}%\n"
        f"<tg-emoji emoji-id='5303547422373349738'>💰</tg-emoji> Баланс : {wallet.amount} кут\n"
        f"<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> Цель : {wallet.target} кут\n"
        f"<tg-emoji emoji-id='5321021153219732362'>⚡️</tg-emoji> До цели : {left} кут\n"
        f"<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> Награда : +{wallet.reward} кут"
    )


# Telegram принимает только эти style у InlineKeyboardButton.
# «default» в API нет — из‑за него весь reply_markup мог отвергаться,
# и _swap откатывался к тексту без premium emoji.
_BTN_STYLES = frozenset({"primary", "success", "danger"})


def _btn(text: str, *, data: str = None, url: str = None, web_app: str = None,
         icon: str = None, style: Optional[str] = None) -> InlineKeyboardButton:
    """Кнопка: опционально style (primary/success/danger) + premium-иконка."""
    kwargs: Dict[str, Any] = {"text": text}
    if style and str(style) in _BTN_STYLES:
        kwargs["style"] = str(style)
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    if web_app:
        kwargs["web_app"] = WebAppInfo(url=web_app)
    elif url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = data
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        # На случай сборки aiogram без style/icon - не роняем меню.
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


_TG_EMOJI_RE = re.compile(
    r"<tg-emoji[^>]*emoji-id=['\"]([0-9]+)['\"][^>]*>(.*?)</tg-emoji>",
    re.DOTALL,
)


def _emoji_id(value: str) -> Optional[str]:
    """ID премиум-эмодзи для icon_custom_emoji_id у кнопки."""
    m = _TG_EMOJI_RE.search(value or "")
    return m.group(1) if m else None


def _plain_emoji(value: str) -> str:
    """Убирает <tg-emoji> из текста, оставляет unicode и обычные слова.

    Важно: нельзя брать rfind('>') - это закрывающий тег, и в кнопку
    уезжал сырой HTML.
    """
    raw = (value or "").strip()
    if not raw:
        return raw
    return _TG_EMOJI_RE.sub(lambda m: (m.group(2) or "").strip(), raw).strip()


def _label_for_button(label: str) -> Tuple[str, Optional[str]]:
    """Текст кнопки + icon id. HTML в text не попадает."""
    icon = _emoji_id(label)
    text = _plain_emoji(label) or "·"
    if icon:
        # Иконку рисует Telegram - ведущий unicode не дублируем.
        parts = text.split(None, 1)
        if len(parts) == 2 and not parts[0][:1].isalnum():
            text = parts[1]
    return text, icon


# ──────────────────────────────────────────────────────────────────────
# Реестр одиночных игр
# ──────────────────────────────────────────────────────────────────────
# Логика партии ВСЕГДА в module/func (trade.py, slots.py, …).
# Онбординг только приводит новичка к сообщению и подсказывает команду.
#
# ВСЕ тексты описания игры перед стартом живут ЗДЕСЬ:
#   rules      — правила (🤙 / 👋), как увидит новичок
#   board_lead — подсказка, если нужен выбор (куб / трейд / рулетка)
#   tip_lead   — первая строка подсказки в группе после партии
#   help_cmd / help_examples — как писать команду самому
#
# Меняйте <tg-emoji …> и фразы прямо в словаре. Экран перед игрой
# собирается из emoji + title + rules + ставка/площадка + подсказка.


def _render_game_text(
    game: Dict[str, Any],
    *,
    bet: int,
    free_quest: bool,
    where: str,
    hint: str,
    extra: str = "",
) -> str:
    """Экран описания игры — только из полей GAMES (emoji/title/rules).

    Ставка и площадка подставляются автоматически:
      {bet} / с задания|с баланса / {where}
    Подсказка внизу — hint (или board_lead / «Начать играть»).
    """
    source = "с задания" if free_quest else "с баланса"
    emoji = str(game.get("emoji") or "").strip()
    title = str(game.get("title") or "Игра").strip()
    rules = str(game.get("rules") or "").strip("\n")

    parts: List[str] = [
        f"{emoji} <b>{title}</b>".strip(),
        "",
    ]
    if rules:
        parts.append(rules)
        parts.append("")
    parts.append(
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> "
        f"Ставка : {int(bet)} кут ({source})"
    )
    parts.append(
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {where}"
    )
    block = (extra or "").strip()
    if block:
        parts.extend(["", block])
    hint_text = (hint or "").strip() or "Нажмите «Начать играть»"
    parts.extend([
        "",
        f"<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>{hint_text}</b>",
    ])
    return "\n".join(parts)


def _game_action_hint(game: Dict[str, Any]) -> str:
    """Подсказка на экране выбора: board_lead → variant_hint → старт."""
    if game.get("variants"):
        return (
            str(game.get("board_lead") or "").strip()
            or str(game.get("variant_hint") or "").strip()
            or "Сделайте выбор"
        )
    return "Нажмите «Начать играть»"


def _variant_button_rows(
    variants: Sequence[Tuple[str, str]],
    *,
    bet: int,
    game_key: str,
    rows: Optional[Sequence[int]] = None,
) -> List[List[InlineKeyboardButton]]:
    """Кнопки выбора: либо явная раскладка рядов, либо аккуратная сетка."""
    buttons: List[InlineKeyboardButton] = []
    for label, value in variants:
        text, icon = _label_for_button(label)
        buttons.append(_btn(
            text,
            data=f"ob_play:{game_key}:{bet}:{value}",
            icon=icon,
            style="success",
        ))

    if not buttons:
        return []

    layout = [int(n) for n in (rows or ()) if int(n) > 0]
    if layout and sum(layout) == len(buttons):
        out: List[List[InlineKeyboardButton]] = []
        i = 0
        for width in layout:
            out.append(buttons[i:i + width])
            i += width
        return out

    per_row = 3 if len(buttons) > 4 else 2
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


GAMES: Dict[str, Dict[str, Any]] = {
    "soccer": {
        "title": "Футбол",
        "emoji": "<tg-emoji emoji-id='5373101763442255191'>⚽️</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "футбол {bet}",
        "help_cmd": "футбол (ваша ставка)",
        "help_examples": ("футбол 10",),
        "tip_lead": (
            "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> "
            "Ваша игра уже в нашей группе. Дальше - одной строкой."
        ),
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Гол - забираете большой выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо - теряете."
        ),
        "module": "bot.tggames.soccer",
        "func": "tgsoccer",
    },
    "slots": {
        "title": "Слоты",
        "emoji": "<tg-emoji emoji-id='5891135206580031104'>🎉</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "слоты {bet}",
        "help_cmd": "слоты (ваша ставка)",
        "help_examples": ("слоты 10",),
        "tip_lead": "<tg-emoji emoji-id='5891135206580031104'>🎉</tg-emoji> <b>Барабаны ждут.</b> Повтор - одной командой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Три одинаковых - крупный выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Иначе - теряете."
        ),
        "module": "bot.tggames.slots",
        "func": "tgslots",
    },
    "tank": {
        "title": "Башня",
        "emoji": "<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji>",
        "min": 2,
        "cmd": "башня {bet}",
        "help_cmd": "башня (ваша ставка)",
        "help_examples": ("башня 10",),
        "tip_lead": "<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji> <b>Этажи ждут.</b> Забирайте вовремя.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Забираете до обвала - выигрыш растёт.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Обвал - теряете."
        ),
        "module": "bot.games.tank",
        "func": "game_filter_tank",
    },
    "darts": {
        "title": "Дартс",
        "emoji": "<tg-emoji emoji-id='5890815115552362075'>🎯</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "дартс {bet}",
        "help_cmd": "дартс (ваша ставка)",
        "help_examples": ("дартс 10",),
        "tip_lead": "<tg-emoji emoji-id='5890815115552362075'>🎯</tg-emoji> <b>Дротик улетел.</b> Ещё бросок - одной строкой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> В центр - забираете большой выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо - теряете."
        ),
        "module": "bot.tggames.darts",
        "func": "tgdarts",
    },
    "basket": {
        "title": "Баскетбол",
        "emoji": "<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "баскет {bet}",
        "help_cmd": "баскет (ваша ставка)",
        "help_examples": ("баскет 10",),
        "tip_lead": "<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji> <b>Мяч в воздухе.</b> Ещё - одной командой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> В кольцо - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо - теряете."
        ),
        "module": "bot.tggames.basket",
        "func": "tgbasket",
    },
    "bowling": {
        "title": "Боулинг",
        "emoji": "<tg-emoji emoji-id='5891120371762990493'>🎳</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "боулинг {bet}",
        "help_cmd": "боулинг (ваша ставка)",
        "help_examples": ("боулинг 10",),
        "tip_lead": "<tg-emoji emoji-id='5891120371762990493'>🎳</tg-emoji> <b>Кегли ждут.</b> Ещё заход - одной строкой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Страйк - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Иначе - теряете."
        ),
        "module": "bot.tggames.bowling",
        "func": "tgbowling",
    },
    "kube": {
        "title": "Кубик",
        "emoji": "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "куб {bet} {v}",
        "help_cmd": "куб (ваша ставка) (число)",
        "help_examples": ("куб 10 4", "куб 10 6"),
        "tip_lead": "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> <b>Число выбрано.</b> Дальше - сами.",
        "board_lead": "Выберите число на кубике - партия стартует сразу.",
        "variants": [(str(n), str(n)) for n in range(1, 7)],
        "variant_rows": (3, 3),
        "variant_hint": "Выберите число",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Угадали число - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет - теряете."
        ),
        "module": "bot.tggames.kube",
        "func": "tgkube",
    },
    "balls": {
        "title": "Шарик",
        "emoji": "<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji>",
        "min": 2,
        "cmd": "шарик {bet}",
        "help_cmd": "шарик (ваша ставка)",
        "help_examples": ("шарик 10",),
        "tip_lead": "<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji> <b>Стаканы на столе.</b> Ещё - одной командой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Угадали стакан - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет - теряете."
        ),
        "module": "bot.games.balls",
        "func": "balls",
    },
    "provoda": {
        "title": "Провода",
        "emoji": "<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji>",
        "min": 2,
        "cmd": "провода {bet}",
        "help_cmd": "провода (ваша ставка)",
        "help_examples": ("провода 10",),
        "tip_lead": "<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji> <b>Верный провод.</b> Повтор - одной строкой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Верный провод - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Ошибка - теряете."
        ),
        "module": "bot.games.provoda",
        "func": "provoda",
    },
    "bombs": {
        "title": "Бомбы",
        "emoji": "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji>",
        "min": 3,
        "cmd": "бомбы {bet}",
        "help_cmd": "бомбы (ваша ставка)",
        "help_examples": ("бомбы 10",),
        "tip_lead": "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji> <b>Поле открыто.</b> Новая сетка - одной командой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Забираете до бомбы - выигрыш растёт.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Бомба - теряете всё."
        ),
        "module": "bot.games.bombs",
        "func": "bombs",
    },
    "plate": {
        "title": "Плиты",
        "emoji": "<tg-emoji emoji-id='5246916607833304803'>💫</tg-emoji>",
        "min": 2,
        "cmd": "плиты {bet}",
        "help_cmd": "плиты (ваша ставка)",
        "help_examples": ("плиты 10",),
        "tip_lead": "<tg-emoji emoji-id='5246916607833304803'>💫</tg-emoji> <b>Шаг за шагом.</b> Ещё забег - одной строкой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Забираете до провала - выигрыш растёт.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Провал - теряете."
        ),
        "module": "bot.games.plate",
        "func": "plate",
    },
    "risk": {
        "title": "Риск",
        "emoji": "<tg-emoji emoji-id='5438449312893792440'>🌴</tg-emoji>",
        "min": 5,
        "cmd": "риск {bet}",
        "help_cmd": "риск (ваша ставка)",
        "help_examples": ("риск 10",),
        "tip_lead": "<tg-emoji emoji-id='5438449312893792440'>🌴</tg-emoji> <b>Множитель растёт.</b> Новая волна - одной командой.",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Шаг умножает выигрыш - забираете вовремя.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Волна - теряете."
        ),
        "module": "bot.games.risk",
        "func": "risk",
    },
    "trade": {
        "title": "Трейд",
        "emoji": "<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji>",
        "min": 2,
        "instant": True,
        "cmd": "трейд {v} {bet}",
        "help_cmd": "трейд (направление) (ваша ставка)",
        "help_examples": ("трейд вверх 10", "трейд вниз 10"),
        "tip_lead": "<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji> <b>Сделка закрыта.</b> Дальше - сами.",
        "board_lead": "Куда пойдёт график? Нажмите кнопку - и партия начнётся сразу.",
        "variants": [
            ("<tg-emoji emoji-id='5339384049670593248'>↗️</tg-emoji> Вверх", "вверх"),
            ("<tg-emoji emoji-id='5339179750961224703'>📉</tg-emoji> Вниз", "вниз"),
        ],
        "variant_rows": (2,),
        "variant_hint": "Выберите направление",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Угадали направление - забираете выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет - теряете."
        ),
        "module": "bot.games.trade",
        "func": "trade",
    },
    "fortuna": {
        "title": "Рулетка",
        "emoji": "<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji>",
        "min": 3,
        "instant": True,
        "cmd": "рулетка {bet} {v}",
        "help_cmd": "рулетка (ваша ставка) (число / цвет / чёт)",
        "help_examples": ("рулетка 10 красное", "рулетка 10 черное", "рулетка 10 7"),
        "tip_lead": (
            "<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji> "
            "<b>Шарик остановился.</b> Следующий спин - одной строкой."
        ),
        "board_lead": "Число, цвет или чёт - нажмите и играйте.",
        # Ряды: 1–6 · 7–12 · красное/чёрное · чёт/нечет
        "variants": [
            ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"), ("6", "6"),
            ("7", "7"), ("8", "8"), ("9", "9"), ("10", "10"), ("11", "11"), ("12", "12"),
            ("<tg-emoji emoji-id='5339546996434812675'>🔴</tg-emoji> Красное", "красное"),
            ("<tg-emoji emoji-id='5424616516018537963'>⚫️</tg-emoji> Чёрное", "черное"),
            ("Чётное", "чет"),
            ("Нечётное", "нечет"),
        ],
        "variant_rows": (6, 6, 2, 2),
        "variant_hint": "Выберите число, цвет или чёт/нечет",
        "rules": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Угадали число, цвет или чёт - выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Нет - теряете."
        ),
        "module": "bot.games.Fortuna",
        "func": "Fortuna",
    },
}

# Порядок кнопок - порядок словаря: сверху самые быстрые и понятные.
SOLO_ORDER: Tuple[str, ...] = tuple(GAMES)

# Быстрые игры: партия кончается сразу, поэтому итог летит в личку следом.
INSTANT_GAMES = frozenset(k for k, g in GAMES.items() if g.get("instant"))


# ──────────────────────────────────────────────────────────────────────
# Состояние: что человек выбрал до вступления в клуб
# ──────────────────────────────────────────────────────────────────────
_pending: Dict[int, Tuple[str, int, Optional[str], float]] = {}
_launch_lock: Dict[int, float] = {}
# Токен запуска: не перетираем личку, если человек уже ушёл с экрана готовности.
_notify_token: Dict[int, int] = {}
# Сильные ссылки на фоновые запуски: иначе asyncio может тихо отменить задачу.
_bg_tasks: Set[asyncio.Task] = set()
_handler_cache: Dict[str, Any] = {}
_PENDING_TTL = 3600.0
_LAUNCH_COOLDOWN = 3.0


def _remember(user_id: int, game_key: str, bet: int, variant: Optional[str]) -> None:
    _pending[user_id] = (game_key, bet, variant, time.monotonic())


def _recall(user_id: int) -> Optional[Tuple[str, int, Optional[str]]]:
    item = _pending.get(user_id)
    if not item:
        return None
    game_key, bet, variant, born = item
    if time.monotonic() - born > _PENDING_TTL:
        _pending.pop(user_id, None)
        return None
    return game_key, bet, variant


def _too_fast(user_id: int) -> bool:
    now = time.monotonic()
    last = _launch_lock.get(user_id, 0.0)
    if now - last < _LAUNCH_COOLDOWN:
        return True
    _launch_lock[user_id] = now
    return False


def _bump_notify_token(user_id: int) -> int:
    token = int(time.monotonic() * 1000)
    _notify_token[user_id] = token
    return token


def _notify_token_alive(user_id: int, token: int) -> bool:
    return _notify_token.get(user_id) == token


def _spawn_bg(coro, *, label: str) -> asyncio.Task:
    """create_task с сильной ссылкой - иначе партия может исчезнуть до dice."""
    task = asyncio.create_task(coro, name=f"onboarding:{label}")
    _bg_tasks.add(task)

    def _done(done: asyncio.Task) -> None:
        _bg_tasks.discard(done)
        try:
            exc = done.exception()
        except asyncio.CancelledError:
            print(f"[ONBOARDING] фон отменён: {label}")
            return
        if exc is not None:
            print(f"[ONBOARDING] фон упал ({label}): {exc!r}")
            print(traceback.format_exc())

    task.add_done_callback(_done)
    return task


def _resolve_handler(game: Dict[str, Any]):
    """Обработчик игры: module:func, с кэшем после первого импорта."""
    module = str(game.get("module") or "")
    func = str(game.get("func") or "")
    key = f"{module}:{func}"
    cached = _handler_cache.get(key)
    if cached is not None:
        return cached
    if not module or not func:
        raise RuntimeError(f"у игры нет handler: {game.get('title')!r}")
    mod = import_module(module)
    handler = getattr(mod, func, None)
    if handler is None or not callable(handler):
        raise RuntimeError(f"handler не найден: {key}")
    _handler_cache[key] = handler
    return handler


def _allowed_variants(game: Dict[str, Any]) -> Dict[str, str]:
    """value → label для проверки выбора перед запуском."""
    out: Dict[str, str] = {}
    for label, value in (game.get("variants") or ()):
        out[str(value)] = str(label)
    return out


def _build_launch_command(game: Dict[str, Any], bet: int, variant: Optional[str]) -> str:
    """Рабочая команда для синтетического сообщения в группе."""
    template = str(game.get("cmd") or "").strip()
    if not template:
        raise ValueError(f"пустой шаблон команды у {game.get('title')!r}")

    allowed = _allowed_variants(game)
    if allowed:
        pick = "" if variant is None else str(variant)
        if pick not in allowed:
            raise ValueError(
                f"нужен выбор для {game.get('title')!r}, получено {variant!r}"
            )
        text = template.format(bet=int(bet), v=pick)
    else:
        text = template.format(bet=int(bet), v="")

    command = " ".join(str(text).split())
    if not command:
        raise ValueError(f"команда пустая после сборки у {game.get('title')!r}")
    return command


def _synthetic_command_message(anchor: Message, user: User, command: str) -> Message:
    """Сообщение «как от игрока»: тот же якорь в чате, текст - игровая команда.

    Не копируем HTML-entities якоря - у команды свой чистый текст.
    """
    chat = anchor.chat
    if not isinstance(chat, Chat):
        raise RuntimeError("у якоря нет chat")

    thread_id = getattr(anchor, "message_thread_id", None)
    date = anchor.date or datetime.now(timezone.utc)
    try:
        synthetic = Message(
            message_id=int(anchor.message_id),
            date=date,
            chat=chat,
            from_user=user,
            text=command,
            message_thread_id=thread_id,
        )
    except Exception:
        # Старые/новые версии aiogram могут отличаться набором полей.
        synthetic = anchor.model_copy(update={
            "text": command,
            "from_user": user,
            "entities": None,
            "caption_entities": None,
        })
    return synthetic.as_(bot1)


# ──────────────────────────────────────────────────────────────────────
# Кошелёк игрока: свои куты или виртуальный баланс бесплатного задания
# ──────────────────────────────────────────────────────────────────────
class Wallet:
    """Откуда списывается ставка прямо сейчас.

    У бесплатного задания свой баланс: игры берут ставку из него, а не из
    кут игрока. Поэтому проверять перед запуском нужно именно его, иначе
    человек с нулём на счету увидит «не хватает» на задании, где всё есть.
    """

    def __init__(self, amount: int, *, free_quest: bool = False,
                 max_bet: Optional[int] = None, chat_id: Optional[int] = None,
                 chat_ref: Optional[str] = None, target: int = 0, reward: int = 0):
        self.amount = amount
        self.free_quest = free_quest
        self.max_bet = max_bet
        self.chat_id = chat_id
        self.chat_ref = chat_ref
        self.target = target
        self.reward = reward

    @property
    def in_club(self) -> bool:
        """Задание привязано к клубу - значит игру можно запустить отсюда."""
        if not self.free_quest:
            return True
        if self.chat_id and int(self.chat_id) == CLUB_CHAT_ID:
            return True
        if CLUB_USERNAME and self.chat_ref and CLUB_USERNAME.lower() in str(self.chat_ref).lower():
            return True
        return not self.chat_id and not self.chat_ref


async def _wallet(user_id: int) -> Wallet:
    """Кошелёк для онбординга.

    Важно: в dict из get_active_gc_assignment часто НЕТ поля free -
    оно живёт в шаблоне. Раньше из-за этого бесплатное задание
    не виделось, и бот думал, что у новичка 0 кут.
    """
    assignment = await _active_free_quest(user_id)
    if assignment is None:
        return Wallet(await _balance(user_id))

    current = await _quest_balance(user_id, assignment)
    max_bet = _int(assignment.get("betlimit")) or None
    if max_bet is not None and max_bet <= 0:
        max_bet = None

    return Wallet(
        current,
        free_quest=True,
        max_bet=max_bet,
        chat_id=_int(assignment.get("target_chat_id")) or None,
        chat_ref=assignment.get("target_chat_ref"),
        target=_int(assignment.get("target_amount")),
        reward=_int(assignment.get("reward_amount")),
    )


async def _active_quest(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        assignment = await gc_get_active_assignment(user_id)
    except Exception as e:
        print(f"[ONBOARDING] Активное задание {user_id}: {e!r}")
        return None
    return assignment if isinstance(assignment, dict) else None


async def _active_free_quest(user_id: int) -> Optional[Dict[str, Any]]:
    """Только бесплатное активное задание (free='+')."""
    assignment = await _active_quest(user_id)
    if assignment is None:
        return None
    if not await _assignment_is_free(user_id, assignment):
        return None
    enriched = dict(assignment)
    enriched["free"] = "+"
    return enriched


async def _assignment_is_free(user_id: int, assignment: Dict[str, Any]) -> bool:
    """free может отсутствовать в assignment - читаем из шаблона."""
    raw = str(assignment.get("free") or "").strip()
    if raw == "+":
        return True
    if raw == "-":
        return False

    try:
        if await db.gc_active_is_free(user_id):
            return True
    except Exception as e:
        print(f"[ONBOARDING] gc_active_is_free {user_id}: {e!r}")

    tid = _int(assignment.get("template_id"))
    if tid <= 0:
        return False
    try:
        flag = await db.get_gc_template_free_flag(tid)
        return str(flag or "").strip() == "+"
    except Exception as e:
        print(f"[ONBOARDING] get_gc_template_free_flag {tid}: {e!r}")
        return False


async def _quest_balance(user_id: int, assignment: Dict[str, Any]) -> int:
    """Текущий виртуальный баланс задания.

    Источник истины в БД: two_balance_initial (текущий).
    two_balance - стартовая сумма (фолбэк).
    """
    try:
        current = await db.gc_get_current_two_balance(user_id)
        if current is not None:
            return _int(current)
    except Exception as e:
        print(f"[ONBOARDING] gc_get_current_two_balance {user_id}: {e!r}")

    if assignment.get("two_balance_initial") is not None:
        return _int(assignment.get("two_balance_initial"))
    return _int(assignment.get("two_balance"))


def _wallet_from_assignment(assignment: Dict[str, Any], *, is_free: bool) -> Wallet:
    """Собрать кошелёк из уже известной строки assignment (после take)."""
    if assignment.get("two_balance_initial") is not None:
        current = _int(assignment.get("two_balance_initial"))
    else:
        current = _int(assignment.get("two_balance"))
    max_bet = _int(assignment.get("betlimit")) or None
    if max_bet is not None and max_bet <= 0:
        max_bet = None
    return Wallet(
        current,
        free_quest=is_free,
        max_bet=max_bet,
        chat_id=_int(assignment.get("target_chat_id")) or None,
        chat_ref=assignment.get("target_chat_ref"),
        target=_int(assignment.get("target_amount")),
        reward=_int(assignment.get("reward_amount")),
    )


def _bet_cap(game: Dict[str, Any], wallet: Wallet) -> int:
    """Максимум, который можно поставить сейчас."""
    cap = int(wallet.amount)
    if wallet.max_bet is not None:
        cap = min(cap, int(wallet.max_bet))
    return max(0, cap)


def _bet_for(game: Dict[str, Any], wallet: Wallet) -> int:
    """Ставка по умолчанию (если человек не выбрал кнопку).

    На задании берём ~10% виртуального баланса - новичок реже сжигает всё.
    Иначе - обычная первая ставка, но не ниже минимума игры.
    """
    floor = int(game["min"])
    cap = _bet_cap(game, wallet)
    if cap < floor:
        return 0

    if wallet.free_quest:
        safe = max(floor, (wallet.amount * SAFE_BET_PERCENT) // 100)
        bet = min(safe, cap)
    else:
        bet = min(max(FIRST_BET, floor), cap)

    return bet if bet >= floor else 0


def _stake_choices(game: Dict[str, Any], wallet: Wallet) -> List[int]:
    """Суммы для инлайн-кнопок выбора ставки."""
    floor = int(game["min"])
    cap = _bet_cap(game, wallet)
    if cap < floor:
        return []

    picks: List[int] = []
    for n in STAKE_PRESETS:
        if floor <= int(n) <= cap:
            picks.append(int(n))

    # Рекомендуемая (~10%) и «все, что можно» - если ещё не в списке.
    recommended = min(cap, max(floor, (wallet.amount * SAFE_BET_PERCENT) // 100))
    for n in (floor, recommended, cap):
        n = int(n)
        if floor <= n <= cap and n not in picks:
            picks.append(n)

    picks.sort()
    # Не больше 12 кнопок: минимум, середина, максимум.
    if len(picks) > 12:
        head = picks[:4]
        mid = picks[len(picks) // 2 - 2: len(picks) // 2 + 2]
        tail = picks[-4:]
        merged: List[int] = []
        for n in head + mid + tail:
            if n not in merged:
                merged.append(n)
        picks = sorted(merged)[:12]
    return picks


def _stake_button_rows(game_key: str, stakes: Sequence[int]) -> List[List[InlineKeyboardButton]]:
    """Кнопки ставки: по 4 в ряд."""
    buttons = [
        _btn(str(n), data=f"ob_stake:{game_key}:{n}", style="success")
        for n in stakes
    ]
    return [buttons[i:i + 4] for i in range(0, len(buttons), 4)]


# ──────────────────────────────────────────────────────────────────────
# Экран 1 - /start  (бренд)
# Рабочие экраны - отдельно: задания, игры, полное меню.
# ──────────────────────────────────────────────────────────────────────
async def start_screen(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    """Первый экран: статус клуба + одно главное действие."""
    wallet = await _wallet(user_id)

    # Активное задание в группе, где бот не админ - не ведём новичка в тупик.
    if wallet.free_quest:
        try:
            venue_ok, _reason = await gc_bot_can_serve_venue(
                wallet.chat_id, wallet.chat_ref,
            )
        except Exception as e:
            print(f"[ONBOARDING] start venue check: {e!r}")
            venue_ok = False
        if not venue_ok:
            where = str(wallet.chat_ref or "").strip() or "группе задания"
            text = _lines(
                "<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> <b>Задание на паузе</b>",
                "",
                _quest_stats(wallet),
                "",
                f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {where}",
                "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Бот должен быть администратором.",
                "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Можно взять другое задание.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
                [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
            ])
            return text, markup

    ready = wallet.amount >= _cheapest_bet()

    if wallet.free_quest:
        # На задании всегда видно три пути: играть дальше, сменить, закончить.
        text = _start_text_player(wallet) if ready else _quest_stuck_text(wallet)
        first = (
            _btn("Продолжить задание", data="ob_games", icon="5472041540605975004", style="success")
            if ready else
            _btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")
        )
        rows = [[first]]
        if ready:
            rows.append([_btn("Другое задание", data="ob_earn", icon="5472401690793614752")])
        rows.append([_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")])
        rows.append([_btn("Меню", data="ob_menu", icon="5318892863780579996")])
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    if ready:
        text = _start_text_player(wallet)
        cta = _btn("Играть!", data="ob_games", icon="5472041540605975004", style="success")
    else:
        text = _start_text_newcomer()
        cta = _btn("Получить куты", data="ob_earn", icon="5472401690793614752", style="success")

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [cta],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])
    return text, markup


def _quest_stuck_text(wallet: Wallet) -> str:
    """Задание активно, но виртуального баланса не хватает даже на минимум."""
    return _lines(
        "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> <b>Баланс задания закончился</b>",
        "",
        _quest_stats(wallet),
        "",
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Так бывает - это не конец.",
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Другое задание даст новый баланс.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
    )


def _cheapest_bet() -> int:
    return min(int(g["min"]) for g in GAMES.values())


def _start_text_newcomer() -> str:
    """Первый экран пустого баланса: бренд → выгода → одно действие."""
    return (
        "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Кут</b>\n"
        "\n"
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> 1 кут = 1 "
        "<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji>\n"
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Первый баланс - бесплатно.\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Выигрыш можно вывести в Stars.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Получить куты»</b>"
    )


def _start_text_player(wallet: Wallet) -> str:
    if wallet.free_quest:
        return _lines(
            "<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> <b>Задание в работе</b>",
            "",
            _quest_stats(wallet),
            "",
            f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {_venue_where(wallet)}",
            "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты не тратятся.",
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Продолжить задание»</b>",
        )
    return _lines(
        "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Кут</b>",
        "",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {wallet.amount} кут",
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> 1 кут = 1 "
        "<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji>",
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {CLUB_WHERE}",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Играть!»</b>",
    )


async def _menu_rows(user_id: Optional[int] = None) -> List[List[InlineKeyboardButton]]:
    """Полное меню - только по кнопке «Меню», не на первом экране."""
    rows: List[List[InlineKeyboardButton]] = []

    bonus = _bonus_button()
    if bonus:
        rows.append([bonus])

    free_quest = False
    if user_id is not None:
        try:
            free_quest = bool((await _wallet(user_id)).free_quest)
        except Exception as e:
            print(f"[ONBOARDING] menu wallet {user_id}: {e!r}")

    rows.extend([
        [_btn("О Куте", data="3412helpstarthelp", icon="5436339947080548936")],
        [_btn("Профиль", data="9back_to_menu1", icon="5192951739623447936")],
        [_btn("Вывод", data="conc_stars", icon="5848021027782661221"),
         _btn("Донат", data="insert_stars", icon="5848259999763011021")],
        [_btn("Задания", data="questions_stars", icon="5318892863780579996")],
    ])
    if free_quest:
        rows.append([_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")])
    rows.extend([
        [_btn("Ферма", web_app=_farm_url(), icon="5208464835079082371")],
        [_btn("Чёрный рынок", data="blackshop", icon="5438440765908874600")],
        [_btn("О нас", data="about_start", icon="6037421444789440735")],
        [_btn("Назад", data="ob_start", icon="5226660202035554522")],
    ])
    return rows


async def _menu_text(user_id: int) -> str:
    wallet = await _wallet(user_id)
    if wallet.free_quest:
        return _lines(
            "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Меню</b>",
            "",
            "<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> Задание активно.",
            _quest_stats(wallet),
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите раздел</b>",
        )
    return _lines(
        "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Меню</b>",
        "",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {wallet.amount} кут",
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> 1 кут = 1"
        "<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji>",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите раздел</b>",
    )


def _bonus_button() -> Optional[InlineKeyboardButton]:
    """Тот же callback, что у бонуса в старом меню: случайное число + '_+'."""
    try:
        from bot.config.config import bonusbet, enabled_bonus
        if not enabled_bonus:
            return None
        return _btn("Бонус", data=f"{random.randint(1, bonusbet)}_+", icon="5294001020039363545")
    except Exception as e:
        print(f"[ONBOARDING] Кнопка бонуса недоступна: {e!r}")
        return None


async def start_payload_screen(
    user_id: int,
    payload: str = "",
) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    """Deep-link с /start: earn → сразу к бесплатным заданиям.

    Нужен кнопке «Другое задание» из группы (?start=earn), чтобы новичок
    не попадал на общий дом, а сразу видел следующий шаг.
    """
    key = str(payload or "").strip().lower()
    if key not in ("earn", "ob_earn", "free", "getkut"):
        return None

    free = await _free_quests(user_id)
    if not free:
        return _no_quests_bridge_text(), _no_quests_bridge_markup()

    rows: List[List[InlineKeyboardButton]] = [
        [_btn(
            f"{_int(q.get('start_amount'))} → {_int(q.get('target_amount'))}"
            f" · +{_int(q.get('reward_amount'))}",
            data=f"ob_quest:{_quest_id(q)}:0",
            icon="5472401690793614752",
            style="success",
        )]
        for q in free[:FREE_QUESTS_PER_PAGE]
    ]
    if len(free) > FREE_QUESTS_PER_PAGE:
        pages = max(1, (len(free) + FREE_QUESTS_PER_PAGE - 1) // FREE_QUESTS_PER_PAGE)
        rows.append(_earn_nav(0, pages))
    rows.append([_btn("Назад", data="ob_start", icon="5226660202035554522")])
    return _earn_list_text(), InlineKeyboardMarkup(inline_keyboard=rows)


async def show_home(message: Message, user_id: int, *, as_new: bool = False) -> bool:
    """Показать главный экран онбординга в этом сообщении.

    Дом у бота один: и /start, и возвраты из «О Куте», бонуса и прочих
    разделов приводят сюда, иначе новичок теряет прогресс задания из виду.
    as_new=True - отправить новым сообщением вместо перерисовки.
    Возвращает False, если показать не вышло: вызывающий код покажет
    свой запасной экран.
    """
    try:
        text, markup = await start_screen(user_id)
    except Exception as e:
        print(f"[ONBOARDING] show_home({user_id}) экран: {e!r}")
        return False

    _bump_notify_token(user_id)
    send = message.answer if as_new else message.edit_text
    last_err: Optional[BaseException] = None
    for name, body, kb in (
        ("full", text, markup),
        ("no_icons", text, _rebuild_markup(markup, keep_icons=False, keep_styles=True)),
        ("bare_kb", text, _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
        ("plain", _html_plain(text), _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
    ):
        try:
            await send(
                body, reply_markup=kb,
                parse_mode="HTML", disable_web_page_preview=True,
            )
            if name != "full":
                print(f"[ONBOARDING] show_home fallback={name} err={last_err!r}")
            return True
        except Exception as e:
            last_err = e
            if "message is not modified" in str(e).lower():
                return True
            if not _can_downgrade_markup(e):
                print(f"[ONBOARDING] show_home({user_id}) без даунгрейда: {e!r}")
                break
    print(f"[ONBOARDING] show_home({user_id}): не удалось показать ({last_err!r})")
    return False


@dp.callback_query(F.data == "ob_start")
async def ob_start(call: CallbackQuery):
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    text, markup = await start_screen(call.from_user.id)
    await _swap(call, text, markup)


@dp.callback_query(F.data == "ob_menu")
async def ob_menu(call: CallbackQuery):
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    text = await _menu_text(call.from_user.id)
    markup = InlineKeyboardMarkup(inline_keyboard=await _menu_rows(call.from_user.id))
    await _swap(call, text, markup)


# ──────────────────────────────────────────────────────────────────────
# Закончить задание: подтверждение -> развилка «другое» / «играть сам»
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_finish")
async def ob_finish(call: CallbackQuery):
    """Спрашиваем подтверждение - досрочный выход обнуляет прогресс."""
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    wallet = await _wallet(call.from_user.id)
    if not wallet.free_quest:
        await _swap(call, _finish_none_text(), _finish_none_markup())
        return
    await _swap(call, _finish_ask_text(wallet), _finish_ask_markup())


@dp.callback_query(F.data == "ob_finish_no")
async def ob_finish_no(call: CallbackQuery):
    """Передумал - возвращаем на главный экран задания."""
    await _ack(call)
    text, markup = await start_screen(call.from_user.id)
    await _swap(call, text, markup)


@dp.callback_query(F.data == "ob_finish_yes")
async def ob_finish_yes(call: CallbackQuery):
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    user_id = call.from_user.id

    wallet = await _wallet(user_id)
    if not wallet.free_quest:
        await _swap(call, _finish_none_text(), _finish_none_markup())
        return

    try:
        ok = bool(await db.cancel_gc_assignment(user_id))
    except Exception as e:
        print(f"[ONBOARDING] cancel_gc_assignment {user_id}: {e!r}")
        ok = False

    if not ok:
        # Задание осталось активным - не бросаем человека на пустом экране.
        await _ack(call, "Не получилось закончить задание. Попробуйте ещё раз.", alert=True)
        text, markup = await start_screen(user_id)
        await _swap(call, text, markup)
        return

    balance = await _balance(user_id)
    await _swap(call, _finish_done_text(balance), _finish_done_markup(balance))


def _finish_ask_text(wallet: Wallet) -> str:
    return _lines(
        "<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> <b>Закончить задание?</b>",
        "",
        _quest_stats(wallet),
        "",
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Прогресс задания сгорит.",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Потом можно взять другое.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Можно вернуться и доиграть</b>",
    )


def _finish_ask_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Вернуться к заданию", data="ob_finish_no", icon="5472041540605975004", style="success")],
        [_btn("Да, закончить", data="ob_finish_yes", icon="5449372007432985754")],
    ])


def _finish_done_text(balance: int) -> str:
    can_play = balance >= _cheapest_bet()
    parts = [
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Задание закончено</b>",
        "",
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {balance} кут",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Другое задание даст новый баланс.",
    ]
    if can_play:
        parts.append(f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {CLUB_WHERE}")
        parts.append(
            "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> Или играйте сами."
        )
    hint = "Выберите: другое задание или играть самому" if can_play else "Нажмите «Другое задание»"
    return _lines(*parts, "", f"<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>{hint}</b>")


def _finish_done_markup(balance: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
    ]
    if balance >= _cheapest_bet():
        rows.append([_btn("Играть сам", data="ob_games", icon="5472041540605975004", style="success")])
    rows.append([_btn("Меню", data="ob_menu", icon="5318892863780579996")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _finish_none_text() -> str:
    return (
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Активного задания нет</b>\n"
        "\n"
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Возьмите бесплатный баланс и сыграйте.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Получить куты»</b>"
    )


def _finish_none_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Получить куты", data="ob_earn", icon="5472401690793614752", style="success")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


# ──────────────────────────────────────────────────────────────────────
# Ветка «пусто», клик 2 - бесплатные задания
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_earn")
async def ob_earn(call: CallbackQuery):
    await _ack(call)
    await _show_earn(call, page=0)


@dp.callback_query(F.data.startswith("ob_earn:"))
async def ob_earn_page(call: CallbackQuery):
    """Пагинация списка бесплатных заданий."""
    try:
        page = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await _ack(call)
    await _show_earn(call, page=max(0, page))


async def _show_earn(call: CallbackQuery, page: int = 0) -> None:
    free = await _free_quests(call.from_user.id)
    if not free:
        # Бесплатных заданий нет - сначала объясняем, потом бонус.
        await _swap(call, _no_quests_bridge_text(), _no_quests_bridge_markup())
        return

    total = len(free)
    pages = max(1, (total + FREE_QUESTS_PER_PAGE - 1) // FREE_QUESTS_PER_PAGE)
    page = min(page, pages - 1)
    start = page * FREE_QUESTS_PER_PAGE
    chunk = free[start:start + FREE_QUESTS_PER_PAGE]

    rows: List[List[InlineKeyboardButton]] = [
        [_btn(
            f"{_int(q.get('start_amount'))} → {_int(q.get('target_amount'))}"
            f" · +{_int(q.get('reward_amount'))}",
            data=f"ob_quest:{_quest_id(q)}:{page}",
            icon="5472401690793614752",
            style="success",
        )]
        for q in chunk
    ]

    if total > FREE_QUESTS_PER_PAGE:
        rows.append(_earn_nav(page, pages))

    rows.append([_btn("Назад", data="ob_start", icon="5226660202035554522")])
    await _swap(call, _earn_list_text(), InlineKeyboardMarkup(inline_keyboard=rows))


def _earn_list_text() -> str:
    return (
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> <b>Бесплатный баланс</b>\n"
        "\n"
        "<blockquote>"
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Берёте задание - играете к цели.\n"
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> <b>Свои куты не списываются.</b>"
        "</blockquote>\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите задание</b>"
    )


def _earn_nav(page: int, pages: int) -> List[InlineKeyboardButton]:
    """Стрелки как в магазине: назад · N/M · вперёд."""
    row: List[InlineKeyboardButton] = []
    prev_page = page - 1 if page > 0 else pages - 1
    next_page = page + 1 if page < pages - 1 else 0
    row.append(_btn(" ", data=f"ob_earn:{prev_page}", icon="5805509901048356965"))
    row.append(_btn(f"{page + 1}/{pages}", data="ob_noop"))
    row.append(_btn(" ", data=f"ob_earn:{next_page}", icon="5807453545548487345"))
    return row


@dp.callback_query(F.data == "ob_noop")
async def ob_noop(call: CallbackQuery):
    await _ack(call)


@dp.callback_query(F.data.startswith("ob_quest:"))
async def ob_quest(call: CallbackQuery):
    """Карточка задания. Берёт его штатный обработчик qst:gcstart."""
    parts = (call.data or "").split(":")
    try:
        quest_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        await _ack(call, "Задание не открылось", alert=True)
        return

    await _ack(call)

    quest = next(
        (q for q in await _free_quests(call.from_user.id) if _quest_id(q) == quest_id),
        None,
    )
    if quest is None:
        # Задание исчезло из списка - не уводим в бонус, а обратно к выбору.
        await _show_earn(call, page=page)
        return

    await _swap(call, _earn_card_text(quest), _earn_card_markup(quest_id, page))


def _earn_card_text(quest: Dict[str, Any]) -> str:
    start = _int(quest.get("start_amount"))
    target = _int(quest.get("target_amount"))
    reward = _int(quest.get("reward_amount"))
    limit = _int(quest.get("betlimit"))
    card = (
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> <b>{start} → {target} кут</b>\n"
        f"<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> Награда : <b>+{reward} кут</b>"
    )
    if limit:
        card += (
            f"\n<tg-emoji emoji-id='5471954679250498498'>🛡</tg-emoji> "
            f"Ставка до : {limit} кут"
        )
    return (
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> <b>Бесплатный вход</b>\n"
        "\n"
        f"<blockquote>{card}</blockquote>\n"
        "\n"
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Взять задание»</b>"
    )


def _earn_card_markup(quest_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Взять задание", data=f"ob_take:{quest_id}:{page}", icon="5472041540605975004", style="success")],
        [_btn("Назад", data=f"ob_earn:{page}", icon="5226660202035554522")],
    ])


@dp.callback_query(F.data.startswith("ob_take:"))
async def ob_take(call: CallbackQuery):
    """Берём задание сами и сразу ведём в выбор игры."""
    parts = (call.data or "").split(":")
    try:
        quest_id = int(parts[1])
    except (ValueError, IndexError):
        await _ack(call, "Задание не открылось", alert=True)
        return

    # Отвечаем до похода в базу: выдача задания - несколько запросов подряд,
    # и на медленной связи ответ на нажатие успел бы просрочиться.
    await _ack(call, "Беру задание…")

    ok, msg, created = await _activate_quest(call.from_user.id, quest_id)
    if not ok:
        await _swap(call, _take_error_text(msg), _take_error_markup())
        return

    wallet = await _wallet(call.from_user.id)
    # Если кэш/реплика ещё не отдала free - собираем кошелёк из созданной строки.
    if (not wallet.free_quest or wallet.amount <= 0) and created:
        wallet = _wallet_from_assignment(created, is_free=True)

    if not wallet.free_quest or wallet.amount < _cheapest_bet():
        print(
            f"[ONBOARDING] После take кошелёк пуст: user={call.from_user.id} "
            f"free={wallet.free_quest} amount={wallet.amount} created={bool(created)}"
        )
        await _swap(
            call,
            _take_failed_text(),
            InlineKeyboardMarkup(inline_keyboard=[
                [_btn("К заданиям", data="ob_earn", icon="5472401690793614752", style="success")],
                [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
            ]),
        )
        return

    await _swap(call, _games_text(wallet, accepted=True), _games_markup(wallet))


async def _activate_quest(
    user_id: int, template_id: int,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Создаёт бесплатное задание. При другом активном - заменяет его.

    Возвращает (ok, сообщение, assignment|None).
    """
    try:
        tpl = await db.get_gc_template_by_id(template_id)
    except Exception as e:
        print(f"[ONBOARDING] get_gc_template_by_id: {e!r}")
        tpl = None
    if not tpl:
        return False, "Это задание больше недоступно.", None

    status = str(tpl.get("status") or "active").lower()
    if status not in ("active", ""):
        return False, "Это задание отключено.", None

    if str(tpl.get("free") or "-").strip() != "+":
        return False, "Это задание недоступно бесплатно.", None

    # Новичок не должен взять задание в группе, где бот не админ.
    try:
        venue_ok, venue_reason = await gc_bot_can_serve_template(tpl)
    except Exception as e:
        print(f"[ONBOARDING] venue check fail: {e!r}")
        venue_ok, venue_reason = False, "error"
    if not venue_ok:
        print(
            f"[ONBOARDING] Отказ take: бот не админ в группе задания "
            f"tid={template_id} reason={venue_reason}"
        )
        return False, "Это задание сейчас недоступно. Выберите другое.", None

    existing = None
    try:
        existing = await db.get_active_gc_assignment(user_id)
    except Exception as e:
        print(f"[ONBOARDING] get_active_gc_assignment: {e!r}")

    if existing:
        try:
            existing_tid = int(existing.get("template_id") or 0)
        except Exception:
            existing_tid = 0
        if existing_tid == template_id:
            enriched = _enrich_assignment_from_template(existing, tpl)
            return True, "Задание уже активно.", enriched
        try:
            await db.remove_assignment_by_user(user_id, restore_slot=True)
        except TypeError:
            try:
                await db.remove_assignment_by_user(user_id)
            except Exception as e:
                print(f"[ONBOARDING] remove_assignment_by_user: {e!r}")
                return False, "Не удалось сменить задание.", None
        except Exception as e:
            print(f"[ONBOARDING] remove_assignment_by_user: {e!r}")
            return False, "Не удалось сменить задание.", None

    # слоты
    try:
        tpl = await db.get_gc_template_by_id(template_id) or tpl
        max_u = tpl.get("max_users")
        done_u = int(tpl.get("completed_users") or 0)
        if max_u is not None:
            max_i = int(max_u)
            if max_i <= 0 or done_u >= max_i:
                return False, "Все слоты этого задания уже заняты.", None
    except Exception:
        pass

    try:
        reserved = await db.increment_gc_template_completed(template_id, step=1)
    except TypeError:
        try:
            reserved = await db.increment_gc_template_completed(template_id)
        except Exception as e:
            print(f"[ONBOARDING] increment_gc_template_completed: {e!r}")
            return False, "Не удалось взять задание.", None
    except Exception as e:
        print(f"[ONBOARDING] increment_gc_template_completed: {e!r}")
        return False, "Не удалось взять задание.", None

    if not reserved:
        return False, "Все слоты этого задания уже заняты.", None

    two_init = _int(tpl.get("start_amount"))
    if two_init <= 0:
        try:
            await db.decrement_gc_template_completed(template_id, step=1)
        except Exception:
            pass
        return False, "У задания нет стартового баланса.", None

    betlimit = tpl.get("betlimit")
    try:
        betlimit = None if betlimit in (None, "", 0, "0") else int(betlimit)
    except Exception:
        betlimit = None

    try:
        first_name = await db.get_firstname_by_user_id(user_id)
    except Exception:
        first_name = None
    try:
        username = await db.get_username_by_user_id(user_id)
    except Exception:
        username = None

    try:
        created = await db.create_active_assignment(
            user_id,
            template_id=template_id,
            first_name=first_name,
            username=username,
            two_balance_initial=two_init,
            betlimit=betlimit,
            target_amount=_int(tpl.get("target_amount")),
            reward_amount=_int(tpl.get("reward_amount")),
        )
    except TypeError:
        # Старая сигнатура - только позиционные.
        try:
            created = await db.create_active_assignment(
                user_id,
                template_id,
                first_name,
                username,
                two_init,
                betlimit,
                _int(tpl.get("target_amount")),
                _int(tpl.get("reward_amount")),
            )
        except Exception as e:
            print(f"[ONBOARDING] create_active_assignment: {e!r}")
            created = None
    except Exception as e:
        print(f"[ONBOARDING] create_active_assignment: {e!r}")
        created = None

    if not created:
        try:
            await db.decrement_gc_template_completed(template_id, step=1)
        except Exception:
            try:
                await db.decrement_gc_template_completed(template_id)
            except Exception:
                pass
        return False, "Не удалось взять задание. Попробуйте ещё раз.", None

    enriched = _enrich_assignment_from_template(created, tpl)
    return True, "Задание принято. Виртуальный баланс начислен.", enriched


def _enrich_assignment_from_template(
    assignment: Dict[str, Any], tpl: Dict[str, Any],
) -> Dict[str, Any]:
    """Добавляет free/чат/цифры шаблона - их может не быть в строке assignment."""
    out = dict(assignment or {})
    out["free"] = "+"
    if out.get("target_chat_id") is None and tpl.get("target_chat_id") is not None:
        out["target_chat_id"] = tpl.get("target_chat_id")
    if not out.get("target_chat_ref") and tpl.get("target_chat_ref"):
        out["target_chat_ref"] = tpl.get("target_chat_ref")
    if not _int(out.get("target_amount")) and tpl.get("target_amount") is not None:
        out["target_amount"] = tpl.get("target_amount")
    if not _int(out.get("reward_amount")) and tpl.get("reward_amount") is not None:
        out["reward_amount"] = tpl.get("reward_amount")
    # Если create вернул пустой баланс - подставляем старт из шаблона.
    if _int(out.get("two_balance_initial")) <= 0 and _int(tpl.get("start_amount")) > 0:
        out["two_balance_initial"] = _int(tpl.get("start_amount"))
        out["two_balance"] = _int(tpl.get("start_amount"))
    return out


def _take_failed_text() -> str:
    return (
        "<tg-emoji emoji-id='5292275525518127278'>🎁</tg-emoji> <b>Задание принято</b>\n"
        "\n"
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Баланс ещё подтягивается.\n"
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты в безопасности.\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Откройте задания ещё раз.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «К заданиям»</b>"
    )


def _take_error_text(reason: str) -> str:
    """Задание взять не вышло: показываем экраном, а не всплывашкой."""
    why = reason or "Это задание сейчас недоступно."
    return _lines(
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Задание не открылось</b>",
        "",
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> {why}",
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты не тронуты.",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Рядом есть другие бесплатные задания.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «К заданиям»</b>",
    )


def _take_error_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("К заданиям", data="ob_earn", icon="5472401690793614752", style="success")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


async def _open_bonus(call: CallbackQuery) -> None:
    """Бесплатных заданий нет - сначала мост, потом штатный бонус."""
    await _swap(call, _no_quests_bridge_text(), _no_quests_bridge_markup())


@dp.callback_query(F.data == "ob_bonus")
async def ob_bonus(call: CallbackQuery):
    await _ack(call)
    try:
        from main import process_bonus_request
        await process_bonus_request(
            user=call.from_user,
            chat_id=call.message.chat.id,
            reply_to=call.message,
            edit_message=call.message,
        )
    except Exception as e:
        print(f"[ONBOARDING] Не удалось открыть бонус: {e!r}")
        await _swap(call, _no_quests_text(), _no_quests_markup())


async def _free_quests(user_id: int) -> List[Dict[str, Any]]:
    """Бесплатные задания только там, где бот - админ группы.

    Новичок на /start не должен видеть неисправные группы.
    Во вкладке «Челленджи» они остаются с пометкой «Неисправно».
    """
    try:
        rows = await gc_load_templates_for_user(user_id)
    except Exception as e:
        print(f"[ONBOARDING] Список заданий {user_id}: {e!r}")
        return []

    free = [
        r for r in (rows or [])
        if isinstance(r, dict)
        and str(r.get("free") or "-").strip() == "+"
        and _quest_id(r) > 0
    ]
    if not free:
        return []

    try:
        marked = await gc_mark_templates_venue_status(free)
    except Exception as e:
        print(f"[ONBOARDING] Проверка групп заданий {user_id}: {e!r}")
        # На ошибке проверки не рискуем показывать новичкам сомнительные.
        return []

    healthy = [r for r in marked if r.get("bot_venue_ok")]
    skipped = len(marked) - len(healthy)
    if skipped:
        print(
            f"[ONBOARDING] Скрыто неисправных бесплатных заданий: {skipped} "
            f"(user={user_id})"
        )
    return healthy


def _quest_id(quest: Dict[str, Any]) -> int:
    return _int(quest.get("id")) or _int(quest.get("template_id"))


def _no_quests_bridge_text() -> str:
    return (
        "<tg-emoji emoji-id='5208464835079082371'>🌿</tg-emoji> <b>Бесплатных заданий сейчас нет</b>\n"
        "\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Новые появляются регулярно.\n"
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Пока куты можно взять через бонус.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Взять бонус»</b>"
    )


def _no_quests_bridge_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Взять бонус", data="ob_bonus", icon="5294001020039363545", style="success")],
        [_btn("Назад", data="ob_start", icon="5226660202035554522")],
    ])


def _no_quests_text() -> str:
    """Запасной текст, если бонус открыть не удалось."""
    return (
        "<tg-emoji emoji-id='5208464835079082371'>🌿</tg-emoji> <b>Бесплатных заданий сейчас нет</b>\n"
        "\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Новые появляются регулярно.\n"
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Пока куты можно взять через бонус.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Бонус»</b>"
    )


def _no_quests_markup() -> InlineKeyboardMarkup:
    try:
        from bot.config.config import bonusbet
        n = max(1, int(bonusbet))
    except Exception:
        n = 2
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Бонус", data=f"{random.randint(1, n)}_+", icon="5294001020039363545", style="success")],
        [_btn("Назад", data="ob_start", icon="5226660202035554522")],
    ])


# ──────────────────────────────────────────────────────────────────────
# Ветка «есть куты», клик 2 - выбор игры
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_games")
async def ob_games(call: CallbackQuery):
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    wallet = await _wallet(call.from_user.id)
    if wallet.free_quest and wallet.amount < _cheapest_bet():
        # Ставить нечем - вместо витрины игр показываем реальный выход.
        await _swap(call, _quest_stuck_text(wallet), _quest_stuck_markup())
        return
    await _swap(call, _games_text(wallet), _games_markup(wallet))


@dp.callback_query(F.data == "ob_next")
async def ob_next(call: CallbackQuery):
    """После игры: обновить прогресс задания и снова предложить игру."""
    await _ack(call)
    _bump_notify_token(call.from_user.id)
    wallet = await _wallet(call.from_user.id)
    if wallet.free_quest:
        if wallet.amount < _cheapest_bet():
            await _swap(call, _quest_stuck_text(wallet), _quest_stuck_markup())
            return
        left = max(0, wallet.target - wallet.amount)
        if left <= 0 or wallet.amount >= wallet.target:
            text = _lines(
                "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> <b>Цель достигнута</b>",
                "",
                _quest_stats(wallet),
                "",
                "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Награда уже ваша или скоро придёт.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Играйте дальше или закончите задание</b>",
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Играть ещё", data="ob_games", icon="5472041540605975004", style="success")],
                [_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")],
                [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
            ])
            await _swap(call, text, markup)
            return
        text = _lines(
            "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>Продолжайте</b>",
            "",
            _quest_stats(wallet),
            "",
            "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты не тратятся.",
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите игру</b>",
        )
        await _swap(call, text, _games_markup(wallet))
        return
    await _swap(call, _games_text(wallet), _games_markup(wallet))


def _quest_stuck_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
        [_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _games_text(wallet: Wallet, *, accepted: bool = False) -> str:
    """Витрина игр — короткие тексты, правьте здесь."""
    if wallet.free_quest:
        where = _venue_name(wallet)
        stats = _quest_stats(wallet)
        title = "Задание принято" if accepted else "Выберите игру"
        return (
            f"<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>{title}</b>\n"
            "\n"
            f"<blockquote>{stats}</blockquote>\n"
            "\n"
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> в <b>{where}</b>\n"
            "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.\n"
            "\n"
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите игру</b>"
        )
    return (
        "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>Выберите игру</b>\n"
        "\n"
        "<blockquote>"
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : <b>{wallet.amount} кут</b>\n"
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в <b>{CLUB_WHERE}</b>"
        "</blockquote>\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите на игру</b>"
    )


def _games_markup(wallet: Optional[Wallet] = None) -> InlineKeyboardMarkup:
    # Premium icon_custom_emoji_id из emoji-id игры.
    # При DOCUMENT_INVALID _swap откатит экран без иконок.
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(SOLO_ORDER), 2):
        row = []
        for k in SOLO_ORDER[i:i + 2]:
            game = GAMES[k]
            text, icon = _label_for_button(f"{game['emoji']} {game['title']}")
            row.append(_btn(text, data=f"ob_game:{k}", icon=icon))
        rows.append(row)
    if wallet is not None and wallet.free_quest:
        rows.append([
            _btn("Другое задание", data="ob_earn", icon="5472401690793614752"),
            _btn("Закончить", data="ob_finish", icon="5449372007432985754"),
        ])
    rows.append([_btn("Назад", data="ob_start", icon="5226660202035554522")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ──────────────────────────────────────────────────────────────────────
# Клик 3 - правила → ставка → (выбор) → запуск
# ──────────────────────────────────────────────────────────────────────
def _game_screen_extra(wallet: Wallet) -> str:
    if not wallet.free_quest:
        return ""
    return (
        f"{_quest_stats(wallet)}\n"
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты не тратятся."
    )


async def _show_stake_picker(
    call: CallbackQuery,
    *,
    game_key: str,
    game: Dict[str, Any],
    wallet: Wallet,
) -> None:
    """Описание игры + инлайн-кнопки суммы первой ставки."""
    stakes = _stake_choices(game, wallet)
    if not stakes:
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    suggested = _bet_for(game, wallet) or stakes[0]
    text = _render_game_text(
        game,
        bet=suggested,
        free_quest=wallet.free_quest,
        where=_venue_where(wallet),
        hint="Выберите сумму ставки",
        extra=_game_screen_extra(wallet),
    )
    rows = _stake_button_rows(game_key, stakes)
    rows.append([_btn("Другая игра", data="ob_games", icon="5472041540605975004")])
    await _swap(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


async def _show_variant_board(
    call: CallbackQuery,
    *,
    game_key: str,
    game: Dict[str, Any],
    wallet: Wallet,
    bet: int,
) -> None:
    """После выбора ставки — варианты (рулетка / куб / трейд)."""
    variants: Sequence[Tuple[str, str]] = game.get("variants") or ()
    text = _render_game_text(
        game,
        bet=bet,
        free_quest=wallet.free_quest,
        where=_venue_where(wallet),
        hint=_game_action_hint(game),
        extra=_game_screen_extra(wallet),
    )
    rows = _variant_button_rows(
        variants,
        bet=bet,
        game_key=game_key,
        rows=game.get("variant_rows"),
    )
    rows.append([
        _btn("Другая ставка", data=f"ob_game:{game_key}", icon="5472041540605975004"),
    ])
    rows.append([_btn("Другая игра", data="ob_games", icon="5472041540605975004")])
    await _swap(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


async def _show_confirm_play(
    call: CallbackQuery,
    *,
    game_key: str,
    game: Dict[str, Any],
    wallet: Wallet,
    bet: int,
) -> None:
    """Игры без вариантов: подтверждение ставки → старт."""
    text = _render_game_text(
        game,
        bet=bet,
        free_quest=wallet.free_quest,
        where=_venue_where(wallet),
        hint="Нажмите «Начать играть»",
        extra=_game_screen_extra(wallet),
    )
    rows = [
        [_btn(
            "Начать играть",
            data=f"ob_play:{game_key}:{bet}",
            icon="5472041540605975004",
            style="success",
        )],
        [_btn("Другая ставка", data=f"ob_game:{game_key}", icon="5472041540605975004")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
    ]
    await _swap(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ob_game:"))
async def ob_game(call: CallbackQuery):
    """Описание игры и выбор суммы ставки кнопками."""
    game_key = call.data.split(":", 1)[1] if ":" in call.data else ""
    if game_key not in GAMES:
        await _ack(call, "Такой игры нет", alert=True)
        return

    await _ack(call)
    game = GAMES[game_key]
    wallet = await _wallet(call.from_user.id)
    floor = int(game["min"])

    if wallet.free_quest and wallet.max_bet is not None and wallet.max_bet < floor:
        await _swap(call, _bet_limit_text(game, wallet), _bet_limit_markup())
        return

    if _bet_cap(game, wallet) < floor:
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    await _show_stake_picker(call, game_key=game_key, game=game, wallet=wallet)


@dp.callback_query(F.data.startswith("ob_stake:"))
async def ob_stake(call: CallbackQuery):
    """Выбрана сумма ставки → варианты или подтверждение старта."""
    parts = (call.data or "").split(":")
    if len(parts) < 3:
        await _ack(call, "Не удалось разобрать ставку", alert=True)
        return
    game_key = parts[1]
    try:
        bet = int(parts[2])
    except ValueError:
        await _ack(call, "Не удалось разобрать ставку", alert=True)
        return

    if game_key not in GAMES:
        await _ack(call, "Такой игры нет", alert=True)
        return

    await _ack(call)
    game = GAMES[game_key]
    wallet = await _wallet(call.from_user.id)
    floor = int(game["min"])
    cap = _bet_cap(game, wallet)

    if bet < floor or bet > cap:
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    if game.get("variants"):
        await _show_variant_board(
            call, game_key=game_key, game=game, wallet=wallet, bet=bet,
        )
        return

    await _show_confirm_play(
        call, game_key=game_key, game=game, wallet=wallet, bet=bet,
    )


@dp.callback_query(F.data.startswith("ob_play:"))
async def ob_play(call: CallbackQuery):
    parts = (call.data or "").split(":")
    if len(parts) < 3:
        await _ack(call, "Не удалось разобрать игру", alert=True)
        return

    game_key = parts[1]
    variant = parts[3] if len(parts) > 3 else None
    try:
        bet = int(parts[2])
    except ValueError:
        await _ack(call, "Не удалось разобрать ставку", alert=True)
        return

    if game_key not in GAMES:
        await _ack(call, "Такой игры нет", alert=True)
        return

    await _ack(call)
    _remember(call.from_user.id, game_key, bet, variant)
    await _try_launch(call, game_key, bet, variant)


@dp.callback_query(F.data.in_({"ob_joined", "ob_retry"}))
async def ob_resume(call: CallbackQuery):
    """«Я вошёл» и «Попробовать снова» - продолжаем с выбранной игрой."""
    await _ack(call)
    saved = _recall(call.from_user.id)
    if not saved:
        wallet = await _wallet(call.from_user.id)
        await _swap(call, _games_text(wallet), _games_markup(wallet))
        return
    await _try_launch(call, saved[0], saved[1], saved[2])


async def _try_launch(call: CallbackQuery, game_key: str, bet: int,
                      variant: Optional[str]) -> None:
    """Проверки → запуск в чате задания/клуба → ссылка в личку."""
    user = call.from_user
    game = GAMES[game_key]
    wallet = await _wallet(user.id)
    venue_chat_id, venue_url, venue_ref = _play_venue(wallet)

    # 0. Выбор обязателен, если у игры есть варианты (рулетка, куб, трейд).
    allowed = _allowed_variants(game)
    if allowed and (variant is None or str(variant) not in allowed):
        await _swap(
            call,
            _choice_required_text(
                game,
                bet=bet,
                free_quest=wallet.free_quest,
                where=_venue_where(wallet, venue_ref),
            ),
            _choice_required_markup(game_key),
        )
        return

    # 1. Человек в чате, где задание засчитывается?
    if not await _in_chat(user.id, venue_chat_id):
        await _swap(
            call,
            _join_text(
                game,
                bet=bet,
                free_quest=wallet.free_quest,
                venue_url=venue_url,
            ),
            _join_markup(venue_url),
        )
        return

    # 2. Есть чем платить ставку - своими кутами или балансом задания?
    if wallet.amount < bet or bet < int(game["min"]):
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    # 3. Хватает ли казны чата на выплату?
    if not await _chat_can_pay(venue_chat_id, bet):
        await _swap(call, _empty_treasury_text(), _empty_treasury_markup())
        return

    # 4. Защита от двойного нажатия - с понятным экраном, не молча.
    if _too_fast(user.id):
        await _swap(call, _wait_text(), _wait_markup())
        return

    try:
        command = _build_launch_command(game, bet, variant)
    except Exception as e:
        print(f"[ONBOARDING] команда {game_key}/{user.id}: {e!r}")
        await _swap(call, _failed_text(), _failed_markup())
        return

    dm_chat_id = call.message.chat.id
    dm_message_id = call.message.message_id
    balance_before = wallet.amount
    token = _bump_notify_token(user.id)

    anchor = await _launch(
        user, game_key, bet, variant, command,
        play_chat_id=venue_chat_id,
        play_chat_ref=venue_ref,
        dm_chat_id=dm_chat_id,
        dm_message_id=dm_message_id,
        balance_before=balance_before,
        free_quest=wallet.free_quest,
        notify_token=token,
    )
    if anchor is None:
        await _swap(call, _failed_text(), _failed_markup())
        return

    play_url = _message_url(venue_chat_id, anchor.message_id, venue_ref)
    await _swap(
        call,
        _ready_text(
            game, bet, wallet,
            game_key=game_key,
            venue_ref=venue_ref,
        ),
        _ready_markup(play_url, free_quest=wallet.free_quest),
    )


async def _launch(
    user: User,
    game_key: str,
    bet: int,
    variant: Optional[str],
    command: str,
    *,
    play_chat_id: int,
    play_chat_ref: Optional[str],
    dm_chat_id: int,
    dm_message_id: int,
    balance_before: int,
    free_quest: bool,
    notify_token: int,
) -> Optional[Message]:
    """Публикует якорь в чате задания/клуба и запускает игру от имени игрока."""
    game = GAMES[game_key]
    anchor = None
    try:
        handler = _resolve_handler(game)
        anchor = await _send_anchor(play_chat_id, user, game, bet)
        synthetic = _synthetic_command_message(anchor, user, command)

        print(
            f"[ONBOARDING] launch {game_key} user={user.id} chat={play_chat_id} "
            f"bet={bet} variant={variant!r} cmd={command!r} "
            f"anchor={anchor.message_id}",
            flush=True,
        )

        # Партия может длиться секунды (dice / анимация). Ссылку в личку
        # отдаём сразу; задачу держим в _bg_tasks, иначе asyncio её съест.
        _spawn_bg(
            _run_game_and_notify(
                handler, synthetic,
                user=user,
                user_id=user.id,
                game_key=game_key,
                bet=bet,
                play_chat_id=play_chat_id,
                play_chat_ref=play_chat_ref,
                anchor_message_id=anchor.message_id,
                dm_chat_id=dm_chat_id,
                dm_message_id=dm_message_id,
                balance_before=balance_before,
                free_quest=free_quest,
                notify_token=notify_token,
            ),
            label=f"{game_key}:{user.id}:{anchor.message_id}",
        )
        return anchor
    except Exception as e:
        print(f"[ONBOARDING] Не удалось запустить {game_key} для {user.id}: {e!r}")
        print(traceback.format_exc())
        if anchor is not None:
            try:
                await bot1.delete_message(play_chat_id, anchor.message_id)
            except Exception:
                pass
        return None


def _group_launch_text(user: User, game: Dict[str, Any], bet: int, *, plain: bool = False) -> str:
    """Минималистичный якорь в группе — маркетинг + premium emoji."""
    emoji = _plain_emoji(game["emoji"]) if plain else str(game.get("emoji") or "")
    name = _name(user)
    title = str(game.get("title") or "Игра")
    return (
        "<blockquote>"
        f"{emoji} <b>{name}</b>\n"
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> "
        f"<b>{title}</b> · <b>{int(bet)} кут</b>\n"
        f"<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> "
        f"<b>Партия уже здесь.</b>"
        "</blockquote>"
        if not plain else
        "<blockquote>"
        f"{emoji} <b>{name}</b>\n"
        f"🔥 <b>{title}</b> · <b>{int(bet)} кут</b>\n"
        f"🤙 <b>Партия уже здесь.</b>"
        "</blockquote>"
    )


async def _send_anchor(
    play_chat_id: int,
    user: User,
    game: Dict[str, Any],
    bet: int,
) -> Message:
    """Якорь в группе: сначала с premium emoji, при отказе - unicode."""
    rich = _group_launch_text(user, game, bet, plain=False)
    plain = _group_launch_text(user, game, bet, plain=True)
    try:
        return await bot1.send_message(
            chat_id=play_chat_id,
            text=rich,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        err = str(e).lower()
        if "document_invalid" in err or "can't parse entities" in err:
            return await bot1.send_message(
                chat_id=play_chat_id,
                text=plain,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        raise


async def _run_game_and_notify(
    handler,
    synthetic: Message,
    *,
    user: User,
    user_id: int,
    game_key: str,
    bet: int,
    play_chat_id: int,
    play_chat_ref: Optional[str],
    anchor_message_id: int,
    dm_chat_id: int,
    dm_message_id: int,
    balance_before: int,
    free_quest: bool,
    notify_token: int,
) -> None:
    try:
        await handler(synthetic)
    except asyncio.CancelledError:
        print(
            f"[ONBOARDING] Игра {game_key} отменена у {user_id} "
            f"(chat={play_chat_id} anchor={anchor_message_id})",
            flush=True,
        )
        await _notify_launch_failed(
            user_id=user_id,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id,
            notify_token=notify_token,
            play_chat_id=play_chat_id,
            anchor_message_id=anchor_message_id,
        )
        raise
    except Exception as e:
        print(
            f"[ONBOARDING] Игра {game_key} упала у {user_id}: {e!r} "
            f"(chat={play_chat_id} anchor={anchor_message_id} "
            f"text={getattr(synthetic, 'text', None)!r})",
            flush=True,
        )
        print(traceback.format_exc())
        await _notify_launch_failed(
            user_id=user_id,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id,
            notify_token=notify_token,
            play_chat_id=play_chat_id,
            anchor_message_id=anchor_message_id,
        )
        return

    print(
        f"[ONBOARDING] game done {game_key} user={user_id} "
        f"chat={play_chat_id} anchor={anchor_message_id}",
        flush=True,
    )

    # Подсказка в группе для новичка - после каждой onboarding-игры.
    try:
        await _maybe_send_newbie_help_tip(
            user=user,
            play_chat_id=play_chat_id,
            play_chat_ref=play_chat_ref,
            anchor_message_id=anchor_message_id,
            free_quest=free_quest,
            game_key=game_key,
            bet=bet,
        )
    except Exception as e:
        print(f"[ONBOARDING] newbie tip {user_id}: {e!r}")

    # Сессионные игры живут на колбэках - прогресс после партии
    # человек обновляет кнопкой «Играть ещё».
    if game_key not in INSTANT_GAMES:
        return

    try:
        await _notify_after_game(
            user_id=user_id,
            game_key=game_key,
            bet=bet,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id,
            balance_before=balance_before,
            free_quest=free_quest,
            notify_token=notify_token,
            play_chat_ref=play_chat_ref,
        )
    except Exception as e:
        print(f"[ONBOARDING] Уведомление после игры {game_key}/{user_id}: {e!r}")


async def _notify_launch_failed(
    *,
    user_id: int,
    dm_chat_id: int,
    dm_message_id: int,
    notify_token: int,
    play_chat_id: int,
    anchor_message_id: int,
) -> None:
    """Если партия не стартовала - не оставляем новичка на пустом «готово»."""
    if not _notify_token_alive(user_id, notify_token):
        return

    text = _failed_text()
    markup = _failed_markup()
    variants: List[Tuple[str, InlineKeyboardMarkup]] = [
        (text, markup),
        (text, _markup_without_icons(markup)),
        (_html_plain(text), _markup_without_icons(markup)),
    ]
    for body, kb in variants:
        if not _notify_token_alive(user_id, notify_token):
            return
        try:
            await bot1.edit_message_text(
                chat_id=dm_chat_id,
                message_id=dm_message_id,
                text=body,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            break
        except Exception as e:
            if "message is not modified" in str(e).lower():
                break
    else:
        for body, kb in variants:
            if not _notify_token_alive(user_id, notify_token):
                break
            try:
                await bot1.send_message(
                    chat_id=dm_chat_id,
                    text=body,
                    reply_markup=kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                break
            except Exception:
                continue

    # Якорь без партии только путает - убираем, если ещё висит.
    try:
        await bot1.delete_message(play_chat_id, anchor_message_id)
    except Exception:
        pass


async def _maybe_send_newbie_help_tip(
    *,
    user: User,
    play_chat_id: int,
    play_chat_ref: Optional[str],
    anchor_message_id: int,
    free_quest: bool,
    game_key: str = "",
    bet: int = 0,
) -> None:
    if not await _is_newbie(user.id):
        return
    venue = play_chat_ref or (
        CLUB_WHERE if int(play_chat_id) == CLUB_CHAT_ID else "этой группе"
    )
    if venue and not str(venue).startswith("@") and not str(venue).startswith("http"):
        if str(venue).replace("_", "").isalnum():
            venue = f"@{venue}"
    text = newbie_help_tip_text(
        mention=_mention_html(user.id, user.first_name),
        free_quest=free_quest,
        venue_label=str(venue),
        game_key=game_key,
        bet=bet,
    )
    await _send_html_chat(
        play_chat_id,
        text,
        reply_to_message_id=anchor_message_id,
    )


async def _notify_after_game(
    *,
    user_id: int,
    game_key: str,
    bet: int,
    dm_chat_id: int,
    dm_message_id: int,
    balance_before: int,
    free_quest: bool,
    notify_token: int,
    play_chat_ref: Optional[str] = None,
) -> None:
    """После партии в клубе - свежий прогресс в личку + «Играть ещё»."""
    # Даём БД дописать баланс задания после выплаты/списания.
    await asyncio.sleep(1.2)
    if not _notify_token_alive(user_id, notify_token):
        return

    wallet = await _wallet(user_id)
    game = GAMES.get(game_key) or {}
    quest_mode = free_quest or wallet.free_quest
    is_newbie = await _is_newbie(user_id)
    text = _after_game_text(
        game, bet, wallet,
        balance_before=balance_before,
        free_quest=quest_mode,
        is_newbie=is_newbie,
        venue_ref=play_chat_ref,
    )
    markup = _after_game_markup(wallet, free_quest=quest_mode)

    if not _notify_token_alive(user_id, notify_token):
        return

    variants: List[Tuple[str, str, InlineKeyboardMarkup]] = [
        ("full", text, markup),
        ("no_icons", text, _rebuild_markup(markup, keep_icons=False, keep_styles=True)),
        ("bare_kb", text, _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
        ("plain", _html_plain(text), _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
    ]
    last_err: Optional[BaseException] = None
    for name, body, kb in variants:
        if not _notify_token_alive(user_id, notify_token):
            return
        try:
            await bot1.edit_message_text(
                chat_id=dm_chat_id,
                message_id=dm_message_id,
                text=body,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            if name != "full":
                print(f"[ONBOARDING] итог fallback={name} err={last_err!r}")
            return
        except Exception as e:
            last_err = e
            if "message is not modified" in str(e).lower():
                return
            if not _can_downgrade_markup(e):
                break

    for name, body, kb in variants:
        if not _notify_token_alive(user_id, notify_token):
            return
        try:
            await bot1.send_message(
                chat_id=dm_chat_id,
                text=body,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            if name != "full":
                print(f"[ONBOARDING] итог (send) fallback={name}")
            return
        except Exception as e:
            last_err = e

    print(f"[ONBOARDING] Не удалось отправить итог {user_id}: {last_err!r}")


def _delta_line(before: int, after: int) -> str:
    delta = after - before
    if delta > 0:
        return f"<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Итог : +{delta} кут"
    if delta < 0:
        return f"<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Итог : {delta} кут"
    return f"<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Итог : без изменений"


def _after_game_text(
    game: Dict[str, Any],
    bet: int,
    wallet: Wallet,
    *,
    balance_before: int,
    free_quest: bool,
    is_newbie: bool = False,
    venue_ref: Optional[str] = None,
) -> str:
    title = game.get("title") or "Игра"
    emoji = game.get("emoji") or "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji>"
    where = _venue_where(wallet, venue_ref)
    head = _lines(
        f"{emoji} <b>{title}</b>",
        "",
        (
            f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Ставка : {bet} кут "
            f"({'с задания' if bool(free_quest or wallet.free_quest) else 'с баланса'})"
        ),
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {where}",
    )

    if free_quest and wallet.free_quest:
        reached = wallet.target > 0 and wallet.amount >= wallet.target
        if reached:
            return _lines(
                "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> <b>Цель достигнута</b>",
                "",
                head,
                _delta_line(balance_before, wallet.amount),
                "",
                _quest_stats(wallet),
                "",
                "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Награда уже ваша или скоро придёт.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Играйте дальше или закончите задание</b>",
            )
        if wallet.amount <= 0:
            return _lines(
                "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> <b>Баланс задания закончился</b>",
                "",
                head,
                "",
                "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Так бывает - это не конец.",
                "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
                "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Возьмите другое задание.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
            )
        tip = ""
        if is_newbie:
            tip = (
                f"<tg-emoji emoji-id='5318892863780579996'>📖</tg-emoji> "
                f"В {where} можно писать : <code>хелп игры</code>"
            )
        return _lines(
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Партия сыграна</b>",
            "",
            head,
            _delta_line(balance_before, wallet.amount),
            "",
            _quest_stats(wallet),
            tip,
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Играть ещё»</b>",
        )

    if free_quest and not wallet.free_quest:
        if wallet.amount >= _cheapest_bet():
            return _lines(
                "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> <b>Задание закрыто</b>",
                "",
                f"{emoji} <b>{title}</b>",
                f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Ставка : {bet} кут (с задания)",
                f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {wallet.amount} кут",
                "",
                "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Вы в клубе.",
                "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> Дальше играйте сами.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Играйте сами или возьмите другое задание</b>",
            )
        return _lines(
            "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> <b>Задание закрыто</b>",
            "",
            f"{emoji} <b>{title}</b>",
            f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Ставка : {bet} кут (с задания)",
            "",
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Так бывает.",
            "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
            "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Возьмите другое задание.",
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
        )

    return _lines(
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Партия сыграна</b>",
        "",
        f"{emoji} <b>{title}</b>",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Ставка : {bet} кут (с баланса)",
        _delta_line(balance_before, wallet.amount),
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {wallet.amount} кут",
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> в {where}",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Выберите следующую игру</b>",
    )



def _after_game_markup(wallet: Wallet, *, free_quest: bool) -> InlineKeyboardMarkup:
    if wallet.free_quest and wallet.amount > 0:
        # Задание живо: играть дальше, сменить игру или выйти - всё под рукой.
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Играть ещё", data="ob_next", icon="5472041540605975004", style="success")],
            [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
            [_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")],
            [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
        ])
    if wallet.free_quest:
        # Баланс задания сгорел, но задание ещё активно.
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
            [_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")],
            [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
        ])
    if free_quest:
        # Задание закрылось: цель взята или виртуальный баланс сгорел.
        if wallet.amount >= _cheapest_bet():
            return InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Играть сам", data="ob_games", icon="5472041540605975004", style="success")],
                [_btn("Другое задание", data="ob_earn", icon="5472401690793614752")],
                [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
            ])
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
            [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Играть ещё", data="ob_games", icon="5472041540605975004", style="success")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


# ──────────────────────────────────────────────────────────────────────
# Тексты состояний
# ──────────────────────────────────────────────────────────────────────
def _ready_text(
    game: Dict[str, Any],
    bet: int,
    wallet: Wallet,
    *,
    game_key: str = "",
    venue_ref: Optional[str] = None,
) -> str:
    """Текст после запуска — описание из GAMES[…].rules."""
    where = _venue_where(wallet, venue_ref)
    if wallet.free_quest:
        hint = (
            "Откройте игру - итог придёт сюда"
            if game_key in INSTANT_GAMES
            else "Откройте игру, затем «Играть ещё»"
        )
        card = _render_game_text(
            game,
            bet=bet,
            free_quest=True,
            where=where,
            hint=hint,
            extra=_quest_stats(wallet),
        )
    else:
        card = _render_game_text(
            game,
            bet=bet,
            free_quest=False,
            where=where,
            hint=f"Откройте игру в {where}",
        )
    return (
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Игра готова</b>\n"
        "\n"
        f"{card}"
    )


def _ready_markup(play_url: str, *, free_quest: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [_btn("Открыть мою игру", url=play_url, icon="5472041540605975004", style="success")],
    ]
    if free_quest:
        rows.append([_btn("Играть ещё", data="ob_next", icon="5472041540605975004", style="success")])
        rows.append([_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")])
    else:
        rows.append([_btn("Другая игра", data="ob_games", icon="5472041540605975004")])
    rows.append([_btn("Меню", data="ob_menu", icon="5318892863780579996")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _join_text(
    game: Dict[str, Any],
    *,
    bet: int,
    free_quest: bool,
    venue_url: str = CLUB_URL,
) -> str:
    """Текст «войдите в группу» — описание из GAMES[…].rules."""
    where = "группе задания" if venue_url != CLUB_URL else CLUB_WHERE
    return _render_game_text(
        game,
        bet=bet,
        free_quest=free_quest,
        where=where,
        hint="Вступите и нажмите «Я вошёл»",
        extra=(
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> "
            "Войдите и нажмите «Я вошёл»."
        ),
    )


def _join_markup(venue_url: str = CLUB_URL) -> InlineKeyboardMarkup:
    label = "Войти в группу" if venue_url != CLUB_URL else "Войти в клуб"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(label, url=venue_url, icon="5264737672684907396", style="success")],
        [_btn("Я вошёл", data="ob_joined", icon="5472041540605975004", style="success")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _no_funds_text(game: Dict[str, Any], wallet: Wallet) -> str:
    need = int(game["min"])
    if wallet.free_quest:
        if wallet.amount <= 0:
            return _lines(
                "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> <b>Баланс задания закончился</b>",
                "",
                f"{game['emoji']} <b>{game['title']}</b>",
                f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Нужно от {need} кут",
                "",
                "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Так бывает - это не конец.",
                "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
                "",
                "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
            )
        return _lines(
            "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> <b>На эту игру не хватает</b>",
            "",
            f"{game['emoji']} <b>{game['title']}</b>",
            f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Нужно от {need} кут",
            f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> На задании : {wallet.amount} кут",
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Возьмите игру полегче.",
            "",
            "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другая игра»</b>",
        )
    return _lines(
        "<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> <b>Не хватает на ставку</b>",
        "",
        f"{game['emoji']} <b>{game['title']}</b>",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Нужно от {need} кут",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Баланс : {wallet.amount} кут",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Бесплатное задание даст баланс.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Получить куты»</b>",
    )


def _no_funds_markup(wallet: Wallet) -> InlineKeyboardMarkup:
    if wallet.free_quest and wallet.amount > 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другая игра", data="ob_games", icon="5472041540605975004", style="success")],
            [_btn("Закончить задание", data="ob_finish", icon="5449372007432985754")],
            [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
        ])
    if wallet.free_quest:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon="5472401690793614752", style="success")],
            [_btn("Ферма", web_app=_farm_url(), icon="5208464835079082371")],
            [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Получить куты", data="ob_earn", icon="5472401690793614752", style="success")],
        [_btn("Ферма", web_app=_farm_url(), icon="5208464835079082371")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _bet_limit_text(game: Dict[str, Any], wallet: Wallet) -> str:
    return _lines(
        "<tg-emoji emoji-id='5471954679250498498'>🛡</tg-emoji> <b>Лимит ставки задания</b>",
        "",
        f"{game['emoji']} <b>{game['title']}</b>",
        f"<tg-emoji emoji-id='5453900977432188793'>⭐️</tg-emoji> Нужно от {int(game['min'])} кут",
        f"<tg-emoji emoji-id='5471954679250498498'>🛡</tg-emoji> Лимит задания : до {wallet.max_bet} кут",
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Возьмите другую игру.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другая игра»</b>",
    )


def _bet_limit_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004", style="success")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _empty_treasury_text() -> str:
    return (
        "<tg-emoji emoji-id='5208464835079082371'>🌿</tg-emoji> <b>Клуб пополняет казну</b>\n"
        "\n"
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Ставки на паузе - ненадолго.\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> На ферме куты растут без ставок.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Загляните на ферму или попробуйте снова</b>"
    )


def _empty_treasury_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Ферма", web_app=_farm_url(), icon="5208464835079082371", style="success")],
        [_btn("Попробовать снова", data="ob_retry", icon="5472041540605975004")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _failed_text() -> str:
    return (
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Игра не открылась</b>\n"
        "\n"
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Ставка не списана.\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Попробуйте ещё раз - клуб уже ждёт.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Попробовать снова»</b>"
    )


def _failed_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Попробовать снова", data="ob_retry", icon="5472041540605975004", style="success")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _wait_text() -> str:
    return (
        "<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Секунду…</b>\n"
        "\n"
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Прошлая игра ещё запускается.\n"
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Подождите пару секунд и нажмите снова.\n"
        "\n"
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Попробовать снова»</b>"
    )


def _wait_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Попробовать снова", data="ob_retry", icon="5472041540605975004", style="success")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


def _choice_required_text(
    game: Dict[str, Any],
    *,
    bet: int,
    free_quest: bool,
    where: str,
) -> str:
    """Текст «сначала выберите» — описание из GAMES[…].rules."""
    return _render_game_text(
        game,
        bet=bet,
        free_quest=free_quest,
        where=where,
        hint=_game_action_hint(game),
    )



def _choice_required_markup(game_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Выбрать снова", data=f"ob_game:{game_key}", icon="5472041540605975004", style="success")],
        [_btn("Другая игра", data="ob_games", icon="5472041540605975004")],
        [_btn("Меню", data="ob_menu", icon="5318892863780579996")],
    ])


# ──────────────────────────────────────────────────────────────────────
# Вспомогательное
# ──────────────────────────────────────────────────────────────────────
def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mention_html(user_id: int, first_name: Optional[str] = None) -> str:
    """Упоминание игрока в HTML (для группы)."""
    raw = (first_name or "Игрок")
    for ch in "<>&":
        raw = raw.replace(ch, "")
    safe = raw[:32] or "Игрок"
    return f'<a href="tg://user?id={int(user_id)}">{safe}</a>'


def _safe_display_name(first_name: Optional[str] = None) -> str:
    raw = (first_name or "Игрок")
    for ch in "<>&":
        raw = raw.replace(ch, "")
    return raw[:32] or "Игрок"


def _name(user: User) -> str:
    return _safe_display_name(user.first_name)


async def _is_newbie(user_id: int) -> bool:
    """True, если с первого /start прошло не больше NEWBIE_HINT_DAYS суток."""
    try:
        return bool(await db.is_bot_newbie(int(user_id), days=NEWBIE_HINT_DAYS))
    except Exception as e:
        print(f"[ONBOARDING] is_bot_newbie({user_id}): {e!r}")
        return False


def _venue_ref_label(wallet: Wallet, venue_ref: Optional[str] = None) -> Optional[str]:
    """@юзернейм площадки задания, если задание идёт не в клубе."""
    if not (wallet.free_quest and wallet.chat_id and int(wallet.chat_id) != CLUB_CHAT_ID):
        return None
    ref = str(venue_ref or wallet.chat_ref or "").strip()
    if not ref:
        return ""
    return ref if ref.startswith("@") or ref.startswith("http") else f"@{ref.lstrip('@')}"


def _venue_name(wallet: Wallet, venue_ref: Optional[str] = None) -> str:
    """Именительный падеж - для строк вида «Площадка : …»."""
    ref = _venue_ref_label(wallet, venue_ref)
    if ref is None:
        return CLUB_NAME
    return ref or "группа задания"


def _venue_where(wallet: Wallet, venue_ref: Optional[str] = None) -> str:
    """Предложный падеж - для строк вида «играть в …»."""
    ref = _venue_ref_label(wallet, venue_ref)
    if ref is None:
        return CLUB_WHERE
    return ref or "группе задания"


def _play_venue(wallet: Wallet) -> Tuple[int, str, Optional[str]]:
    """Куда запускать игру: чат задания или клуб.

    Если в бесплатном задании указана группа - играем там.
    Если группы нет - дефолтный клуб (см. ONBOARDING_CLUB).

    Returns: (chat_id, open_url, chat_ref)
    """
    if wallet.free_quest and wallet.chat_id:
        ref = str(wallet.chat_ref or "").strip()
        return wallet.chat_id, _chat_open_url(wallet.chat_id, ref), ref or None
    return CLUB_CHAT_ID, CLUB_URL, (f"@{CLUB_USERNAME}" if CLUB_USERNAME else None)


async def _send_html_chat(
    chat_id: int,
    text: str,
    *,
    reply_to_message_id: Optional[int] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Optional[Message]:
    """Отправка HTML в чат с откатом без premium emoji."""
    variants = (text, _html_plain(text))
    last_err: Optional[BaseException] = None
    for body in variants:
        try:
            return await bot1.send_message(
                chat_id=chat_id,
                text=body,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception as e:
            last_err = e
            if "message to be replied not found" in str(e).lower():
                reply_to_message_id = None
                continue
    print(f"[ONBOARDING] send_html_chat({chat_id}): {last_err!r}")
    return None


def _example_command(game: Dict[str, Any], bet: int) -> Tuple[str, str]:
    """Готовая строка команды и выбранный вариант, если игра его требует.

    Берём cmd из GAMES (тот же шаблон, что уходит в игру). Ставку
    подставляем актуальную; вариант — первый из variants / help_examples.
    """
    template = str(game.get("cmd") or "").strip()
    options: Sequence[Tuple[str, str]] = game.get("variants") or ()
    pick = str(options[0][1]) if options else ""
    if template:
        text = template.format(bet=int(bet), v=pick)
        return " ".join(text.split()), pick

    # Запасной путь: первый help_examples из реестра, с заменой числа ставки.
    examples = tuple(game.get("help_examples") or ())
    if not examples:
        return "", pick
    sample = str(examples[0])
    # «футбол 10» / «трейд вверх 10» → подставить текущую ставку в хвост.
    parts = sample.split()
    if parts and parts[-1].isdigit():
        parts[-1] = str(int(bet))
        sample = " ".join(parts)
    return sample, pick


def newbie_help_tip_text(
    *,
    mention: str,
    free_quest: bool,
    venue_label: str,
    game_key: str = "",
    bet: int = 0,
) -> str:
    """Короткая подсказка в группе после onboarding-игры.

    tip_lead / cmd — из GAMES. Минимум строк, маркетинг в blockquote.
    """
    game = GAMES.get(game_key) or {}
    again = max(int(bet or 0), int(game.get("min") or 2))
    example, _pick = _example_command(game, again)
    tip_lead = str(game.get("tip_lead") or "").strip()
    if not tip_lead:
        tip_lead = (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> "
            "<b>Партия сыграна.</b>"
        )

    body_lines = [tip_lead]
    if example:
        body_lines.append(
            f"<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> "
            f"Ещё : <code>{example}</code>"
        )
    body_lines.append(
        f"<tg-emoji emoji-id='5318892863780579996'>📖</tg-emoji> "
        f"<code>хелп игры</code>"
    )
    if free_quest:
        body_lines.append(
            "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> "
            "<b>Софт с задания.</b>"
        )

    return (
        f"{mention}\n"
        f"<blockquote>{chr(10).join(body_lines)}</blockquote>"
    )


def newbie_quest_failed_text(*, mention: str) -> str:
    """Провал бесплатного задания - спокойный маркетинг для новичка."""
    return _lines(
        f"<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> {mention}",
        "",
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Баланс задания закончился.</b>",
        "",
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Так бывает - это не конец.",
        "<tg-emoji emoji-id='5461094635336139106'>🐸</tg-emoji> Свои куты целы.",
        "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> Возьмите другое задание.",
        "",
        "<tg-emoji emoji-id='5470177992950946662'>👇</tg-emoji> <b>Нажмите «Другое задание»</b>",
    )


def newbie_quest_failed_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(
            "Другое задание",
            url=f"{BOT_URL}?start=earn",
            icon="5472401690793614752",
            style="success",
        )],
    ])


def _chat_open_url(chat_id: int, chat_ref: Optional[str] = None) -> str:
    ref = str(chat_ref or "").strip().lstrip("@")
    if ref and ref.replace("_", "").isalnum():
        return f"https://t.me/{ref}"
    s = str(int(chat_id))
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}"
    return CLUB_URL


def _message_url(chat_id: int, message_id: int, chat_ref: Optional[str] = None) -> str:
    ref = str(chat_ref or "").strip().lstrip("@")
    if ref and ref.replace("_", "").isalnum():
        return f"https://t.me/{ref}/{message_id}"
    s = str(int(chat_id))
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    return f"{CLUB_URL}/{message_id}"


async def _in_chat(user_id: int, chat_id: int) -> bool:
    try:
        member = await bot1.get_chat_member(chat_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        print(f"[ONBOARDING] Проверка членства {user_id} в {chat_id}: {e!r}")
        return False


async def _in_club(user_id: int) -> bool:
    return await _in_chat(user_id, CLUB_CHAT_ID)


async def _balance(user_id: int) -> int:
    try:
        return _int(await db.get_user_balance(user_id))
    except Exception:
        return 0


async def _chat_can_pay(chat_id: int, bet: int) -> bool:
    try:
        balance = await db.get_chat_balance(bot1, chat_id)
        return _int(balance) >= bet
    except Exception as e:
        print(f"[ONBOARDING] Казна чата {chat_id} недоступна: {e!r}")
        return True  # не блокируем игрока из-за сбоя чтения


async def _club_can_pay(bet: int) -> bool:
    return await _chat_can_pay(CLUB_CHAT_ID, bet)


def _html_plain(text: str) -> str:
    """tg-emoji → обычный unicode, если Telegram отверг document id."""
    return _TG_EMOJI_RE.sub(lambda m: (m.group(2) or "").strip(), text or "")


def _rebuild_markup(
    markup: InlineKeyboardMarkup,
    *,
    keep_icons: bool = True,
    keep_styles: bool = True,
) -> InlineKeyboardMarkup:
    """Копия клавиатуры без иконок и/или style — для мягкого отката."""
    rows: List[List[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard or []:
        new_row: List[InlineKeyboardButton] = []
        for btn in row:
            kwargs: Dict[str, Any] = {"text": btn.text or "·"}
            if btn.callback_data is not None:
                kwargs["callback_data"] = btn.callback_data
            elif btn.url:
                kwargs["url"] = btn.url
            elif btn.web_app:
                kwargs["web_app"] = btn.web_app
            if keep_icons:
                icon = getattr(btn, "icon_custom_emoji_id", None)
                if icon:
                    kwargs["icon_custom_emoji_id"] = icon
            if keep_styles:
                style = getattr(btn, "style", None)
                if style and str(style) in _BTN_STYLES:
                    kwargs["style"] = str(style)
            try:
                new_row.append(InlineKeyboardButton(**kwargs))
            except TypeError:
                kwargs.pop("style", None)
                kwargs.pop("icon_custom_emoji_id", None)
                new_row.append(InlineKeyboardButton(**kwargs))
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _markup_without_icons(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    return _rebuild_markup(markup, keep_icons=False, keep_styles=True)


def _is_noop_edit_error(err: BaseException) -> bool:
    return "message is not modified" in str(err).lower()


def _can_downgrade_markup(err: BaseException) -> bool:
    """Можно ли пробовать более простой reply_markup / текст без premium."""
    text = str(err).lower()
    needles = (
        "document_invalid",
        "can't parse entities",
        "unsupported start tag",
        "reply_markup",
        "button",
        "icon_custom_emoji",
        "button_style",
        "style",
        "entity_text",
        "custom emoji",
    )
    return any(n in text for n in needles)


async def _ack(call: CallbackQuery, text: str = "", *, alert: bool = False) -> None:
    """Снять «часики» с кнопки. Никогда не бросает исключение.

    Ответ на нажатие живёт у Telegram считанные секунды. Если он не прошёл
    (очередь после рестарта, клик по старому сообщению, повторный ответ),
    экран всё равно обязан смениться - иначе человек жмёт кнопку, и ничего
    не происходит. Поэтому ack - всегда best-effort.
    """
    try:
        await call.answer(text, show_alert=alert)
    except Exception as e:
        print(f"[ONBOARDING] ответ на нажатие не прошёл ({call.data!r}): {e!r}")


async def _swap(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Меняет экран на месте. Premium emoji снимаем только при отказе Telegram.

    Порядок:
      1) полный текст + иконки кнопок
      2) полный текст + кнопки без иконок
      3) полный текст + кнопки без иконок/style
      4) unicode-текст (последний резерв)
    На сетевые/прочие ошибки не скатываемся сразу в plain — иначе пропадают
    все <tg-emoji>.
    """
    variants: List[Tuple[str, str, InlineKeyboardMarkup]] = [
        ("full", text, markup),
        ("no_icons", text, _rebuild_markup(markup, keep_icons=False, keep_styles=True)),
        ("bare_kb", text, _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
        ("plain", _html_plain(text), _rebuild_markup(markup, keep_icons=False, keep_styles=False)),
    ]
    last_err: Optional[BaseException] = None

    async def _try_edit(body: str, kb: InlineKeyboardMarkup) -> bool:
        nonlocal last_err
        try:
            await call.message.edit_text(
                body, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            last_err = e
            if _is_noop_edit_error(e):
                return True
            return False

    async def _try_answer(body: str, kb: InlineKeyboardMarkup) -> bool:
        nonlocal last_err
        try:
            await call.message.answer(
                body, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            last_err = e
            return False

    for name, body, kb in variants:
        if await _try_edit(body, kb):
            if name != "full":
                print(f"[ONBOARDING] экран показан fallback={name} err={last_err!r}")
            return
        if not _can_downgrade_markup(last_err or Exception()):
            # Не emoji/markup — пробуем новое сообщение с тем же телом,
            # не прыгая сразу к plain.
            if await _try_answer(body, kb):
                if name != "full":
                    print(f"[ONBOARDING] экран (answer) fallback={name} err={last_err!r}")
                return
            print(f"[ONBOARDING] edit/answer failed без даунгрейда ({name}): {last_err!r}")
            break
        print(f"[ONBOARDING] {name} отклонён, пробуем проще: {last_err!r}")

    for name, body, kb in variants:
        if await _try_answer(body, kb):
            print(f"[ONBOARDING] экран (answer) fallback={name}")
            return

    print(f"[ONBOARDING] Не удалось показать экран: {last_err!r}")


# ──────────────────────────────────────────────────────────────────────
# Синяя кнопка «Меню» в Telegram
# ──────────────────────────────────────────────────────────────────────
@dp.startup()
async def _register_commands(**_: Any) -> None:
    try:
        await bot1.set_my_commands([
            BotCommand(command="start", description="Клуб и игры"),
            BotCommand(command="profile", description="Профиль и баланс"),
            BotCommand(command="bonus", description="Ежедневный бонус"),
            BotCommand(command="shop", description="Магазин предметов"),
            BotCommand(command="help", description="Справка"),
        ])
        print("[ONBOARDING] Команды бота зарегистрированы")
    except Exception as e:
        print(f"[ONBOARDING] set_my_commands: {e!r}")
