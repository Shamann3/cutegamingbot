# -*- coding: utf-8 -*-
"""Брак - дизайн всех сообщений.

Как править
-----------
Сообщение целиком - в text= тройными кавычками.
Эмодзи сообщения - в emoji=.
Кнопки написаны целиком сразу под этим текстом: text="подпись", icon=, color=, data=.
Ряд из двух кнопок - это один список [кнопка, кнопка]. Кнопка с новой строки - свой ряд.
data= - куда ведёт кнопка. {book_id}, {token}, {verb_id}, {amount} подставляются сами.
Слово на кнопке и то же слово в тексте пиши одинаково.
Предмет - отдельный экран item_…: текст, под ним «Купить» и «Использовать», used= - фраза, когда предмет сработал.

Типографика
-----------
<b>жирный</b> - то, на чём нужно сосредоточиться.
<i>курсив</i> - доп. текст, в основном навигация: что нажать, куда отправить.
<u>подчёркнутый</u> - только самое важное: цена, минуты, «оба», один раз.
Доп. информация - в <blockquote><b><i>…</i></b></blockquote>
Много текста - тоже в цитате, блоки разделяй пустой строкой.

WORDS для кнопок, тостов и истории - без тегов: Telegram их там не рисует.
В тексте можно: <b> <i> <u> <code> {name} {a} {b} {heart} {spark}

Чат показывает этот файл. После правки нужен перезапуск бота.
Цены, искра и эффекты считаются в других файлах. Здесь только слова.
"""

from __future__ import annotations

import re
import textwrap


def t(text) -> str:
    """Срезает пустые края у тройных кавычек, внутренние строки оставляет."""
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return "\n".join(line for line in (t(item) for item in text) if line)
    return textwrap.dedent(str(text)).strip("\n")


def say(key: str, **vals) -> str:
    tmpl = WORDS[key]
    return tmpl.format(**vals) if vals else tmpl


_TAG_RE = re.compile(r"<[^>]+>")
_EMOJI_RE = re.compile(r"<tg-emoji emoji-id=['\"](\d+)['\"]>(.*?)</tg-emoji>", re.I | re.S)


def plain(text) -> str:
    """Текст для кнопки, тоста и истории: без тегов, Telegram их там не рисует."""
    return " ".join(_TAG_RE.sub("", str(text or "")).split())


def emoji_id(tag: str) -> str:
    raw = str(tag or "").strip()
    match = _EMOJI_RE.search(raw)
    if match:
        return match.group(1)
    if raw.isdigit():
        return raw
    return ""


def b(*, text: str, icon: str = "", color: str = "default", go: str, data: str = "", when: str = "") -> dict:
    item = {
        "text": t(text),
        "go": go,
        "show": when or "always",
        "when": when,
        "style": color or "default",
        "color": color or "default",
        "data": data or ("mrg:" + go),
    }
    icon = t(icon)
    if icon:
        item["icon"] = icon
    return item


def msg(*, emoji: str, text: str = "", buttons=None, **more) -> dict:
    data = {
        "emoji": t(emoji),
        "text": t(text),
        "buttons": list(buttons or []),
    }
    for key, val in more.items():
        data[key] = t(val) if isinstance(val, (str, list, tuple)) else val
    return data


def iter_button_rows(buttons) -> list:
    out = []
    for row in buttons or []:
        if isinstance(row, dict) and row.get("repeat"):
            out.append(row)
        elif isinstance(row, dict):
            out.append([row])
        else:
            out.append(list(row))
    return out


def quoted(*buttons) -> str:
    parts = []
    for button in buttons:
        word = button["text"] if isinstance(button, dict) else str(button)
        parts.append("«" + word + "»")
    return " ".join(parts)


def screen(name, text, buttons=None, emoji=""):
    """Кладёт экран в SCREENS и возвращает текст, чтобы старые имена жили."""
    body = msg(emoji=emoji or HEART, text=text, buttons=buttons)
    SCREENS[name] = body
    return body["text"]


def button_rows(name, show=(), **slots):
    """Ряды кнопок экрана. show — какие условные кнопки включить (feast, leave, play)."""
    flags = set(show or ())
    out = []
    for row in iter_button_rows(SCREENS[name]["buttons"]):
        built = []
        for button in row:
            when = button.get("when") or ""
            if when and when not in flags:
                continue
            text = str(button.get("text") or "")
            data = str(button.get("data") or "")
            if slots:
                text = text.format(**slots)
                data = data.format(**slots)
            built.append({
                "text": text,
                "data": data,
                "style": button.get("style") or button.get("color") or "default",
                "icon": emoji_id(button.get("icon") or ""),
            })
        if built:
            out.append(built)
    return out


# --- значки кнопок. Другие id не подставлять ---
RED_ID = "5388870246243274946"
DOT_ID = "5337017423906226569"
NO_ID = "5226660202035554522"
HEART = "<tg-emoji emoji-id='" + RED_ID + "'>❤</tg-emoji>"
SPARK = "<tg-emoji emoji-id='" + DOT_ID + "'>🔴</tg-emoji>"
NO_MARK = "<tg-emoji emoji-id='" + NO_ID + "'>❌</tg-emoji>"
HEARTS_SHELF = "💖"

# Часы по умолчанию, если в панели пусто. Луна с 21 включительно до 6. Рассвет с 6 до 10.
MOON_FROM, MOON_TO = 21, 6
DAWN_FROM, DAWN_TO = 6, 10


# Кнопки не спрятаны выше. Каждая написана под своим сообщением, в SCREENS.


# ===========================================================================
# Короткие тексты экранов помощи. Человек их тоже видит.
# ===========================================================================

HELP_PAY = "Платит тот, кто написал «брак»."
HELP_CMD = "Мой брак"


def _line(body: str) -> str:
    """Одна фраза: знак и текст, как человек увидит сообщение."""
    return HEART + " " + t(body)


# ===========================================================================
# Экраны. У каждого: целый текст, потом кнопки.
# ===========================================================================

SCREENS = {

    "ask_free": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} зовёт {b}</b>
        <i>Бесплатно. {which} из {free}. «Согласиться» «Отказать» «Отменить заявку» · {minutes} мин.</i>
        """,
        buttons=[
            [
                b(text="Отказать", icon=NO_MARK, color="danger", go="no", data="mrg:no:{book_id}"),
                b(text="Согласиться", icon=HEART, color="success", go="yes", data="mrg:yes:{book_id}"),
            ],
            [
                b(text="Отменить заявку", color="primary", go="stop", data="mrg:stop:{book_id}"),
            ],
        ],
    ),

    "ask_paid": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} зовёт {b}</b>
        <i>{price} кут. Свадьба {which}. «Согласиться» «Отказать» · {minutes} мин.</i>
        """,
        buttons=[
            [
                b(text="Отказать", icon=NO_MARK, color="danger", go="no", data="mrg:no:{book_id}"),
                b(text="Согласиться", icon=HEART, color="success", go="yes", data="mrg:yes:{book_id}"),
            ],
            [
                b(text="Отменить заявку", color="primary", go="stop", data="mrg:stop:{book_id}"),
            ],
        ],
    ),

    "wed_free": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b} вместе</b>
        {spark} <i>Бесплатно. Каждому по {each}: своя половина.</i>
        """,
    ),

    "wed_paid": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b} вместе</b>
        {spark} <i>{price} кут. Каждому по {each}: своя половина.</i>
        """,
    ),

    "leave_ask": msg(
        emoji=HEART,
        text="""
        {heart} <b>Расторгнуть брак с {b}?</b>
        <i>Куты не вернутся.</i>
        """,
        buttons=[
            [
                b(text="Остаться", icon=HEART, color="success", go="stay", data="mrg:stay:{token}"),
                b(text="Развестись", icon=NO_MARK, color="danger", go="leave", data="mrg:leave:{token}"),
            ],
        ],
    ),

    "private": msg(emoji=HEART, text=_line("""<b>Отношения живут в группе.</b>""")),
    "project_off": msg(emoji=HEART, text=_line("""<b>Отношения в проекте выключены.</b>""")),
    "off": msg(emoji=HEART, text=_line("""<b>В этой группе отношения выключены.</b>""")),
    "on_ok": msg(emoji=HEART, text=_line("""<b>Отношения в группе включены.</b>""")),
    "off_ok": msg(emoji=HEART, text=_line("""<b>Отношения в группе выключены.</b>""")),
    "on_already": msg(emoji=HEART, text=_line("""<i>Отношения здесь уже включены.</i>""")),
    "off_already": msg(emoji=HEART, text=_line("""<i>Отношения здесь уже выключены.</i>""")),
    "creator_only": msg(emoji=HEART, text=_line("""<b>+браки и -браки пишет создатель группы.</b>""")),
    "need_reply": msg(emoji=HEART, text=_line("""<b>Ответьте «брак» на сообщение.</b> <i>{minutes} мин.</i>""")),
    "not_found": msg(emoji=HEART, text=_line("""<b>Не вижу, кого звать.</b>""")),
    "bot": msg(emoji=HEART, text=_line("""<b>Бота в брак не зовут.</b>""")),
    "self": msg(emoji=HEART, text=_line("""<b>Себя позвать нельзя.</b>""")),

    "already_you": msg(emoji=HEART, text=_line("""<b>Вы уже в браке с {b}.</b>""")),
    "already_them": msg(emoji=HEART, text=_line("""<b>{b} уже в браке.</b>""")),
    "busy": msg(emoji=HEART, text=_line("""<b>Сейчас заявка уже есть.</b>""")),
    "poor": msg(emoji=HEART, text=_line("""<b>Нужно {price} кут, у вас {have}.</b>""")),
    "poor_late": msg(emoji=HEART, text=_line("""<b>К согласию не хватило {price} кут.</b>""")),
    "not_married": msg(emoji=HEART, text=_line("""<b>Брака нет.</b> <i>Ответьте «брак» на сообщение. Награда: огонёк на двоих.</i>""")),
    "tone_old": msg(emoji=HEART, text=_line("""<b>Этот брак из старой книги.</b>""")),

    "expired": msg(emoji=HEART, text=_line("""<b>{minutes} мин. Заявка закрыта.</b>""")),
    "stopped": msg(emoji=HEART, text=_line("""<b>Заявку отменили. Куты не списаны.</b>""")),
    "refused": msg(emoji=HEART, text=_line("""<b>{b} отказал(а). Куты не списаны.</b>""")),
    "skip_ok": msg(emoji=HEART, text=_line("""<i>Жест не отправлен.</i>""")),
    "stay_ok": msg(emoji=HEART, text=_line("""<b>Вы остались вместе.</b>""")),

    "till_closed": msg(emoji=HEART, text=_line("""<b>Куты не приняты. Заявка закрыта.</b>""")),
    "leave_ok": msg(emoji=HEART, text=_line("""<b>{a} и {b} больше не вместе.</b>""")),
    "leave_them": msg(emoji=HEART, text=_line("""<b>{a} расторг(ла) брак.</b>""")),
    "rp_tomorrow": msg(emoji=HEART, text=_line("""<b>{title} уже в вашей половине сегодня.</b>""")),
    "rp_poor": msg(emoji=HEART, text=_line("""<b>{title}: {price} кут, у вас {have}.</b>""")),
    "rp_pay": msg(
        emoji=HEART,
        text=_line("""<b>{title} · {price} кут</b>"""),
        buttons=[
            [
                b(text="Списать {amount} кут", icon=HEART, color="success", go="pay", data="mrg:pay:{verb_id}"),
            ],
            [
                b(text="Не сейчас", color="default", go="skip", data="mrg:skip:{verb_id}"),
            ],
        ],
    ),

    "top_empty": msg(emoji=HEART, text=_line("""<b>В этой группе пока нет пар.</b>""")),
    "top": msg(
        emoji=HEART,
        text=_line("""<b>Кто вместе дольше</b>"""),
        buttons=[
            [
                b(text="Мой брак", color="default", go="mine", data="mrg:mine:0"),
                b(text="Пары", color="primary", go="list", data="mrg:list:0"),
            ],
        ],
    ),
    "list": msg(
        emoji=HEART,
        text=_line("""<b>Пары этой группы</b>"""),
        buttons=[
            [
                b(text="Мой брак", color="default", go="mine", data="mrg:mine:0"),
                b(text="Топ", color="primary", go="top", data="mrg:top:0"),
            ],
        ],
    ),

    "rp_need": msg(emoji=HEART, text=_line("""<b>Сначала брак.</b> <i>Ответьте «брак» на сообщение.</i>""")),
    "rp_pair": msg(emoji=HEART, text=_line("""<b>Жест пишут своей паре.</b>""")),
    "rp_done": msg(emoji=HEART, text=_line("""<b>Это слово уже в вашей половине.</b>""")),
    "rp_wait": msg(
        emoji=HEART,
        text=_line("""<b>⏳ {title}</b> <i>снова через {left}. Искры на месте.</i>"""),
    ),

    "what": msg(
        emoji=HEART,
        text=_line("""
        <b>Что это</b>
        <i>Огонёк на двоих. Каждый день оба закрывают свою часть лимита.</i>
        <i>Напишите паре доброе слово. День станет длиннее.</i>
        """),
        buttons=[
            [b(text="Как", icon=HEART, color="primary", go="how", data="mrg:use:0")],
            [b(text="Лимит", icon=SPARK, color="default", go="fire", data="mrg:fire:0", when="play")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    "how": msg(
        emoji=HEART,
        text=_line("""
        <b>Как</b>
        <i>Ответьте паре: обнять, поцеловать, пожалеть, принести чай.</i>
        <i>Искры падают вам. День закроется, когда готовы оба.</i>
        """),
        buttons=[
            [b(text="Слово паре", icon=HEART, color="primary", go="care", data="mrg:care:0", when="play")],
            [b(text="Лимит", icon=SPARK, color="default", go="fire", data="mrg:fire:0", when="play")],
            [
                b(text="Что это", color="default", go="what", data="mrg:what:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    "hold": msg(
        emoji=HEART,
        text=_line("""
        <b>Забыл</b>
        <i>Не закрыли свою часть — огонёк тухнет.</i>
        <i>Вчера ещё живо. Срок написан на «Лимит», это сегодня до этого часа.</i>
        """),
        buttons=[
            [b(text="Лимит", icon=SPARK, color="primary", go="fire", data="mrg:fire:0", when="play")],
            [
                b(text="Как", color="default", go="how", data="mrg:use:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    "gest_help": msg(
        emoji=HEART,
        text=HEART + " " + t("""<b>Слово паре</b>""") + "\n" + SPARK + " " + t("""
        <i>Искры — в вашу половину. Оба закрыли свою — день в серии.</i>
        """),
        buttons=[
            [
                b(text="Забыл", color="default", go="hold", data="mrg:hold:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),

    # «Праздник» виден, когда праздник открыт. «Расторгнуть» — когда брак можно закрыть.
    # Строки под именами — CARD_HEAD и дальше, в этом же файле.
    "card": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b}</b>
        """,
        buttons=[
            [b(text="Праздник", icon=HEART, color="primary", go="feast", data="mrg:feast:0", when="feast")],
            [
                b(text="Слово паре", icon=HEART, color="primary", go="gest", data="mrg:gest:{token}"),
                b(text="Магазин", icon=HEART, color="primary", go="bag", data="mrg:bag:0"),
            ],
            [
                b(text="Лимит", icon=SPARK, color="default", go="fire", data="mrg:fire:0"),
                b(text="Награды", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [
                b(text="Что это", color="default", go="what", data="mrg:what:0"),
                b(text="Как", color="default", go="how", data="mrg:use:0"),
            ],
            [
                b(text="Забыл", color="default", go="hold", data="mrg:hold:0"),
                b(text="Всего", color="default", go="stat", data="mrg:stat:0"),
            ],
            [b(text="Лента", color="default", go="rib", data="mrg:rib:0")],
            [b(text="Расторгнуть", icon=NO_MARK, color="danger", go="warn", data="mrg:warn:{token}", when="leave")],
        ],
    ),

    "tone": msg(
        emoji=SPARK,
        text="""
        {spark} <b>Лимит</b>
        <i>Общий лимит делится надвое. Закройте свою — искры приходят словом паре.</i>
        """,
        buttons=[
            [b(text="Обнять", icon=HEART, color="primary", go="hug", data="mrg:act:hug:{token}")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),

    "gest": msg(
        emoji=SPARK,
        text="""
        {emoji} <b>{a}</b> {does} <b>{b}</b>{note}
        """,
        buttons=[
            [
                b(text="Обнять", icon=HEART, color="primary", go="hug", data="mrg:act:hug:{token}"),
                b(text="Поцеловать", icon=HEART, color="primary", go="kiss", data="mrg:act:kiss:{token}"),
            ],
            [
                b(text="Чмок", icon=HEART, color="primary", go="peck", data="mrg:act:peck:{token}"),
                b(text="Воздушный", icon=HEART, color="primary", go="air", data="mrg:act:air:{token}"),
            ],
            [
                b(text="Похвалить", icon=HEART, color="primary", go="praise", data="mrg:act:praise:{token}"),
                b(text="Погладить", icon=HEART, color="primary", go="stroke", data="mrg:act:stroke:{token}"),
            ],
            [
                b(text="Роза", icon=HEART, color="primary", go="rose", data="mrg:act:rose:{token}"),
                b(text="Комплимент", icon=HEART, color="primary", go="compliment", data="mrg:act:compliment:{token}"),
            ],
            [
                b(text="За руку", icon=HEART, color="primary", go="hand", data="mrg:act:hand:{token}"),
                b(text="На ночь", icon=HEART, color="primary", go="night", data="mrg:act:night:{token}"),
            ],
            [
                b(text="Забыл", color="default", go="hold", data="mrg:hold:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),

    # Кнопки экранов с числами. Сам текст собирается из строк ниже: числа пары живые.
    "spark_nav": msg(
        emoji=SPARK,
        text=_line("""<b>Лимит</b> <i>Одно число на двоих. Каждому своя часть.</i>"""),
        buttons=[
            [b(text="Слово паре", icon=HEART, color="primary", go="care", data="mrg:care:0", when="play")],
            [
                b(text="Как", color="default", go="how", data="mrg:use:0"),
                b(text="Награды", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    "level_nav": msg(
        emoji=SPARK,
        text=_line("""<b>Награды</b> <i>Больше дней вместе — больше лимит и дар.</i>"""),
        buttons=[
            [
                b(text="Лимит", icon=SPARK, color="default", go="fire", data="mrg:fire:0"),
                b(text="Что это", color="default", go="what", data="mrg:what:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    "stat_nav": msg(
        emoji=HEART,
        text=_line("""<b>Всего</b> <i>Сколько искр уже легло в огонёк.</i>"""),
        buttons=[
            [
                b(text="Лимит", icon=SPARK, color="default", go="fire", data="mrg:fire:0"),
                b(text="Награды", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),

    "ribbon_ask": msg(
        emoji=HEART,
        text="""
        🎀 <b>Снять ленту?</b>
        <i>Брак останется.</i>
        """,
        buttons=[
            [
                b(text="Снять", icon=NO_MARK, color="danger", go="riboff", data="mrg:rib:off"),
                b(text="Оставить", icon=HEART, color="success", go="ribstay", data="mrg:rib:stay"),
            ],
        ],
    ),
    "ribbon_worn": msg(
        emoji=HEART,
        text="""
        🎀 <b>Лента на вас</b>
        """,
        buttons=[
            [b(text="Снять ленту", icon=NO_MARK, color="danger", go="ribask", data="mrg:rib:ask")],
            [
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
                b(text="Магазин", icon=HEART, color="default", go="bag", data="mrg:bag:0"),
            ],
        ],
    ),
    "ribbon_none": msg(
        emoji=HEART,
        text="""
        🎀 <b>Ленты нет</b>
        <i>Своя, в предметах.</i>
        """,
        buttons=[
            [
                b(text="Магазин", icon=HEART, color="default", go="bag", data="mrg:bag:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    "back": msg(
        emoji=HEART,
        text="""
        К паре
        """,
        buttons=[
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),

    "shop": msg(
        emoji=HEART,
        text=_line("""
        <b>Магазин</b>
        <i>Те же вещи, что в общем магазине. Цена оттуда.</i>
        """),
        buttons=[
            [b(text="Искры", icon=SPARK, color="primary", go="shelf_fire", data="mrg:bag:fire")],
            [
                b(text="Знак", icon=HEART, color="default", go="shelf_mark", data="mrg:bag:mark"),
                b(text="Ужин", icon=HEART, color="default", go="shelf_meal", data="mrg:bag:meal"),
            ],
            [b(text="Тихий день", color="default", go="shelf_quiet", data="mrg:bag:quiet")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    "shop_back": msg(
        emoji=HEART,
        text="""
        Все предметы
        """,
        buttons=[
            [b(text="Все предметы", color="primary", go="shop", data="mrg:bag:0")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),

    "feast": msg(
        emoji=HEART,
        text="""
        {heart} <b>Праздник</b>
        <b>{name}</b>
        <i>{aura} Выберите один дар. Он откроется, когда оба назовут одно и то же.</i>
        """,
        buttons=[
            [b(text="Конверт", icon=HEART, color="primary", go="envelope", data="mrg:wish:envelope")],
            [b(text="Забота", icon=HEART, color="primary", go="care_prize", data="mrg:wish:care")],
            [b(text="Лента", icon=HEART, color="primary", go="ribbon_prize", data="mrg:wish:ribbon")],
            [b(text="Премиум 3 мес.", icon=HEART, color="primary", go="premium3", data="mrg:wish:premium3")],
            [b(text="Премиум 6 мес.", icon=HEART, color="primary", go="premium6", data="mrg:wish:premium6")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),


    # ===========================================================================
    # Предметы. У каждого: сообщение, под ним кнопки, used= — фраза, когда сработал.
    # ===========================================================================

    "item_glow": msg(
        emoji="""🎇""",
        text="""
        🎇 <b>Блик брака</b>
        <i>Создан для увеличения лимита поддержки в отношениях на {n} {acc}.</i>
        """,
        buttons=[
            [
                b(text="Купить блик", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:glow"),
                b(text="Зажечь", icon=HEART, color="primary", go="guse", data="mrg:guse:glow"),
            ],
        ],
        used="Вам добавилось 3 заботы.",
        title="Блик брака",
        name1="mrgglow",
        price=12,
        care=3,
        effect="self",
    ),

    "item_candle": msg(
        emoji="""🕯""",
        text="""
        🕯 <b>Свеча брака</b>
        <i>Создана для увеличения лимита поддержки на {n} {acc}.</i>
        """,
        buttons=[
            [
                b(text="Купить свечу", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:candle"),
                b(text="Зажечь", icon=HEART, color="primary", go="guse", data="mrg:guse:candle"),
            ],
        ],
        used="Вам добавилось 8 забот.",
        title="Свеча брака",
        name1="mrgcandle",
        price=25,
        care=8,
        effect="self",
    ),

    "item_hearth": msg(
        emoji="""🎆""",
        text="""
        🎆 <b>Очаг брака</b>
        <i>Создан для увеличения лимита на {n} {acc}.</i>
        """,
        buttons=[
            [
                b(text="Купить очаг", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:hearth"),
                b(text="Разжечь", icon=HEART, color="primary", go="guse", data="mrg:guse:hearth"),
            ],
        ],
        used="Вам добавилось 20 забот.",
        title="Очаг брака",
        name1="mrghearth",
        price=70,
        care=20,
        effect="self",
    ),

    "item_match": msg(
        emoji="""🪔""",
        text="""
        🪔 <b>Спичка брака</b>
        <i>Если вчера вы не успели поддержать отношения искрой, спичка заполняет вашу половину поддержки.</i>
        """,
        buttons=[
            [
                b(text="Купить спичку", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:match"),
                b(text="Чиркнуть", icon=HEART, color="primary", go="guse", data="mrg:guse:match"),
            ],
        ],
        used="Ваша вчерашняя часть закрыта.",
        title="Спичка брака",
        name1="mrgmatch",
        price=80,
        care=0,
        effect="gap",
    ),

    "item_ribbon": msg(
        emoji="""🎀""",
        text="""
        🎀 <b>Лента брака</b>
        <i>Повесьте ленту на себя. В профиле будет видно, что вы находитесь в отношениях.</i>
        """,
        buttons=[
            [
                b(text="Купить ленту", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:ribbon"),
                b(text="Надеть", icon=HEART, color="primary", go="guse", data="mrg:guse:ribbon"),
            ],
        ],
        used="Лента теперь на вас. В профиле видно, что вы в браке.",
        title="Лента брака",
        name1="mrribbon",
        price=150,
        care=0,
        effect="mark",
    ),

    "item_tulip": msg(
        emoji="""🌷""",
        text="""
        🌷 <b>Тюльпан брака</b>
        <i>Создан для увеличения лимита поддержки партнёра на {n} {acc}.</i>
        """,
        buttons=[
            [
                b(text="Купить тюльпан", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:tulip"),
                b(text="Отдать", icon=HEART, color="primary", go="guse", data="mrg:guse:tulip"),
            ],
        ],
        used="Партнёру добавилось 5 забот. Цветок теперь в руках партнёра.",
        title="Тюльпан брака",
        name1="mrgtulip",
        price=18,
        care=5,
        effect="other",
    ),

    "item_honey": msg(
        emoji="""🍯""",
        text="""
        🍯 <b>Мёд брака</b>
        <i>Создан для увеличения лимита поддержки двоих на {n} {acc}. Проводите время вместе, как настоящая семья.</i>
        """,
        buttons=[
            [
                b(text="Купить мёд", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:honey"),
                b(text="Открыть", icon=HEART, color="primary", go="guse", data="mrg:guse:honey"),
            ],
        ],
        used="Вам и партнёру добавилось по 4 заботы.",
        title="Мёд брака",
        name1="mrghoney",
        price=30,
        care=4,
        effect="both",
    ),

    "item_moon": msg(
        emoji="""🌙""",
        text="""
        🌙 <b>Луна брака</b>
        <i>Ночной светильник. Работает только с {moon_from} до {moon_to} по Москве и медленно заполняет вашу половину поддержки за сегодня.</i>
        """,
        buttons=[
            [
                b(text="Купить луну", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:moon"),
                b(text="Поставить", icon=HEART, color="primary", go="guse", data="mrg:guse:moon"),
            ],
        ],
        used="Ночь. Ваша часть на сегодня закрыта.",
        title="Луна брака",
        name1="mrgmoon",
        price=95,
        care=0,
        effect="norm",
    ),

    "item_dawn": msg(
        emoji="""🌄""",
        text="""
        🌄 <b>Рассвет брака</b>
        <i>Декоративная иллюстрация, которая помогает вспомнить тёплые времена отношений. Сработает, только если вчерашний день ещё можно спасти. Вам добавится {n} {nom}.</i>
        """,
        buttons=[
            [
                b(text="Купить рассвет", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:dawn"),
                b(text="Встретить", icon=HEART, color="primary", go="guse", data="mrg:guse:dawn"),
            ],
        ],
        used="Утро. Вам добавилось 6 забот.",
        title="Рассвет брака",
        name1="mrgdawn",
        price=32,
        care=6,
        effect="dawn",
    ),

    "item_vow": msg(
        emoji="""📃""",
        text="""
        📃 <b>Клятва брака</b>
        <i>Используется один раз за все отношения. При использовании ответьте на сообщение партнёра.</i>
        """,
        buttons=[
            [
                b(text="Купить клятву", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:vow"),
                b(text="Прочитать", icon=HEART, color="primary", go="guse", data="mrg:guse:vow"),
            ],
        ],
        used="Клятва прочитана. Это можно сделать только один раз.",
        title="Клятва брака",
        name1="mrgvow",
        price=48,
        care=0,
        effect="vow",
    ),

    "item_propose": msg(
        emoji="""💠""",
        text="""
        💠 <b>Предложение</b>
        <i>Сделайте предложение руки и сердца своему партнёру.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:propose"),
                b(text="Сказать", icon=HEART, color="primary", go="guse", data="mrg:guse:propose"),
            ],
        ],
        used="Вы сделали предложение. Теперь можно подарить кольцо.",
        title="Предложение",
        name1="mrgpropose",
        price=60,
        care=0,
        effect="propose",
    ),

    "item_band": msg(
        emoji="""💎""",
        text="""
        💎 <b>Брачное кольцо</b>
        <i>Сделайте предложение руки и сердца своему партнёру, и вы станете семьёй.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:band"),
                b(text="Надеть", icon=HEART, color="primary", go="guse", data="mrg:guse:band"),
            ],
        ],
        used="Кольцо теперь у партнёра. Вы стали семьёй.",
        title="Брачное кольцо",
        name1="mrgband",
        price=180,
        care=0,
        effect="ring",
    ),

    "item_seedcuke": msg(
        emoji="""🌱🥒""",
        text="""
        🌱🥒 <b>Саженец огурца</b>
        <i>Посадите саженец на ферме. Спустя время вырастет то, что можно использовать в крафте.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:seedcuke"),
                b(text="На ферму", icon=HEART, color="primary", go="guse", data="mrg:guse:seedcuke"),
            ],
        ],
        used="Саженец сажают на ферме.",
        title="Саженец огурца",
        name1="mrgseedcuke",
        price=15,
        care=0,
        effect="seed",
        craft="Ферма: 30 минут и 3 полива. Урожай — огурец.",
        on=True,
        growMin=30,
        waters=3,
    ),

    "item_seedtom": msg(
        emoji="""🌱🍅""",
        text="""
        🌱🍅 <b>Саженец помидора</b>
        <i>Посадите саженец на ферме. Спустя время вырастет то, что можно использовать в крафте.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:seedtom"),
                b(text="На ферму", icon=HEART, color="primary", go="guse", data="mrg:guse:seedtom"),
            ],
        ],
        used="Саженец сажают на ферме.",
        title="Саженец помидора",
        name1="mrgseedtom",
        price=15,
        care=0,
        effect="seed",
        craft="Ферма: 30 минут и 3 полива. Урожай — помидор.",
        on=True,
        growMin=30,
        waters=3,
    ),

    "item_seedcab": msg(
        emoji="""🌱🥬""",
        text="""
        🌱🥬 <b>Саженец капусты</b>
        <i>Посадите саженец на ферме. Спустя время вырастет то, что можно использовать в крафте.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:seedcab"),
                b(text="На ферму", icon=HEART, color="primary", go="guse", data="mrg:guse:seedcab"),
            ],
        ],
        used="Саженец сажают на ферме.",
        title="Саженец капусты",
        name1="mrgseedcab",
        price=15,
        care=0,
        effect="seed",
        craft="Ферма: 30 минут и 3 полива. Урожай — капуста.",
        on=True,
        growMin=30,
        waters=3,
    ),

    "item_cuke": msg(
        emoji="""🥒""",
        text="""
        🥒 <b>Огурец</b>
        <i>Это еда. Из неё через крафт готовят что-то интересное.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:cuke"),
                b(text="В крафт", icon=HEART, color="primary", go="guse", data="mrg:guse:cuke"),
            ],
        ],
        used="Огурец ждёт тарелку.",
        title="Огурец",
        name1="mrgcuke",
        price=0,
        care=0,
        effect="pantry",
        craft="Крафт: сок с помидором, салат с помидором и капустой.",
        on=False,
    ),

    "item_tom": msg(
        emoji="""🍅""",
        text="""
        🍅 <b>Помидор</b>
        <i>Это еда. Из неё через крафт готовят что-то интересное.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:tom"),
                b(text="В крафт", icon=HEART, color="primary", go="guse", data="mrg:guse:tom"),
            ],
        ],
        used="Помидор ждёт тарелку.",
        title="Помидор",
        name1="mrgtom",
        price=0,
        care=0,
        effect="pantry",
        craft="Крафт: сок с огурцом, суп с капустой, салат со всеми тремя.",
        on=False,
    ),

    "item_cab": msg(
        emoji="""🥬""",
        text="""
        🥬 <b>Капуста</b>
        <i>Это еда. Из неё через крафт готовят что-то интересное.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:cab"),
                b(text="В крафт", icon=HEART, color="primary", go="guse", data="mrg:guse:cab"),
            ],
        ],
        used="Капуста ждёт тарелку.",
        title="Капуста",
        name1="mrgcab",
        price=0,
        care=0,
        effect="pantry",
        craft="Крафт: суп с помидором, салат с огурцом и помидором.",
        on=False,
    ),

    "item_juice": msg(
        emoji="""🥤""",
        text="""
        🥤 <b>Сок вдвоём</b>
        <i>Еда, которую вы едите вместе. Обоим добавится от {food_from} до {food_to} {food_word} в отношениях.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:juice"),
                b(text="Выпить", icon=HEART, color="primary", go="guse", data="mrg:guse:juice"),
            ],
        ],
        used="Обоим по +8.",
        title="Сок вдвоём",
        name1="mrgjuice",
        price=0,
        care=8,
        effect="both",
        craft="Огурец + помидор.",
        on=False,
    ),

    "item_soup": msg(
        emoji="""🍲""",
        text="""
        🍲 <b>Суп вдвоём</b>
        <i>Еда, которую вы едите вместе. Обоим добавится от {food_from} до {food_to} {food_word} в отношениях.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:soup"),
                b(text="Съесть", icon=HEART, color="primary", go="guse", data="mrg:guse:soup"),
            ],
        ],
        used="Обоим по +12.",
        title="Суп вдвоём",
        name1="mrgsoup",
        price=0,
        care=12,
        effect="both",
        craft="Капуста + помидор.",
        on=False,
    ),

    "item_salad": msg(
        emoji="""🥗""",
        text="""
        🥗 <b>Салат вдвоём</b>
        <i>Еда, которую вы едите вместе. Обоим добавится от {food_from} до {food_to} {food_word} в отношениях.</i>
        """,
        buttons=[
            [
                b(text="Купить", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:salad"),
                b(text="Съесть", icon=HEART, color="primary", go="guse", data="mrg:guse:salad"),
            ],
        ],
        used="Обоим по +15. Ужин вместе.",
        title="Салат вдвоём",
        name1="mrgsalad",
        price=0,
        care=15,
        effect="both",
        craft="Огурец + помидор + капуста.",
        on=False,
    ),

    # Обряды. Кнопка одна: предмет уже у человека, покупать его не нужно.

    "rite_bouquet": msg(
        emoji="""💐""",
        text="""
        💐 <b>Букет</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Букет", icon=HEART, color="primary", go="guse", data="mrg:guse:bouquet"),
            ],
        ],
        used="",
        title="Букет",
        name1="mrgbouquet",
        rite=True,
        effect="bouquet",
    ),

    "rite_propose": msg(
        emoji="""💠""",
        text="""
        💠 <b>Колечко</b>
        <i>Сделайте предложение руки и сердца своему партнёру.</i>
        """,
        buttons=[
            [
                b(text="Колечко", icon=HEART, color="primary", go="guse", data="mrg:guse:propose"),
            ],
        ],
        used="",
        title="Колечко",
        name1="mrgpropose",
        rite=True,
        effect="propose",
    ),

    "rite_wedring": msg(
        emoji="""💎""",
        text="""
        💎 <b>Обручальное</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Кольцо", icon=HEART, color="primary", go="guse", data="mrg:guse:wedring"),
            ],
        ],
        used="",
        title="Обручальное",
        name1="mrgring",
        rite=True,
        effect="family",
    ),

    "rite_thread": msg(
        emoji="""🧵""",
        text="""
        🧵 <b>Красная нить</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Нить", icon=HEART, color="primary", go="guse", data="mrg:guse:thread"),
            ],
        ],
        used="",
        title="Красная нить",
        name1="mrgthread",
        rite=True,
        effect="thread",
    ),

    "item_quiet": msg(
        emoji="""🤫""",
        text="""
        🤫 <b>Тихий день</b>
        <i>Раз в неделю. Если вы не успели набрать свою часть, тихий день закрывает её за вас.</i>
        """,
        buttons=[
            [
                b(text="Купить тихий день", icon=HEART, color="success", go="gbuy", data="mrg:gbuy:quiet"),
                b(text="Затихнуть", icon=HEART, color="primary", go="guse", data="mrg:guse:quiet"),
            ],
        ],
        used="Тихий день закрыл вашу половину.",
        title="Тихий день",
        name1="mrgquiet",
        price=40,
        care=0,
        effect="quiet",
    ),
}


def _go(name: str, go: str) -> dict:
    """Кнопка экрана. Имена ниже только указывают на неё, текст живёт в экране."""
    for row in iter_button_rows(SCREENS[name]["buttons"]):
        for button in row:
            if button.get("go") == go:
                return button
    raise KeyError(name + ":" + go)


NO, YES, STOP = _go("ask_free", "no"), _go("ask_free", "yes"), _go("ask_free", "stop")
STAY, LEAVE = _go("leave_ask", "stay"), _go("leave_ask", "leave")
CARD_LEAVE = _go("card", "warn")
GEST, GIFT = _go("card", "gest"), _go("card", "bag")
TONE, LEVEL = _go("card", "fire"), _go("card", "lvl")
WHAT, HOW = _go("card", "what"), _go("card", "how")
HOLD, STAT = _go("card", "hold"), _go("card", "stat")
RIBBON, FEAST = _go("card", "rib"), _go("card", "feast")
BACK = _go("back", "mine")
MINE, LIST = _go("top", "mine"), _go("top", "list")
TOP = _go("list", "top")
SKIP, PAY = _go("rp_pay", "skip"), _go("rp_pay", "pay")
RIBBON_OFF_BTN = _go("ribbon_worn", "ribask")
RIBBON_DO, RIBBON_KEEP = _go("ribbon_ask", "riboff"), _go("ribbon_ask", "ribstay")
HUG = _go("tone", "hug")
GUIDE_GEST = _go("how", "care")

BTN_NO, BTN_YES, BTN_STOP = NO["text"], YES["text"], STOP["text"]
BTN_STAY, BTN_LEAVE, BTN_CARD_LEAVE = STAY["text"], LEAVE["text"], CARD_LEAVE["text"]
BTN_TONE, BTN_GEST, BTN_LEVEL = TONE["text"], GEST["text"], LEVEL["text"]
BTN_WHAT, BTN_HOW, BTN_HOLD = WHAT["text"], HOW["text"], HOLD["text"]
BTN_STAT, BTN_BACK, BTN_MINE = STAT["text"], BACK["text"], MINE["text"]
BTN_TOP, BTN_LIST, BTN_SKIP, BTN_GIFT = TOP["text"], LIST["text"], SKIP["text"], GIFT["text"]
BTN_FEAST = FEAST["text"]
BTN_RIBBON = RIBBON["text"]
BTN_RIBBON_OFF, BTN_RIBBON_DO, BTN_RIBBON_KEEP = RIBBON_OFF_BTN["text"], RIBBON_DO["text"], RIBBON_KEEP["text"]


def _shown(name: str) -> str:
    return SCREENS[name]["text"]


PROPOSE_FREE = _shown("ask_free")
PROPOSE_PAID = _shown("ask_paid")
WED_OK_FREE = _shown("wed_free")
WED_OK_PAID = _shown("wed_paid")
LEAVE_ASK = _shown("leave_ask")
PRIVATE = _shown("private")
PROJECT_OFF = _shown("project_off")
OFF = _shown("off")
ON_OK = _shown("on_ok")
OFF_OK = _shown("off_ok")
ON_ALREADY = _shown("on_already")
OFF_ALREADY = _shown("off_already")
CREATOR_ONLY = _shown("creator_only")
NEED_REPLY = _shown("need_reply")
NOT_FOUND = _shown("not_found")
BOT = _shown("bot")
SELF = _shown("self")
ALREADY_YOU = _shown("already_you")
ALREADY_THEM = _shown("already_them")
BUSY = _shown("busy")
POOR = _shown("poor")
POOR_LATE = _shown("poor_late")
NOT_MARRIED = _shown("not_married")
TONE_OLD = _shown("tone_old")
EXPIRED = _shown("expired")
STOPPED = _shown("stopped")
REFUSED = _shown("refused")
SKIP_OK = _shown("skip_ok")
STAY_OK = _shown("stay_ok")
TILL_CLOSED = _shown("till_closed")
LEAVE_OK = _shown("leave_ok")
LEAVE_THEM = _shown("leave_them")
RP_TOMORROW = _shown("rp_tomorrow")
RP_POOR = _shown("rp_poor")
RP_PAY_ASK = _shown("rp_pay")
TOP_EMPTY = _shown("top_empty")
TOP_TITLE = _shown("top")
LIST_TITLE = _shown("list")
TOP_ROW = "{n}. {a} и {b} · {span}"
LIST_ROW = "{n}. {a} и {b} · {meta}"
RP_NEED_WED = _shown("rp_need")
RP_ONLY_PAIR = _shown("rp_pair")
RP_DONE = _shown("rp_done")
RP_WAIT = _shown("rp_wait")
WHAT_TEXT = _shown("what")
HOW_TEXT = _shown("how")
HOLD_TEXT = _shown("hold")
GEST_TEXT = _shown("gest_help")
CARD_TEXT = _shown("card")


# ===========================================================================
# Короткие тексты. Человек их тоже видит.
# Тосты и подписи - правь внутри WORDS. Без тегов.
# Имена ниже только называют эти строки, чтобы старый код их находил.
# ===========================================================================

WORDS = {
    "retry": "Не прошло. Нажмите ещё раз.",
    "not_invited": "Отвечает только тот, кого позвали.",
    "not_payer": "Отменяет тот, кто написал «брак».",
    "not_pair": "Это чужая пара.",
    "closed": "Заявка уже закрыта.",
    "expired": "Время вышло. Куты не списаны.",
    "busy": "Кто-то из двоих уже занят заявкой.",
    "till": "Куты не списаны. Попробуйте позже.",
    "till_rp": "Куты не списаны. Нажмите ещё раз.",
    "no_marriage": "Брака нет. Ответьте «брак» на сообщение.",
    "off": "Отношения выключены.",
    "rp_today": "Этот жест сегодня уже был.",
    "poor_gift": "Кутов не хватает. Предмет не куплен.",
    "ribbon_locked": "Лента открывается в новом браке.",
    "ribbon_toast": "Лента снята.",
    "ribbon_note": "Лента на вас.",
    "player": "игрок",
    "partner": "партнёром",
    "keeper": "создатель",
    "item": "Предмет",
    "buy": "Купить",
    "use": "Использовать",
    "take": "Взять",
    "buy_price": "Купить {price}",
    "farm": "На ферму",
    "craft": "В крафт",
    "level": "Уровень",
    "support": "Поддержал отношения с {name}",
    "tone_ready": "Тонус {score} · сегодня уже учтён",
    "tone_now": "Тонус {score} · {label}",
    "tone_high": "в тонусе",
    "tone_mid": "спокойно",
    "tone_low": "тихо",
    "tone_cold": "остывает",
    "tone_up": "Жест сегодня поднимет тонус до {n}.",
    "tone_held": "Сегодня тонус уже {n}.",
    "spark_fading": "искра гаснет",
    "spark_out": "искра погасла",
    "spark_day": "искра {days}",
    "spark_new": "новая искра",
    "spark_family": "семья",
    "quiet_closed": "Тихий день закрыл вашу половину.",
    "rite_ready": "Готово.",
    "no_bond": "Брака нет.",
}

ALERT_RETRY = WORDS["retry"]
ALERT_NOT_INVITED = WORDS["not_invited"]
ALERT_NOT_PAYER = WORDS["not_payer"]
ALERT_NOT_PAIR = WORDS["not_pair"]
ALERT_CLOSED = WORDS["closed"]
ALERT_EXPIRED = WORDS["expired"]
ALERT_BUSY = WORDS["busy"]
ALERT_TILL = WORDS["till"]
ALERT_TILL_RP = WORDS["till_rp"]
ALERT_NO_MARRIAGE = WORDS["no_marriage"]
ALERT_OFF = WORDS["off"]
ALERT_RP_TODAY = WORDS["rp_today"]
POOR_GIFT = WORDS["poor_gift"]
RIBBON_LOCKED = WORDS["ribbon_locked"]
RIBBON_TOAST = WORDS["ribbon_toast"]
RIBBON_NOTE = WORDS["ribbon_note"]
PLAYER = WORDS["player"]
PARTNER_WORD = WORDS["partner"]
KEEPER_WORD = WORDS["keeper"]
ITEM_WORD = WORDS["item"]
BUY_WORD = WORDS["buy"]
USE_WORD = WORDS["use"]
TAKE_WORD = WORDS["take"]
BUY_PRICE = WORDS["buy_price"]
FARM_BTN = _go("item_seedcuke", "guse")["text"]
CRAFT_BTN = _go("item_cuke", "guse")["text"]
WORDS["farm"], WORDS["craft"] = FARM_BTN, CRAFT_BTN
LEVEL_WORD = WORDS["level"]
SUPPORT_LINE = WORDS["support"]
TONE_READY = WORDS["tone_ready"]
TONE_NOW = WORDS["tone_now"]
TONE_HIGH, TONE_MID, TONE_LOW, TONE_COLD = WORDS["tone_high"], WORDS["tone_mid"], WORDS["tone_low"], WORDS["tone_cold"]
TONE_UP = WORDS["tone_up"]
TONE_HELD = WORDS["tone_held"]
SPARK_FADING = WORDS["spark_fading"]
SPARK_OUT = WORDS["spark_out"]
SPARK_DAY = WORDS["spark_day"]
SPARK_NEW = WORDS["spark_new"]
SPARK_FAMILY = WORDS["spark_family"]
QUIET_CLOSED = WORDS["quiet_closed"]
RITE_READY = WORDS["rite_ready"]
NO_BOND = WORDS["no_bond"]

RITE_ALERT = {
    "bouquet": "Букетный период открыт.",
    "propose": "Вы сделали предложение.",
    "family": "Теперь у вас семейная жизнь.",
    "thread": "Нить держит пару, даже если искра погаснет.",
    "ahead": "Эта ступень уже открыта.",
}


# --- отказ предмета. {moon_from} и часы рассвета подставляются из панели ---

GIFT_ALERT = {
    "old": "Предметы откроются, когда брак будет новый.",
    "bad": "Такого предмета нет.",
    "none": "Этого предмета у вас нет.",
    "calm": "Спичка нужна, только если вчера вы не успели и день ещё можно спасти.",
    "full": "Ваша вчерашняя часть уже закрыта.",
    "worn": "Лента уже надета на вас.",
    "fade": "Сейчас этот предмет не поможет.",
    "ahead": "Это уже сделано.",
    "week": "Тихий день можно взять только один раз в неделю.",
    "late": "Рассвет работает, только если вчерашний день ещё можно спасти.",
    "day": "Сегодня это уже было.",
    "silent": "Сначала ответьте партнёру.",
    "done": "Ваша часть на сегодня уже закрыта.",
    "night": "Луна работает только с {moon_from} до {moon_to} по Москве.",
    "sun": "Рассвет работает только с {dawn_from} до {dawn_to} по Москве.",
    "sworn": "Клятву можно прочитать только один раз за весь брак.",
    "behind": "Партнёр и так не отстаёт.",
    "empty": "У вас ещё нет своей заботы.",
    "spare": "Лишней заботы нет.",
    "held": "Этот предмет уже работает.",
    "alive": "Ваши дни вместе ещё не пропали.",
    "gone": "Возвращать уже нечего.",
    "early": "Рано. Сначала вы оба должны закрыть сегодняшний день.",
    "heard": "Ответ уже есть.",
    "cold": "Дни вместе уже пропали.",
    "said": "Предложение уже сказано.",
    "wait": "Сначала сделайте предложение.",
    "giver": "Кольцо дарит тот, кто сделал предложение.",
    "kept": "Кольцо уже у вас.",
    "home": "Вы уже семья.",
    "away": "Партнёра ещё нет в игре.",
    "field": "Посадите этот саженец на ферме. В чате он не тратится.",
    "cook": "Сначала приготовьте из этого еду. Само оно заботу не даёт.",
}

SEED_LINE = "Посадите саженец на ферме. Спустя время вырастет то, что можно использовать в крафте."
DINNER_LINE = "Из урожая через крафт готовят еду, которую едят вместе."
PANTRY_LINE = "Это еда. Из неё через крафт готовят что-то интересное."
DISH_NEED = "Эту еду едят вместе."
DISH_NEED_SUB = "Сначала нужен живой брак."
DISH_OK = "Вы поели вместе. Забота добавилась обоим."


# Описание предмета — курсив в его экране item_… выше. {n} {acc} {nom} и часы подставляются сами.

def _italic(text):
    found = re.search(r"<i>(.*?)</i>", str(text or ""), re.S)
    return found.group(1).strip() if found else ""


ABOUT = {
    key.split("_", 1)[1]: _italic(SCREENS[key]["text"])
    for key in SCREENS
    if key.startswith("item_")
}

FOOD_SAME = "Еда, которую вы едите вместе. Обоим добавится {food_to} {food_word} в отношениях."

# Кто, кому и сколько. Число и слово «забота» подставляются.
CARE_YOU, CARE_MATE, CARE_BOTH = "Вам", "Партнёру", "Вам и партнёру"
CARE_ONE, CARE_FEW, CARE_MANY = "забота", "заботы", "забот"
CARE_GOT = "{who} добавилось {n} {word}."
CARE_GOT_EACH = "{who} добавилось по {n} {word}."
SPARK_ACC = ("искру", "искры", "искр")
SPARK_NOM = ("искра", "искры", "искр")

# Эти фразы показываются, когда предмет сработал. Число в строке — то, что у предмета в care.
TOUCH_MOON = SCREENS["item_moon"]["used"]
TOUCH_DAWN_PREFIX = "Утро. "
TOUCH_MATCH = SCREENS["item_match"]["used"]
TOUCH_VOW = SCREENS["item_vow"]["used"]
TOUCH_RIBBON = SCREENS["item_ribbon"]["used"]
TOUCH_PROPOSE = SCREENS["item_propose"]["used"]
TOUCH_RING = SCREENS["item_band"]["used"]
TOUCH_GLOW = SCREENS["item_glow"]["used"]
TOUCH_CANDLE = SCREENS["item_candle"]["used"]
TOUCH_HEARTH = SCREENS["item_hearth"]["used"]
TOUCH_TULIP = SCREENS["item_tulip"]["used"]
TOUCH_HONEY = SCREENS["item_honey"]["used"]
TOUCH_DAWN = SCREENS["item_dawn"]["used"]
TOUCH_SEED = SCREENS["item_seedcuke"]["used"]
TOUCH_CUKE = SCREENS["item_cuke"]["used"]
TOUCH_TOM = SCREENS["item_tom"]["used"]
TOUCH_CAB = SCREENS["item_cab"]["used"]
TOUCH_JUICE = SCREENS["item_juice"]["used"]
TOUCH_SOUP = SCREENS["item_soup"]["used"]
TOUCH_SALAD = SCREENS["item_salad"]["used"]


# --- праздник ---

FEAST_AURA = {
    7: "Семь дней вместе. Первый праздник вашей пары.",
    14: "Две недели вместе. День, который уже хочется отметить.",
    30: "Месяц вместе. Настоящий праздник.",
    100: "Сто дней вместе. Большой праздник ваших отношений.",
}
FEAST_TITLE = "Праздник"
FEAST_DAY = "День пары"
FEAST_GIFT = "Дар"
FEAST_REACHED = "Вы дошли до этого дня вместе."
FEAST_PICK = "Выберите один дар. Он откроется, когда оба назовут одно и то же."
FEAST_NONE = "Сейчас тишина между праздниками."
FEAST_EARLY = "Этот дар берегут до большого праздника, с месяца вместе."
FEAST_WAIT = "Ваш выбор сохранён. Дар откроется, когда партнёр назовёт то же."
FEAST_DIFFER = "Вы назвали разные дары. Праздник соберётся, когда выбор совпадёт."
FEAST_OFF = "Этот дар сейчас закрыт."
FEAST_BOOK = "Книга праздников сейчас закрыта."
FEAST_FUND_SHORT = "Праздничный фонд ещё не покрывает этот дар."
FEAST_KEEPER_EMPTY = "Премиум ещё не готов. Создатель видит это."
FEAST_ENVELOPE = "Праздничный конверт из фонда: {amount} кут."
FEAST_SORRY = "Дар не успели приготовить. Вместо него праздничный конверт."
FEAST_READY = "Праздничный дар уже у вас."
FEAST_KEEPER_OK = "Премиум готовит @{name}. Это торжественный дар проекта."
FEAST_KEEPER_HOLD = "{heart} <b>Праздник · {name}</b>\nПредмет премиума уже у вас. Передайте его паре сами. Бот Telegram Premium не используется."
FEAST_KEEPER_MISS = "{heart} <b>Праздник · {name}</b>\nПредмета премиума нет на складе или фонд его не покрыл. Передайте свой, если решите. Бот Telegram Premium не используется."

PRIZE_COPY = {
    "envelope": "Праздничный конверт. Если дар не успели приготовить, пара получает куты.",
    "care": "Праздничная забота. Блик, свеча или очаг — каждому из двоих.",
    "ribbon": "Праздничная лента. В профиле останется знак этих отношений.",
    "premium3": "Торжественный дар проекта на три месяца. Его передаёт создатель.",
    "premium6": "Большой праздник. Дар на шесть месяцев тоже передаёт создатель.",
}
PERIODS = (
    {"day": 7, "name": "Первая неделя"},
    {"day": 14, "name": "Две недели"},
    {"day": 30, "name": "Месяц"},
    {"day": 100, "name": "Сто дней"},
)
# Кнопка праздника — это name. Оба должны нажать одно и то же имя.
PRIZES = (
    {"id": "envelope", "name": _go("feast", "envelope")["text"], "emoji": "✉️", "on": True, "blurb": PRIZE_COPY["envelope"]},
    {"id": "care", "name": _go("feast", "care_prize")["text"], "emoji": "🕯", "on": True, "blurb": PRIZE_COPY["care"]},
    {"id": "ribbon", "name": _go("feast", "ribbon_prize")["text"], "emoji": "🎀", "on": True, "blurb": PRIZE_COPY["ribbon"]},
    {"id": "premium3", "name": _go("feast", "premium3")["text"], "emoji": "⭐", "on": True, "blurb": PRIZE_COPY["premium3"]},
    {"id": "premium6", "name": _go("feast", "premium6")["text"], "emoji": "🌟", "on": True, "blurb": PRIZE_COPY["premium6"]},
)
QUIET_NAME = "Тихий день"
QUIET_CODE = "mrgquiet"
QUIET_EMOJI = "🤫"
QUIET_BUY = _go("item_quiet", "gbuy")["text"]
QUIET_USE = _go("item_quiet", "guse")["text"]


# Старые короткие подписи. Если в базе ещё они, показываем новое простое описание.
OLD_ABOUT = {
    "glow": ("Вам +3 в руке. Лишнее остаётся на следующие дни.",),
    "candle": ("Вам +8. Лишнее остаётся на следующие дни.",),
    "hearth": ("Вам +20. Лишнее остаётся на следующие дни.",),
    "match": ("Пока искра гаснет: дожигает вашу вчерашнюю половину.",),
    "ribbon": ("Ваш знак в профиле. Партнёр покупает свою.",),
    "tulip": ("Партнёру +5. Лишнее остаётся у него.",),
    "honey": ("Обоим +4. Лишнее остаётся на следующие дни.",),
    "moon": ("С 21:00 до 6:00 добирает вашу норму. Лишнее не кладёт.",),
    "dawn": ("С 6:00 до 10:00, пока искра гаснет: вам +6.",),
    "vow": ("Один раз, после вашего ответа: добирает вашу норму.",),
    "propose": ("Один раз: статус «сделал предложение». После этого можно дарить кольцо.",),
    "band": ("После предложения. Кольцо остаётся у второго. Статус: семейная жизнь.",),
    "seedcuke": ("30 минут и 3 полива. Вырастет огурец.",),
    "seedtom": ("30 минут и 3 полива. Вырастет помидор.",),
    "seedcab": ("30 минут и 3 полива. Вырастет капуста.",),
    "cuke": ("Для ужина. Сам искру не даёт.",),
    "tom": ("Для ужина. Сам искру не даёт.",),
    "cab": ("Для ужина. Сам искру не даёт.",),
    "juice": ("Обоим по +8. Огурец и помидор.",),
    "soup": ("Обоим по +12. Капуста и помидор.",),
    "salad": ("Обоим по +15. Огурец, помидор и капуста.",),
    "quiet": ("Раз в 7 дней закрывает вашу половину, если не успели.",),
    "glow2": ("Возьмите в руке. Вам добавится 3 заботы. Лишнее останется на другие дни.",),
    "candle2": ("Зажгите свечу. Вам добавится 8 забот. Лишнее останется на другие дни.",),
    "hearth2": ("Разожгите очаг. Вам добавится 20 забот. Лишнее останется на другие дни.",),
    "match2": ("Если вчера вы не успели и день ещё можно спасти, спичка добивает вашу часть.",),
    "ribbon2": ("Надевается только на вас. В профиле будет видно, что вы в браке. У партнёра своя лента.",),
    "tulip2": ("Отдайте цветок партнёру. Ему добавится 5 забот. Лишнее останется у него.",),
    "honey2": ("Съешьте вместе. Вам и партнёру добавится по 4 заботы. Лишнее останется на другие дни.",),
    "moon2": ("Только ночью, с 21:00 до 6:00. Добивает вашу часть на сегодня. Лишнего не добавляет.",),
    "dawn2": ("Только утром, с 6:00 до 10:00, и только если вчерашний день ещё можно спасти. Вам добавится 6 забот.",),
    "vow2": ("Только один раз за весь брак. Сначала ответьте партнёру. Потом добьёт вашу часть на сегодня.",),
    "propose2": ("Скажите один раз. После этого можно подарить кольцо.",),
    "band2": ("Сначала сделайте предложение. Кольцо останется у партнёра. Потом вы станете семьёй.",),
    "seed2": ("Посадите на ферме. Растёт 30 минут. Полить нужно 3 раза. Вырастет огурец.", "Посадите на ферме. Растёт 30 минут. Полить нужно 3 раза. Вырастет помидор.", "Посадите на ферме. Растёт 30 минут. Полить нужно 3 раза. Вырастет капуста."),
    "pantry2": ("Само заботу не даёт. Нужен, чтобы приготовить сок или салат.", "Само заботу не даёт. Нужен для сока, супа и салата.", "Само заботу не даёт. Нужен, чтобы приготовить суп или салат."),
    "juice2": ("Выпейте вместе. Вам и партнёру добавится по 8 забот. Готовится из огурца и помидора.",),
    "soup2": ("Съешьте вместе. Вам и партнёру добавится по 12 забот. Готовится из капусты и помидора.",),
    "salad2": ("Съешьте вместе. Вам и партнёру добавится по 15 забот. Нужны огурец, помидор и капуста.",),
}


# --- карточка, искра, лента. {heart} и {spark} подставляются ---

HELP_PAGE = (
    "{heart}\n<code>" + HELP_CMD + "</code>\n"
    "<i>{pay} {ladder} «{yes}» «{no}»</i>\n"
    "{spark} искра тонус «{level}» — по {each}"
)
PROFILE_EMPTY = "{heart} Брака нет. Ответьте «брак» на сообщение человека. Награда: огонёк на двоих."
PROFILE_WITH = "{mark} В браке с {name} · {span}"
PROFILE_TONE = " · {tone}"
TONE_LINE = "{spark} <b>Тонус {score} · {label}</b>{tail}"
PAIR_LINE = "Вы {you} из {need} · {partner} {other} из {need}"
SPARE_LINE = "Запас: ты {yours} · {partner} {theirs}"
SPARE_DAYS = " · ещё {ahead} дн."
LIMIT_LINE = "<i>Лимит {goal}. Половина каждому {need}.</i>"
LIMIT_HEAD = "<b>Лимит {goal}</b> <i>каждому по {need}</i>"
BAR_ON = "●"
BAR_OFF = "○"
METER_LINE = "<b>{who}</b> {bar}"
METER_READY = "готово"
METER_LEFT = "ещё {left}"
METER_EXTRA = "+{extra}"
STEP_YOU = "<i>✦ вам ещё {left} · напишите паре</i>"
STEP_THEM = "<i>✦ вы готовы · паре ещё {left}</i>"
STEP_FIRST_YOU = "<i>⏳ {when} · вам ещё {left} · первый огонёк</i>"
STEP_FIRST_THEM = "<i>⏳ {when} · паре ещё {left} · вы готовы · первый огонёк</i>"
STEP_FIRST_BOTH = "<i>⏳ {when} · вам {you} · паре {them} · первый огонёк</i>"
STEP_FIRST_WAIT = "<i>⏳ {when} · обе части уже есть</i>"
STEP_OPEN_YOU = "<i>⏳ {when} · вам ещё {left} · иначе огонёк тухнет</i>"
STEP_OPEN_THEM = "<i>⏳ {when} · паре ещё {left} · вы готовы</i>"
STEP_OPEN_BOTH = "<i>⏳ {when} · вам {you} · паре {them}</i>"
STEP_OPEN_WAIT = "<i>⏳ {when} · обе части уже есть</i>"
HOME_YOU = "<i>Вам ещё {left}. «Слово паре» — искры в вашу половину.</i>"
HOME_THEM = "<i>Ваша половина есть. Ждём половину пары.</i>"
NEXT_GIFT = "<i>🎁 день {day} · {name}</i>"
WAS_LINE = "<i>Серия была {n} {word}. Вы уже не чужие.</i>"
WAS_SHORT = "<i>Было {n} {word}. Вы уже не чужие.</i>"
CARD_HEAD = "{heart} <b>{a} и {b}</b>"
CARD_TOGETHER = "<b>Вместе {span}</b>"
CARD_DATE = "<i>{date}</i>"
CARD_TONE = "<i>{tone}</i>"
CLOCK_WORD = "12:00"
WHEN_TODAY = "сегодня до {clock}"
SPARK_ZERO = "{spark} <b>С нуля · {level}</b>"
SPARK_FADE = "{spark} <b>Гаснет · {days}</b>"
SPARK_YESTERDAY = "<i>До {clock} закройте вчерашнюю половину.</i>"
SPARK_LIVE = "{spark} <b>{days} · {level}</b>"
SPARK_MIDNIGHT = "<i>Обе половины есть. В полночь серия длиннее.</i>"
FLAME_MARK = "🔥"
FLAME_TODAY = "◌"
FLAME_OFF = "·"
FLAME_NOW = "сегодня"
FLAME_NAMES = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
FLAME_COUNT = "🔥 <b>{days}</b> {word}"
FLAME_OPEN = "<i>◌ справа — сегодня, ещё можно зажечь</i>"
FLAME_LIT = "<i>сегодня уже горит</i>"
FLAME_FIRST = ""
FLAME_RISK = ""
FLAME_ZERO = "<i>◌ справа — сегодня. Пока пусто.</i>"
SPARK_COAT = "<i>Пальто: один пропуск не гасит серию.</i>"
LEVELS_TITLE = "{spark} <b>Награды</b>"
LEVEL_LEAD = "<i>Больше дней — больше лимит.</i>"
LEVEL_NOW = " · сейчас"
LEVEL_ROW = "<b>{name}</b> <i>{days} дн. · лимит {goal} · половина {share}{mark}</i>"
LEVEL_NEXT = "<i>До «{name}» ещё {days} дн. Лимит станет {goal}, каждому по {share}.</i>"
HOLIDAY_HEAD = "🎁 <b>Дары</b>"
HOLIDAY_NOTE = "<i>Оба жмут один дар. Совпало — он ваш.</i>"
HOLIDAY_LINE = "🎁 <b>{day}</b> {name} · <i>{gift}{mark}</i>"
HOLIDAY_SOON = " ← скоро"
HOLIDAY_GIFT = {
    7: "блик +3, куты или лента",
    14: "свеча +8, куты или лента",
    30: "очаг +20 или премиум",
    100: "большой дар",
}
FIRE_FADE = "{spark} <b>вчера ещё живо · {days}</b>"
FIRE_YESTERDAY = "<i>⏳ сегодня до {clock} · каждому ещё {need} за вчера</i>"
FIRE_HEAD = "{spark} <b>{name} · день {days}</b>"
FIRE_SPLIT = "<i>Лимит {goal} · каждому {need}</i>"
FIRE_DO = "<i>✦ вам ещё {left} · кнопка «Слово паре»</i>"
FIRE_WAIT = "<i>✦ вы готовы · ждём пару</i>"
FIRE_DONE = "<i>✦ обе части есть</i>"
FIRE_TODAY = "Лимит {goal}. Половина каждому: {need}."
CARE_SAVED = "<i>+{n}. Вчерашняя половина закрыта.</i>"
CARE_FADING = "<i>+{n}. Нужна и вторая половина, иначе серия гаснет.</i>"
CARE_PLUS = "<i>+{n} в вашу половину.</i>"
BOND_FAMILY = "{heart} <b>Семья</b>"
BOND_YOU = "{heart} <b>Вы сделали предложение</b>"
BOND_THEM = "{heart} <b>Вам сделали предложение</b>"
BOND_BOUQUET = "{heart} <b>Букет</b>"
TALK_BOTH = "{spark} <i>вы уже написали друг другу</i>"
TALK_YOU = "{spark} <i>вы написали · ждём пару</i>"
TALK_THEM = "{spark} <i>пара написала · ответьте хоть слово</i>"
TALK_NONE = "{spark} <i>напишите паре хоть слово · и паре тоже</i>"
STATS_LINE = "{heart} <b>{name}</b>\n<i>{pair}</i>\n<i>Всего искр {total}. Они уже в серии.</i>"
SHOP_HOME = SCREENS["shop"]["text"]
GIFT_TITLE = "{heart} <b>Магазин</b>\n<i>Цена как в общем магазине.</i>"
GIFT_STOCK = " У вас {have} шт."
GIFT_ROW = "{emoji} <b>{name}</b> · {price} кут\n<i>{about}{stock}</i>"
GIFT_FREE = "{emoji} <b>{name}</b>\n<i>{about}{stock}</i>"
SHOP_FIRE = "{heart} <b>Искры</b>\n<i>Добить свою часть лимита.</i>"
SHOP_MARK = "{heart} <b>Знак</b>\n<i>Лента и кольца. Цена из общего магазина.</i>"
SHOP_MEAL = "{heart} <b>Ужин</b>\n<i>Вырастить и съесть вместе.</i>"
SHOP_QUIET = "{heart} <b>Тихий день</b>\n<i>Раз в неделю закрывает вашу часть.</i>"
GIFT_RIBBON = "🎀 <i>Лента уже на вас.</i>"
GIFT_EMPTY = "<i>Пока пусто.</i>"
RIBBON_ON = SCREENS["ribbon_worn"]["text"]
RIBBON_OFF_HOME = SCREENS["ribbon_none"]["text"]
RIBBON_ASK = SCREENS["ribbon_ask"]["text"]
RIBBON_GONE = "🎀 <b>Лента снята</b>"
VERB_PRICE = "{label} · {price}"
RP_LINE = SCREENS["gest"]["text"]

TODAY_WORD = "сегодня"
HALF_YEAR = "полгода"
ONE_YEAR = "год"
YEAR_AND_HALF = "полтора года"
SPAN_SEC = ("секунду", "секунды", "секунд")
SPAN_MIN = ("минуту", "минуты", "минут")
SPAN_HOUR = ("час", "часа", "часов")
SPAN_DAY = ("день", "дня", "дней")
SPAN_WEEK = ("неделю", "недели", "недель")
SPAN_MONTH = ("месяц", "месяца", "месяцев")
SPAN_YEAR = ("год", "года", "лет")

SEED_PREFIX = "Саженец "
NAME_TAIL = " брака"
PAIR_TAIL = " вдвоём"
SEED_FRUIT = {"огурца": "Огурец", "помидора": "Помидор", "капусты": "Капуста"}


def shelf_from(key):
    """Строка каталога из экрана предмета. Текст и кнопки правятся в экране."""
    screen = SCREENS[key]
    buy = use = ""
    for row in iter_button_rows(screen.get("buttons")):
        for button in row:
            if button.get("go") == "gbuy":
                buy = button["text"]
            elif button.get("go") == "guse":
                use = button["text"]
    item_id = key.split("_", 1)[1]
    if screen.get("rite"):
        return {
            "id": item_id,
            "name": screen.get("title") or "",
            "name1": screen.get("name1") or "",
            "emoji": screen.get("emoji") or "",
            "effect": screen.get("effect") or "",
            "use": use,
            "rite": True,
        }
    built = {
        "id": item_id,
        "name": screen.get("title") or "",
        "name1": screen.get("name1") or "",
        "emoji": screen.get("emoji") or "",
        "price": int(screen.get("price") or 0),
        "care": int(screen.get("care") or 0),
        "effect": screen.get("effect") or "",
        "buy": buy,
        "use": use,
        "touch": t(screen.get("used") or ""),
        "line": _italic(screen["text"]),
    }
    if screen.get("craft"):
        built["craft"] = screen["craft"]
    if "on" in screen:
        built["on"] = bool(screen["on"])
    if screen.get("growMin"):
        built["growMin"] = int(screen["growMin"])
        built["waters"] = int(screen.get("waters") or 0)
    return built


def _pack(*keys):
    return tuple(shelf_from(key) for key in keys)


# Каталог собирается из экранов item_… и rite_… выше. Цены и эффекты тоже там.
G1 = _pack("item_glow", "item_candle", "item_hearth")
G2 = _pack("item_match", "item_ribbon")
G3 = _pack("item_tulip", "item_honey", "item_moon", "item_dawn", "item_vow")
G4 = ()
G5 = _pack("item_propose", "item_band")
G6 = _pack(
    "item_seedcuke", "item_seedtom", "item_seedcab",
    "item_cuke", "item_tom", "item_cab",
    "item_juice", "item_soup", "item_salad",
)
R1 = _pack("rite_bouquet", "rite_propose")
R2 = _pack("rite_wedring", "rite_thread")


# Подписи эффектов на полке панели. Пустая третья ячейка — без числа заботы.
EFFECT_SHELF = (
    ("self", "Тепло себе", "Забота"),
    ("other", "Тепло партнёру", "Забота"),
    ("both", "Тепло обоим", "Забота"),
    ("norm", "Ночью добить свою норму", ""),
    ("dawn", "Утром, пока искра гаснет", "Забота"),
    ("gap", "Дожечь вчерашнюю половину", ""),
    ("vow", "Один раз дописать день после ответа", ""),
    ("mark", "Свой знак в профиле", ""),
    ("propose", "Сделать предложение", ""),
    ("ring", "Отдать кольцо после предложения", ""),
    ("seed", "Саженец на ферму", ""),
    ("pantry", "Овощ для крафта", ""),
)

R1 = (
    {"id": "bouquet", "name": "Букет", "name1": "mrgbouquet", "emoji": "💐", "effect": "bouquet", "use": "Букет", "rite": True},
    {"id": "propose", "name": "Колечко", "name1": "mrgpropose", "emoji": "💠", "effect": "propose", "use": "Колечко", "rite": True},
)
R2 = (
    {"id": "wedring", "name": "Обручальное", "name1": "mrgring", "emoji": "💎", "effect": "family", "use": "Кольцо", "rite": True},
    {"id": "thread", "name": "Красная нить", "name1": "mrgthread", "emoji": "🧵", "effect": "thread", "use": "Нить", "rite": True},
)


# --- жесты. Кнопки жеста собираются отсюда, по две в ряд, снизу «Забыл» и «К паре» ---

# Подпись кнопки жеста — text= на экране gest. Здесь она называется для старого кода.
VERB_LABEL = {
    button["go"]: button["text"]
    for row in iter_button_rows(SCREENS["gest"]["buttons"])
    for button in row
    if str(button.get("data") or "").startswith("mrg:act:")
}
P1 = (
    {"id": "hug", "verbs": ("обнять", "обними", "обнимаю", "обнимашки"), "emoji": HEART, "does": "обнимает", "price": 0, "care": 4, "wait": 30},
    {"id": "kiss", "verbs": ("поцеловать", "поцелуй", "поцелую"), "emoji": HEART, "does": "целует", "price": 0, "care": 4, "wait": 30},
    {"id": "peck", "verbs": ("чмокнуть", "чмок"), "emoji": HEART, "does": "чмокает", "price": 0, "care": 2, "wait": 30},
)
P2 = (
    {"id": "air", "verbs": ("воздушный поцелуй",), "emoji": HEART, "does": "шлёт воздушный поцелуй", "price": 0, "care": 2, "wait": 30},
    {"id": "praise", "verbs": ("похвалить", "хвалю"), "emoji": HEART, "does": "хвалит", "price": 0, "care": 3, "wait": 30},
    {"id": "stroke", "verbs": ("погладить", "погладь"), "emoji": HEART, "does": "гладит", "price": 0, "care": 2, "wait": 30},
)
P3 = (
    {"id": "rose", "verbs": ("подарить розу", "роза", "розу"), "emoji": HEART, "does": "дарит розу", "price": 0, "care": 5, "wait": 30},
    {"id": "compliment", "verbs": ("сказать комплимент", "комплимент"), "emoji": HEART, "does": "говорит комплимент", "price": 0, "care": 3, "wait": 30},
    {"id": "hand", "verbs": ("взять за руку", "держать за руку", "за руку"), "emoji": HEART, "does": "берёт за руку", "price": 0, "care": 2, "wait": 30},
)
P4 = (
    {"id": "night", "verbs": ("спокойной ночи", "доброй ночи"), "emoji": HEART, "does": "желает спокойной ночи", "price": 0, "care": 3, "wait": 30},
)
# Добрые команды из commands1. Каждая кормит огонёк. Злые и взрослые сюда не входят.
P5 = (
    {"id": "waist", "title": "Прижать", "verbs": ("прижать за талию",), "emoji": HEART, "does": "прижимает", "price": 0, "care": 3, "wait": 30},
    {"id": "sign", "title": "Автограф", "verbs": ("дать автограф",), "emoji": HEART, "does": "даёт автограф", "price": 0, "care": 2, "wait": 30},
    {"id": "greet", "title": "Поздравить", "verbs": ("поздравить",), "emoji": HEART, "does": "поздравляет", "price": 0, "care": 2, "wait": 30},
    {"id": "wink", "title": "Подмигнуть", "verbs": ("подмигнуть",), "emoji": HEART, "does": "подмигивает", "price": 0, "care": 1, "wait": 30},
    {"id": "bite", "title": "Кусь", "verbs": ("кусь",), "emoji": HEART, "does": "кусает играючи", "price": 0, "care": 1, "wait": 30},
    {"id": "shake", "title": "Рукопожатие", "verbs": ("пожать руку",), "emoji": HEART, "does": "жмёт руку", "price": 0, "care": 2, "wait": 30},
    {"id": "purr", "title": "Мурчать", "verbs": ("помурчать",), "emoji": HEART, "does": "мурчит", "price": 0, "care": 2, "wait": 30},
    {"id": "feed", "title": "Накормить", "verbs": ("накормить",), "emoji": HEART, "does": "кормит", "price": 0, "care": 3, "wait": 30},
    {"id": "treat", "title": "Покормить", "verbs": ("покормить",), "emoji": HEART, "does": "кормит", "price": 0, "care": 3, "wait": 30},
    {"id": "drink", "title": "Напоить", "verbs": ("напоить",), "emoji": HEART, "does": "поит", "price": 0, "care": 2, "wait": 30},
    {"id": "caress", "title": "Приласкать", "verbs": ("приласкать",), "emoji": HEART, "does": "ласкает", "price": 0, "care": 3, "wait": 30},
    {"id": "pity", "title": "Пожалеть", "verbs": ("пожалеть",), "emoji": HEART, "does": "жалеет", "price": 0, "care": 3, "wait": 30},
    {"id": "flirt", "title": "Флирт", "verbs": ("флиртовать",), "emoji": HEART, "does": "флиртует", "price": 0, "care": 2, "wait": 30},
    {"id": "tea", "title": "Чай", "verbs": ("принести чай",), "emoji": HEART, "does": "приносит чай", "price": 0, "care": 2, "wait": 30},
    {"id": "cheer", "title": "Обрадовать", "verbs": ("обрадовать",), "emoji": HEART, "does": "радует", "price": 0, "care": 2, "wait": 30},
    {"id": "laugh", "title": "Смешить", "verbs": ("смешить",), "emoji": HEART, "does": "смешит", "price": 0, "care": 2, "wait": 30},
    {"id": "aid", "title": "Помочь", "verbs": ("помочь",), "emoji": HEART, "does": "помогает", "price": 0, "care": 3, "wait": 30},
    {"id": "cry", "title": "Поплакать", "verbs": ("поплакать",), "emoji": HEART, "does": "плачет рядом", "price": 0, "care": 2, "wait": 30},
    {"id": "clap", "title": "Похлопать", "verbs": ("похлопать",), "emoji": HEART, "does": "хлопает", "price": 0, "care": 1, "wait": 30},
    {"id": "play", "title": "Поиграть", "verbs": ("поиграть",), "emoji": HEART, "does": "играет", "price": 0, "care": 2, "wait": 30},
    {"id": "sorry", "title": "Извиниться", "verbs": ("извиниться",), "emoji": HEART, "does": "извиняется", "price": 0, "care": 3, "wait": 30},
    {"id": "forgive", "title": "Прощение", "verbs": ("попросить прощения",), "emoji": HEART, "does": "просит прощения", "price": 0, "care": 3, "wait": 30},
)
SHARED_WITH_GENERAL_RP = frozenset({
    "обнять", "поцеловать", "чмок", "воздушный поцелуй", "похвалить", "погладить",
    "прижать за талию", "дать автограф", "поздравить", "подмигнуть", "кусь",
    "пожать руку", "помурчать", "накормить", "покормить", "напоить", "приласкать",
    "пожалеть", "флиртовать", "принести чай", "обрадовать", "смешить", "помочь",
    "поплакать", "похлопать", "поиграть", "извиниться", "попросить прощения",
})
QUIET_UNLESS_PAIR = frozenset({"доброй ночи", "спокойной ночи"})


# --- уровни. name и life читает карточка. days и goal считает искра ---

LEVEL_A = (
    {"id": 1, "days": 0, "name": "Знакомство", "goal": 10, "life": "Вы ещё узнаёте друг друга. Ответа на сегодня уже достаточно."},
    {"id": 2, "days": 1, "name": "Симпатия", "goal": 10, "life": "Уже хочется написать первым."},
    {"id": 3, "days": 3, "name": "Тепло", "goal": 16, "life": "Разговор стал привычкой, как чай вечером."},
    {"id": 4, "days": 7, "name": "Близость", "goal": 22, "life": "Молчание уже понятно. Ответ всё равно нужен обоим."},
    {"id": 5, "days": 14, "name": "Пара", "goal": 30, "life": "У вас уже есть свой тон. День без него заметен."},
    {"id": 6, "days": 21, "name": "Нежность", "goal": 34, "life": "Забота находится сама. Кладут её всё равно оба."},
)
LEVEL_B = (
    {"id": 7, "days": 30, "name": "Союз", "goal": 40, "life": "Вы держитесь обычными словами. Комната от этого тише."},
    {"id": 8, "days": 45, "name": "Клятва", "goal": 48, "life": "Обещание уже живёт в обычном ответе."},
    {"id": 9, "days": 60, "name": "Дом", "goal": 56, "life": "Вечер узнаётся без объяснений."},
    {"id": 10, "days": 90, "name": "Очаг", "goal": 64, "life": "Тепло остаётся, даже если день был коротким."},
    {"id": 11, "days": 180, "name": "Годы", "goal": 72, "life": "Вы узнаёте друг друга по одной фразе."},
    {"id": 12, "days": 365, "name": "Навсегда", "goal": 80, "life": "Этот день такой же, как вчерашний. И от этого спокойно."},
)
LEVEL_EMPTY = LEVEL_A[0]["name"]


# --- фразы, которые бот узнаёт. Регистр не важен, лишние слова рядом уже не команда ---

WED_WORDS = frozenset({"выйти замуж", "предложение руки", "рука и сердце", "бракосочетание", "пожениться", "поженимся", "женитьба", "жениться", "женимся", "свадьба", "замуж", "брак"})
CARD_WORDS = frozenset({"карточка брака", "статус брака", "мой брак", "наш брак", "моя пара", "наша пара"})
LEAVE_WORDS = frozenset({"развод", "развестись", "разведемся", "развелись"})
TOP_WORDS = frozenset({"топ браков", "топ браки"})
ON_WORDS = frozenset({"+браки", "+ браки", "включить браки"})
OFF_WORDS = frozenset({"-браки", "- браки", "выключить браки"})
LIST_WORDS = frozenset({"браки", "список браков"})
TONE_WORDS = frozenset({"тонус", "мой тонус", "наш тонус", "искра"})
RIBBON_COMMANDS = frozenset({
    "снять ленту",
    "снять ленту брака",
    "сними ленту",
    "сними ленту брака",
    "убери ленту",
    "убери ленту брака",
    "убрать ленту",
    "убрать ленту брака",
    "снимите ленту",
    "снимите ленту брака",
    "снять свою ленту",
    "снять свою ленту брака",
    "снять ленту с профиля",
    "убрать ленту с профиля",
    "снять брачную ленту",
    "убрать брачную ленту",
    "снять ленточку",
    "снять ленточку брака",
})
