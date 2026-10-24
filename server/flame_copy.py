# -*- coding: utf-8 -*-
"""Огонёк — все тексты, которые видит человек.

Как править
-----------
Как в текстах брака: сообщение целиком лежит в тройных кавычках.
Строка с # над ним говорит, где человек его видит и когда. Решётка в Telegram не уходит.
Слоты {days} {name} {base} {words} бот подставляет сам. Их не удаляйте и не переименовывайте.
Короткий тост, кнопка и строка истории — одна строка с # в конце. Теги там не рисуются.
После правки перезапустите бота.

Норма сообщений, дни наград, статусы и цены — вкладка «Огонёк».
Здесь только слова. Логика серии — server/flame_engine.py.
Тексты Бонуса + — server/flame_bonus_plus_copy.py, тем же способом.
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
# Как: строка «значок 40 дней», под ней одна цитата.
#      Сначала бонус и куты, затем «+ Предметы :» и каждый предмет со своей строки.
#      Слоты: {mark} {days} {body} {face} {gifts} {words}.

# Значок слева от срока. Первое число — «с такого дня включительно».
# Дальше id премиум-эмодзи и запасной значок, если премиум не рисуется.
REWARD_DAY_MARKS = (
    (365, "5357421327470866510", "⚫️"),  # от 365 дней
    (100, "5357065356286405053", "⚫️"),  # от 100
    (50, "5199552030615558774", "🪙"),   # от 50
    (40, "5278467510604160626", "💰"),   # от 40
    (30, "5952066863931331270", "⭐️"),   # от 30
    (25, "5985379274524202415", "💲"),   # от 25
    (20, "5382164415019768638", "🪙"),   # от 20
    (10, "5424746623462823358", "🏅"),   # от 10
    (0, "5325547803936572038", "✨"),    # всё раньше
)
# Значок строки «Бесплатный бонус» и «Бонус ×2» внутри цитаты дня.
REWARD_BONUS_EMOJI = "5438440765908874600"
# Значок строки кут внутри цитаты дня. Запасной — 💰.
REWARD_KUTY_EMOJI = "5375296873982604963"
# Порядок групп внутри одного дня. kind — из базы наград.
REWARD_GROUPS = (
    ("bonus", "🎁", "Бонус"),
    ("bonus_x2", "🎁", "Бонус ×2"),
    ("kuty", "💰", "Куты"),
    ("item", "📦", "Предметы"),
)
# Если у предмета в каталоге нет эмодзи — ставим это.
REWARD_ITEM_FALLBACK = "🎁"
# Между двумя подарками одной группы, если их пришлось склеить в одну строку.
REWARD_GIFT_GAP = " · "
# Строка над цитатой дня. {mark} премиум-значок, {days} «40 дней».
REWARD_DAY_HEAD = "{mark} <b>{days}</b>"
# Одна цитата на все подарки дня. {body} строки через перевод строки.
REWARD_QUOTE = "<blockquote>{body}</blockquote>"
# Куты внутри цитаты. {face} значок, {gifts} «10 кут».
REWARD_KUTY = "{face} {gifts}"
# Бонус и бонус ×2. {face} значок, {words} «Бесплатный бонус» или «Бонус ×2».
REWARD_PLAIN = "{face} {words}"
# Заголовок списка предметов внутри цитаты. Пишется только если предметы есть.
REWARD_ITEMS = "<b>+ Предметы :</b>"
# Один предмет. {face} эмодзи из каталога, {words} имя.
REWARD_ITEM = "{face} {words}"


def _slots(template: str, **slots: str) -> str:
    def swap(match):
        return slots.get(match.group(1), match.group(0))

    return re.sub(r"\{([a-z_]+)\}", swap, template)


def _gap(text: str) -> str:
    """Пустой кусок справки не оставляет дыру. Непустой начинается с пустой строки."""
    body = str(text or "").strip("\n")
    return f"\n\n{body}" if body else ""


def _tighten(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def status_help_line(days: str, name: str) -> str:
    """Строка статуса в справке. Слова — HELP_STATUS_LINE."""
    safe = html.escape(" ".join(str(name or "").split()), quote=False)
    return _slots(HELP_STATUS_LINE, days=str(days or ""), name=safe)


def reward_mark(day: int) -> str:
    """Премиум-значок слева от срока в справке."""
    n = int(day or 0)
    for start, eid, fallback in REWARD_DAY_MARKS:
        if n >= int(start):
            return emoji(str(eid), str(fallback))
    return emoji(REWARD_DAY_MARKS[-1][1], REWARD_DAY_MARKS[-1][2])


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
    """Один день: бонус и куты сверху, предметы списком под «+ Предметы :»."""
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
    lines = []
    item_lines = []
    for key in sequence:
        if key == "item":
            for face, text in packed[key]:
                item_lines.append(_slots(
                    REWARD_ITEM,
                    face=_coded_face(face),
                    words=html.escape(text, quote=False),
                ))
            continue
        if key in {"bonus", "bonus_x2"}:
            words = " · ".join(
                _plain_reward(text) for _face, text in packed[key] if text
            )
            lines.append(_slots(
                REWARD_PLAIN,
                face=emoji(REWARD_BONUS_EMOJI, "🎁"),
                words=html.escape(words, quote=False),
            ))
            continue
        bits = [
            html.escape(text, quote=False)
            for _face, text in packed[key]
            if text
        ]
        if not bits:
            continue
        face = emoji(REWARD_KUTY_EMOJI, "💰") if key == "kuty" else _coded_face(
            packed[key][0][0] or "🎁"
        )
        lines.append(_slots(REWARD_KUTY, face=face, gifts=REWARD_GIFT_GAP.join(bits)))
    if item_lines:
        lines.append(REWARD_ITEMS)
        lines.extend(item_lines)
    body = "\n".join(lines) or "награда"
    head = _slots(
        REWARD_DAY_HEAD,
        mark=_coded_face(str(mark or "")) or emoji(REWARD_DAY_MARKS[-1][1], "✨"),
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


# Подписи наград без HTML. Теги сюда не пишите: история и кнопки их не рисуют.
PHRASE_BONUS = "бесплатный бонус"  # Справка, карточка дня: обычный бонус, одна штука.
PHRASE_BONUS_N = "бесплатный бонус ×{n}"  # Справка, если обычных бонусов несколько. {n} — число.
PHRASE_X2 = "бонус ×2"  # Справка, карточка дня: бонус с удвоением.
PHRASE_X2_N = "бонус ×2 ×{n}"  # Справка, если бонусов ×2 несколько.
PHRASE_KUTY = "{n} кут"  # Справка и объявление: куты. {n} — число.
PHRASE_ITEM_N = "{name} ×{n}"  # Справка и объявление: предмет, если штук больше одной.

# Личка и официальные группы, когда день дал бонус. Это не строка справки.
ANNOUNCE_BONUS = "бесплатное открытие бонуса"  # Обычный бонус, одна штука.
ANNOUNCE_BONUS_N = "бесплатное открытие бонуса ×{n}"  # Обычный бонус, несколько штук.
ANNOUNCE_X2 = "бесплатное открытие бонуса ×2"  # Бонус ×2, одна штука.
ANNOUNCE_X2_N = "бесплатное открытие бонуса ×2 ×{n}"  # Бонус ×2, несколько штук.


def kind_words(kind: str, amount: int, item: str = "") -> str:
    """Подпись награды без HTML. Слова — PHRASE_* выше."""
    amount = max(1, int(amount or 1))
    if kind == "bonus":
        return PHRASE_BONUS if amount == 1 else _slots(PHRASE_BONUS_N, n=str(amount))
    if kind == "bonus_x2":
        return PHRASE_X2 if amount == 1 else _slots(PHRASE_X2_N, n=str(amount))
    if kind == "kuty":
        return _slots(PHRASE_KUTY, n=str(amount))
    if kind == "item" and item:
        return item if amount == 1 else _slots(PHRASE_ITEM_N, name=item, n=str(amount))
    return ""


def announce_label(kind: str, amount: int = 1, item: str = "") -> str:
    """Подпись подарка в личке и в группах. Слова — ANNOUNCE_* и PHRASE_*."""
    amount = max(1, int(amount or 1))
    if kind == "bonus":
        return ANNOUNCE_BONUS if amount == 1 else _slots(ANNOUNCE_BONUS_N, n=str(amount))
    if kind == "bonus_x2":
        return ANNOUNCE_X2 if amount == 1 else _slots(ANNOUNCE_X2_N, n=str(amount))
    return kind_words(kind, amount, item)


# ---------------------------------------------------------------------------
# Блок огонька в «кто я»
# Где: профиль, команда «кто я», над строками активности.
# Три факта и ничего больше: сколько горит сейчас, рекорд, статус.
# {now} «3 дня» или «погас». {record} «10 дней». {status} название или «нет».
# ---------------------------------------------------------------------------
PROFILE = """
{head} <b>Огонёк</b>
<blockquote>{now_face} Сейчас · <b>{now}</b>
{best_face} Рекорд · <b>{record}</b>
{status_face} Статус · <b>{status}</b></blockquote>
"""
PROFILE_OUT = "погас"  # Сейчас, если серия не горит.
PROFILE_NO_STATUS = "нет"  # Рекорд или статус, если их ещё нет.


def profile_line(now: str, record: str, status: str, status_emoji: str = "") -> str:
    """Блок огонька в профиле. Слова — PROFILE."""
    return _tighten(_slots(
        PROFILE,
        head=emoji("5357421327470866510", "⚫️"),
        now_face=emoji("5330346824299490543", "🕯"),
        best_face=emoji("5424746623462823358", "🏅"),
        status_face=emoji(status_emoji or "5952066863931331270", "⭐️"),
        now=html.escape(str(now or ""), quote=False),
        record=html.escape(str(record or ""), quote=False),
        status=html.escape(str(status or ""), quote=False),
    ))


# ---------------------------------------------------------------------------
# Справка «хелп огонёк»
# Где: ответ на «хелп огонёк», «что такое огонёк», «как пользоваться огоньком».
# {base} {words} — норма из вкладки. {rewards} — дни с подарками.
# {skip} — что не считается.
# {how_extra} {off} {growth} {warm} {restore} — пустые, если раздел выключен.
# {close} — последняя строка, подпись идеи.
# Статусы в эту справку не входят: они видны в профиле.
# ---------------------------------------------------------------------------
HELP = """
<tg-emoji emoji-id='5357421327470866510'>⚫️</tg-emoji> <b>Огонёк сообщений</b>
<tg-emoji emoji-id='5352676440875769889'>🗽</tg-emoji> Устали писать просто так? Пусть у сообщений появится цель.
<tg-emoji emoji-id='5330346824299490543'>🕯</tg-emoji> Продлите огонёк. И те же сообщения в официальных группах начнут приносить пользу

<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>Награды за дни</b>
{rewards}

<tg-emoji emoji-id='5402485258211859739'>🎈</tg-emoji> <b>Как работает</b>
<tg-emoji emoji-id='5456504676801338603'>🎁</tg-emoji> <b>Напишите {base} сообщений в официальных группах.</b>
В каждом сообщении - от {words} слов.

<tg-emoji emoji-id='5474230973199587674'>🎁</tg-emoji> <b>Успейте до 00:00 МСК.</b> Набрали норму - огонёк продлевается на 1 день

<tg-emoji emoji-id='5404424216902673748'>🎁</tg-emoji> Не продлили до <b>00:00 МСК</b> - огонёк гаснет. Награды за уже пройденные дни не выдаются. Следующая будет, только когда огонёк станет длиннее, чем уже был.

<tg-emoji emoji-id='5427334027726055110'>🎁</tg-emoji> {skip}{how_extra}{off}{growth}{warm}{restore}

{close}
"""

# Где: справка, под заголовком «Награды за дни», если награды в базе есть. {cards} подставит бот.
HELP_REWARDS = """
Подарок приходит один раз

{cards}
"""

# Где: справка, если дней с наградами ещё нет.
HELP_REWARDS_EMPTY = "Подарок приходит один раз\n\nНаграды за дни скоро появятся. Огонёк уже можно продлевать."

# Где: справка, строка «что не считается». Первая — когда повтор подряд не идёт в норму.
HELP_SKIP_DUP = "Команды, игры и одно и то же сообщение подряд не считаются."
HELP_SKIP_PLAIN = "Команды и игры не считаются."

# Где: справка, сразу под «что не считается», только если возврат включён. {restore} — «3 дня».
HELP_RESTORE_WINDOW = "Перестанете продлевать - серия погаснет. Вернуть огонёк можно ещё {restore}."

# Где: справка, если огонёк выключен во вкладке.
HELP_OFF = "<i>Сейчас огонёк выключен. Когда включат — его снова можно продлевать.</i>"

# Где: справка, одна строка. Таблицу «со 7-го дня — 250» сюда не пишите.
HELP_GROWTH = "<i>Норма сообщений для продлевания огонька будет расти со временем</i>"

# Где: справка, блок статусов. {lines} — строки HELP_STATUS_LINE.
HELP_STATUS = """
{star} <b>Статус в профиле</b>
Пока огонёк горит — рядом с именем своя подпись. Чем длиннее серия, тем заметнее.
{lines}
"""

# Где: одна строка статуса в справке. {days} «10 дней», {name} название из вкладки.
HELP_STATUS_LINE = "Если огонёк горит уже {days} — <b>{name}</b>"

# Где: справка, блок тёплого часа.
# {warm_from} «1 день». {warm_hour} «20:00–21:00». {warm_every} сколько сообщений.
HELP_WARM = """
<tg-emoji emoji-id='5354952069168009105'>🍦</tg-emoji> <b>Тёплый час</b>
Если огонёк горит уже {warm_from},
в <b>{warm_hour} МСК.</b> написав {warm_every} сообщений, вы сможете получить какой-то подарок от проекта
"""

# Где: справка, блок возврата. {line} — текст restore_help_line. Только если возврат включён.
HELP_RESTORE = """
{flame} <b>Вернуть огонёк</b>
{line}
"""

# Где: последняя строка справки «хелп огонёк».
HELP_CLOSE = "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b><i>Идея была придумана старшим сотрудником проекта <a href=\"https://t.me/Stremlenue\">@Stremlenue</a></i></b>"


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
    """Собирает справку из HELP выше. Слова не добавляет — только подставляет слоты."""
    _ = (gift_on, gift_mult, gift_item_count, titles, warm_cap)
    reward_block = (
        _slots(HELP_REWARDS, cards="\n\n".join(rewards)).strip("\n")
        if rewards else HELP_REWARDS_EMPTY
    )
    how_extra = ""
    if int(restore_days or 0) > 0:
        how_extra = "\n" + _slots(HELP_RESTORE_WINDOW, restore=span_days(restore_days))
    warm = ""
    if warm_on:
        hour = str(warm_hour or "").strip() or "этот час"
        warm = _slots(
            HELP_WARM,
            warm_from=str(warm_from),
            warm_every=str(int(warm_every)),
            warm_hour=hour,
        ).strip("\n")
    restore = ""
    if restore_line:
        restore = _slots(HELP_RESTORE, flame=emoji(EMOJI), line=restore_line).strip("\n")
    return _tighten(_slots(
        HELP,
        base=str(int(base)),
        words=str(int(words)),
        rewards=reward_block,
        skip=HELP_SKIP_DUP if block_dup else HELP_SKIP_PLAIN,
        how_extra=how_extra,
        off=_gap(HELP_OFF) if not enabled else "",
        growth=_gap(HELP_GROWTH) if rises else "",
        warm=_gap(warm),
        restore=_gap(restore),
        close=HELP_CLOSE,
    ))


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


def _piece(name: str, count: int) -> str:
    return name if int(count or 1) == 1 else _slots(PHRASE_ITEM_N, name=name, n=str(int(count)))


def restore_ways(*, kuty: int, item: str, count: int) -> str:
    ways = []
    if int(kuty or 0) > 0:
        ways.append(_slots(RESTORE_KUTY, n=str(int(kuty))))
    if item:
        ways.append(f"<b>{html.escape(_piece(item, count), quote=False)}</b>")
    return RESTORE_OR.join(ways)


def restore_help_line(*, days: int, kuty: int, item: str, count: int) -> str:
    """Абзац возврата в справке. Слова — RESTORE_HELP."""
    return show(RESTORE_HELP, days=str(int(days)), price=restore_ways(kuty=kuty, item=item, count=count))


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


def show(template: str, **slots: str) -> str:
    """Подставляет слоты в сообщение. Края тройных кавычек не попадают в чат."""
    return _slots(str(template).strip("\n"), **slots)


# ---------------------------------------------------------------------------
# Личка и группы, когда день серии дал подарок
# ---------------------------------------------------------------------------
# Где: личка человеку. {flame} значок, {days} «5 дней».
# {title} — строка статуса или пусто. {gift} значок «Вам пришло». {gifts} строки подарков.
REWARD_PRIVATE = """
{flame} <b>Огонёк уже {days}</b>
{title}{gift} <b>Вам пришло</b>
<blockquote>{gifts}</blockquote>
<i>Завтра до <b>00:00</b> МСК продлите снова.</i>
"""

# Где: личка, строка статуса над подарками. Пустая, если статуса нет. {title} название.
REWARD_TITLE = "<tg-emoji emoji-id='5469967260380612012'>🏆</tg-emoji> <b>{title}</b>\n"

# Где: личка, одна строка подарка внутри цитаты. {gift} уже готовые слова.
REWARD_GIFT_LINE = "<tg-emoji emoji-id='5325547803936572038'>✨</tg-emoji> <b>{gift}</b>"

# Где: все официальные группы. {name} имя со ссылкой, {days} срок, {gifts} подарки через « · ».
REWARD_HALL = """
{flame} <b>{name}</b>
огонёк уже <b>{days}</b>
<blockquote>{gifts}</blockquote>
<code>хелп огонёк</code> - с <b>первого дня</b>.
"""

# Между подарками в объявлении группы.
REWARD_HALL_GAP = " · "

# Где: личка, день продлён, а подарка на этот день нет. {title} строка статуса или пусто.
STREAK = """
{flame} <b>Огонёк уже {days}</b>
{title}<blockquote><tg-emoji emoji-id='5852868430952144622'>🔥</tg-emoji> Продлён ещё на <b>1 день</b>.
Завтра до <b>00:00</b> МСК продлите снова.</blockquote>
"""

# Где: личка тёплого часа. В группы не уходит. {gift} что выпало.
WARM = """
{warm} <b>Тёплый час</b>
<blockquote>🌟 Вы попали в удачный час.
Подарок выдаётся отдельно. Дневную норму огонька он не заменяет.</blockquote>
{gift_emoji} <b>{gift}</b>
"""

# Где: личка раз в сутки, сводка огонька. {state} — PROFIT_KEPT или PROFIT_OPEN.
# {title} строка статуса или пусто. {next} {loot} дописываются снизу, могут быть пустыми.
PROFIT = """
{flame} <b>Ваш огонёк сегодня</b>
{title}<blockquote>Серия : <b>{streak}</b> · место <b>#{rank}</b>
{state}</blockquote>{next}{loot}
"""

# Где: сводка, если сегодня норма уже набрана.
PROFIT_KEPT = "{spark} Сегодня огонёк уже <b>продлён</b>. Завтра до 00:00 по Москве продлите его снова, иначе погаснет."

# Где: сводка, если сегодня норма ещё не набрана.
PROFIT_OPEN = "{mark} Сегодня огонёк ещё <b>не продлён</b>. Успейте до 00:00 по Москве."

# Где: низ сводки, сколько дней до следующей награды. {day} срок, {left} число, {word} день/дня/дней, {gift} что будет.
PROFIT_NEXT = "\n{gift} До <b>{day}</b> ещё <b>{left}</b> {word} : {what}. Один день за раз."

# Где: низ сводки, когда все назначенные награды уже получены.
PROFIT_DONE = "\n<i>Назначенные награды уже у вас. Дальше каждое продление просто растит серию огонька .</i>"

# Где: низ сводки, что уже пришло сегодня. {gifts} список.
PROFIT_LOOT = "\nУже сегодня : {gifts}."

# Где: топ, когда живых серий нет.
TOP_EMPTY = """
{cup} <b>Лучшие огоньки</b>
<blockquote>Самые длинные живые серии.
<i>Пока пусто. Продлите огонёк сегодня - и вы будете в списке.</i></blockquote>
"""

# Где: топ живых серий, шапка. {rows} строки TOP_ROW.
TOP = """
{cup} <b>Лучшие огоньки</b>
<i>Только живые серии. Погасшие сюда не попадают.</i>

{rows}
"""

# Где: одна строка топа. {mark} место, {name} имя, {label} срок.
# {title} « · статус» или пусто. {record} « · рекорд» или пусто.
TOP_ROW = "{mark} {name} — <b>{label}</b>{title}{record}"
TOP_RECORD = " · <i>рекорд</i>"  # Хвост строки топа, если это рекорд человека.
TOP_TITLE = " · <b>{title}</b>"  # Хвост строки топа, название статуса.

# Где: ответ на «вернуть огонёк», пока срок не вышел.
# {label} длина серии, {window} «сегодня» или «ещё N дн.», {ways} цена.
RESTORE_OFFER = """
{flame} <b>Вернуть огонёк</b>
<blockquote>Серия <b>{label}</b> ещё можно вернуть : {window}.
Новая серия сжигает старую.
Цена видна заранее. Отказ ничего не списывает.
После возврата снова продлите огонёк до 00:00 по Москве.</blockquote>
Цена : {ways}.
"""

# Где: справка, абзац про цену возврата. {days} число дней, {price} чем платить.
RESTORE_HELP = """
Если перестанете продлевать, напишите «<b>вернуть огонёк</b>» в течение <b>{days}</b> дн. Серия вернётся целиком. Цена: {price}.
Новая серия сжигает старую. После возврата снова продлите огонёк до 00:00 по Москве.
"""

RESTORE_KUTY = "<b>{n}</b> кут"  # Кусок цены возврата: куты.
RESTORE_OR = " или "  # Между кутами и предметом в цене возврата.

# Где: после успешного возврата. {label} длина серии.
RESTORE_DONE = """
{flame} <b>Огонёк снова горит</b>
<blockquote>Серия огонька <b>{label}</b> снова с вами.
Сегодня до <b>00:00</b> по Москве снова продлите огонёк - иначе он погаснет.</blockquote>
"""

# Где: «вернуть огонёк», а огонёк и так горит.
RESTORE_ALIVE = """
{flame} <b>Огонёк уже горит</b>
<blockquote>Огонёк горит, возвращать нечего.
Продлите его до 00:00 по Москве.</blockquote>
"""

# Где: «вернуть огонёк», погасшей серии нет.
RESTORE_NONE = """
{flame} <b>Возвращать нечего</b>
<blockquote>Погасшей серии огонька нет.
Если погаснет огонёк - напишите «вернуть огонёк».</blockquote>
"""

# Где: «вернуть огонёк», срок возврата уже прошёл.
RESTORE_LATE = """
{flame} <b>Срок прошёл</b>
<blockquote>Срок возврата прошёл.
Новую серию можно начать продлив огонёк сегодня.</blockquote>
"""

# Где: «вернуть огонёк», возврат выключен во вкладке.
RESTORE_OFF = """
{flame} <b>Возврат выключен</b>
<blockquote>Сейчас вернуть нельзя.
Новую серию огонька начинают так же : продлевают огонёк.</blockquote>
"""

# Где: не хватило кут. {price} число.
RESTORE_POOR = """
{flame} <b>Не хватает кут</b>
<blockquote>Нужно <b>{price}</b> кут.
Ничего не списано.</blockquote>
"""

# Где: нет предмета для возврата. {piece} «Купон» или «Купон ×2».
RESTORE_NO_ITEM = """
{flame} <b>Нет предмета</b>
<blockquote>Нужен <b>{piece}</b>.
Ничего не списано.</blockquote>
"""

RESTORE_BUSY = "Уже вернули или срок прошёл. Ничего не списано."  # Ответ, если возврат уже закрыт. Тегов нет.

# Где: человек нажал «Отказаться».
RESTORE_CANCEL = """
{flame} <b>Возврат отменён</b>
<blockquote>Ничего не списано.</blockquote>
"""

BUTTON_KUTY = "Оплатить {price} кут"  # Кнопка оплаты возврата кутами. Тегов нет.
BUTTON_ITEM = "Оплатить {piece}"  # Кнопка оплаты возврата предметом. Тегов нет.
BUTTON_CANCEL = "Отказаться"  # Кнопка отказа от возврата. Тегов нет.
ALERT_STRANGER = "Эта кнопка не ваша."  # Всплывашка: чужую кнопку возврата нажал другой человек.
ALERT_POOR = "Чтобы вернуть огонёк, нужно {price} кут."  # Всплывашка: не хватило кут.
ALERT_NO_ITEM = "Чтобы вернуть огонёк, нужен предмет : {piece}."  # Всплывашка: нет предмета.
BUTTON_HELP = "Огонёк сообщений"  # Кнопка справки огонька в общем «хелп».
BUTTON_TOP = "Лучшие огоньки"  # Кнопка топа огоньков.
ALERT_TOP = "Не удалось открыть список огоньков. Напишите ещё раз чуть позже."  # Всплывашка, если топ не открылся.
HISTORY_GRANT = "огонёк"  # История баланса: начисление за день серии или тёплый час.
HISTORY_RESTORE = "вернуть огонёк"  # История баланса: списание цены возврата.


def screen_streak(label: str, title: str, gifts: str) -> str:
    """Личка, день без подарка. Слова — STREAK."""
    _ = gifts
    head = f"<b>{html.escape(title, quote=False)}</b>\n" if title else ""
    return show(STREAK, flame=emoji(EMOJI), days=html.escape(label, quote=False), title=head)


def screen_reward_private(label: str, title: str, gifts: list[str]) -> str:
    """Личка с подарком. Слова — REWARD_PRIVATE."""
    lines = [show(REWARD_GIFT_LINE, gift=gift) for gift in _plain_gifts(gifts)]
    title_line = _slots(REWARD_TITLE, title=html.escape(title, quote=False)) if title else ""
    return show(
        REWARD_PRIVATE,
        flame=emoji(EMOJI),
        days=html.escape(label, quote=False),
        title=title_line,
        gift=emoji("5438440765908874600", "🎁"),
        gifts="\n".join(lines) or show(REWARD_GIFT_LINE, gift="награда"),
    )


def screen_reward_hall(name_html: str, label: str, gifts: list[str]) -> str:
    """Объявление во все официальные группы. Слова — REWARD_HALL."""
    body = REWARD_HALL_GAP.join(f"<b>{gift}</b>" for gift in _plain_gifts(gifts)) or "<b>награда</b>"
    return show(
        REWARD_HALL,
        flame=emoji(EMOJI),
        name=name_html or "Игрок",
        days=html.escape(label, quote=False),
        gifts=body,
    )


def screen_warm(label: str) -> str:
    """Личка тёплого часа. Слова — WARM."""
    safe = html.escape(" ".join(str(label or "награда").split()) or "награда", quote=False)
    return show(
        WARM,
        warm=emoji("5296561370303592127", "🌟"),
        gift_emoji=emoji("5438440765908874600", "🎁"),
        gift=safe,
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
    """Ежедневная сводка в личку. Слова — PROFIT, PROFIT_KEPT, PROFIT_OPEN."""
    head = f"<b>{title}</b>\n" if title else ""
    state = show(
        PROFIT_KEPT if kept else PROFIT_OPEN,
        spark=emoji("5321021153219732362", "⚡️"),
        mark=emoji("5467519850576354798", "❕"),
    )
    return show(
        PROFIT,
        flame=emoji(EMOJI),
        title=head,
        streak=str(streak),
        rank=str(rank),
        state=state,
        next=next_line or "",
        loot=loot_line or "",
    )


def profit_next(day_label: str, left: int, day_word: str, gift: str) -> str:
    """Низ сводки до следующей награды. Слова — PROFIT_NEXT."""
    return _slots(
        PROFIT_NEXT,
        gift=emoji("5438440765908874600", "🎁"),
        day=str(day_label),
        left=str(int(left)),
        word=str(day_word),
        what=str(gift),
    )


def profit_next_done() -> str:
    """Низ сводки, когда награды уже получены. Слова — PROFIT_DONE."""
    return PROFIT_DONE


def profit_loot(labels: list[str]) -> str:
    """Низ сводки: что уже пришло сегодня. Слова — PROFIT_LOOT."""
    if not labels:
        return ""
    body = " · ".join(f"<b>{label}</b>" for label in labels)
    return _slots(PROFIT_LOOT, gifts=body)


def screen_top_empty() -> str:
    """Топ, когда серий нет. Слова — TOP_EMPTY."""
    return show(TOP_EMPTY, cup=emoji("5354962501643578130"))


def screen_top(rows: list[str]) -> str:
    """Топ живых серий. Слова — TOP."""
    return show(TOP, cup=emoji("5354962501643578130"), rows="\n".join(rows))


def top_mark(index: int) -> str:
    medals = {
        1: emoji("5294001020039363545", "🏆"),
        2: emoji("5458612419116933783", "🏆"),
        3: emoji("5469967260380612012", "🏆"),
    }
    return medals.get(int(index), f"<b>{int(index)}.</b>")


def top_row(index: int, name_html: str, label: str, title: str = "", record: bool = False) -> str:
    """Одна строка топа. Слова — TOP_ROW, TOP_TITLE, TOP_RECORD."""
    return show(
        TOP_ROW,
        mark=top_mark(index),
        name=name_html,
        label=html.escape(str(label or ""), quote=False),
        title=show(TOP_TITLE, title=html.escape(title, quote=False)) if title else "",
        record=TOP_RECORD if record else "",
    )


def _window(days_left: int) -> str:
    return "сегодня" if int(days_left) <= 1 else f"ещё {int(days_left)} дн."


def screen_restore_offer(label: str, days_left: int, ways: str) -> str:
    """Карточка возврата. Слова — RESTORE_OFFER."""
    return show(
        RESTORE_OFFER,
        flame=emoji(EMOJI),
        label=str(label),
        window=_window(days_left),
        ways=ways,
    )


def screen_restore_done(label: str) -> str:
    return show(RESTORE_DONE, flame=emoji(EMOJI), label=str(label))


def screen_restore_alive() -> str:
    return show(RESTORE_ALIVE, flame=emoji(EMOJI))


def screen_restore_none() -> str:
    return show(RESTORE_NONE, flame=emoji(EMOJI))


def screen_restore_late() -> str:
    return show(RESTORE_LATE, flame=emoji(EMOJI))


def screen_restore_off() -> str:
    return show(RESTORE_OFF, flame=emoji(EMOJI))


def screen_restore_poor(price: int) -> str:
    return show(RESTORE_POOR, flame=emoji(EMOJI), price=str(int(price)))


def screen_restore_no_item(name: str, count: int) -> str:
    return show(RESTORE_NO_ITEM, flame=emoji(EMOJI), piece=html.escape(_piece(name, count), quote=False))


def screen_restore_busy() -> str:
    return RESTORE_BUSY


def screen_restore_cancel() -> str:
    return show(RESTORE_CANCEL, flame=emoji(EMOJI))


def button_kuty(price: int) -> str:
    return show(BUTTON_KUTY, price=str(int(price)))


def button_item(name: str, count: int) -> str:
    return show(BUTTON_ITEM, piece=_piece(name, count))


def button_cancel() -> str:
    return BUTTON_CANCEL


def alert_stranger() -> str:
    return ALERT_STRANGER


def alert_poor(price: int) -> str:
    return show(ALERT_POOR, price=str(int(price)))


def alert_no_item(name: str, count: int) -> str:
    return show(ALERT_NO_ITEM, piece=_piece(name, count))


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
    if folded in _MINE_EXACT or folded in RESTORE_COMMANDS:
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


# «мой огонёк» — только эта фраза, без хвоста. ё/е и регистр уже сняты.
# Где: человек пишет в чат или личку и получает свою карточку.
_MINE_EXACT = frozenset({
    "мой огонек",
    "огонек мой",
    "мойогонек",
    "мой огонечек",
    "огонечек мой",
    "мой огонь",
    "огонь мой",
    "мой flame",
    "my flame",
    "flame мой",
})


def is_flame_mine_text(text: str) -> bool:
    """True — открыть личную карточку. Лишние слова не подходят."""
    folded = _fold_cmd(text)
    if not folded or len(folded) > 40:
        return False
    return folded in _MINE_EXACT


# ---------------------------------------------------------------------------
# Карточка «мой огонёк»
# Где: ответ на «мой огонёк». Кнопки под сообщением меняют этот же текст.
# {now} {record} {status} — как в профиле. {extra} — сегодня, следующий подарок.
# ---------------------------------------------------------------------------
MINE = """
{head} <b>Ваш огонёк</b>

{now_face} Сейчас · <b>{now}</b>
{best_face} Рекорд · <b>{record}</b>
{status_face} Статус · <b>{status}</b>
{extra}
"""
# Где: карточка, если сегодняшняя норма уже закрыта.
MINE_TODAY_DONE = "<tg-emoji emoji-id='5474230973199587674'>🎁</tg-emoji> Сегодня огонёк уже продлён"
# Где: карточка, пока норма не закрыта. {have} уже написано, {need} сколько нужно.
MINE_TODAY = "<tg-emoji emoji-id='5456504676801338603'>🎁</tg-emoji> Сегодня · <b>{have}</b> из <b>{need}</b>"
# Где: карточка, ближайший ещё не полученный день. {day} «11 дней».
MINE_NEXT = "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> Следующий подарок · <b>{day}</b>"
# Где: карточка, если дней с новым подарком больше нет.
MINE_NEXT_NONE = "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> Дальше подарков пока нет"
# Где: карточка, если серия короче рекорда.
MINE_REPLAY = "<tg-emoji emoji-id='5404424216902673748'>🎁</tg-emoji> Дни до рекорда идут без подарка"
# Где: огонёк выключен во вкладке.
MINE_OFF = """
<tg-emoji emoji-id='5357421327470866510'>⚫️</tg-emoji> <b>Ваш огонёк</b>

Сейчас огонёк выключен. Когда включат — здесь появится серия.
"""
# Где: база недоступна.
MINE_FAIL = "Огонёк сейчас не открывается. Напишите ещё раз."
# Где: кнопка «Что дальше».
MINE_NEXT_SCREEN = """
<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>Следующий подарок</b>

{card}

{lead}
"""
MINE_NEXT_LEAD = "Сейчас <b>{now}</b>. Рекорд <b>{record}</b>."
MINE_NEXT_EMPTY = """
<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>Следующий подарок</b>

Дальше дней с подарком пока нет.
"""
# Где: кнопка «Как устроен». {base} {words} норма. {skip} что не считается. {growth} или пусто.
MINE_HOW = """
<tg-emoji emoji-id='5402485258211859739'>🎈</tg-emoji> <b>Как устроен</b>

<tg-emoji emoji-id='5456504676801338603'>🎁</tg-emoji> <b>Напишите {base} сообщений</b> в официальных группах.
В каждом — от {words} слов.

<tg-emoji emoji-id='5474230973199587674'>🎁</tg-emoji> До <b>00:00 МСК</b>. Набрали норму — огонёк +1 день.

<tg-emoji emoji-id='5404424216902673748'>🎁</tg-emoji> Не успели — огонёк гаснет. Пройденные дни второй раз не награждаются.

<tg-emoji emoji-id='5427334027726055110'>🎁</tg-emoji> {skip}{growth}
"""

MINE_BTN_NEXT = "Что дальше"  # Кнопка следующего подарка. Тегов нет.
MINE_BTN_RESTORE = "Вернуть"  # Кнопка возврата серии. Тегов нет.
MINE_BTN_HOW = "Как устроен"  # Кнопка коротких правил. Тегов нет.
MINE_BTN_BACK = "Назад"  # Кнопка к карточке. Тегов нет.
MINE_BTN_CLOSE = "Закрыть"  # Кнопка закрытия. Тегов нет.


def _mine_faces(status_emoji: str = "") -> dict:
    return {
        "head": emoji("5357421327470866510", "⚫️"),
        "now_face": emoji("5330346824299490543", "🕯"),
        "best_face": emoji("5424746623462823358", "🏅"),
        "status_face": emoji(status_emoji or "5952066863931331270", "⭐️"),
    }


def screen_mine(
    *,
    now: str,
    record: str,
    status: str,
    status_emoji: str = "",
    today_done: bool = False,
    have: int = 0,
    need: int = 0,
    next_day: str = "",
    replay: bool = False,
) -> str:
    """Главный экран «мой огонёк». Слова — MINE и соседние строки."""
    parts = []
    if today_done:
        parts.append(MINE_TODAY_DONE)
    elif int(need or 0) > 0:
        parts.append(_slots(MINE_TODAY, have=str(int(have)), need=str(int(need))))
    if next_day:
        parts.append(_slots(MINE_NEXT, day=html.escape(str(next_day), quote=False)))
    else:
        parts.append(MINE_NEXT_NONE)
    if replay:
        parts.append(MINE_REPLAY)
    extra = "\n" + "\n".join(parts) if parts else ""
    return _tighten(_slots(
        MINE,
        extra=extra,
        now=html.escape(str(now or ""), quote=False),
        record=html.escape(str(record or ""), quote=False),
        status=html.escape(str(status or ""), quote=False),
        **_mine_faces(status_emoji),
    ))


def screen_mine_off() -> str:
    return _tighten(MINE_OFF)


def screen_mine_fail() -> str:
    return MINE_FAIL


def screen_mine_next(card: str, now: str, record: str, replay: bool = False) -> str:
    """Экран «Что дальше». {card} — готовая карточка дня или пусто."""
    if not str(card or "").strip():
        return _tighten(MINE_NEXT_EMPTY)
    lead = _slots(
        MINE_NEXT_LEAD,
        now=html.escape(str(now or ""), quote=False),
        record=html.escape(str(record or ""), quote=False),
    )
    if replay:
        lead = lead + "\n" + MINE_REPLAY
    return _tighten(_slots(MINE_NEXT_SCREEN, card=str(card), lead=lead))


def screen_mine_how(*, base: int, words: int, block_dup: bool = True, rises: bool = False) -> str:
    """Экран «Как устроен». Короче полной справки."""
    growth = _gap(HELP_GROWTH) if rises else ""
    return _tighten(_slots(
        MINE_HOW,
        base=str(int(base)),
        words=str(int(words)),
        skip=HELP_SKIP_DUP if block_dup else HELP_SKIP_PLAIN,
        growth=growth,
    ))


def mine_button_next() -> str:
    return MINE_BTN_NEXT


def mine_button_restore() -> str:
    return MINE_BTN_RESTORE


def mine_button_how() -> str:
    return MINE_BTN_HOW


def mine_button_back() -> str:
    return MINE_BTN_BACK


def mine_button_close() -> str:
    return MINE_BTN_CLOSE


def button_help() -> str:
    return BUTTON_HELP


def button_top() -> str:
    return BUTTON_TOP


def alert_top_failed() -> str:
    return ALERT_TOP
