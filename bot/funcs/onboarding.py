"""Онбординг: три клика, две ветки.

Ветка «пусто» - у человека нет кут:
    клик 1 - /start ........... на что нужны куты и как получить первые бесплатно
    клик 2 - бесплатное задание, оно даёт виртуальный баланс
    клик 3 - игра в группе задания (или дефолт-клуб, если группы нет)

Ветка «есть куты»:
    клик 1 - /start
    клик 2 - выбор игры → сразу доска в группе (без «Начать играть» в личке)
    клик 3 - ОДНО сообщение в личке: карточка + «Открыть мою игру» (url)
             + в группе доска «Начать игру» / выбор
             (без второго одинакового экрана, только edit)

Любая игра без вариантов (футбол, башня, шарик, …): в группе сначала
текст + кнопка «Начать игру»; партия стартует только после клика.
Игры с выбором (куб / трейд / рулетка): доска выбора в группе.

После каждой onboarding-партии в группе — tip «Ещё шаг?» + пример команды
+ «хелп игры» (для сессий — строго после конца партии, не при старте UI).
Личка («Открыть мою игру») после партии меняется на итог + «Играть ещё».

При проигрыше задания - мягкое сообщение.

Дефолт-клуб: ONBOARDING_CLUB = auto|test|prod (константа / env).
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from importlib import import_module
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from aiogram import F
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)

from bot.db_create.pklcode import LazyGameStore
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
# Клуб (дефолтная площадка онбординга)
# ──────────────────────────────────────────────────────────────────────
# Одна строка. Меняй здесь или через env ONBOARDING_CLUB.
#   "test" → -1002135149822 (тестовая группа)
#   "prod" → -1001612636292 (@CuteGamingChat)
#   "auto" → как DATABASE_MODE / APP_MODE (test→test, main→prod)
ONBOARDING_CLUB = "prod"  # <<< "auto" | "test" | "prod"

_CLUB_PRESETS: Dict[str, Dict[str, Any]] = {
    "prod": {
        "chat_id": -1001612636292,
        "username": "CuteGamingChat",
    },
    "test": {
        "chat_id": -1002135149822,
        "username": "",  # приватная группа — ссылки через t.me/c/...
    },
}


def _resolve_club_mode() -> str:
    """Приоритет: env ONBOARDING_CLUB → константа → auto по DATABASE_MODE."""
    raw = (os.getenv("ONBOARDING_CLUB") or "").strip().lower()
    if not raw:
        raw = str(ONBOARDING_CLUB or "auto").strip().lower()
    if raw in ("main", "prod", "production"):
        return "prod"
    if raw in ("test", "sandbox"):
        return "test"
    # auto / пусто — как база
    try:
        from bot.config.config import DATABASE_MODE
        mode = str(DATABASE_MODE or "").strip().lower()
    except Exception:
        mode = ""
    if not mode:
        mode = (os.getenv("APP_MODE") or "").strip().lower()
    if mode in ("test", "sandbox"):
        return "test"
    return "prod"


def _club_open_url(chat_id: int, username: str = "") -> str:
    name = str(username or "").strip().lstrip("@")
    if name and name.replace("_", "").isalnum():
        return f"https://t.me/{name}"
    s = str(int(chat_id))
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}"
    return f"https://t.me/{s}"


def _club_from_mode(mode: str) -> Tuple[int, str, str]:
    preset = _CLUB_PRESETS.get(mode) or _CLUB_PRESETS["prod"]
    chat_id = int(preset["chat_id"])
    username = str(preset.get("username") or "").strip().lstrip("@")
    return chat_id, username, _club_open_url(chat_id, username)


CLUB_CHAT_ID, CLUB_USERNAME, CLUB_URL = _club_from_mode(_resolve_club_mode())
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


# ──────────────────────────────────────────────────────────────────────
# Shared emoji для хелперов (_quest_stats). Тексты экранов - прямо в функциях с <tg-emoji>
# ──────────────────────────────────────────────────────────────────────
E_HAT = "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji>"
E_STAR = "<tg-emoji emoji-id='5436339947080548936'>🌟</tg-emoji>"
E_TGSTAR = "<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji>"
E_GAME = "<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji>"
E_BOLT = "<tg-emoji emoji-id='5258466470676940666'>✈️</tg-emoji>"
E_CUP = "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji>"
E_GIFT = "<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji>"
E_LEAF = "<tg-emoji emoji-id='5208464835079082371'>🌿</tg-emoji>"
E_DOWN = "<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji>"
# Площадка / «куда играть» — премиум 🛬
E_PLANE = "<tg-emoji emoji-id='5398017375532498315'>🛬</tg-emoji>"
# Баланс — премиум ✨
E_COIN = "<tg-emoji emoji-id='5397981293512243749'>✨</tg-emoji>"
# Итог партии — премиум ⚡️
E_RESULT = "<tg-emoji emoji-id='5397976749436842796'>⚡️</tg-emoji>"
E_TARGET = "<tg-emoji emoji-id='5418238674267556907'>⭐</tg-emoji>"
E_BAR = "<tg-emoji emoji-id='5397976749436842796'>⚡️</tg-emoji>"      # прогресс / итог
E_SAFE = "<tg-emoji emoji-id='5471954679250498498'>🛡</tg-emoji>"     # рекомендуемая ставка
# «Партия сыграна» / следующий шаг — премиум 🤩
E_NEXT = "<tg-emoji emoji-id='5348423147647414077'>🤩</tg-emoji>"
E_HELP = "<tg-emoji emoji-id='5318892863780579996'>📖</tg-emoji>"     # хелп / справка
E_FIRE = "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji>"     # хук / огонь
E_OK = "<tg-emoji emoji-id='5206607081334906820'>✅</tg-emoji>"       # спокойно, не страшно

# Эффект применяется только к новым сообщениям, поэтому нужен один - на /start.
EFFECT_START = "5107584321108051014"   # 👍

ICON_PLAY = "5425094988260188065"
ICON_ABOUT = "5436339947080548936"
ICON_PROFILE = "5192951739623447936"
ICON_CLOSE = "5226660202035554522"
ICON_GIFT = "5317000922096769303"
ICON_FARM = "5208464835079082371"
ICON_GROUP = "5264737672684907396"
ICON_TASKS = "5318892863780579996"
ICON_WITHDRAW = "5848021027782661221"
ICON_DONATE = "5848259999763011021"
ICON_MARKET = "5438440765908874600"
ICON_BONUS = "5224257782013769471"
ICON_US = "6037421444789440735"
ICON_MENU = "5318892863780579996"
ICON_FINISH = "5305629674058061875"  # закончить задание (как в балансе)
# Стрелки как в магазине.
ICON_PREV = "5805509901048356965"
ICON_NEXT = "5807453545548487345"

# Сколько бесплатных заданий на одной странице.
# Навигация появляется только если заданий больше этого числа.
FREE_QUESTS_PER_PAGE = 10

# Безопасная ставка: доля от баланса задания (10% = не сжечь всё сразу).
# Итоговая ставка ещё ограничивается рекомендуемой долей баланса группы.
SAFE_BET_PERCENT = 10

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


def _hint(text: str) -> str:
    return f"<tg-emoji emoji-id='5418238674267556907'>⭐</tg-emoji> <b>{text}</b>"


_TG_EMOJI_RE = re.compile(
    r"<tg-emoji[^>]*emoji-id=['\"]([0-9]+)['\"][^>]*>(.*?)</tg-emoji>",
    re.DOTALL,
)


def _bold_html_line(line: str) -> str:
    """Жирная строка: premium <tg-emoji> снаружи <b>, иначе клиент рвёт bold."""
    plain = (line or "").replace("<b>", "").replace("</b>", "")
    if not plain.strip():
        return plain
    if "<tg-emoji" not in plain:
        return f"<b>{plain}</b>"
    parts: List[str] = []
    last = 0
    for m in _TG_EMOJI_RE.finditer(plain):
        before = plain[last:m.start()]
        if before:
            parts.append(f"<b>{before}</b>" if before.strip() else before)
        parts.append(m.group(0))
        last = m.end()
    after = plain[last:]
    if after:
        parts.append(f"<b>{after}</b>" if after.strip() else after)
    return "".join(parts) if parts else f"<b>{plain}</b>"


def _bq(*parts: str) -> str:
    """blockquote, где каждая непустая строка целиком в <b>.

    Так цифры, хвосты и эмодзи внутри цитаты всегда жирные -
    даже если в исходной строке <b> стоял только на подписи.
    """
    chunks = [str(p) for p in parts if p is not None and str(p).strip()]
    lines: List[str] = []
    for chunk in chunks:
        for line in chunk.split("\n"):
            if not line.strip():
                continue
            lines.append(_bold_html_line(line))
    return f"<blockquote>{chr(10).join(lines)}</blockquote>"


def _progress_line(current: int, target: int) -> str:
    """Живой прогресс до цели задания: [■■■□□□□□□□] 30%."""
    if target <= 0:
        pct = 0
        filled = 0
    else:
        pct = int(max(0, min(100, (current * 100) // target)))
        filled = int(round(pct * PROGRESS_SEGMENTS / 100))
        filled = max(0, min(PROGRESS_SEGMENTS, filled))
    bar = "■" * filled + "□" * (PROGRESS_SEGMENTS - filled)
    return f"<tg-emoji emoji-id='5350835008007324644'>🌟</tg-emoji> [{bar}] {pct}%"


def _quest_stats(wallet: "Wallet") -> str:
    """Карточка прогресса задания - цифры + прогресс-бар."""
    left = max(0, wallet.target - wallet.amount)
    return _bq(
        _progress_line(wallet.amount, wallet.target),
        f"<tg-emoji emoji-id='5348418461838098123'>💰</tg-emoji> Баланс : {wallet.amount} кут",
        f"<tg-emoji emoji-id='5348054995935706813'>💡</tg-emoji> Цель : {wallet.target} кут",
        f"<tg-emoji emoji-id='5348103735224581633'>🕺</tg-emoji> До цели : {left} кут",
        f"<tg-emoji emoji-id='5348582551063641258'>😌</tg-emoji> Награда : +{wallet.reward} кут",
    )


def _btn(text: str, *, data: str = None, url: str = None, web_app: str = None,
         icon: str = None, style: Optional[str] = "default") -> InlineKeyboardButton:
    """Кнопка в оформлении проекта: style + иконка кастомным эмодзи.

    style=None - без цветного стиля (нужно для плотных сеток чисел рулетки).
    """
    kwargs: Dict[str, Any] = {"text": text}
    if style:
        kwargs["style"] = style
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
        # Сначала снимаем style, icon оставляем (цифры кубика = только premium).
        kwargs.pop("style", None)
        try:
            return InlineKeyboardButton(**kwargs)
        except TypeError:
            kwargs.pop("icon_custom_emoji_id", None)
            return InlineKeyboardButton(**kwargs)


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
    """Текст кнопки + icon id.

    Если есть premium icon - в text только подпись (без unicode),
    иначе иконка и обычный эмодзи дублируются на кнопке.
    """
    icon = _emoji_id(label)
    text = _plain_emoji(label) or "·"
    if icon:
        parts = text.split(None, 1)
        if len(parts) == 2 and not parts[0][:1].isalnum():
            text = parts[1]
    return text, icon


# Icon id для кнопок меню игр (анимированный premium на кнопке).
# В text кнопки - только название, без обычного эмодзи.
GAME_ICON_IDS: Dict[str, str] = {
    "soccer": "5373101763442255191",
    "slots": "5891135206580031104",
    "tank": "5204467307153234577",
    "darts": "5890815115552362075",
    "basket": "5891181665241271999",
    "bowling": "5891120371762990493",
    "kube": "5890971177484029249",
    "balls": "5363877049863786071",
    "provoda": "5782990399672946716",
    "bombs": "5469654973308476699",
    "plate": "5246916607833304803",
    "risk": "5438449312893792440",
    "trade": "5296306038792808890",
    "fortuna": "5321499578216769477",
}


# ──────────────────────────────────────────────────────────────────────
# Реестр одиночных игр
# ──────────────────────────────────────────────────────────────────────
# Логика партии ВСЕГДА в module/func (trade.py, slots.py, …).
# Онбординг только приводит новичка к сообщению и подсказывает команду.
GAMES: Dict[str, Dict[str, Any]] = {
    "soccer": {
        "title": "Футбол", "emoji": "<tg-emoji emoji-id='5373101763442255191'>⚽️</tg-emoji>", "min": 2,
        "cmd": "футбол {bet}",
        "help_cmd": "футбол (ваша ставка)",
        "help_examples": ("футбол 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Ещё удар?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Гол - забираете выигрыш. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо - проигрыш.",
        "module": "bot.tggames.soccer", "func": "tgsoccer",
    },
    "slots": {
        "title": "Слоты", "emoji": "<tg-emoji emoji-id='5891135206580031104'>🎉</tg-emoji>", "min": 2,
        "cmd": "слоты {bet}",
        "help_cmd": "слоты (ваша ставка)",
        "help_examples": ("слоты 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Крутим снова?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Три одинаковых символа - крупный выигрыш.",
        "module": "bot.tggames.slots", "func": "tgslots",
    },
    "tank": {
        "title": "Башня", "emoji": "<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji>", "min": 2,
        "cmd": "башня {bet}",
        "help_cmd": "башня (ваша ставка)",
        "help_examples": ("башня 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Ещё этаж?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Этаж за этажом выигрыш растёт. Успейте забрать до обвала.",
        "module": "bot.games.tank", "func": "game_filter_tank",
    },
    "darts": {
        "title": "Дартс", "emoji": "<tg-emoji emoji-id='5890815115552362075'>🎯</tg-emoji>", "min": 2,
        "cmd": "дартс {bet}",
        "help_cmd": "дартс (ваша ставка)",
        "help_examples": ("дартс 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> В яблочко ещё раз?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Попали в центр - забираете большой выигрыш",
        "module": "bot.tggames.darts", "func": "tgdarts",
    },
    "basket": {
        "title": "Баскетбол", "emoji": "<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji>", "min": 2,
        "cmd": "баскет {bet}",
        "help_cmd": "баскет (ваша ставка)",
        "help_examples": ("баскет 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Ещё бросок?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Попали в кольцо - выигрыш. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо - теряете ставку.",
        "module": "bot.tggames.basket", "func": "tgbasket",
    },
    "bowling": {
        "title": "Боулинг", "emoji": "<tg-emoji emoji-id='5891120371762990493'>🎳</tg-emoji>", "min": 2,
        "cmd": "боулинг {bet}",
        "help_cmd": "боулинг (ваша ставка)",
        "help_examples": ("боулинг 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Ещё страйк?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Страйк - выигрыш. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Всё остальное - нет.",
        "module": "bot.tggames.bowling", "func": "tgbowling",
    },
    "kube": {
        "title": "Кубик", "emoji": "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji>", "min": 2,
        "cmd": "куб {bet} {v}",
        "help_cmd": "куб (ваша ставка) (число)",
        "help_examples": ("куб 10 4", "куб 10 6"),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Угадаете число?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Выберите число на кубике - партия стартует сразу.",
        # Premium-иконки 1–6: в text кнопки цифр нет — только icon_custom_emoji_id.
        "variants": [
            ("<tg-emoji emoji-id='5348324054161967894'>\u200b</tg-emoji>", "1"),
            ("<tg-emoji emoji-id='5350559846632537457'>\u200b</tg-emoji>", "2"),
            ("<tg-emoji emoji-id='5350719542106540014'>\u200b</tg-emoji>", "3"),
            ("<tg-emoji emoji-id='5350505304842846481'>\u200b</tg-emoji>", "4"),
            ("<tg-emoji emoji-id='5348566874433011485'>\u200b</tg-emoji>", "5"),
            ("<tg-emoji emoji-id='5348527025726439836'>\u200b</tg-emoji>", "6"),
        ],
        "variant_rows": (3, 3),
        "variant_hint": "Число выбирается в группе",
        "rules": "<tg-emoji emoji-id='5397976749436842796'>⚡</tg-emoji> Угадал число на кубике - выигрыш в несколько ставок.",
        "module": "bot.tggames.kube", "func": "tgkube",
    },
    "balls": {
        "title": "Шарик", "emoji": "<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji>", "min": 2,
        "cmd": "шарик {bet}",
        "help_cmd": "шарик (ваша ставка)",
        "help_examples": ("шарик 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Хотите ещё раз?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Три стакана, под одним шарик. Угадали - выигрыш.",
        "module": "bot.games.balls", "func": "balls",
    },
    "provoda": {
        "title": "Провода", "emoji": "<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji>", "min": 2,
        "cmd": "провода {bet}",
        "help_cmd": "провода (ваша ставка)",
        "help_examples": ("провода 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Какой провод режем?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Перерезали верный провод - выигрыш. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Ошиблись - теряете ставку.",
        "module": "bot.games.provoda", "func": "provoda",
    },
    "bombs": {
        "title": "Бомбы", "emoji": "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji>", "min": 3,
        "cmd": "бомбы {bet}",
        "help_cmd": "бомбы (ваша ставка)",
        "help_examples": ("бомбы 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Попробовать еще раз?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Открываете клетки, выигрыш растёт. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Бомба - теряете всё.",
        "module": "bot.games.bombs", "func": "bombs",
    },
    "plate": {
        "title": "Плиты", "emoji": "<tg-emoji emoji-id='5246916607833304803'>💫</tg-emoji>", "min": 2,
        "cmd": "плиты {bet}",
        "help_cmd": "плиты (ваша ставка)",
        "help_examples": ("плиты 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Ещё шаг?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Шагаете по плитам, выигрыш растёт. \n<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Провалились - теряете ставку.",
        "module": "bot.games.plate", "func": "plate",
    },
    "risk": {
        "title": "Риск", "emoji": "<tg-emoji emoji-id='5438449312893792440'>🌴</tg-emoji>", "min": 5,
        "cmd": "риск {bet}",
        "help_cmd": "риск (ваша ставка)",
        "help_examples": ("риск 10",),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Рискнём ещё?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Нажмите кнопку - и партия стартует.",
        "rules": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Каждый шаг умножает выигрыш. Забирайте, пока не сгорел.",
        "module": "bot.games.risk", "func": "risk",
    },
    "trade": {
        "title": "Трейд", "emoji": "<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji>", "min": 2,
        "cmd": "трейд {v} {bet}",
        "help_cmd": "трейд (ваша ставка)",
        "help_examples": ("трейд вверх 10", "трейд вниз 10"),
        "tip_lead": "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> Куда график в этот раз?",
        "board_lead": "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> Куда пойдёт график? Нажмите кнопку - и партия начнётся сразу.",
        "variants": [
            ("<tg-emoji emoji-id='5339384049670593248'>↗️</tg-emoji> Вверх", "вверх"),
            ("<tg-emoji emoji-id='5339179750961224703'>📉</tg-emoji> Вниз", "вниз"),
        ],
        # Вверх = рост (зелёный), вниз = падение (красный).
        "variant_styles": {"вверх": "success", "вниз": "danger"},
        "variant_hint": "Направление выбирается в группе",
        "rules": "<tg-emoji emoji-id='5397976749436842796'>⚡</tg-emoji> Угадали направление - выигрыш. Иногда сделка срывается.",
        "module": "bot.games.trade", "func": "trade",
    },
    "fortuna": {
        "title": "Рулетка",
        "emoji": "<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji>",
        "min": 3,
        "cmd": "рулетка {bet} {v}",
        "help_cmd": "рулетка (ставка) (цвет / число / чёт / диапазон)",
        # Tip после партии: 4 принципа (цвет · чёт · число · диапазон).
        "help_examples": (
            "рулетка 10 красное/черное",
            "рулетка 10 четное/нечётное",
            "рулетка 10 7",
            "рулетка 10 1 6",
            "рулетка 10 6 12",
        ),
        # В tip после партии показываем несколько примеров, не одну строку.
        "tip_show_examples": True,
        "tip_lead": (
            "<tg-emoji emoji-id='5222148368955877900'>🔥</tg-emoji> "
            "Попробовать ещё раз?"
        ),
        "board_lead": (
            "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> "
            "Выберите цвет, чёт, число или диапазон — и крутим."
        ),
        # Ряды: числа · диапазоны · цвет · чёт/нечет
        # Диапазоны: кнопка 1–6 → «рулетка 10 1 6», кнопка 6–12 → «рулетка 10 6 12».
        # В callback — «1-6»/«6-12» (без пробела); в команду нормализуем в «1 6»/«6 12».
        "variants": [
            ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"), ("6", "6"),
            ("7", "7"), ("8", "8"), ("9", "9"), ("10", "10"), ("11", "11"), ("12", "12"),
            ("1–6", "1-6"),
            ("6–12", "6-12"),
            ("<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji> Красное", "красное"),
            ("<tg-emoji emoji-id='5449692618151695997'>🖤</tg-emoji> Чёрное", "черное"),
            ("Чётное", "чет"),
            ("Нечётное", "нечет"),
        ],
        "variant_rows": (6, 6, 2, 2, 2),
        # None = без цветного style (серая кнопка Telegram).
        "variant_styles": {
            "1-6": "primary",
            "6-12": "primary",
            "1 6": "primary",
            "6 12": "primary",
            "красное": None,
            "черное": None,
            "чет": None,
            "нечет": None,
        },
        "variant_hint": "Цвет, чёт, число или диапазон",
        "rules": (
            "<tg-emoji emoji-id='5296372434692234934'>❤️</tg-emoji> "
            "<b>Цвет</b> · \n"
            "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> "
            "<b>Чёт / нечет</b> · \n"
            "<tg-emoji emoji-id='5188307557126524632'>1️⃣</tg-emoji> "
            "<b>Число 0–12</b> · \n"
            "<tg-emoji emoji-id='5386629944057026256'>🔢</tg-emoji> "
            "<b>Диапазон</b> \n"
            "<code>1 6</code> / <code>6 12</code>\n\n"
            "<tg-emoji emoji-id='5397976749436842796'>⚡</tg-emoji> Угадали — выигрыш.\n"
            "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> Мимо — ставка сгорает."
        ),
        "module": "bot.games.Fortuna", "func": "Fortuna",
    },
}

# Порядок кнопок - порядок словаря: сверху самые быстрые и понятные.
SOLO_ORDER: Tuple[str, ...] = tuple(GAMES)

# Игры, которые заканчиваются внутри первого handler'а (dice / one-shot).
INSTANT_GAMES = frozenset({
    "soccer", "slots", "darts", "basket", "bowling", "kube", "fortuna", "trade",
})

# Игры без вариантов: в группе сначала текст + «Начать игру» (как футбол),
# потом handler. Сюда входят и dice, и сессии (башня / шарик / …).
CONFIRM_START_GAMES = frozenset(
    k for k, g in GAMES.items() if not g.get("variants")
)

# Сессионные: handler возвращается при старте UI, а не после конца партии.
# Подсказка «Ещё этаж?» — только после закрытия сессии.
SESSION_GAMES = frozenset(k for k in GAMES if k not in INSTANT_GAMES)

# uid→message_id активной доски в main (LazyGameStore).
_SESSION_MSG_STORES: Dict[str, str] = {
    "tank": "user_messagetank",
    "balls": "user_message_ball",
    "bombs": "user_message_bombss",
    "plate": "user_message_plate",
    "risk": "user_message_risk",
    "provoda": "user_message_wires",
}

# Активное состояние сессии (флаг closed), если есть.
_SESSION_ACTIVE_STORES: Dict[str, str] = {
    "tank": "tank_active_games",
    "balls": "active_games_ball",
    "bombs": "bombs_user_game_data",
    "plate": "active_games_plate",
    "risk": "active_games_risk",
    "provoda": "active_games_wires",
}

# Макс. ожидание конца сессии для tip (чуть дольше типичного SESSION_TTL).
_SESSION_TIP_WAIT = 21 * 60.0


# ──────────────────────────────────────────────────────────────────────
# Состояние онбординга (всё runtime — только LazyGameStore)
# ──────────────────────────────────────────────────────────────────────
# Каждый стор — ОТДЕЛЬНОЕ имя. Одно имя = один GameStore на весь процесс;
# шарить нельзя (иначе dict’ы сливаются и ещё могут пересечься с играми).
# Статические конфиги (GAMES, пресеты клуба и т.п.) сюда не кладём.
_pending: Dict[int, Tuple[str, int, Optional[str], float]] = LazyGameStore(
    "onboarding_pending"
)
_launch_lock: Dict[Tuple[int, str], float] = LazyGameStore("onboarding_launch_lock")
# Токен запуска: не перетираем личку, если человек уже ушёл с экрана готовности.
_notify_token: Dict[int, int] = LazyGameStore("onboarding_notify_token")
# Ожидающие итог после сессии: (user_id, notify_token) → payload.
# Ключ по токену — старый watcher не сносит pending новой партии.
_pending_session_tips: Dict[Tuple[int, int], Dict[str, Any]] = LazyGameStore(
    "onboarding_pending_session_tips"
)
# Флаги «уже отправили» — dict[key]=True (API как у set: in / assign / pop / clear).
_session_finish_sent: Dict[Tuple[int, int], bool] = LazyGameStore(
    "onboarding_session_finish_sent"
)
# Один tip на токен запуска (сессия или instant).
_tip_sent_tokens: Dict[Tuple[int, int], bool] = LazyGameStore(
    "onboarding_tip_sent_tokens"
)
# Доски выбора/старта, которые уже забрали (защита от двойного клика).
_consumed_boards: Dict[Tuple[int, int], bool] = LazyGameStore(
    "onboarding_consumed_boards"
)
# Короткоживущая сессия UI онбординга (uid → payload), переживает рестарт.
_ob_session: Dict[int, Dict[str, Any]] = LazyGameStore("onboarding_ob_session")


def _pending_tip_key(user_id: int, notify_token: int) -> Tuple[int, int]:
    return (int(user_id), int(notify_token))


def _pick_pending_for_finish(
    user_id: int,
    *,
    message_id: Optional[int] = None,
) -> Optional[Tuple[Tuple[int, int], Dict[str, Any]]]:
    """Находит pending именно той партии, которая только что закончилась."""
    uid = int(user_id)
    items = [(k, v) for k, v in _pending_session_tips.items() if k[0] == uid]
    if not items:
        return None
    if message_id:
        mid = int(message_id)
        for k, v in items:
            try:
                if int(v.get("board_mid") or 0) == mid:
                    return k, v
                if int(v.get("anchor_message_id") or 0) == mid:
                    return k, v
            except Exception:
                continue
    finished: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
    for k, v in items:
        gk = str(v.get("game_key") or "")
        if gk not in SESSION_GAMES:
            continue
        exp = v.get("board_mid")
        try:
            exp_mid = int(exp) if exp else None
        except Exception:
            exp_mid = None
        if _session_is_finished(gk, uid, exp_mid):
            finished.append((k, v))
    if finished:
        return max(finished, key=lambda x: x[0][1])
    if len(items) == 1:
        return items[0]
    live = _notify_token.get(uid)
    if live:
        key = _pending_tip_key(uid, int(live))
        hit = _pending_session_tips.get(key)
        if hit is not None:
            return key, hit
    return max(items, key=lambda x: x[0][1])


_PENDING_TTL = 3600.0
_LAUNCH_COOLDOWN = 3.0


def _remember(user_id: int, game_key: str, bet: int, variant: Optional[str]) -> None:
    _pending[user_id] = (game_key, bet, variant, time.time())


def _recall(user_id: int) -> Optional[Tuple[str, int, Optional[str]]]:
    item = _pending.get(user_id)
    if not item:
        return None
    game_key, bet, variant, born = item
    # wall-clock: после рестарта monotonic ломает TTL у LazyGameStore
    if time.time() - float(born or 0) > _PENDING_TTL:
        _pending.pop(user_id, None)
        return None
    return game_key, bet, variant


def _too_fast(
    user_id: int,
    *,
    bucket: str = "launch",
    cooldown: Optional[float] = None,
) -> bool:
    """Антиспам по корзинам: board (лишка) и start (группа) не мешают друг другу.

    Раньше общий кулдаун после выбора игры блокировал «Начать игру» → «Секунду…».
    """
    now = time.time()
    window = float(_LAUNCH_COOLDOWN if cooldown is None else cooldown)
    key = (int(user_id), str(bucket or "launch"))
    last = float(_launch_lock.get(key, 0.0) or 0.0)
    if now - last < window:
        return True
    _launch_lock[key] = now
    if len(_launch_lock) > 5000:
        # Простая уборка устаревших ключей.
        cutoff = now - max(_LAUNCH_COOLDOWN, window) * 4
        for k, ts in list(_launch_lock.items()):
            if float(ts or 0) < cutoff:
                _launch_lock.pop(k, None)
    return False


def _bump_notify_token(user_id: int) -> int:
    token = int(time.time() * 1000)
    _notify_token[user_id] = token
    return token


def _notify_token_alive(user_id: int, token: int) -> bool:
    return _notify_token.get(user_id) == token


def _session_set(user_id: int, **kwargs: Any) -> None:
    cur = dict(_ob_session.get(user_id) or {})
    cur.update(kwargs)
    cur["ts"] = time.time()
    _ob_session[user_id] = cur


def _session_get(user_id: int) -> Dict[str, Any]:
    cur = _ob_session.get(user_id) or {}
    ts = float(cur.get("ts") or 0)
    if ts and time.time() - ts > _PENDING_TTL:
        _ob_session.pop(user_id, None)
        return {}
    return cur


def _needs_group_choice(game_key: str, variant: Optional[str]) -> bool:
    game = GAMES.get(game_key) or {}
    return bool(game.get("variants")) and not variant


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
        if self.chat_ref and CLUB_USERNAME.lower() in str(self.chat_ref).lower():
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


async def _group_balance_for_wallet(wallet: Wallet) -> Optional[float]:
    """Баланс группы для умного расчёта ставки новичка."""
    chat_id = int(wallet.chat_id or 0)
    if chat_id <= 0:
        chat_id = int(CLUB_CHAT_ID or 0)
    if chat_id <= 0:
        return None
    try:
        raw = await db.get_chat_balancebalance(bot1, chat_id)
        if raw in (None, ""):
            return 0.0
        return float(raw)
    except Exception as e:
        print(f"[ONBOARDING] group balance for bet: {e!r}")
        return None


def _bet_for(
    game: Dict[str, Any],
    wallet: Wallet,
    *,
    group_balance: Optional[float] = None,
) -> int:
    """Ставка для запуска.

    На задании: ~10% виртуального баланса и не выше рекомендуемой ставки
    по балансу группы — новичок реже сжигает всё и не давит на бч.
    Иначе — обычная первая ставка, тоже с учётом бч (если известен).
    """
    floor = int(game["min"])
    if wallet.amount < floor:
        return 0

    if wallet.free_quest:
        from_user = max(floor, (wallet.amount * SAFE_BET_PERCENT) // 100)
    else:
        from_user = max(FIRST_BET, floor)

    bet = min(int(from_user), int(wallet.amount))

    if group_balance is not None:
        try:
            from bot.funcs.group_balance_level import (
                recommended_bet,
                effective_stake_cap,
                get_settings,
            )
            cfg = get_settings()
            from_group = int(recommended_bet(group_balance, cfg) or 0)
            # Учитываем бч только если рекомендуемая ставка покрывает минимум игры —
            # иначе новичок застрял бы на старте.
            if from_group >= floor:
                bet = min(bet, from_group)
            # Для обычной (не free) игры учитываем потолок ★ группы.
            if not wallet.free_quest:
                cap_chat = int(wallet.chat_id or 0) or int(CLUB_CHAT_ID or 0)
                if cap_chat:
                    cap = effective_stake_cap(cap_chat, cfg=cfg)
                    if cap is not None:
                        bet = min(bet, int(cap))
        except Exception as e:
            print(f"[ONBOARDING] group-aware bet fail: {e!r}")

    if wallet.max_bet is not None:
        bet = min(bet, wallet.max_bet)
    if bet < floor:
        return 0
    return int(bet)


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
            where = str(wallet.chat_ref or "").strip() or "в группе задания"
            pause = _bq(
                f"Группа : {where}",
                "Бот должен быть администратором, чтобы игры засчитывались.",
                "Можно взять другое доступное задание.",
            )
            text = (
                f"{_path(1)}\n\n"
                f"{E_TARGET} <b>Задание на паузе</b>\n\n"
                f"{_quest_stats(wallet)}\n\n"
                f"{pause}\n\n"
                f"{_hint('Нажмите «Другое задание»')}"
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Другое задание", data="ob_earn", icon="5346141321717363100", style="success")],
                [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
            ])
            return text, markup

    ready = wallet.amount >= _cheapest_bet()

    if ready:
        text = _start_text_player(wallet)
        if wallet.free_quest:
            rows: List[List[InlineKeyboardButton]] = [
                [_btn("Продолжить задание", data="ob_games", icon="5346028458566759465", style="success")],
                [_btn("Другое задание", data="ob_earn", icon=ICON_GIFT, style="success")],
                [_btn("Закончить задание", data="ob_finish", icon=ICON_FINISH, style="danger")],
                [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
            ]
            return text, InlineKeyboardMarkup(inline_keyboard=rows)
        cta = _btn("Играть!", data="ob_games", icon="5348423147647414077", style="success")
    else:
        text = _start_text_newcomer()
        cta = _btn("Получить куты", data="ob_earn", icon="5346141321717363100", style="success")

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [cta],
        [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
    ])
    return text, markup


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
    rows.append([_btn("Назад", data="ob_start", icon=ICON_CLOSE)])
    return _earn_list_text(), InlineKeyboardMarkup(inline_keyboard=rows)


async def show_home(message: Message, user_id: int, *, as_new: bool = False) -> bool:
    """Показать главный экран онбординга в этом сообщении.

    Дом у бота один: и /start, и возвраты из «О Куте», бонуса и прочих
    разделов приводят сюда. as_new=True - отправить новым сообщением.
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
        ("no_icons", text, _markup_without_icons(markup)),
        ("plain", _html_plain(text), _markup_without_icons(markup)),
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
    print(f"[ONBOARDING] show_home({user_id}): не удалось показать ({last_err!r})")
    return False


def _cheapest_bet() -> int:
    return min(int(g["min"]) for g in GAMES.values())


def _start_text_newcomer() -> str:
    """Первый экран. Правь текст прямо здесь."""
    return (
        f"<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Кут - Элитный игровой клуб</b>\n\n"
        f"<blockquote>"
        f"<b>1 кут = 1 <tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>\n"
        f"<b>Старт без доната</b>"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Получите куты</b>"
    )


def _start_text_player(wallet: Wallet) -> str:
    """Стартовый экран игрока. Правь текст прямо здесь."""
    if wallet.free_quest:
        where = _venue_label(wallet)
        return (
            f"<tg-emoji emoji-id='5418238674267556907'>⭐</tg-emoji> <b>Задание</b>\n\n"
            f"{_quest_stats(wallet)}\n\n"
            f"<blockquote>"
            f"<b>Играть {where}</b>\n"
            f"<b>Свои куты не трогаем</b>\n"
            f"<b>Можно взять другое или закончить</b>"
            f"</blockquote>\n\n"
            f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Продолжить</b>"
        )
    return (
        f"<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Кут - элитный игровой клуб</b>\n\n"
        f"<blockquote>"
        f"<b>{wallet.amount} кут</b>\n"
        f"<b>1 кут = 1 <tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>"
        f"</blockquote>"
    )

async def _menu_rows(user_id: Optional[int] = None) -> List[List[InlineKeyboardButton]]:
    """Полное меню - только по кнопке «Меню», не на первом экране.

    user_id оставлен в сигнатуре для совместимости вызовов.
    """
    _ = user_id
    rows: List[List[InlineKeyboardButton]] = []

    bonus = _bonus_button()
    if bonus:
        rows.append([bonus])

    rows.extend([
        [_btn("О Куте", data="3412helpstarthelp", icon=ICON_ABOUT)],
        [_btn("Профиль", data="9back_to_menu1", icon=ICON_PROFILE)],
        [_btn("Вывод", data="conc_stars", icon=ICON_WITHDRAW),
         _btn("Донат", data="insert_stars", icon=ICON_DONATE)],
        [_btn("Задания", data="questions_stars", icon=ICON_TASKS)],
        [_btn("Ферма", web_app=_farm_url(), icon=ICON_FARM)],
        [_btn("Чёрный рынок", data="blackshop", icon=ICON_MARKET)],
        [_btn("О нас", data="about_start", icon=ICON_US)],
        [_btn("Назад", data="ob_start", icon=ICON_CLOSE)],
    ])
    return rows


async def _menu_text(user_id: int) -> str:
    """Меню. Правь текст прямо здесь."""
    wallet = await _wallet(user_id)
    if wallet.free_quest:
        body = (
            f"<b>Задание активно</b>\n\n"
            f"{_quest_stats(wallet)}\n\n"
            f"<blockquote><b>Свои куты не трогаем</b></blockquote>\n"
            f"<blockquote><b>Можно играть самостоятельно</b></blockquote>"
        )
    else:
        body = (
            f"<blockquote>"
            f"<b>{wallet.amount} кут</b>\n"
            f"<b>1 кут = 1 <tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>"
            f"</blockquote>"
        )
    return (
        f"<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Главное меню</b>\n\n"
        f"{body}\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Выберите раздел</b>"
    )

def _bonus_button() -> Optional[InlineKeyboardButton]:
    """Тот же callback, что у бонуса в старом меню: случайное число + '_+'."""
    try:
        from bot.config.config import bonusbet, enabled_bonus
        if not enabled_bonus:
            return None
        return _btn("Бонус", data=f"{random.randint(1, bonusbet)}_+", icon=ICON_BONUS)
    except Exception as e:
        print(f"[ONBOARDING] Кнопка бонуса недоступна: {e!r}")
        return None


@dp.callback_query(F.data == "ob_start")
async def ob_start(call: CallbackQuery):
    await call.answer()
    _bump_notify_token(call.from_user.id)
    text, markup = await start_screen(call.from_user.id)
    await _swap(call, text, markup)


@dp.callback_query(F.data == "ob_menu")
async def ob_menu(call: CallbackQuery):
    await call.answer()
    _bump_notify_token(call.from_user.id)
    text = await _menu_text(call.from_user.id)
    markup = InlineKeyboardMarkup(inline_keyboard=await _menu_rows(call.from_user.id))
    await _swap(call, text, markup)


# ──────────────────────────────────────────────────────────────────────
# Закончить задание → подтверждение → мост «другое / сам»
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_finish")
async def ob_finish(call: CallbackQuery):
    """Подтверждение досрочного выхода из бесплатного задания."""
    await call.answer()
    _bump_notify_token(call.from_user.id)
    wallet = await _wallet(call.from_user.id)
    if not wallet.free_quest:
        await _swap(call, _finish_none_text(), _finish_none_markup())
        return
    await _swap(call, _finish_ask_text(wallet), _finish_ask_markup())


@dp.callback_query(F.data == "ob_finish_no")
async def ob_finish_no(call: CallbackQuery):
    await call.answer()
    text, markup = await start_screen(call.from_user.id)
    await _swap(call, text, markup)


@dp.callback_query(F.data == "ob_finish_yes")
async def ob_finish_yes(call: CallbackQuery):
    """Снимаем активное задание и ведём новичка к следующему шагу."""
    await call.answer()
    _bump_notify_token(call.from_user.id)
    user_id = call.from_user.id
    wallet = await _wallet(user_id)
    if not wallet.free_quest:
        await _swap(call, _finish_none_text(), _finish_none_markup())
        return

    ok = False
    try:
        ok = bool(await db.cancel_gc_assignment(user_id))
    except Exception as e:
        print(f"[ONBOARDING] cancel_gc_assignment {user_id}: {e!r}")
        ok = False

    if not ok:
        await call.answer("Не удалось закончить задание. Попробуйте ещё раз.", show_alert=True)
        text, markup = await start_screen(user_id)
        await _swap(call, text, markup)
        return

    balance = await _balance(user_id)
    await _swap(call, _finish_done_text(balance), _finish_done_markup(balance))


def _finish_ask_text(wallet: Wallet) -> str:
    where = _venue_label(wallet)
    card = _bq(
        f"{E_OK} <b>Свои куты целы - их не трогаем</b>",
        f"{E_FIRE} Прогресс задания сбросится",
        f"{E_CUP} Награда за цель при досрочном выходе не выдаётся",
        f"{E_STAR} Дальше: другое задание или играть самому в {where}",
    )
    return (
        f"{_path(1)}\n\n"
        f"{E_TARGET} <b>Закончить задание?</b>\n\n"
        f"{_quest_stats(wallet)}\n\n"
        f"{card}\n\n"
        f"{_hint('Подтвердите или вернитесь')}"
    )


def _finish_ask_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Да, закончить", data="ob_finish_yes", icon=ICON_FINISH, style="danger")],
        [_btn("Продолжить задание", data="ob_finish_no", icon=ICON_PLAY, style="success")],
    ])


def _finish_done_text(balance: int) -> str:
    club = f"@{CLUB_USERNAME}" if CLUB_USERNAME else "в группе клуба"
    card = _bq(
        f"{E_OK} Задание закрыто - свои куты целы",
        f"{E_COIN} Баланс : {balance} кут",
        f"{E_GIFT} Можно взять другое задание",
        f"{E_GAME} Или играть самому в {club}",
    )
    return (
        f"{_path(0)}\n\n"
        f"{E_OK} <b>Задание закончено</b>\n\n"
        f"{card}\n\n"
        f"{_hint('Выберите, что дальше')}"
    )


def _finish_done_markup(balance: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [_btn("Другое задание", data="ob_earn", icon=ICON_GIFT, style="success")],
    ]
    if balance >= _cheapest_bet():
        rows.append([_btn("Играть сам", data="ob_games", icon=ICON_PLAY, style="success")])
    rows.append([_btn("Меню", data="ob_menu", icon=ICON_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _finish_none_text() -> str:
    return (
        f"{E_OK} <b>Активного задания нет</b>\n\n"
        f"{_bq(f'{E_GIFT} Можно взять бесплатное задание', f'{E_GAME} Или играть на своём балансе')}\n\n"
        f"{_hint('Выберите следующий шаг')}"
    )


def _finish_none_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Получить куты", data="ob_earn", icon=ICON_GIFT, style="success")],
        [_btn("Играть!", data="ob_games", icon=ICON_PLAY)],
        [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
    ])


# ──────────────────────────────────────────────────────────────────────
# Ветка «пусто», клик 2 - бесплатные задания
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_earn")
async def ob_earn(call: CallbackQuery):
    await call.answer()
    await _show_earn(call, page=0)


@dp.callback_query(F.data.startswith("ob_earn:"))
async def ob_earn_page(call: CallbackQuery):
    """Пагинация списка бесплатных заданий."""
    try:
        page = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await call.answer()
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
            icon=ICON_GIFT,
            style="success",
        )]
        for q in chunk
    ]

    if total > FREE_QUESTS_PER_PAGE:
        rows.append(_earn_nav(page, pages))

    rows.append([_btn("Назад", data="ob_start", icon=ICON_CLOSE)])
    await _swap(call, _earn_list_text(), InlineKeyboardMarkup(inline_keyboard=rows))


def _earn_list_text() -> str:
    """Список заданий. Правь текст прямо здесь."""
    return (
        f"<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> <b>Куты без доната</b>\n\n"
        f"<blockquote>"
        f"<b>Играете на баланс задания</b>\n"
        f"<b>Дошли до цели - награда ваша</b>\n"
        f"<b>Свои куты не трогаем</b>"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Выберите задание</b>"
    )

def _earn_nav(page: int, pages: int) -> List[InlineKeyboardButton]:
    """Стрелки как в магазине: назад · N/M · вперёд."""
    row: List[InlineKeyboardButton] = []
    prev_page = page - 1 if page > 0 else pages - 1
    next_page = page + 1 if page < pages - 1 else 0
    row.append(_btn(" ", data=f"ob_earn:{prev_page}", icon=ICON_PREV))
    row.append(_btn(f"{page + 1}/{pages}", data="ob_noop"))
    row.append(_btn(" ", data=f"ob_earn:{next_page}", icon=ICON_NEXT))
    return row


@dp.callback_query(F.data == "ob_noop")
async def ob_noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("ob_quest:"))
async def ob_quest(call: CallbackQuery):
    """Карточка задания. Берёт его штатный обработчик qst:gcstart."""
    parts = (call.data or "").split(":")
    try:
        quest_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        await call.answer("Задание не открылось", show_alert=True)
        return

    await call.answer()

    quest = next(
        (q for q in await _free_quests(call.from_user.id) if _quest_id(q) == quest_id),
        None,
    )
    if quest is None:
        await _open_bonus(call)
        return

    await _swap(call, _earn_card_text(quest), _earn_card_markup(quest_id, page))


def _earn_card_text(quest: Dict[str, Any]) -> str:
    """Карточка задания. Правь текст прямо здесь."""
    start = _int(quest.get("start_amount"))
    target = _int(quest.get("target_amount"))
    reward = _int(quest.get("reward_amount"))
    limit = _int(quest.get("betlimit"))

    card = (
        f"<blockquote>"
        f"<b>Старт : {start} кут</b>\n"
        f"<b>Цель : {target} кут</b>\n"
        f"<b>Награда : +{reward} кут</b>"
    )
    if limit:
        card += f"\n<b>Ставка до : {limit} кут</b>"
    card += "</blockquote>"

    return (
        f"<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> <b>Задание</b>\n\n"
        f"{card}\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Взять и играть</b>"
    )

def _earn_card_markup(quest_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Взять задание", data=f"ob_take:{quest_id}:{page}", icon=ICON_PLAY, style="success")],
        [_btn("Назад", data=f"ob_earn:{page}", icon=ICON_CLOSE)],
    ])


@dp.callback_query(F.data.startswith("ob_take:"))
async def ob_take(call: CallbackQuery):
    """Берём задание сами и сразу ведём в выбор игры."""
    parts = (call.data or "").split(":")
    try:
        quest_id = int(parts[1])
    except (ValueError, IndexError):
        await call.answer("Задание не открылось", show_alert=True)
        return

    ok, msg, created = await _activate_quest(call.from_user.id, quest_id)
    if not ok:
        await call.answer(msg, show_alert=True)
        return

    await call.answer(msg, show_alert=False)

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
                [_btn("К заданиям", data="ob_earn", icon=ICON_GIFT, style="success")],
                [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
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
    body = _bq(
        f"{E_BOLT} Свои куты в безопасности.",
        f"{E_STAR} Откройте задания ещё раз - виртуальный баланс уже там.",
    )
    return (
        f"{E_TARGET} <b>Задание принято, но баланс ещё не подтянулся</b>\n\n"
        f"{body}\n\n"
        f"{_hint('Нажмите «К заданиям»')}"
    )


async def _open_bonus(call: CallbackQuery) -> None:
    """Бесплатных заданий нет - сначала мост, потом штатный бонус."""
    await _swap(call, _no_quests_bridge_text(), _no_quests_bridge_markup())


@dp.callback_query(F.data == "ob_bonus")
async def ob_bonus(call: CallbackQuery):
    await call.answer()
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
        f"{_path(1)}\n\n"
        f"{E_LEAF} <b>Бесплатных заданий сейчас нет.</b>\n\n"
        f"{_bq('Новые появляются регулярно.', 'Пока куты можно взять через бонус.')}\n\n"
        f"{_hint('Нажмите «Взять бонус»')}"
    )


def _no_quests_bridge_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Взять бонус", data="ob_bonus", icon=ICON_BONUS, style="success")],
        [_btn("Назад", data="ob_start", icon=ICON_CLOSE)],
    ])


def _no_quests_text() -> str:
    """Запасной текст, если бонус открыть не удалось."""
    return (
        f"{E_LEAF} <b>Бесплатных заданий сейчас нет.</b>\n\n"
        f"{_bq('Новые появляются регулярно.', 'Пока куты можно взять через бонус.')}\n\n"
        f"{_hint('Нажмите «Бонус»')}"
    )


def _no_quests_markup() -> InlineKeyboardMarkup:
    try:
        from bot.config.config import bonusbet
        n = max(1, int(bonusbet))
    except Exception:
        n = 2
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Бонус", data=f"{random.randint(1, n)}_+", icon=ICON_BONUS, style="success")],
        [_btn("Назад", data="ob_start", icon=ICON_CLOSE)],
    ])


# ──────────────────────────────────────────────────────────────────────
# Ветка «есть куты», клик 2 - выбор игры
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "ob_games")
async def ob_games(call: CallbackQuery):
    await call.answer()
    _bump_notify_token(call.from_user.id)
    _session_set(
        call.from_user.id,
        board_message_id=0,
        play_url="",
        ready_card=False,
        game_key="",
    )
    wallet = await _wallet(call.from_user.id)
    await _swap(call, _games_text(wallet), _games_markup(wallet))


@dp.callback_query(F.data == "ob_next")
async def ob_next(call: CallbackQuery):
    """После игры: обновить прогресс задания и снова предложить игру."""
    await call.answer()
    _bump_notify_token(call.from_user.id)
    wallet = await _wallet(call.from_user.id)
    if wallet.free_quest:
        left = max(0, wallet.target - wallet.amount)
        if left <= 0 or wallet.amount >= wallet.target:
            text = (
                f"{_path(2)}\n\n"
                f"{E_CUP} <b>Цель достигнута</b>\n\n"
                f"{_quest_stats(wallet)}\n\n"
                f"{_bq('Награда уже на балансе или скоро придёт.', 'Можно играть дальше или закончить задание.')}\n\n"
                f"{_hint('Можно играть дальше или открыть меню')}"
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Играть!", data="ob_games", icon=ICON_PLAY, style="success")],
                [_btn("Закончить задание", data="ob_finish", icon=ICON_FINISH, style="danger")],
                [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
            ])
            await _swap(call, text, markup)
            return
        text = (
            f"{_path(2)}\n\n"
            f"{E_NEXT} <b>Что дальше</b>\n\n"
            f"{_quest_stats(wallet)}\n\n"
            f"{_bq(f'{E_BOLT} Свои куты не трогаем', f'{E_STAR} Можно взять другое или закончить и играть сам')}\n\n"
            f"{_hint('Выберите игру и продолжайте')}"
        )
        await _swap(call, text, _games_markup(wallet))
        return
    await _swap(call, _games_text(wallet), _games_markup(wallet))


def _games_text(wallet: Wallet, *, accepted: bool = False) -> str:
    """Экран выбора игр. Правь текст прямо здесь."""
    if wallet.free_quest:
        where = _venue_label(wallet)
        stats = _quest_stats(wallet)
        if accepted:
            return (
                f"<tg-emoji emoji-id='5190517223311059564'>🎁</tg-emoji> <b>Баланс задания готов</b>\n\n"
                f"{stats}\n\n"
                f"<blockquote>"
                f"<b>Играть в {where}</b>\n"
                f"<b>1 кут = 1 <tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>\n"
                f"<b>Свои куты не трогаем</b>\n"
                f"<b>Можно закончить и играть сам</b>"
                f"</blockquote>\n\n"
                f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Выберите игру</b>"
            )
        return (
            f"<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>Ваш ход</b>\n\n"
            f"{stats}\n\n"
            f"<blockquote>"
            f"<b>{where}</b>\n"
            f"<b>Ставка бережная: ваш баланс + баланс группы</b>\n"
            f"<b>Свои куты не трогаем</b>\n"
            f"<b>Можно закончить и играть сам</b>"
            f"</blockquote>\n\n"
            f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Выберите игру</b>"
        )
    club = f"@{CLUB_USERNAME}" if CLUB_USERNAME else "в группе клуба"
    return (
        f"<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>Игры</b>\n\n"
        f"<blockquote>"
        f"<b>{wallet.amount} кут</b>\n"
        f"<b>1 кут = 1 <tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji></b>\n"
        f"<b>Ставка с баланса · {club}</b>"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> <b>Выберите игру</b>"
    )


def _games_markup(wallet: Optional[Wallet] = None) -> InlineKeyboardMarkup:
    # Premium icon = эмодзи на кнопке. В text только название,
    # иначе Telegram рисует два эмодзи подряд.
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(SOLO_ORDER), 2):
        row = []
        for k in SOLO_ORDER[i:i + 2]:
            game = GAMES[k]
            icon = GAME_ICON_IDS.get(k) or _emoji_id(game["emoji"])
            row.append(_btn(game["title"], data=f"ob_game:{k}", icon=icon))
        rows.append(row)
    if wallet is not None and wallet.free_quest:
        rows.append([
            _btn("Другое задание", data="ob_earn", icon=ICON_GIFT, style="success"),
            _btn("Закончить задание", data="ob_finish", icon="5305629674058061875", style="danger"),
        ])
    rows.append([_btn("Назад", data="ob_start", icon=ICON_CLOSE)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ──────────────────────────────────────────────────────────────────────
# Клик 3 - правила и запуск
# ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("ob_game:"))
async def ob_game(call: CallbackQuery):
    """Выбор игры → сразу доска в группе + одна карточка в личке.

    Как футбол: без «Начать играть» в личке. В группе — текст и
    «Начать игру» (или выбор), в личке — «Открыть мою игру».
    """
    game_key = call.data.split(":", 1)[1] if ":" in call.data else ""
    if game_key not in GAMES:
        await call.answer("Такой игры нет", show_alert=True)
        return

    await call.answer()
    game = GAMES[game_key]
    wallet = await _wallet(call.from_user.id)
    floor = int(game["min"])

    if wallet.free_quest and wallet.max_bet is not None and wallet.max_bet < floor:
        await _swap(call, _bet_limit_text(game, wallet), _bet_limit_markup())
        return

    group_bal = await _group_balance_for_wallet(wallet)
    bet = _bet_for(game, wallet, group_balance=group_bal)
    if bet < floor:
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    # Старая ссылка больше не действует.
    _bump_notify_token(call.from_user.id)
    _session_set(
        call.from_user.id,
        game_key=game_key,
        bet=bet,
        board_message_id=0,
        play_url="",
        ready_card=False,
    )
    _remember(call.from_user.id, game_key, bet, None)

    # Все игры — один принцип: выбор → сразу сообщение в группе + ссылка в личке.
    await _try_launch(call, game_key, bet, None)


@dp.callback_query(F.data.startswith("ob_play:"))
async def ob_play(call: CallbackQuery):
    parts = (call.data or "").split(":")
    if len(parts) < 3:
        await call.answer("Не удалось разобрать игру", show_alert=True)
        return

    game_key = parts[1]
    variant = parts[3] if len(parts) > 3 else None
    try:
        bet = int(parts[2])
    except ValueError:
        await call.answer("Не удалось разобрать ставку", show_alert=True)
        return

    if game_key not in GAMES:
        await call.answer("Такой игры нет", show_alert=True)
        return

    await call.answer()
    # Для choice-игр выбор должен быть в группе.
    if (GAMES[game_key].get("variants")) and call.message and call.message.chat.type == "private":
        variant = None
    _remember(call.from_user.id, game_key, bet, variant)
    await _try_launch(call, game_key, bet, variant)


@dp.callback_query(F.data.in_({"ob_joined", "ob_retry"}))
async def ob_resume(call: CallbackQuery):
    """«Открыть игру» / «Попробовать снова» - продолжаем с выбранной игрой."""
    await call.answer()
    saved = _recall(call.from_user.id)
    if not saved:
        wallet = await _wallet(call.from_user.id)
        await _swap(call, _games_text(wallet), _games_markup(wallet))
        return
    await _try_launch(call, saved[0], saved[1], saved[2])


async def _edit_only(
    call: CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup,
) -> bool:
    """Только edit текущего сообщения. Никогда не шлёт второе в личку."""
    if call.message is None:
        return False
    variants: List[Tuple[str, InlineKeyboardMarkup]] = [
        (text, markup),
        (text, _markup_without_icons(markup)),
        (_html_plain(text), _markup_without_icons(markup)),
    ]
    for body, kb in variants:
        try:
            await call.message.edit_text(
                body, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return await _swap_markup(call, markup)
    # Текст тот же / edit текста не приняли — пробуем хотя бы кнопки.
    return await _swap_markup(call, markup)


async def _show_ready_link(
    call: CallbackQuery,
    *,
    game: Dict[str, Any],
    game_key: str,
    bet: int,
    wallet: Wallet,
    play_url: str,
    venue_ref: Optional[str] = None,
) -> None:
    """Одно сообщение в личке: карточка + «Открыть мою игру» (url на доску в группе).

    Никогда не создаёт второе сообщение — только edit того, что уже на экране.
    """
    venue_label = _venue_label(wallet, venue_ref)
    card = _game_card_text(
        game, bet, wallet,
        game_key=game_key,
        venue_label=venue_label,
    )
    kb = _ready_markup(play_url, free_quest=wallet.free_quest)
    _session_set(
        call.from_user.id,
        play_url=play_url,
        ready_card=True,
        game_key=game_key,
        bet=bet,
    )

    current = ""
    if call.message is not None:
        current = (
            getattr(call.message, "html_text", None)
            or call.message.text
            or ""
        )
    # Уже эта карточка — меняем только кнопки (без мигания текста).
    same_card = bool(current) and (
        str(game.get("title") or "") in current
        and "Ставка" in current
    )
    if same_card and await _swap_markup(call, kb):
        return

    if not await _edit_only(call, card, kb):
        print(
            f"[ONBOARDING] Не удалось обновить личку со ссылкой "
            f"{game_key}/{call.from_user.id} → {play_url}"
        )


async def _try_launch(call: CallbackQuery, game_key: str, bet: int,
                      variant: Optional[str]) -> None:
    """Проверки → доска выбора или партия в группе → ссылка в личку.

    Логика партии всегда из module/func игры (trade.py, slots.py, …).
    """
    user = call.from_user
    game = GAMES[game_key]
    wallet = await _wallet(user.id)
    venue_chat_id, venue_url, venue_ref = _play_venue(wallet)

    if not await _in_chat(user.id, venue_chat_id):
        await _swap(call, _join_text(game, venue_url), _join_markup(venue_url))
        return

    if wallet.amount < bet or bet < int(game["min"]):
        await _swap(call, _no_funds_text(game, wallet), _no_funds_markup(wallet))
        return

    if not await _chat_can_pay(venue_chat_id, bet):
        await _swap(call, _empty_treasury_text(), _empty_treasury_markup())
        return

    # Повтор «Открыть игру»: партия уже ждёт — не плодим вторую доску,
    # а снова даём ссылку на ту же.
    sess = _session_get(user.id)
    existing_board = int(sess.get("board_message_id") or 0)
    existing_chat = int(sess.get("play_chat_id") or 0)
    if (
        existing_board
        and existing_chat == int(venue_chat_id)
        and sess.get("game_key") == game_key
        and int(sess.get("bet") or 0) == int(bet)
        and (
            game_key in CONFIRM_START_GAMES
            or _needs_group_choice(game_key, variant)
        )
    ):
        play_url = str(sess.get("play_url") or "").strip() or _message_url(
            venue_chat_id, existing_board, venue_ref,
        )
        await _show_ready_link(
            call,
            game=game,
            game_key=game_key,
            bet=bet,
            wallet=wallet,
            play_url=play_url,
            venue_ref=venue_ref,
        )
        return

    if _too_fast(user.id, bucket="board", cooldown=1.5):
        try:
            await call.answer("Секунду…", show_alert=False)
        except Exception:
            pass
        return

    dm_chat_id = call.message.chat.id
    dm_message_id = call.message.message_id
    balance_before = wallet.amount
    token = _bump_notify_token(user.id)

    _session_set(
        user.id,
        game_key=game_key,
        bet=bet,
        play_chat_id=venue_chat_id,
        play_chat_ref=venue_ref,
        dm_chat_id=dm_chat_id,
        dm_message_id=dm_message_id,
        balance_before=balance_before,
        free_quest=wallet.free_quest,
        notify_token=token,
        board_message_id=0,
        play_url="",
        ready_card=False,
    )

    if _needs_group_choice(game_key, variant):
        board = await _launch_choice_board(
            user, game_key, bet,
            play_chat_id=venue_chat_id,
            play_chat_ref=venue_ref,
        )
        if board is None:
            await _swap(call, _failed_text(), _failed_markup())
            return
        play_url = _message_url(venue_chat_id, board.message_id, venue_ref)
        _session_set(user.id, board_message_id=board.message_id, play_url=play_url)
        await _show_ready_link(
            call,
            game=game,
            game_key=game_key,
            bet=bet,
            wallet=wallet,
            play_url=play_url,
            venue_ref=venue_ref,
        )
        return

    if game_key in CONFIRM_START_GAMES:
        board = await _launch_confirm_board(
            user, game_key, bet,
            play_chat_id=venue_chat_id,
            play_chat_ref=venue_ref,
        )
        if board is None:
            await _swap(call, _failed_text(), _failed_markup())
            return
        play_url = _message_url(venue_chat_id, board.message_id, venue_ref)
        _session_set(user.id, board_message_id=board.message_id, play_url=play_url)
        # Та же карточка (фото 1), кнопка → URL на доску «Начать игру» в группе.
        await _show_ready_link(
            call,
            game=game,
            game_key=game_key,
            bet=bet,
            wallet=wallet,
            play_url=play_url,
            venue_ref=venue_ref,
        )
        return

    anchor = await _launch(
        user, game_key, bet, variant,
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
    _session_set(user.id, board_message_id=anchor.message_id, play_url=play_url)
    await _show_ready_link(
        call,
        game=game,
        game_key=game_key,
        bet=bet,
        wallet=wallet,
        play_url=play_url,
        venue_ref=venue_ref,
    )


def _choice_board_text(user: User, game_key: str, bet: int) -> str:
    """Доска выбора в группе: весь текст жирным, включая имя."""
    game = GAMES[game_key]
    lead = game.get("board_lead") or "Сделайте выбор - партия начнётся сразу."
    hint = game.get("variant_hint") or "Ваш ход"
    title_line = f"{game['title']} · ставка {bet} кут"
    return (
        f"{game['emoji']} {_mention_html(user.id, user.first_name)}\n\n"
        f"{_bold_html_line(title_line)}\n\n"
        f"{_bq(lead, game.get('rules') or '')}\n\n"
        f"{E_DOWN} {_bold_html_line(str(hint))}"
    )


def _variant_button_style(
    game: Dict[str, Any],
    *,
    value_s: str,
    text: str,
    icon: Optional[str],
) -> Optional[str]:
    """Style кнопки выбора: digit → None; иначе variant_styles или success.

    В variant_styles можно явно указать None (без цветного style) —
    так у рулетки «чёрное / чёт / нечет» остаются нейтральными.
    """
    if (icon and value_s.isdigit()) or (text or "").isdigit():
        return None
    style_map = game.get("variant_styles") or {}
    if value_s in style_map:
        style = style_map[value_s]
    else:
        style = "success"
    if style is None:
        return None
    if style not in ("success", "danger", "primary", "default"):
        return "success"
    return style


def _choice_board_markup(game_key: str, bet: int, owner_id: int) -> InlineKeyboardMarkup:
    """Кнопки выбора в группе. Раскладка из GAMES.variant_rows, если задана."""
    game = GAMES[game_key]
    variants: Sequence[Tuple[str, str]] = game.get("variants") or ()
    buttons: List[InlineKeyboardButton] = []
    for label, value in variants:
        text, icon = _label_for_button(label)
        value_s = str(value or "").strip()
        # Premium-цифры (кубик): на кнопке только icon, без обычного «1»…«6».
        if icon and value_s.isdigit():
            text = "\u200b"
        else:
            if not (text or "").strip():
                text = value_s or "·"
            elif (text or "").isdigit():
                pass
            elif (
                not any(ch.isalpha() for ch in text)
                and not any(ch.isdigit() for ch in text)
            ):
                # Только символы/эмодзи без букв и цифр — дописываем value.
                # Важно: не трогаем «1–6» / «6–12».
                text = f"{text} {value_s}".strip()
        style = _variant_button_style(game, value_s=value_s, text=text, icon=icon)
        buttons.append(_btn(
            text,
            data=f"ob_gpick:{owner_id}:{game_key}:{bet}:{value}",
            icon=icon,
            style=style,
        ))

    rows: List[List[InlineKeyboardButton]] = []
    layout = [int(n) for n in (game.get("variant_rows") or ()) if int(n) > 0]
    if layout and sum(layout) == len(buttons):
        i = 0
        for width in layout:
            rows.append(buttons[i:i + width])
            i += width
    else:
        per_row = 3 if len(buttons) > 4 else 2
        for i in range(0, len(buttons), per_row):
            rows.append(buttons[i:i + per_row])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _launch_choice_board(
    user: User,
    game_key: str,
    bet: int,
    *,
    play_chat_id: int,
    play_chat_ref: Optional[str],
) -> Optional[Message]:
    """Сообщение в группе с кнопками выбора. Партия ещё не начата."""
    text = _choice_board_text(user, game_key, bet)
    markup = _choice_board_markup(game_key, bet, user.id)
    try:
        return await _send_html_chat(play_chat_id, text, reply_markup=markup)
    except Exception as e:
        print(f"[ONBOARDING] choice board {game_key}/{user.id}: {e!r}")
        return None


def _confirm_board_text(user: User, game_key: str, bet: int) -> str:
    """Сообщение в группе: весь текст жирным, включая имя."""
    game = GAMES[game_key]
    lead = game.get("board_lead") or game.get("rules") or (
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> "
        "Нажмите кнопку - и партия стартует."
    )
    title_line = f"{game['title']} · ставка {bet} кут"
    return (
        f"{game['emoji']} {_mention_html(user.id, user.first_name)}\n\n"
        f"{_bold_html_line(title_line)}\n\n"
        f"{_bq(lead)}\n\n"
        f"{E_DOWN} {_bold_html_line('Нажмите «Начать игру»')}"
    )


def _confirm_board_markup(owner_id: int, game_key: str, bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(
            "Начать игру",
            data=f"ob_gstart:{owner_id}:{game_key}:{bet}",
            icon="5425094988260188065",
            style="primary",
        ),
    ]])


async def _launch_confirm_board(
    user: User,
    game_key: str,
    bet: int,
    *,
    play_chat_id: int,
    play_chat_ref: Optional[str],
) -> Optional[Message]:
    """Сообщение в группе с кнопкой старта. Партия ещё не начата."""
    text = _confirm_board_text(user, game_key, bet)
    markup = _confirm_board_markup(user.id, game_key, bet)
    try:
        return await _send_html_chat(play_chat_id, text, reply_markup=markup)
    except Exception as e:
        print(f"[ONBOARDING] confirm board {game_key}/{user.id}: {e!r}")
        return None


@dp.callback_query(F.data.startswith("ob_gpick:"))
async def ob_gpick(call: CallbackQuery):
    """Клик выбора в группе → настоящий handler из файла игры."""
    parts = (call.data or "").split(":")
    # ob_gpick:{owner}:{game}:{bet}:{variant...}
    # variant может содержать пробелы (диапазон «1 6»).
    if len(parts) < 5:
        await call.answer("Не удалось разобрать выбор", show_alert=True)
        return

    try:
        owner_id = int(parts[1])
    except ValueError:
        await call.answer("Не удалось разобрать игрока", show_alert=True)
        return
    game_key, bet_raw = parts[2], parts[3]
    variant_raw = ":".join(parts[4:]).strip()
    if game_key not in GAMES:
        await call.answer("Такой игры нет", show_alert=True)
        return
    try:
        bet = int(bet_raw)
    except ValueError:
        await call.answer("Не удалось разобрать ставку", show_alert=True)
        return

    user = call.from_user
    if int(user.id) != owner_id:
        await call.answer("Это партия другого игрока", show_alert=True)
        return

    game = GAMES[game_key]
    # «1-6» → «1 6», «6-12» → «6 12» (команда рулетки всегда с пробелом).
    variant = _variant_to_cmd_arg(variant_raw)
    allowed = _allowed_variant_values(game)
    if not variant or (variant_raw not in allowed and variant not in allowed):
        await call.answer("Такого выбора нет", show_alert=True)
        return

    sess = _session_get(user.id)
    wallet = await _wallet(user.id)
    if wallet.amount < bet or bet < int(game["min"]):
        await call.answer("Не хватает на ставку", show_alert=True)
        return

    if _too_fast(user.id, bucket="start", cooldown=0.8):
        await call.answer("Секунду…", show_alert=False)
        return

    await call.answer()

    play_chat_id = call.message.chat.id if call.message else int(sess.get("play_chat_id") or 0)
    play_chat_ref = sess.get("play_chat_ref")
    dm_chat_id = int(sess.get("dm_chat_id") or user.id)
    dm_message_id = int(sess.get("dm_message_id") or 0)
    balance_before = int(sess.get("balance_before") or wallet.amount)
    free_quest = bool(sess.get("free_quest")) if "free_quest" in sess else wallet.free_quest
    token = int(sess.get("notify_token") or _bump_notify_token(user.id))

    _remember(user.id, game_key, bet, variant)
    _session_set(user.id, last_variant=variant)
    # Доску с цифрами/выбором удаляем сразу; партия идёт от короткого якоря.
    anchor = await _consume_start_board(
        call.message, user=user, game_key=game_key, bet=bet,
        play_chat_ref=play_chat_ref,
    )
    if anchor is None:
        try:
            await bot1.send_message(
                play_chat_id,
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Не удалось стартовать. Нажмите игру ещё раз.</b>",
                parse_mode="HTML",
            )
        except Exception:
            try:
                await call.answer("Не удалось стартовать — попробуйте ещё раз", show_alert=True)
            except Exception:
                pass
        return
    try:
        handler = getattr(import_module(game["module"]), game["func"])
        # 1–6 → «рулетка 10 1 6», 6–12 → «рулетка 10 6 12»
        cmd_text = " ".join(str(game["cmd"]).format(bet=bet, v=variant).split())
        synthetic = anchor.model_copy(update={
            "text": cmd_text,
            "from_user": user,
        }).as_(bot1)
        print(
            f"[ONBOARDING] gpick launch {game_key} uid={user.id} "
            f"raw={variant_raw!r} cmd={cmd_text!r} anchor={anchor.message_id}",
            flush=True,
        )
        asyncio.create_task(_run_game_and_notify(
            handler, synthetic,
            user=user,
            user_id=user.id,
            game_key=game_key,
            bet=bet,
            play_chat_id=play_chat_id,
            play_chat_ref=play_chat_ref,
            anchor_message_id=anchor.message_id,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id or anchor.message_id,
            balance_before=balance_before,
            free_quest=free_quest,
            notify_token=token,
            variant=variant,
        ))
    except Exception as e:
        print(f"[ONBOARDING] gpick launch {game_key}/{user.id}: {e!r}", flush=True)
        try:
            await bot1.send_message(
                play_chat_id,
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Не удалось запустить игру. Попробуйте ещё раз.</b>",
                reply_to_message_id=getattr(anchor, "message_id", None),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return


@dp.callback_query(F.data.startswith("ob_gstart:"))
async def ob_gstart(call: CallbackQuery):
    """Кнопка «Начать игру» в группе → handler игры (футбол, башня, …)."""
    parts = (call.data or "").split(":")
    # ob_gstart:{owner}:{game}:{bet}
    if len(parts) < 4:
        await call.answer("Не удалось разобрать игру", show_alert=True)
        return

    try:
        owner_id = int(parts[1])
    except ValueError:
        await call.answer("Не удалось разобрать игрока", show_alert=True)
        return
    game_key, bet_raw = parts[2], parts[3]
    if game_key not in GAMES or game_key not in CONFIRM_START_GAMES:
        await call.answer("Такой игры нет", show_alert=True)
        return
    try:
        bet = int(bet_raw)
    except ValueError:
        await call.answer("Не удалось разобрать ставку", show_alert=True)
        return

    user = call.from_user
    if int(user.id) != owner_id:
        await call.answer("Это партия другого игрока", show_alert=True)
        return

    game = GAMES[game_key]
    sess = _session_get(user.id)
    wallet = await _wallet(user.id)
    if wallet.amount < bet or bet < int(game["min"]):
        await call.answer("Не хватает на ставку", show_alert=True)
        return

    if _too_fast(user.id, bucket="start", cooldown=0.8):
        await call.answer("Секунду…", show_alert=False)
        return

    await call.answer()

    play_chat_id = call.message.chat.id if call.message else int(sess.get("play_chat_id") or 0)
    play_chat_ref = sess.get("play_chat_ref")
    dm_chat_id = int(sess.get("dm_chat_id") or user.id)
    dm_message_id = int(sess.get("dm_message_id") or 0)
    balance_before = int(sess.get("balance_before") or wallet.amount)
    free_quest = bool(sess.get("free_quest")) if "free_quest" in sess else wallet.free_quest
    token = int(sess.get("notify_token") or _bump_notify_token(user.id))

    _remember(user.id, game_key, bet, None)
    # Сообщение «Начать игру» удаляем сразу после клика.
    anchor = await _consume_start_board(
        call.message, user=user, game_key=game_key, bet=bet,
        play_chat_ref=play_chat_ref,
    )
    if anchor is None:
        return
    try:
        handler = getattr(import_module(game["module"]), game["func"])
        synthetic = anchor.model_copy(update={
            "text": game["cmd"].format(bet=bet, v=""),
            "from_user": user,
        }).as_(bot1)
        asyncio.create_task(_run_game_and_notify(
            handler, synthetic,
            user=user,
            user_id=user.id,
            game_key=game_key,
            bet=bet,
            play_chat_id=play_chat_id,
            play_chat_ref=play_chat_ref,
            anchor_message_id=anchor.message_id,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id or anchor.message_id,
            balance_before=balance_before,
            free_quest=free_quest,
            notify_token=token,
        ))
    except Exception as e:
        print(f"[ONBOARDING] gstart launch {game_key}/{user.id}: {e!r}")
        try:
            await call.answer("Не удалось запустить игру", show_alert=True)
        except Exception:
            pass


async def _consume_start_board(
    board: Optional[Message],
    *,
    user: User,
    game_key: str,
    bet: int,
    play_chat_ref: Optional[str] = None,
) -> Optional[Message]:
    """Сразу убирает доску выбора/старта и ставит короткий якорь партии.

    Порядок важен для UX:
      1) снять кнопки (нельзя кликнуть дважды)
      2) удалить сообщение с доской
      3) отправить компактный якорь под dice/сессию
    Работает для куба, рулетки, трейда, футбола, башни и любой другой игры.
    """
    if board is None:
        return None

    chat_id = int(board.chat.id)
    mid = int(board.message_id)
    key = (chat_id, mid)
    if key in _consumed_boards:
        return None
    _consumed_boards[key] = True
    if len(_consumed_boards) > 4000:
        _consumed_boards.clear()
        _consumed_boards[key] = True

    game = GAMES.get(game_key) or {}
    opener = (
        f"{game.get('emoji') or E_GAME} {_mention_html(user.id, user.first_name)}"
        f" <b>· {game.get('title') or 'Игра'} · {bet} кут</b>"
    )

    # 1) Мгновенно убираем кнопки — доска больше не кликабельна.
    try:
        await bot1.edit_message_reply_markup(
            chat_id=chat_id, message_id=mid, reply_markup=None,
        )
    except Exception:
        try:
            await board.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # 2) Удаляем само сообщение с выбором / «Начать игру».
    deleted = False
    try:
        await bot1.delete_message(chat_id=chat_id, message_id=mid)
        deleted = True
    except Exception as e:
        print(f"[ONBOARDING] delete start board: {e!r}")
        try:
            await board.delete()
            deleted = True
        except Exception as e2:
            print(f"[ONBOARDING] delete start board retry: {e2!r}")

    # 3) Якорь, на который ответит игра.
    anchor = await _send_html_chat(chat_id, opener)
    if anchor is None:
        # Жёсткий фолбэк: plain text — иначе доска уже удалена и чат «молчит».
        try:
            plain = (
                f"{_safe_display_name(user.first_name)} · "
                f"{game.get('title') or 'Игра'} · {bet} кут"
            )
            anchor = await bot1.send_message(chat_id=chat_id, text=plain)
        except Exception as e:
            print(f"[ONBOARDING] consume plain anchor fail: {e!r}", flush=True)
    if anchor is None and not deleted:
        # Удалить не вышло и якорь не создался — превращаем доску в якорь.
        for body in (opener, _html_plain(opener)):
            try:
                edited = await bot1.edit_message_text(
                    chat_id=chat_id,
                    message_id=mid,
                    text=body,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=None,
                )
                anchor = edited or board
                break
            except Exception as e:
                print(f"[ONBOARDING] consume edit fallback: {e!r}")
        if anchor is None:
            return None
    if anchor is None:
        return None

    play_url = _message_url(chat_id, anchor.message_id, play_chat_ref)
    _session_set(
        user.id,
        board_message_id=anchor.message_id,
        play_url=play_url,
        play_chat_id=chat_id,
    )

    # В личке «Открыть мою игру» ведёт на живой якорь, не на удалённую доску.
    sess = _session_get(user.id)
    dm_chat_id = int(sess.get("dm_chat_id") or 0)
    dm_message_id = int(sess.get("dm_message_id") or 0)
    if dm_chat_id and dm_message_id:
        try:
            await bot1.edit_message_reply_markup(
                chat_id=dm_chat_id,
                message_id=dm_message_id,
                reply_markup=_ready_markup(
                    play_url,
                    free_quest=bool(sess.get("free_quest")),
                ),
            )
        except Exception:
            try:
                await bot1.edit_message_reply_markup(
                    chat_id=dm_chat_id,
                    message_id=dm_message_id,
                    reply_markup=_markup_without_icons(_ready_markup(
                        play_url,
                        free_quest=bool(sess.get("free_quest")),
                    )),
                )
            except Exception:
                pass
    return anchor


def _game_card_text(
    game: Dict[str, Any],
    bet: int,
    wallet: Wallet,
    *,
    game_key: str = "",
    venue_label: str = "",
) -> str:
    """Единая карточка в личке для шага 1 и шага 2 (фото 1 ↔ фото 2).

    Меняются только кнопки: «Открыть игру» → «Открыть мою игру» (url).
    Текст правил/ставки/подсказки один и тот же — из GAMES.rules.
    """
    source = "с задания" if wallet.free_quest else "с баланса"
    where = venue_label or _venue_label(wallet)
    has_choice = bool(game.get("variants"))
    body = (
        f"{game['emoji']} <b>{game['title']}</b>\n\n"
        f"<blockquote>"
        f"<b>{game['rules']}</b>\n"
        f"<b><tg-emoji emoji-id='5453900977432188793'>⭐</tg-emoji> Ставка : {bet} кут ({source})</b>\n"
        f"<b>{where}</b>"
    )
    if wallet.free_quest:
        body += "\n<b>Свои куты не трогаем</b>"
    body += "</blockquote>\n\n"
    if has_choice:
        body += (
            "<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> "
            "<b>Откройте игру — выбор кнопками в группе</b>"
        )
    else:
        body += (
            "<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> "
            "<b>Откройте игру — старт кнопкой в группе</b>"
        )
    return body


async def _launch(
    user: User,
    game_key: str,
    bet: int,
    variant: Optional[str],
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
        opener = (
            f"{game['emoji']} {_mention_html(user.id, user.first_name)}"
            f" <b>· {game['title']} · {bet} кут</b>"
        )
        try:
            anchor = await bot1.send_message(
                chat_id=play_chat_id,
                text=opener,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            # Если премиум-эмодзи в якоре не принялись - шлём unicode.
            if "DOCUMENT_INVALID" in str(e).upper() or "document_invalid" in str(e).lower():
                anchor = await bot1.send_message(
                    chat_id=play_chat_id,
                    text=(
                        f"{_plain_emoji(game['emoji'])} {_mention_html(user.id, user.first_name)}"
                        f" <b>· {game['title']} · {bet} кут</b>"
                    ),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            else:
                raise

        handler = getattr(import_module(game["module"]), game["func"])

        # Синтетическое сообщение: чат и якорь - от бота, автор - игрок,
        # текст - обычная игровая команда. Игра отвечает на якорь.
        synthetic = anchor.model_copy(update={
            "text": game["cmd"].format(bet=bet, v=variant or ""),
            "from_user": user,
        }).as_(bot1)

        # Не держим колбэк — ссылку в личку отдаём сразу.
        asyncio.create_task(_run_game_and_notify(
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
            variant=variant,
        ))
        return anchor
    except Exception as e:
        print(f"[ONBOARDING] Не удалось запустить {game_key} для {user.id}: {e!r}")
        if anchor is not None:
            try:
                await bot1.delete_message(play_chat_id, anchor.message_id)
            except Exception:
                pass
        return None


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
    variant: Optional[str] = None,
) -> None:
    tip_key = _pending_tip_key(user_id, notify_token)
    last_variant = (variant or "").strip() or None
    # Сессионные: регистрируем pending ДО handler, чтобы notify с конца партии
    # не потерялся, если UI закроется очень быстро.
    if game_key in SESSION_GAMES:
        _pending_session_tips[tip_key] = {
            "user": user,
            "game_key": game_key,
            "bet": bet,
            "play_chat_id": play_chat_id,
            "play_chat_ref": play_chat_ref,
            "anchor_message_id": anchor_message_id,
            "dm_chat_id": dm_chat_id,
            "dm_message_id": dm_message_id,
            "balance_before": balance_before,
            "free_quest": free_quest,
            "notify_token": notify_token,
            "board_mid": 0,
            "variant": last_variant,
        }

    try:
        await handler(synthetic)
    except Exception as e:
        print(f"[ONBOARDING] Игра {game_key} упала у {user_id}: {e!r}")
        if game_key in SESSION_GAMES:
            _pending_session_tips.pop(tip_key, None)
        return

    # Сессионные (башня и т.п.): tip + личка — строго после конца партии.
    if game_key in SESSION_GAMES:
        asyncio.create_task(_watch_session_and_finish(user_id=user_id, notify_token=notify_token))
        return

    # Instant: handler = конец партии → tip сразу (любая onboarding-игра).
    try:
        tip_ok = await _send_onboarding_replay_tip(
            user_id=user_id,
            first_name=getattr(user, "first_name", None),
            play_chat_id=play_chat_id,
            play_chat_ref=play_chat_ref,
            reply_to_message_id=anchor_message_id,
            free_quest=free_quest,
            game_key=game_key,
            bet=bet,
            notify_token=notify_token,
            variant=last_variant,
        )
        if not tip_ok:
            await asyncio.sleep(0.25)
            await _send_onboarding_replay_tip(
                user_id=user_id,
                first_name=getattr(user, "first_name", None),
                play_chat_id=play_chat_id,
                play_chat_ref=play_chat_ref,
                reply_to_message_id=0,
                free_quest=free_quest,
                game_key=game_key,
                bet=bet,
                notify_token=notify_token,
                variant=last_variant,
            )
    except Exception as e:
        print(f"[ONBOARDING] replay tip {user_id}: {e!r}")

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


def _session_store_get(attr: str, user_id: int) -> Any:
    try:
        import main as main_mod
        store = getattr(main_mod, attr, None)
        if store is None:
            return None
        return store.get(user_id)
    except Exception:
        return None


def _session_board_mid(game_key: str, user_id: int) -> Optional[int]:
    attr = _SESSION_MSG_STORES.get(game_key)
    if not attr:
        return None
    mid = _session_store_get(attr, user_id)
    try:
        return int(mid) if mid else None
    except Exception:
        return None


def _session_is_finished(game_key: str, user_id: int, expected_mid: Optional[int]) -> bool:
    """True, когда активная доска снята или сессия помечена closed."""
    msg_attr = _SESSION_MSG_STORES.get(game_key)
    if not msg_attr:
        return False
    cur = _session_store_get(msg_attr, user_id)
    if cur is None:
        return True
    try:
        cur_mid = int(cur)
    except Exception:
        return True
    if expected_mid and cur_mid != int(expected_mid):
        # Другая партия того же типа — старую считаем завершённой.
        return True

    active_attr = _SESSION_ACTIVE_STORES.get(game_key)
    if not active_attr:
        return False
    st = _session_store_get(active_attr, user_id)
    if isinstance(st, dict) and st.get("closed"):
        return True
    return False


async def _emit_session_finished_once(
    *,
    user_id: int,
    notify_token: int,
    reply_message_id: Optional[int] = None,
) -> bool:
    """Один раз на запуск: tip в группе сразу, итог в личке фоном."""
    key = _pending_tip_key(user_id, notify_token)
    if key in _session_finish_sent:
        return False

    pending = _pending_session_tips.get(key)
    if not pending or int(pending.get("notify_token") or 0) != int(notify_token):
        return False

    _session_finish_sent[key] = True
    _pending_session_tips.pop(key, None)
    if len(_session_finish_sent) > 2000:
        _session_finish_sent.clear()

    game_key = str(pending.get("game_key") or "")
    bet = int(pending.get("bet") or 10)
    free_quest = bool(pending.get("free_quest"))
    play_chat_ref = pending.get("play_chat_ref")
    reply_to = (
        int(reply_message_id or 0)
        or int(pending.get("board_mid") or 0)
        or int(pending.get("anchor_message_id") or 0)
    )

    # Tip в группе — сразу после партии (для каждой onboarding-игры).
    # Не завязан на «живой» notify_token: tip нужен даже если в личке уже другая карточка.
    last_variant = str(pending.get("variant") or "").strip() or None
    try:
        u = pending.get("user")
        tip_ok = await _send_onboarding_replay_tip(
            user_id=user_id,
            first_name=getattr(u, "first_name", None) if u is not None else None,
            play_chat_id=int(pending["play_chat_id"]),
            play_chat_ref=play_chat_ref,
            reply_to_message_id=reply_to,
            free_quest=free_quest,
            game_key=game_key,
            bet=bet,
            notify_token=notify_token,
            variant=last_variant,
        )
        if not tip_ok:
            await asyncio.sleep(0.25)
            await _send_onboarding_replay_tip(
                user_id=user_id,
                first_name=getattr(u, "first_name", None) if u is not None else None,
                play_chat_id=int(pending["play_chat_id"]),
                play_chat_ref=play_chat_ref,
                reply_to_message_id=0,
                free_quest=free_quest,
                game_key=game_key,
                bet=bet,
                notify_token=notify_token,
                variant=last_variant,
            )
    except Exception as e:
        print(f"[ONBOARDING] session tip {user_id}: {e!r}")

    dm_chat_id = int(pending.get("dm_chat_id") or 0)
    dm_message_id = int(pending.get("dm_message_id") or 0)
    if not dm_chat_id or not dm_message_id:
        sess = _session_get(user_id)
        dm_chat_id = dm_chat_id or int(sess.get("dm_chat_id") or 0)
        dm_message_id = dm_message_id or int(sess.get("dm_message_id") or 0)
    balance_before = int(pending.get("balance_before") or 0)
    if not balance_before:
        balance_before = int(_session_get(user_id).get("balance_before") or 0)

    # Личку обновляем только если токен ещё актуален (не перетёрли новой карточкой).
    if dm_chat_id and dm_message_id and _notify_token_alive(user_id, notify_token):
        asyncio.create_task(_notify_after_game(
            user_id=user_id,
            game_key=game_key,
            bet=bet,
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id,
            balance_before=balance_before,
            free_quest=free_quest,
            notify_token=notify_token,
            play_chat_ref=play_chat_ref,
        ))
    elif not (dm_chat_id and dm_message_id):
        print(f"[ONBOARDING] session finish без dm для {user_id}/{game_key}")
    return True


async def _watch_session_and_finish(*, user_id: int, notify_token: int) -> None:
    """Ждёт конца сессионной партии → tip + обновление лички."""
    tip_key = _pending_tip_key(user_id, notify_token)
    pending = _pending_session_tips.get(tip_key)
    if not pending or int(pending.get("notify_token") or 0) != int(notify_token):
        return
    game_key = str(pending.get("game_key") or "")
    if game_key not in SESSION_GAMES:
        return

    # Доска появляется сразу после handler — без неё итог не шлём
    # (иначе «нет mid» ошибочно выглядит как конец партии).
    board_mid: Optional[int] = None
    for _ in range(40):
        pending = _pending_session_tips.get(tip_key)
        if not pending:
            return
        board_mid = _session_board_mid(game_key, user_id)
        if board_mid:
            pending["board_mid"] = int(board_mid)
            break
        await asyncio.sleep(0.08)
    if not board_mid:
        # Доску не увидели — не трогаем pending: notify из игры / fallback дошлют tip.
        print(f"[ONBOARDING] session board mid miss uid={user_id} game={game_key}")
        return

    deadline = time.monotonic() + _SESSION_TIP_WAIT
    while time.monotonic() < deadline:
        if tip_key not in _pending_session_tips:
            return
        if tip_key in _session_finish_sent:
            return
        if _session_is_finished(game_key, user_id, board_mid):
            # Короткая пауза: UI «Игра завершена» успеет отрисоваться.
            await asyncio.sleep(0.15)
            if not _session_is_finished(game_key, user_id, board_mid):
                await asyncio.sleep(0.35)
                continue
            reply_to = board_mid or int(pending.get("anchor_message_id") or 0)
            await _emit_session_finished_once(
                user_id=user_id,
                notify_token=notify_token,
                reply_message_id=reply_to,
            )
            return
        await asyncio.sleep(0.35)

    # Таймаут — pending оставляем: onboarding_notify / fallback ещё могут сработать.
    print(f"[ONBOARDING] session tip wait timeout uid={user_id} game={game_key}")


async def onboarding_notify_game_finished(
    user_id: int,
    *,
    message_id: Optional[int] = None,
    chat_id: Optional[int] = None,
) -> None:
    """Вызывать из игр в момент реального конца партии (башня / риск / плиты / …).

    Не блокирует колбэк игры: tip + личка уходят фоновой задачей.
    Если pending пропал (рестарт) — всё равно шлём tip из _ob_session.
    """
    uid = int(user_id)
    picked = _pick_pending_for_finish(uid, message_id=message_id)
    if picked:
        tip_key, pending = picked
        token = int(pending.get("notify_token") or tip_key[1] or 0)
        if token:
            if chat_id is not None:
                try:
                    want = int(pending.get("play_chat_id") or 0)
                    got = int(chat_id)
                    if want and got and want != got:
                        print(
                            f"[ONBOARDING] finish chat mismatch "
                            f"uid={uid} want={want} got={got} — tip всё равно"
                        )
                except Exception:
                    pass
            asyncio.create_task(_emit_session_finished_once(
                user_id=uid,
                notify_token=token,
                reply_message_id=message_id,
            ))
            return

    # Fallback: сессия онбординга ещё жива, pending уже съели / пропал.
    sess = _session_get(uid)
    game_key = str(sess.get("game_key") or "")
    if not game_key or game_key not in GAMES:
        return
    token = int(sess.get("notify_token") or 0) or int(time.time() * 1000)
    play_chat_id = int(sess.get("play_chat_id") or chat_id or 0)
    if not play_chat_id:
        return
    first_name = None
    try:
        first_name = await db.get_user_first_name(uid)
    except Exception:
        pass
    asyncio.create_task(_send_onboarding_replay_tip(
        user_id=uid,
        first_name=first_name,
        play_chat_id=play_chat_id,
        play_chat_ref=sess.get("play_chat_ref"),
        reply_to_message_id=int(message_id or sess.get("board_message_id") or 0),
        free_quest=bool(sess.get("free_quest")),
        game_key=game_key,
        bet=int(sess.get("bet") or 10),
        notify_token=token,
        variant=str(sess.get("last_variant") or "").strip() or None,
    ))
    # Личку тоже попробуем обновить, если есть dm ids.
    dm_chat_id = int(sess.get("dm_chat_id") or 0)
    dm_message_id = int(sess.get("dm_message_id") or 0)
    if dm_chat_id and dm_message_id and token and _notify_token_alive(uid, token):
        asyncio.create_task(_notify_after_game(
            user_id=uid,
            game_key=game_key,
            bet=int(sess.get("bet") or 10),
            dm_chat_id=dm_chat_id,
            dm_message_id=dm_message_id,
            balance_before=int(sess.get("balance_before") or 0),
            free_quest=bool(sess.get("free_quest")),
            notify_token=token,
            play_chat_ref=sess.get("play_chat_ref"),
        ))


async def _send_onboarding_replay_tip(
    *,
    user_id: int,
    first_name: Optional[str],
    play_chat_id: int,
    play_chat_ref: Optional[str],
    reply_to_message_id: int,
    free_quest: bool,
    game_key: str,
    bet: int,
    notify_token: int,
    variant: Optional[str] = None,
) -> bool:
    """Tip «Ещё шаг?» в группе после каждой onboarding-партии.

    Для любого игрока (новичок или нет). Один tip на токен запуска.
    """
    key = (int(user_id), int(notify_token or 0))
    if key[1] and key in _tip_sent_tokens:
        return False
    if key[1]:
        _tip_sent_tokens[key] = True
        if len(_tip_sent_tokens) > 3000:
            _tip_sent_tokens.clear()

    if play_chat_ref:
        venue = play_chat_ref
    elif int(play_chat_id) == CLUB_CHAT_ID and CLUB_USERNAME:
        venue = f"@{CLUB_USERNAME}"
    else:
        venue = "в группе клуба"
    if venue and not str(venue).startswith("@") and not str(venue).startswith("http"):
        if str(venue).replace("_", "").isalnum():
            venue = f"@{venue}"

    text = newbie_help_tip_text(
        mention=_mention_html(int(user_id), first_name),
        free_quest=free_quest,
        venue_label=str(venue),
        game_key=game_key,
        bet=bet,
        variant=variant,
    )
    sent = await _send_html_chat(
        int(play_chat_id),
        text,
        reply_to_message_id=int(reply_to_message_id or 0) or None,
    )
    if sent is None:
        print(
            f"[ONBOARDING] replay tip FAIL uid={user_id} game={game_key} "
            f"chat={play_chat_id} reply={reply_to_message_id}"
        )
        # Разрешаем повтор, если отправка не прошла.
        _tip_sent_tokens.pop(key, None)
        return False
    return True


async def _maybe_send_newbie_help_tip(
    *,
    user: User,
    play_chat_id: int,
    play_chat_ref: Optional[str],
    anchor_message_id: int,
    free_quest: bool,
    game_key: str = "",
    bet: int = 10,
    notify_token: int = 0,
) -> None:
    """Совместимость: tip после onboarding-партии (без гейта newbie)."""
    await _send_onboarding_replay_tip(
        user_id=int(user.id),
        first_name=getattr(user, "first_name", None),
        play_chat_id=play_chat_id,
        play_chat_ref=play_chat_ref,
        reply_to_message_id=anchor_message_id,
        free_quest=free_quest,
        game_key=game_key,
        bet=bet,
        notify_token=notify_token or int(time.time() * 1000),
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
    # Короткая пауза: БД успевает дописать баланс, UI не тормозит.
    await asyncio.sleep(0.35)
    if not _notify_token_alive(user_id, notify_token):
        return

    wallet = await _wallet(user_id)
    game = GAMES.get(game_key) or {}
    quest_mode = free_quest or wallet.free_quest
    last_variant = str(_session_get(user_id).get("last_variant") or "").strip() or None
    text = _after_game_text(
        game, bet, wallet,
        balance_before=balance_before,
        free_quest=quest_mode,
        venue_label=_venue_label(wallet, play_chat_ref),
        variant=last_variant,
    )
    markup = _after_game_markup(wallet, free_quest=quest_mode)

    if not _notify_token_alive(user_id, notify_token):
        return

    variants: List[Tuple[str, InlineKeyboardMarkup]] = [
        (text, markup),
        (text, _markup_without_icons(markup)),
        (_html_plain(text), _markup_without_icons(markup)),
    ]
    last_err: Optional[BaseException] = None
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
            return
        except Exception as e:
            last_err = e
            if "message is not modified" in str(e).lower():
                return

    for body, kb in variants:
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
            return
        except Exception as e:
            last_err = e

    print(f"[ONBOARDING] Не удалось отправить итог {user_id}: {last_err!r}")


def _delta_line(before: int, after: int) -> str:
    delta = after - before
    if delta > 0:
        return f"{E_RESULT} Итог : +{delta} кут"
    if delta < 0:
        return f"{E_RESULT} Итог : {delta} кут"
    return f"{E_RESULT} Итог : без изменений"


def _after_game_text(
    game: Dict[str, Any],
    bet: int,
    wallet: Wallet,
    *,
    balance_before: int,
    free_quest: bool,
    venue_label: str = "",
    variant: Optional[str] = None,
) -> str:
    title = game.get("title") or "Игра"
    emoji = game.get("emoji") or E_GAME
    where = venue_label or _venue_label(wallet)
    # Для закрытого задания delta по виртуальному балансу уже не сравнить -
    # показываем только если задание ещё активно.
    show_delta = wallet.free_quest
    delta = _delta_line(balance_before, wallet.amount) if show_delta else ""
    result_card = _bq(
        f"{emoji} {title} · ставка {bet} кут",
        delta,
        f"{E_PLANE} Площадка : {where}",
    ) if delta else _bq(
        f"{emoji} {title} · ставка {bet} кут",
        f"{E_PLANE} Площадка : {where}",
    )

    # Tip с командой и «хелп игры» — всем, не только новичкам.
    help_tip = f"\n{_newbie_replay_tip(game, bet, variant=variant)}\n"

    if free_quest and wallet.free_quest:
        reached = wallet.target > 0 and wallet.amount >= wallet.target
        if reached:
            next_steps = _bq(
                f"{E_CUP} Награда уже на балансе или скоро придёт",
                f"{E_GAME} Дальше - задания, ферма и топ клуба",
                f"{E_STAR} Вы уже в игре - выбирайте следующий ход",
            )
            return (
                f"{_path(2)}\n\n"
                f"{E_CUP} <b>Цель достигнута</b>\n\n"
                f"{result_card}\n\n"
                f"{_quest_stats(wallet)}\n\n"
                f"{next_steps}\n\n"
                f"{_hint('Можно играть дальше или открыть меню')}"
            )
        if wallet.amount <= 0:
            lose = _bq(
                f"{E_OK} Это не конец - так бывает",
                f"{E_BOLT} Свои куты целы",
                f"{E_GIFT} Возьмите другое задание или бонус",
                f"{E_STAR} Первый вход в клуб - за счёт площадки",
            )
            return (
                f"{_path(2)}\n\n"
                f"{E_FIRE} <b>Задание проиграно - и это нормально</b>\n\n"
                f"{result_card}\n\n"
                f"{_quest_stats(wallet)}\n\n"
                f"{lose}\n\n"
                f"{_hint('Нажмите «Другое задание»')}"
            )
        return (
            f"{_path(2)}\n\n"
            f"{E_NEXT} <b>Партия сыграна</b>\n\n"
            f"{result_card}\n\n"
            f"{_quest_stats(wallet)}\n"
            f"{E_BOLT} <b>Свои куты не тратятся.</b>\n"
            f"{help_tip}\n"
            f"{_hint('Играть ещё · другая игра · или закончить задание')}"
        )

    if free_quest and not wallet.free_quest:
        # Задание закрылось во время/после партии.
        closed = _bq(
            f"{emoji} {title} · ставка {bet} кут",
            f"{E_COIN} Баланс : {wallet.amount} кут",
        )
        if wallet.amount >= _cheapest_bet():
            next_steps = _bq(
                f"{E_CUP} Задание закрыто - вы в клубе",
                f"{E_GAME} Можно играть самому или взять другое задание",
                f"{E_STAR} Дальше: игры, ферма, топ",
            )
            return (
                f"{_path(2)}\n\n"
                f"{E_CUP} <b>Задание закрыто</b>\n\n"
                f"{closed}\n"
                f"{E_BOLT} <b>Свои куты целы.</b>\n\n"
                f"{next_steps}\n\n"
                f"{_hint('Играть сам или взять другое задание')}"
            )
        lose = _bq(
            f"{E_OK} Проигрыш - часть игры",
            f"{E_BOLT} Свои куты целы",
            f"{E_GIFT} Возьмите другое задание или бонус",
        )
        return (
            f"{_path(2)}\n\n"
            f"{E_FIRE} <b>Задание закрыто</b>\n\n"
            f"{closed}\n\n"
            f"{lose}\n\n"
            f"{_hint('Возьмите новое задание')}"
        )

    played = _bq(
        f"{emoji} {title} · ставка {bet} кут",
        _delta_line(balance_before, wallet.amount),
        f"{E_COIN} Баланс : {wallet.amount} кут",
        f"{E_PLANE} Площадка : {where}",
    )
    return (
        f"{_path(2)}\n\n"
        f"{E_NEXT} <b>Партия сыграна</b>\n\n"
        f"{played}\n"
        f"{help_tip}\n"
        f"{_hint('Выберите следующую игру')}"
    )


def _after_game_markup(wallet: Wallet, *, free_quest: bool) -> InlineKeyboardMarkup:
    if wallet.free_quest and wallet.amount > 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Играть ещё", data="ob_next", icon="5348423147647414077", style="success")],
            [_btn("Другая игра", data="ob_games", icon="5425094988260188065", style="primary")],
            [_btn("Закончить задание", data="ob_finish", icon=ICON_FINISH, style="danger")],
            [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
        ])
    if free_quest and not wallet.free_quest:
        # Задание закрылось: цель взята или виртуальный баланс сгорел.
        if wallet.amount >= _cheapest_bet():
            return InlineKeyboardMarkup(inline_keyboard=[
                [_btn("Играть одному", data="ob_games", icon="5425094988260188065", style="primary")],
                [_btn("Другое задание", data="ob_earn", icon="5424939755257208778")],
                [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
            ])
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon="5345878375229568510", style="success")],
            [_btn("Получить куты", data="ob_earn", icon="5415777271459891913")],
            [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
        ])
    if free_quest and wallet.free_quest and wallet.amount <= 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon="5345878375229568510", style="success")],
            [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Играть ещё", data="ob_games", icon="5348423147647414077", style="success")],
        [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
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
    venue_label: str = "",
) -> str:
    """Алиас: шаг 2 использует ту же карточку, что и шаг 1."""
    return _game_card_text(
        game, bet, wallet,
        game_key=game_key,
        venue_label=venue_label,
    )


def _ready_markup(play_url: str, *, free_quest: bool = False) -> InlineKeyboardMarkup:
    """Кнопки шага 2: ссылка на партию в группе + навигация."""
    rows = [
        [_btn("Открыть мою игру", url=play_url, icon="5317000922096769303", style="success")],
    ]
    if free_quest:
        rows.append([_btn("Играть ещё", data="ob_next", icon="5348423147647414077", style="success")])
        rows.append([_btn("Закончить задание", data="ob_finish", icon=ICON_FINISH, style="danger")])
        rows.append([_btn("Меню", data="ob_menu", icon=ICON_MENU)])
    else:
        rows.append([_btn("Другая игра", data="ob_games", icon=ICON_PLAY, style="primary")])
        rows.append([_btn("Меню", data="ob_menu", icon=ICON_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _join_text(game: Dict[str, Any], venue_url: str = CLUB_URL) -> str:
    """Вход в группу. Правь текст прямо здесь."""
    if venue_url != CLUB_URL:
        where = "группу задания"
    elif CLUB_USERNAME:
        where = f"@{CLUB_USERNAME}"
    else:
        where = "группу клуба"
    return (
        f"{game['emoji']} <b>{game['title']}</b>\n\n"
        f"<blockquote>"
        f"<b>Зайдите в {where}</b>\n"
        f"<b>Потом нажмите кнопку ниже</b>"
        f"</blockquote>"
    )


def _join_markup(venue_url: str = CLUB_URL) -> InlineKeyboardMarkup:
    if venue_url != CLUB_URL:
        enter = "Зайти в группу"
    elif CLUB_USERNAME:
        enter = f"Зайти в @{CLUB_USERNAME}"
    else:
        enter = "Зайти в группу"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(enter, url=venue_url, icon=ICON_GROUP, style="success")],
        [_btn("Открыть игру", data="ob_joined", icon="5251252690851225502", style="success")],
    ])

def _other_chat_text(wallet: Wallet) -> str:
    where = str(wallet.chat_ref or "").strip() or "своей группе"
    return (
        f"{E_TARGET} <b>Задание в другой группе</b>\n\n"
        f"{_bq(f'Ставки идут в зачёт только в {where}.')}"
    )


def _other_chat_markup(wallet: Wallet) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    ref = str(wallet.chat_ref or "").strip().lstrip("@")
    if ref and ref.replace("_", "").isalnum():
        rows.append([_btn("Открыть группу", url=f"https://t.me/{ref}", icon="5454039464357682228", style="success")])
    rows.append([_btn("Моё задание", data="qst:gc_my", icon=ICON_TASKS)])
    rows.append([_btn("Назад", data="ob_start", icon=ICON_CLOSE)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _no_funds_text(game: Dict[str, Any], wallet: Wallet) -> str:
    need = int(game["min"])
    if wallet.free_quest:
        if wallet.amount <= 0:
            card = _bq(
                f"{game['emoji']} {game['title']} просит {need} кут",
                f"{E_COIN} На задании : 0 кут",
            )
            return (
                f"{E_FIRE} <b>Баланс задания закончился</b>\n\n"
                f"{card}\n"
                f"{_bq(f'{E_OK} Это не конец - так бывает', f'{E_BOLT} Свои куты целы', f'{E_GIFT} Возьмите другое задание или бонус')}\n\n"
                f"{_hint('Нажмите «Другое задание»')}"
            )
        card = _bq(
            f"{game['emoji']} {game['title']} : от {need} кут",
            f"На задании : {wallet.amount} кут",
        )
        return (
            f"{E_COIN} <b>На эту игру не хватает</b>\n\n"
            f"{card}\n"
            f"{E_STAR} <b>Выберите игру полегче - прогресс сохранится.</b>\n"
            f"{E_BOLT} <b>Свои куты не тратятся.</b>\n\n"
            f"{_hint('Нажмите «Другая игра»')}"
        )
    card = _bq(
        f"{game['emoji']} {game['title']} : от {need} кут",
        f"Баланс : {wallet.amount} кут",
    )
    return (
        f"{E_COIN} <b>Не хватает на ставку</b>\n\n"
        f"{card}\n"
        f"{E_GIFT} <b>Бесплатное задание даёт свой баланс для игры.</b>\n\n"
        f"{_hint('Нажмите «Получить куты»')}"
    )


def _no_funds_markup(wallet: Wallet) -> InlineKeyboardMarkup:
    if wallet.free_quest and wallet.amount > 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другая игра", data="ob_games", icon=ICON_PLAY, style="success")],
            [_btn("Закончить задание", data="ob_finish", icon=ICON_FINISH, style="danger")],
            [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
        ])
    if wallet.free_quest:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_btn("Другое задание", data="ob_earn", icon=ICON_GIFT, style="success")],
            [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Получить куты", data="ob_earn", icon=ICON_GIFT, style="success")],
        [_btn("Ферма", web_app=_farm_url(), icon=ICON_FARM)],
        [_btn("Другая игра", data="ob_games", icon=ICON_PLAY)],
    ])


def _bet_limit_text(game: Dict[str, Any], wallet: Wallet) -> str:
    card = _bq(
        f"{game['emoji']} {game['title']} : от {int(game['min'])} кут",
        f"Лимит задания : до {wallet.max_bet} кут",
    )
    return (
        f"{E_SAFE} <b>Лимит ставки задания</b>\n\n"
        f"{card}\n"
        f"{E_STAR} <b>Эта игра не подходит под лимит - возьмите другую.</b>\n"
        f"{E_BOLT} <b>Свои куты не тратятся.</b>\n\n"
        f"{_hint('Нажмите «Другая игра»')}"
    )


def _bet_limit_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Другая игра", data="ob_games", icon=ICON_PLAY, style="primary")],
        [_btn("Меню", data="ob_menu", icon=ICON_MENU)],
    ])


def _empty_treasury_text() -> str:
    return (
        f"{E_LEAF} <b>Клуб пополняет казну</b>\n\n"
        f"{_bq('Ставки на паузе.', 'На ферме куты растут без ставок.')}"
    )


def _empty_treasury_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Ферма", web_app=_farm_url(), icon=ICON_FARM)],
        [_btn("Попробовать снова", data="ob_retry", icon=ICON_PLAY)],
    ])


def _failed_text() -> str:
    return (
        f"{E_PLANE} <b>Игра не открылась.</b>\n\n"
        f"{_bq('Попробуйте ещё раз - клуб уже ждёт.')}"
    )


def _failed_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Попробовать снова", data="ob_retry", icon=ICON_PLAY)],
        [_btn("Другая игра", data="ob_games", icon=ICON_PLAY, style="primary")],
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
    """Упоминание игрока в HTML — всегда жирным (ссылка внутри <b>)."""
    raw = (first_name or "Игрок")
    for ch in "<>&":
        raw = raw.replace(ch, "")
    safe = raw[:32] or "Игрок"
    return f'<b><a href="tg://user?id={int(user_id)}">{safe}</a></b>'


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


def _venue_label(wallet: Wallet, venue_ref: Optional[str] = None) -> str:
    """Короткое имя площадки для текстов."""
    if wallet.free_quest and wallet.chat_id and int(wallet.chat_id) != CLUB_CHAT_ID:
        ref = str(venue_ref or wallet.chat_ref or "").strip()
        if ref:
            return ref if ref.startswith("@") or ref.startswith("http") else f"@{ref.lstrip('@')}"
        return "в группе задания"
    if CLUB_USERNAME:
        return f"@{CLUB_USERNAME}"
    return "в группе клуба"


def _play_venue(wallet: Wallet) -> Tuple[int, str, Optional[str]]:
    """Куда запускать игру: чат задания или клуб.

    Если в бесплатном задании указана группа - играем там.
    Если группы нет - дефолтный клуб (test/prod через ONBOARDING_CLUB).

    Returns: (chat_id, open_url, chat_ref)
    """
    if wallet.free_quest and wallet.chat_id:
        ref = str(wallet.chat_ref or "").strip()
        return wallet.chat_id, _chat_open_url(wallet.chat_id, ref), ref or None
    club_ref = f"@{CLUB_USERNAME}" if CLUB_USERNAME else None
    return CLUB_CHAT_ID, CLUB_URL, club_ref


async def _send_html_chat(
    chat_id: int,
    text: str,
    *,
    reply_to_message_id: Optional[int] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Optional[Message]:
    """Отправка HTML в чат с откатом без premium emoji и без reply."""
    variants = (text, _html_plain(text))
    last_err: Optional[BaseException] = None
    reply_id = reply_to_message_id
    for body in variants:
        try:
            return await bot1.send_message(
                chat_id=chat_id,
                text=body,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_to_message_id=reply_id,
            )
        except Exception as e:
            last_err = e
            err = str(e).lower()
            # Удалённый якорь / thread — пробуем без reply, не теряем tip.
            if reply_id and (
                "message to be replied not found" in err
                or "replied message not found" in err
                or "reply message not found" in err
                or "thread not found" in err
            ):
                reply_id = None
                try:
                    return await bot1.send_message(
                        chat_id=chat_id,
                        text=body,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception as e2:
                    last_err = e2
                    continue
    print(f"[ONBOARDING] send_html_chat({chat_id}): {last_err!r}")
    return None


def _example_with_bet(example: str, bet: int) -> str:
    """Подставляет актуальную ставку в пример команды (первое число)."""
    parts = str(example or "").split()
    if not parts:
        return str(example or "")
    bet_s = str(max(1, int(bet or 10)))
    for i, p in enumerate(parts):
        if p.isdigit():
            parts[i] = bet_s
            break
    return " ".join(parts)


def _variant_to_cmd_arg(variant: str) -> str:
    """Value кнопки → аргумент команды для игры.

    Диапазоны рулетки:
      «1-6» / «1–6» / «1 6»  → «1 6»   → рулетка 10 1 6
      «6-12» / «6–12» / «6 12» → «6 12» → рулетка 10 6 12
    Остальное (цвет, чёт, число) — как есть.
    """
    v = str(variant or "").strip()
    if not v:
        return ""
    # Унифицируем тире/дефисы и схлопываем пробелы.
    compact = " ".join(v.replace("–", "-").replace("—", "-").split())
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", compact)
    if m:
        return f"{int(m.group(1))} {int(m.group(2))}"
    parts = compact.split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0])} {int(parts[1])}"
    return compact


def _allowed_variant_values(game: Dict[str, Any]) -> Set[str]:
    """Допустимые value с доски + нормализованные формы диапазонов."""
    allowed: Set[str] = set()
    for _, v in (game.get("variants") or ()):
        raw = str(v or "").strip()
        if not raw:
            continue
        allowed.add(raw)
        norm = _variant_to_cmd_arg(raw)
        if norm:
            allowed.add(norm)
        # Старые доски могли слать «1 6» / «7 12».
        dash = raw.replace(" ", "-")
        allowed.add(dash)
    return allowed


def _cmd_from_variant(game: Dict[str, Any], bet: int, variant: Optional[str]) -> Optional[str]:
    """Собирает реальную команду из cmd + variant (в т.ч. диапазон «1 6»)."""
    v = _variant_to_cmd_arg(str(variant or "").strip())
    if not v:
        return None
    tmpl = str(game.get("cmd") or "").strip()
    if not tmpl:
        return None
    try:
        return " ".join(tmpl.format(bet=int(bet), v=v).split())
    except Exception:
        return None


def _norm_tip_cmd(cmd: str) -> str:
    """Нормализация команды для сравнения дублей в tip."""
    return " ".join(str(cmd or "").lower().replace("ё", "е").split())


def _cmd_family(cmd: str) -> str:
    """Грубый тип ставки для tip: color / parity / number / range / other."""
    parts = _norm_tip_cmd(cmd).split()
    if len(parts) >= 4 and parts[-2].isdigit() and parts[-1].isdigit():
        return "range"
    if not parts:
        return "other"
    # «красное/черное», «четное/нечетное» — один принцип, без дублей.
    tokens = [t.strip() for t in parts[-1].split("/") if t.strip()]
    color = {"красное", "красный", "черное", "черный", "red", "black"}
    parity = {"чет", "четное", "четный", "нечет", "нечетное", "нечетный", "пар"}
    if any(t in color for t in tokens):
        return "color"
    if any(t in parity for t in tokens):
        return "parity"
    if parts[-1].isdigit():
        return "number"
    return "other"


def _dedupe_tip_examples(examples: List[str]) -> List[str]:
    """Убирает повторные строки tip, сохраняя порядок."""
    seen: Set[str] = set()
    out: List[str] = []
    for ex in examples:
        text = str(ex or "").strip()
        if not text:
            continue
        key = _norm_tip_cmd(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _tip_command_examples(
    game: Dict[str, Any],
    bet: int,
    *,
    variant: Optional[str] = None,
) -> List[str]:
    """Примеры команд для tip: принципы игры без дублей.

    Для рулетки в help_examples уже стоят обучающие строки
    («красное/черное», «четное/нечётное», число, диапазоны).
    Сыгранный вариант поднимаем первым; точные повторы вычищаем.
    """
    bet_i = max(1, int(bet or 10))
    raw = [str(x).strip() for x in (game.get("help_examples") or ()) if str(x).strip()]
    examples = _dedupe_tip_examples([_example_with_bet(x, bet_i) for x in raw])
    primary = _cmd_from_variant(game, bet_i, variant)
    if not examples:
        title = _plain_emoji(str(game.get("title") or "игра")).lower() or "игра"
        examples = [primary or f"{title} {bet_i}"]
    elif primary:
        fam = _cmd_family(primary)
        primary_n = _norm_tip_cmd(primary)
        if fam in ("number", "range"):
            # Сыгранное — первым. Другой диапазон (1 6 vs 6 12) оставляем.
            # Точный дубль primary и лишние number-слоты убираем.
            kept: List[str] = []
            for ex in examples:
                if _norm_tip_cmd(ex) == primary_n:
                    continue
                if fam == "number" and _cmd_family(ex) == "number":
                    continue
                kept.append(ex)
            examples = [primary] + kept
        else:
            # Цвет/чёт — обучающая форма со слэшем, primary не дублируем.
            hit = next((i for i, ex in enumerate(examples) if _cmd_family(ex) == fam), None)
            if hit is not None:
                chosen = examples[hit]
                examples = [chosen] + [x for j, x in enumerate(examples) if j != hit]
    examples = _dedupe_tip_examples(examples)
    if game.get("tip_show_examples"):
        # Рулетка: цвет · чёт · число · 1–6 · 6–12
        return examples[:5]
    return examples[:1]


def _newbie_replay_tip(
    game: Dict[str, Any],
    bet: int,
    *,
    variant: Optional[str] = None,
) -> str:
    """Хук + пример(ы) команды в blockquote + список игр. Весь текст жирный."""
    title = game.get("title") or "Игра"
    tip_lead = game.get("tip_lead") or f"{E_FIRE} Ещё раунд?"
    plain_lead = _plain_emoji(str(tip_lead))
    if "одной строкой" in plain_lead or "уже в нашей группе" in plain_lead:
        tip_lead = f"{E_FIRE} Ещё раунд в «{title}»?"
    examples = _tip_command_examples(game, bet, variant=variant)
    codes = "\n".join(f"<code>{ex}</code>" for ex in examples)
    # Premium <tg-emoji> снаружи <b> — иначе клиент Telegram часто рвёт разметку.
    return (
        f"{_bold_html_line(str(tip_lead))}\n"
        f"<blockquote><b>{codes}</b></blockquote>\n"
        f"{_bold_html_line(f'{E_GAME} Все игры → <code>хелп игры</code>')}"
    )


def newbie_help_tip_text(
    *,
    mention: str,
    free_quest: bool,
    venue_label: str,
    game_key: str = "",
    bet: int = 10,
    variant: Optional[str] = None,
) -> str:
    """Короткая подсказка в группе после партии — всем игрокам.

    Формат: имя → хук → команда-пример → список игр.
    """
    game = GAMES.get(game_key) or {}
    emoji = game.get("emoji") or E_GAME
    body = (
        f"{emoji} {mention}\n\n"
        f"{_newbie_replay_tip(game, bet, variant=variant)}"
    )
    if free_quest:
        body += (
            f"\n"
            f"<b>{E_GIFT} Ставка с задания · {venue_label}</b>"
        )
    return body


def newbie_quest_failed_text(*, mention: str) -> str:
    """Провал задания. Правь текст прямо здесь."""
    # mention уже приходит жирным из _mention_html.
    return (
        f"{E_FIRE} {mention}\n\n"
        f"<b>Задание закрыто</b>\n\n"
        f"<blockquote>"
        f"<b>Свои куты целы</b>\n"
        f"<b>Можно взять другое</b>"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id='5231102735817918643'>👇</tg-emoji> "
        f"<b>Откройте бота</b>"
    )

def newbie_quest_failed_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Взять другое задание", url=BOT_URL, icon=ICON_GIFT, style="success")],
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


def _markup_without_icons(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Fallback без icon_custom_emoji_id.

    Для меню игр возвращаем unicode в text, чтобы кнопка не осталась голой.
    """
    rows: List[List[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard or []:
        new_row: List[InlineKeyboardButton] = []
        for btn in row:
            text = btn.text or "·"
            data = btn.callback_data
            if data and str(data).startswith("ob_game:"):
                key = str(data).split(":", 1)[1]
                game = GAMES.get(key)
                if game:
                    text = f"{_plain_emoji(game['emoji'])} {game['title']}"
            kwargs: Dict[str, Any] = {"text": text}
            if data is not None:
                kwargs["callback_data"] = data
            elif btn.url:
                kwargs["url"] = btn.url
            elif btn.web_app:
                kwargs["web_app"] = btn.web_app
            style = getattr(btn, "style", None)
            if style:
                kwargs["style"] = style
            try:
                new_row.append(InlineKeyboardButton(**kwargs))
            except TypeError:
                kwargs.pop("style", None)
                new_row.append(InlineKeyboardButton(**kwargs))
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _swap_markup(call: CallbackQuery, markup: InlineKeyboardMarkup) -> bool:
    """Обновляет только кнопки текущего сообщения — без нового текста и без дубля.

    True, если кнопки на месте (в т.ч. «message is not modified»).
    """
    if call.message is None:
        return False
    variants = (
        markup,
        _markup_without_icons(markup),
    )
    last_err: Optional[BaseException] = None
    for kb in variants:
        try:
            await call.message.edit_reply_markup(reply_markup=kb)
            return True
        except Exception as e:
            last_err = e
            if "message is not modified" in str(e).lower():
                return True
    print(f"[ONBOARDING] Не удалось обновить кнопки: {last_err!r}")
    return False


async def _swap(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Меняет экран на месте. При DOCUMENT_INVALID откатывает эмодзи/иконки."""
    variants: List[Tuple[str, InlineKeyboardMarkup]] = [
        (text, markup),
        (text, _markup_without_icons(markup)),
        (_html_plain(text), _markup_without_icons(markup)),
    ]
    last_err: Optional[BaseException] = None

    for body, kb in variants:
        try:
            await call.message.edit_text(
                body, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        except Exception as e:
            last_err = e
            if "message is not modified" in str(e).lower():
                # Текст тот же — пробуем хотя бы обновить кнопки, не шлём новое сообщение.
                await _swap_markup(call, markup)
                return

    for body, kb in variants:
        try:
            await call.message.answer(
                body, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        except Exception as e:
            last_err = e

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
