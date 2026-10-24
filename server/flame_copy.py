# -*- coding: utf-8 -*-
"""Огонёк — все тексты, которые видит человек.

Как править
-----------
Этот файл — единственное место со словами бота по огоньку.
У каждой константы в комментарии: ЧТО это, ГДЕ видно, КАК выглядит.
Слоты в фигурных скобках ({days}, {name}…) бот подставляет сам — их не удаляйте.
После правки этого файла перезапустите бота.

Где остальное (не тексты)
- Вкладка панели «Огонёк»: норма, награды, статусы, цены возврата.
- server/flame_engine.py: логика серии, полночь, выдача наград.
"""
from __future__ import annotations

import html
import re

# ---------------------------------------------------------------------------
# Общие эмодзи огонька
# ---------------------------------------------------------------------------
# EMOJI — главный значок огонька.
# Где: заголовок справки, личка при продлении, объявление в группах, возврат, профит.
EMOJI = "5355118129783553944"
# STATUS_EMOJI — значок рядом со статусом в профиле, если у статуса нет своего.
# Где: строка профиля «Статус · огонёк N дней».
STATUS_EMOJI = "5355118129783553944"

# ---------------------------------------------------------------------------
# Статусы в профиле (готовые линейки для вкладки «Огонёк → Статусы»)
# ---------------------------------------------------------------------------
# STATUS_DAYS — с какого дня серии включается каждый статус по порядку.
# Где: только подсказки панели и готовые наборы. Живые статусы хранятся в базе
#      и правятся во вкладке «Статусы».
STATUS_DAYS = (2, 3, 5, 10, 20, 25, 30, 40, 50, 100, 365)

# STATUS_SETS — три готовых набора названий.
# Где: кнопки «Пламя / Серия / Легенда» во вкладке «Статусы».
# Как: нажатие подставляет дни + названия в список; человек видит название
#      в профиле, топе и блоке «Статус в профиле» в «хелп огонёк».
# titles идут строго в том же порядке, что и STATUS_DAYS.
STATUS_SETS = (
    {
        "id": "flame",
        "label": "Пламя",  # подпись кнопки в панели
        "hint": "От искры к вечному огню — самый «огненный» тон",  # подсказка под кнопкой
        "titles": (
            "Искра",           # с 2 дня
            "Тлеющий",         # с 3
            "Живой огонь",     # с 5
            "Негасимый",       # с 10
            "Яркое пламя",     # с 20
            "Горящий",         # с 25
            "Неугасимый",      # с 30
            "Костёр",          # с 40
            "Факел",           # с 50
            "Легенда огня",    # с 100
            "Вечный огонь",    # с 365
        ),
    },
    {
        "id": "series",
        "label": "Серия",
        "hint": "Про длинную серию: держит, тянет, не бросает",
        "titles": (
            "Первый день",
            "Держит искру",
            "Серия жива",
            "Не бросил",
            "Тянет дальше",
            "Жаркая серия",
            "Месяц с огоньком",
            "Сорок дней",
            "Полсотни",
            "Сотня дней",
            "Год без паузы",
        ),
    },
    {
        "id": "legend",
        "label": "Легенда",
        "hint": "Престиж и FOMO: хочется так же в топе",
        "titles": (
            "Новичок огня",
            "На пути",
            "В игре",
            "Заметный",
            "Сильный",
            "Редкий",
            "Элита огня",
            "Мастер серии",
            "Хранитель",
            "Легенда",
            "Миф проекта",
        ),
    },
)


def status_presets() -> list[dict]:
    """Наборы статусов для панели. День берётся из STATUS_DAYS."""
    days = [max(1, int(day)) for day in STATUS_DAYS]
    out = []
    for pack in STATUS_SETS:
        names = list(pack.get("titles") or ())
        titles = []
        for index, day in enumerate(days):
            if index >= len(names):
                break
            name = " ".join(str(names[index] or "").split())
            if not name:
                continue
            titles.append({
                "from_day": day,
                "title": name[:60],
                "emoji_id": STATUS_EMOJI,
            })
        if not titles:
            continue
        out.append({
            "id": str(pack.get("id") or "set"),
            "label": str(pack.get("label") or "Набор"),
            "hint": str(pack.get("hint") or ""),
            "titles": titles,
        })
    return out


def emoji(eid: str, fallback: str = "⚫️") -> str:
    return f"<tg-emoji emoji-id='{eid}'>{fallback}</tg-emoji>"


# ---------------------------------------------------------------------------
# Карточка дня в справке «хелп огонёк» (блок «Награды за дни»)
# ---------------------------------------------------------------------------
# Где: ответ на «хелп огонёк» / «что такое огонёк».
# Как: над цитатой только срок «🌙 40 дней». Вся награда этого дня — одна цитата:
#      куты и бонусы строкой «⚡️ Куты — 10 кут», каждый предмет со своей строки.
#      Слоты: {mark} {days} {body} {face} {title} {gifts} {words}.

# Значок слева от срока. Первое число — «с такого дня включительно».
REWARD_DAY_MARKS = (
    (365, "🏆"),  # от 365 дней
    (90, "👑"),   # от 90
    (30, "🌙"),   # от 30
    (14, "💎"),   # от 14
    (7, "🔥"),    # от 7
    (0, "✨"),    # всё раньше
)
# Порядок и подписи групп внутри одного дня. kind — из базы наград.
REWARD_GROUPS = (
    ("bonus", "🎁", "Бонус"),       # обычный бесплатный бонус
    ("bonus_x2", "✨", "Бонус ×2"), # бонус с удвоением
    ("kuty", "⚡️", "Куты"),         # куты с техгрупп
    ("item", "📦", "Предметы"),     # предметы из каталога
)
# Если у предмета в каталоге нет эмодзи — ставим это.
REWARD_ITEM_FALLBACK = "🎁"
# Между двумя подарками одной группы (например два предмета).
REWARD_GIFT_GAP = " · "
# Строка над цитатой дня. {mark} значок, {days} «40 дней».
# Как выглядит: «🌙 40 дней».
REWARD_DAY_HEAD = "{mark} <b>{days}</b>"
# Одна цитата на все подарки дня. {body} строки через перевод строки.
REWARD_QUOTE = "<blockquote>{body}</blockquote>"
# Куты. {face} значок, {title} «Куты», {gifts} «10 кут».
# Бонус сюда не подставляется: «Бонус — бесплатный бонус» звучит дважды.
REWARD_GROUP = "{face} {title} — {gifts}"
# Бонус и бонус ×2 одной ясной строкой. {face} значок, {words} «Бесплатный бонус».
REWARD_PLAIN = "{face} {words}"
# Один бонус / куты. {words} уже готовая подпись, например «10 кут».
REWARD_GIFT = "{words}"
# Один предмет — отдельная цитата. {face} эмодзи предмета, {words} имя.
REWARD_ITEM = "{face} {words}"


def _slots(template: str, **slots: str) -> str:
    def swap(match):
        return slots.get(match.group(1), match.group(0))

    return re.sub(r"\{([a-z_]+)\}", swap, template)


def reward_mark(day: int) -> str:
    n = int(day or 0)
    for start, face in REWARD_DAY_MARKS:
        if n >= int(start):
            return str(face)
    return "✨"


def reward_face(kind: str, stored: str = "") -> str:
    face = str(stored or "").strip()
    if face:
        return face
    if kind == "item":
        return REWARD_ITEM_FALLBACK
    for key, mark, _title in REWARD_GROUPS:
        if key == kind:
            return str(mark)
    return "🎁"


def _coded_face(face: str) -> str:
    raw = str(face or REWARD_ITEM_FALLBACK).strip() or REWARD_ITEM_FALLBACK
    if raw.startswith("<tg-emoji") or raw.startswith("<code>"):
        return raw
    return html.escape(raw, quote=False)


def reward_day_card(mark: str, label: str, gifts: list[tuple[str, str, str]]) -> str:
    """Один день: бонус, бонус ×2, куты и предметы — разными строками."""
    packed: dict[str, list[tuple[str, str]]] = {}
    order = []
    for kind, face, words in gifts or []:
        text = " ".join(str(words or "").split())
        if not text:
            continue
        key = str(kind or "item")
        if key not in packed:
            order.append(key)
            packed[key] = []
        packed[key].append((str(face or ""), text))
    known = [key for key, _face, _title in REWARD_GROUPS]
    sequence = [key for key in known if key in packed]
    sequence += [key for key in order if key not in sequence]
    titles = {key: title for key, _face, title in REWARD_GROUPS}
    icons = {key: face for key, face, _title in REWARD_GROUPS}
    lines = []
    for key in sequence:
        if key == "item":
            for face, text in packed[key]:
                safe = html.escape(text, quote=False)
                lines.append(_slots(REWARD_ITEM, face=_coded_face(face), words=safe))
            continue
        if key in {"bonus", "bonus_x2"}:
            words = " · ".join(
                _plain_reward(text) for _face, text in packed[key] if text
            )
            icon = html.escape(str(icons.get(key) or "🎁"), quote=False)
            lines.append(_slots(REWARD_PLAIN, face=icon, words=html.escape(words, quote=False)))
            continue
        bits = []
        for _face, text in packed[key]:
            bits.append(_slots(REWARD_GIFT, words=html.escape(text, quote=False)))
        lines.append(_slots(
            REWARD_GROUP,
            face=html.escape(str(icons.get(key) or "🎁"), quote=False),
            title=html.escape(str(titles.get(key) or key), quote=False),
            gifts=REWARD_GIFT_GAP.join(bits),
        ))
    body = "\n".join(lines) or _slots(REWARD_GIFT, words="награда")
    head = _slots(
        REWARD_DAY_HEAD,
        mark=html.escape(str(mark or "✨"), quote=False),
        days=html.escape(str(label or ""), quote=False),
    )
    return head + "\n" + _slots(REWARD_QUOTE, body=body)


def _gift_cap(count: int) -> str:
    """«больше N» требует родительный: 1 подарка, 2 подарков, 5 подарков."""
    n = max(0, int(count or 0))
    mod100 = n % 100
    mod10 = n % 10
    word = "подарка" if mod10 == 1 and mod100 != 11 else "подарков"
    return f"{n} {word}"


def _plain_reward(words: str) -> str:
    """Первая буква заглавная, чтобы строка в цитате не начиналась со строчной."""
    text = " ".join(str(words or "").split())
    if not text:
        return ""
    return text[:1].upper() + text[1:]


def kind_words(kind: str, amount: int, item: str = "") -> str:
    """Подпись награды без HTML.

    Где: справка (через карточку дня), история loot, личка при выдаче.
    Как: «бесплатный бонус», «10 кут», «Ключ ×2».
    """
    amount = max(1, int(amount or 1))
    if kind == "bonus":
        return "бесплатный бонус" if amount == 1 else f"бесплатный бонус ×{amount}"
    if kind == "bonus_x2":
        return "бонус ×2" if amount == 1 else f"бонус ×2 ×{amount}"
    if kind == "kuty":
        return f"{amount} кут"
    if kind == "item" and item:
        return item if amount == 1 else f"{item} ×{amount}"
    return ""


def profile_line(label: str, title: str = "", emoji_id: str = "") -> str:
    """Строка огонька в профиле человека.

    Где: карточка /stat и похожие места профиля.
    Как со статусом: «⭐ Живой огонь · огонёк 10 дней».
    Как без статуса: «⚫️ Огонёк уже 10 дней».
    """
    if title:
        mark = emoji(emoji_id or STATUS_EMOJI)
        return f"{mark} <b>{title}</b> · огонёк <b>{label}</b>"
    return f"{emoji(EMOJI)} <b>Огонёк уже {label}</b>"


# ---------------------------------------------------------------------------
# Справка «хелп огонёк» — слова по блокам
# ---------------------------------------------------------------------------
# Где: ответ бота на «хелп огонёк», «что такое огонёк», «как пользоваться…».
# {base} {words} — норма из вкладки; {warm_*} — тёплый час; {restore} — окно возврата.

HELP_TITLE = "{flame} <b>Огонёк сообщений</b>"  # шапка справки, одна жирная строка
HELP_HOOK = "😴 Устали писать просто так? Пусть у сообщений появится цель."  # крючок под шапкой
HELP_HOOK_ACTION = (
    "🔥 Продлите огонёк. Те же сообщения в официальных группах "
    "начнут приносить подарки."
)  # призыв сразу под крючком
HELP_REWARDS_HEAD = "{gift} <b>Награды за дни</b>"  # заголовок списка наград
HELP_REWARDS_LEAD = (
    "Подарок приходит один раз, сразу в личку. "
    "Сначала ближайший день — дальше приятнее."
)  # строка над карточками дней
HELP_REWARDS_EMPTY = (
    "Награды за дни скоро появятся. Огонёк уже можно продлевать."
)  # если в базе ещё нет наград
HELP_HOW_HEAD = "{spark} <b>Как работает</b>"  # заголовок механики
HELP_HOW_NORM = (
    "📝 Напишите {base} сообщений в официальных группах. "
    "В каждом сообщении — от {words} слов."
)  # норма сообщений
HELP_HOW_CLOCK = "🕛 Успейте до 00:00 МСК. Набрали норму — огонёк сразу +1 день."  # когда продлевается
HELP_HOW_DIE = "❌ Не продлили до 00:00 — огонёк гаснет."  # что если пропустить
HELP_SKIP_PLAIN = "Команды и игры не считаются."  # анти-фарм без дублей
HELP_SKIP_DUP = "Команды, игры и одно и то же сообщение подряд не считаются."  # с анти-дублем
HELP_RESTORE_WINDOW = (
    "Перестанете продлевать — серия погаснет. "
    "Вернуть огонёк можно ещё {restore}."
)  # только если возврат включён и есть цена
HELP_OFF = (
    "<i>Сейчас огонёк выключен. Когда включат — его снова можно продлевать.</i>"
)  # если система выключена во вкладке
HELP_GROWTH = (
    "<i>Норма сообщений для продлевания огонька будет расти со временем</i>"
)  # одна строка про рост нормы; таблицу шагов не пишем
HELP_STATUS_HEAD = "{star} <b>Статус в профиле</b>"  # блок статусов в справке
HELP_STATUS_LEAD = (
    "Пока огонёк горит — рядом с именем своя подпись. "
    "Чем длиннее серия, тем заметнее."
)  # пояснение под заголовком статусов
HELP_WARM_HEAD = "{warm} <b>Тёплый час</b>"  # блок тёплого часа
HELP_WARM_BODY = (
    "Если огонёк горит уже {warm_from}, один час в сутках даёт ещё подарок: "
    "каждые {warm_every} сообщений, и не больше {warm_cap} за день."
)
HELP_WARM_TODAY = "🕐 Сегодня это {warm_hour} МСК."  # текущий удачный час
HELP_RESTORE_HEAD = "{flame} <b>Вернуть огонёк</b>"  # заголовок блока возврата
HELP_CLOSE_RESTORE = (
    "🌱 Продлите один день — серия уже ваша. Если погаснет, вернуть её ещё можно."
)  # финал, если возврат доступен
HELP_CLOSE = (
    "🌱 Продлите один день — серия уже ваша. Перестанете продлевать — огонёк погаснет."
)  # финал без возврата


def screen_help(
    *,
    base: int,
    words: int,
    enabled: bool,
    rises: list[str],
    rewards: list[str],
    titles: list[str],
    warm_on: bool,
    warm_from: str,
    warm_every: int,
    warm_cap: int,
    warm_hour: str,
    gift_on: bool,
    gift_mult: int,
    restore_line: str,
    gift_item_count: int = 1,
    block_dup: bool = True,
    restore_days: int = 0,
) -> str:
    """Собирает полный текст справки из констант HELP_* выше."""
    _ = (gift_on, gift_mult, gift_item_count)
    skip = HELP_SKIP_DUP if block_dup else HELP_SKIP_PLAIN
    parts = [
        _slots(HELP_TITLE, flame=emoji(EMOJI)),
        HELP_HOOK,
        HELP_HOOK_ACTION,
        "",
        _slots(HELP_REWARDS_HEAD, gift=emoji("5438440765908874600", "🎁")),
    ]
    if rewards:
        parts.append(HELP_REWARDS_LEAD)
        parts.append("")
        parts.append("\n\n".join(rewards))
    else:
        parts.append(HELP_REWARDS_EMPTY)
    parts += [
        "",
        _slots(HELP_HOW_HEAD, spark=emoji("5321021153219732362", "⚡️")),
        _slots(HELP_HOW_NORM, base=str(int(base)), words=str(int(words))),
        HELP_HOW_CLOCK,
        HELP_HOW_DIE,
        f"🚫 {skip}",
    ]
    if int(restore_days or 0) > 0:
        parts.append(_slots(HELP_RESTORE_WINDOW, restore=span_days(restore_days)))
    if not enabled:
        parts += ["", HELP_OFF]
    if rises:
        parts += ["", HELP_GROWTH]
    if titles:
        parts += [
            "",
            _slots(HELP_STATUS_HEAD, star=emoji("5233479338791281256", "⭐️")),
            HELP_STATUS_LEAD,
            *titles,
        ]
    if warm_on:
        parts += [
            "",
            _slots(HELP_WARM_HEAD, warm=emoji("5296561370303592127", "🌟")),
            _slots(
                HELP_WARM_BODY,
                warm_from=str(warm_from),
                warm_every=str(int(warm_every)),
                warm_cap=_gift_cap(warm_cap),
            ),
        ]
        if warm_hour:
            parts.append(_slots(HELP_WARM_TODAY, warm_hour=str(warm_hour)))
    if restore_line:
        parts += ["", _slots(HELP_RESTORE_HEAD, flame=emoji(EMOJI)), restore_line]
    parts.append("")
    if int(restore_days or 0) > 0:
        parts.append(HELP_CLOSE_RESTORE)
    else:
        parts.append(HELP_CLOSE)
    return "\n".join(parts)


def span_days(count: int) -> str:
    n = max(0, int(count or 0))
    mod100 = n % 100
    mod10 = n % 10
    if 11 <= mod100 <= 14:
        word = "дней"
    elif mod10 == 1:
        word = "день"
    elif 2 <= mod10 <= 4:
        word = "дня"
    else:
        word = "дней"
    return f"<b>{n}</b> {word}"


def restore_ways(*, kuty: int, item: str, count: int) -> str:
    ways = []
    if int(kuty or 0) > 0:
        ways.append(f"<b>{int(kuty)}</b> кут")
    if item:
        piece = item if int(count or 1) == 1 else f"{item} ×{int(count)}"
        ways.append(f"<b>{piece}</b>")
    return " или ".join(ways)


def restore_help_line(*, days: int, kuty: int, item: str, count: int) -> str:
    price = restore_ways(kuty=kuty, item=item, count=count)
    return (
        f"Если перестанете продлевать, напишите «<b>вернуть огонёк</b>» в течение <b>{int(days)}</b> дн. "
        f"Серия вернётся целиком. Цена: {price}.\n"
        "Новая серия сжигает старую. После возврата снова продлите огонёк до 00:00 по Москве."
    )


def _fill(template: str, **slots: str) -> str:
    def swap(match):
        return slots.get(match.group(1), match.group(0))

    return re.sub(r"\{([a-z_]+)\}", swap, template)


def _plain_gifts(gifts: list[str]) -> list[str]:
    out = []
    for gift in gifts or []:
        text = " ".join(str(gift or "").split())
        if text:
            out.append(html.escape(text, quote=False))
    return out


# ---------------------------------------------------------------------------
# Сообщения при получении награды за день серии
# ---------------------------------------------------------------------------
# REWARD_PRIVATE — личка человеку, когда огонёк дошёл до дня с подарком.
# REWARD_HALL — то же событие во ВСЕ официальные группы (соцдоказательство).
# Слоты: {days} срок, {title} статус или пусто, {gifts} список, {name} имя со ссылкой.

_GIFT_EMOJI = emoji("5438440765908874600", "🎁")  # значок «Вам пришло» в личке
# Строка статуса над подарками в личке. Пустая, если статуса нет.
REWARD_TITLE = "🏅 <b>{title}</b>\n"
# Одна строка подарка в личке (когда нет групп в карточке дня).
REWARD_GIFT_LINE = "✨ <b>{gift}</b>"
# Между подарками в объявлении в группу.
REWARD_HALL_GAP = " · "
# Личка: срок, статус, список подарков, напоминание продлить завтра.
REWARD_PRIVATE = (
    f"{emoji(EMOJI)} <b>Огонёк уже {{days}}</b>\n"
    f"{{title}}{_GIFT_EMOJI} <b>Вам пришло</b>\n"
    "<blockquote>{gifts}</blockquote>\n"
    "<i>Завтра до <b>00:00</b> МСК продлите снова.</i>"
)
# Группа: кто получил, сколько дней, что выпало, как начать так же.
REWARD_HALL = (
    f"{emoji(EMOJI)} <b>{{name}}</b>\n"
    "огонёк уже <b>{days}</b>\n"
    "<blockquote>🎁 {gifts}</blockquote>\n"
    "<code>хелп огонёк</code> — с <b>одного дня</b>."
)


def screen_streak(label: str, title: str, gifts: str) -> str:
    """Личка при продлении дня БЕЗ наград.

    Где: когда норма набрана, а на этот день подарков нет.
    """
    head = f"<b>{html.escape(title, quote=False)}</b>\n" if title else ""
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже {html.escape(label, quote=False)}</b>\n"
        f"{head}"
        "<blockquote>🔥 Продлён ещё на <b>1 день</b>.\n"
        "Завтра до <b>00:00</b> МСК продлите снова.</blockquote>"
    )


def screen_reward_private(label: str, title: str, gifts: list[str]) -> str:
    """Личка тому, кто забрал награду. Слова — в REWARD_PRIVATE."""
    lines = [_fill(REWARD_GIFT_LINE, gift=gift) for gift in _plain_gifts(gifts)]
    title_line = _fill(REWARD_TITLE, title=html.escape(title, quote=False)) if title else ""
    return _fill(
        REWARD_PRIVATE,
        days=html.escape(label, quote=False),
        title=title_line,
        gifts="\n".join(lines) or _fill(REWARD_GIFT_LINE, gift="награда"),
    )


def screen_reward_hall(name_html: str, label: str, gifts: list[str]) -> str:
    """Одно и то же объявление во все официальные группы. Слова — в REWARD_HALL."""
    body = REWARD_HALL_GAP.join(f"<b>{gift}</b>" for gift in _plain_gifts(gifts)) or "<b>награда</b>"
    return _fill(
        REWARD_HALL,
        name=name_html or "Игрок",
        days=html.escape(label, quote=False),
        gifts=body,
    )


def screen_warm(label: str) -> str:
    """Личка при награде тёплого часа.

    Где: удачный час суток, отдельный ролл. В группы не уходит.
    """
    safe = html.escape(" ".join(str(label or "награда").split()) or "награда", quote=False)
    return (
        f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>\n"
        "<blockquote>🌟 Вы попали в удачный час.\n"
        "Подарок отдельно. День огонька он не заменяет.</blockquote>\n"
        f"{emoji('5438440765908874600', '🎁')} <b>{safe}</b>"
    )


def screen_profit(
    *,
    title: str,
    streak: str,
    rank: str,
    kept: bool,
    next_line: str,
    loot_line: str,
) -> str:
    """Ежедневная сводка в личку (профит-час из вкладки).

    Где: раз в сутки тем, у кого огонёк жив.
    """
    head = f"<b>{title}</b>\n" if title else ""
    if kept:
        state = (
            f"{emoji('5321021153219732362', '⚡️')} Сегодня огонёк уже <b>продлён</b>. "
            "Завтра до 00:00 по Москве продлите его снова, иначе погаснет."
        )
    else:
        state = (
            f"{emoji('5467519850576354798', '❕')} Сегодня огонёк ещё <b>не продлён</b>. "
            "Успейте до 00:00 по Москве."
        )
    return (
        f"{emoji(EMOJI)} <b>Ваш огонёк сегодня</b>\n{head}"
        f"<blockquote>Серия: <b>{streak}</b> · место <b>#{rank}</b>\n"
        f"{state}</blockquote>"
        f"{next_line}{loot_line}"
    )


def profit_next(day_label: str, left: int, day_word: str, gift: str) -> str:
    return (
        f"\n{emoji('5438440765908874600', '🎁')} "
        f"До <b>{day_label}</b> ещё <b>{left}</b> {day_word}: {gift}. Один день за раз."
    )


def profit_next_done() -> str:
    return (
        "\n<i>Назначенные награды уже у вас. Дальше каждое продление просто растит серию.</i>"
    )


def profit_loot(labels: list[str]) -> str:
    if not labels:
        return ""
    body = " · ".join(f"<b>{label}</b>" for label in labels)
    return f"\nУже сегодня: {body}."


def screen_top_empty() -> str:
    """Топ огоньков, когда живых серий ещё нет.

    Где: кнопка / команда «лучшие огоньки».
    """
    return (
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>\n"
        "<blockquote>Самые длинные живые серии.\n"
        "<i>Пока пусто. Продлите огонёк сегодня — и вы в списке.</i></blockquote>"
    )


def screen_top(rows: list[str]) -> str:
    """Топ живых серий.

    Где: кнопка / команда «лучшие огоньки».
    """
    head = [
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>",
        "<i>Только живые серии. Погасшие сюда не попадают.</i>",
        "",
    ]
    return "\n".join(head + rows)


def top_mark(index: int) -> str:
    medals = {
        1: emoji("5294001020039363545", "🏆"),
        2: emoji("5458612419116933783", "🏆"),
        3: emoji("5469967260380612012", "🏆"),
    }
    return medals.get(int(index), f"<b>{int(index)}.</b>")


def top_row(index: int, name_html: str, label: str, title: str = "", record: bool = False) -> str:
    mark = " · <i>рекорд</i>" if record else ""
    titled = f" · <b>{title}</b>" if title else ""
    return f"{top_mark(index)} {name_html} — <b>{label}</b>{titled}{mark}"


def screen_restore_offer(label: str, days_left: int, ways: str) -> str:
    """Карточка «вернуть огонёк», когда возврат ещё доступен.

    Где: ответ на «вернуть огонёк».
    """
    window = "сегодня" if int(days_left) <= 1 else f"ещё {int(days_left)} дн."
    return (
        f"{emoji(EMOJI)} <b>Вернуть огонёк</b>\n"
        f"<blockquote>Серия <b>{label}</b> ещё можно вернуть: {window}.\n"
        "Новая серия сжигает старую.\n"
        "Цена видна заранее. Отказ ничего не списывает.\n"
        "После возврата снова продлите огонёк до 00:00 по Москве.</blockquote>\n"
        f"Цена: {ways}."
    )


def screen_restore_done(label: str) -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк снова горит</b>\n"
        f"<blockquote>Серия <b>{label}</b> снова с вами.\n"
        "Сегодня до <b>00:00</b> по Москве снова продлите огонёк — иначе он погаснет.</blockquote>"
    )


def screen_restore_alive() -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже горит</b>\n"
        "<blockquote>Огонёк горит, возвращать нечего.\n"
        "Продлите его до 00:00 по Москве.</blockquote>"
    )


def screen_restore_none() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возвращать нечего</b>\n"
        "<blockquote>Погасшей серии нет.\n"
        "Если погаснет — напишите «вернуть огонёк».</blockquote>"
    )


def screen_restore_late() -> str:
    return (
        f"{emoji(EMOJI)} <b>Срок прошёл</b>\n"
        "<blockquote>Срок возврата прошёл.\n"
        "Новую серию можно начать: продлите огонёк сегодня.</blockquote>"
    )


def screen_restore_off() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат выключен</b>\n"
        "<blockquote>Сейчас вернуть нельзя.\n"
        "Новую серию начинают так же: продлевают огонёк.</blockquote>"
    )


def screen_restore_poor(price: int) -> str:
    return (
        f"{emoji(EMOJI)} <b>Не хватает кут</b>\n"
        f"<blockquote>Нужно <b>{int(price)}</b> кут.\n"
        "Их не хватило. Ничего не списано.</blockquote>"
    )


def screen_restore_no_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return (
        f"{emoji(EMOJI)} <b>Нет предмета</b>\n"
        f"<blockquote>Нужен <b>{piece}</b>.\n"
        "Его нет. Ничего не списано.</blockquote>"
    )


def screen_restore_busy() -> str:
    return "Уже вернули или срок прошёл. Ничего не списано."


def screen_restore_cancel() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат отменён</b>\n"
        "<blockquote>Возврат отменён. Ничего не списано.</blockquote>"
    )


def button_kuty(price: int) -> str:
    """Кнопка оплаты возврата кутами. Где: карточка «вернуть огонёк»."""
    return f"За {int(price)} кут"


def button_item(name: str, count: int) -> str:
    """Кнопка оплаты возврата предметом. Где: карточка «вернуть огонёк»."""
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"За {piece}"


def button_cancel() -> str:
    """Кнопка отказа от возврата. Где: карточка «вернуть огонёк»."""
    return "Отказаться"


def alert_stranger() -> str:
    """Всплывашка, если чужую кнопку возврата нажал другой человек."""
    return "Эта кнопка не ваша."


def alert_poor(price: int) -> str:
    """Всплывашка: не хватило кут на возврат."""
    return f"Чтобы вернуть огонёк, нужно {int(price)} кут."


def alert_no_item(name: str, count: int) -> str:
    """Всплывашка: нет нужного предмета на возврат."""
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"Чтобы вернуть огонёк, нужен предмет: {piece}."


# Команды возврата (без ё — сравнение уже сводит ё→е).
# Где: человек пишет в чат или личку; бот открывает карточку возврата.
RESTORE_COMMANDS = (
    "вернуть огонек",
    "восстановить огонек",
)


def _fold_cmd(text: str) -> str:
    import re
    folded = (text or "").lower().replace("ё", "е").replace("Ё", "е")
    folded = re.sub(r"[^\w\s]+", " ", folded, flags=re.UNICODE)
    return " ".join(folded.split())


def is_restore_command(text: str) -> bool:
    folded = _fold_cmd(text)
    return folded in RESTORE_COMMANDS


# Справка по огоньку: «хелп огонёк», «что такое огонёк», «как пользоваться…»
_HELP_EXACT = frozenset({
    "хелп огонек", "огонек хелп", "помощь огонек", "огонек помощь",
    "хелп огоньки", "огоньки хелп",
    "справка огонек", "огонек справка", "инструкция огонек", "огонек инструкция",
    "help flame", "flame help", "help огонек", "огонек help",
    "что такое огонек", "что такое огоньки", "что за огонек", "что это огонек",
    "что это за огонек", "зачем огонек", "зачем нужен огонек",
    "как пользоваться огоньком", "как пользоваться огонек",
    "как использовать огонек", "как использовать огоньком",
    "как работает огонек", "как работает огонек сообщений",
    "огонек что это", "огонек что такое", "расскажи про огонек",
    "объясни огонек", "про огонек", "про огонек сообщений",
    "хелп огонек сообщений", "огонек сообщений хелп",
    "помощь огонек сообщений",
})

_HELP_HINTS = frozenset({
    "хелп", "хелпа", "помощь", "help", "хепл", "hepl",
    "справка", "справку", "инструкция", "инструкцию", "гайд",
})

_ASK_HINTS = (
    "что такое",
    "что за",
    "что это",
    "что это за",
    "зачем",
    "как пользоваться",
    "как использовать",
    "как работает",
    "как открыть",
    "расскажи",
    "объясни",
    "подскажи",
)


def _has_flame_word(folded: str) -> bool:
    import re
    return bool(re.search(r"(?:^|\s)(?:огон[еь]к\w*|flame)(?:\s|$)", folded))


def is_flame_help_text(text: str) -> bool:
    """True — показать справку огонька (как вкладка в «хелп»)."""
    folded = _fold_cmd(text)
    if not folded or len(folded) > 90:
        return False
    if folded in RESTORE_COMMANDS:
        return False
    if ("вернуть" in folded or "восстановить" in folded) and _has_flame_word(folded):
        return False
    if folded in _HELP_EXACT:
        return True
    if not _has_flame_word(folded):
        return False
    tokens = set(folded.split())
    if tokens & _HELP_HINTS:
        return True
    if any(hint in folded for hint in _ASK_HINTS):
        return True
    return False


def button_help() -> str:
    """Подпись кнопки справки огонька в общем «хелп»."""
    return "Огонёк сообщений"


def button_top() -> str:
    """Подпись кнопки топа огоньков."""
    return "Лучшие огоньки"


def alert_top_failed() -> str:
    """Всплывашка, если топ не открылся."""
    return "Не удалось открыть список огоньков. Напишите ещё раз чуть позже."


# Подписи в истории баланса / cutehistory.
HISTORY_GRANT = "огонёк"          # начисление за день серии или тёплый час
HISTORY_RESTORE = "вернуть огонёк"  # списание цены возврата
