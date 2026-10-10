# -*- coding: utf-8 -*-
"""Брак - дизайн всех сообщений.

Как править
-----------
Сообщение целиком - в text= тройными кавычками.
Эмодзи сообщения - в emoji=.
Каждая кнопка, которую видит человек, написана под своим сообщением:
    b(text="Слово", icon="<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>", color="primary", go="...", data="mrg:...")
Ряд из двух кнопок - один список [кнопка, кнопка]. Кнопка с новой строки - свой ряд.
text= - подпись. color= - default, primary, success или danger.
icon= - премиум-эмодзи этой кнопки. Пишется здесь и больше никуда не смотрит. Пустой icon= - кнопка без значка.
data= - куда ведёт. Его не переписывают. {book_id} {token} {verb_id} {amount} {price} {have} подставляются сами.
Магазин берёт «Купить» и «Использовать» с экрана этого предмета.
Праздник берёт кнопки с экрана feast. «На ферму» и «В крафт» - кнопка использования саженца и блюда.
Слово на кнопке и то же слово в тексте пиши одинаково.
Под текстом строка с # : где его видит человек и когда. Решётка в Telegram не уходит.
when="play" — кнопка только при живом браке. when="feast" — открыт праздник.
when="leave" — развод разрешён. when="late" — праздник с 30-го дня. Пустой when — кнопка всегда.

Типографика
-----------
Вид брака свой: <i>подпись</i> — <b>значение</b>. Без «эмодзи • » на каждой строке и без рамки ┏ ┓.
<b>жирный</b> - значение: имя, число, лимит.
<i>курсив</i> - подпись и что сделать дальше.
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


# Знак в начале текста сообщения. Кнопки его не берут: у каждой свой icon= под сообщением.
RED_ID = "5388870246243274946"
DOT_ID = "5337017423906226569"
HEART = "<tg-emoji emoji-id='" + RED_ID + "'>❤</tg-emoji>"
SPARK = "<tg-emoji emoji-id='" + DOT_ID + "'>🔴</tg-emoji>"
HEARTS_SHELF = "💖"

# Часы по умолчанию, если в панели пусто. Луна с 21 включительно до 6. Рассвет с 6 до 10.
MOON_FROM, MOON_TO = 21, 6
DAWN_FROM, DAWN_TO = 6, 10


# Кнопки не спрятаны выше. Каждая написана под своим сообщением, в SCREENS.


# ===========================================================================
# Короткие тексты экранов помощи. Человек их тоже видит.
# ===========================================================================

HELP_PAY = "Платит тот, кто написал «брак»."  # Кусок справки: кто платит за платную свадьбу.
HELP_CMD = "Мой брак"  # Команда в справке. Пишется как есть, в рамке кода.


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
        <i>Бесплатно. {which} из {free}. Лимит дня делится пополам: доброе слово добавляет искры вам. «Согласиться» «Отказать» «Отменить заявку». {minutes} мин.</i>
        """,
        buttons=[
            [
                b(text="Отказать", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="no", data="mrg:no:{book_id}"),
                b(text="Согласиться", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="yes", data="mrg:yes:{book_id}"),
            ],
            [
                b(text="Отменить заявку", color="primary", go="stop", data="mrg:stop:{book_id}"),
            ],
        ],
    ),
    # Чат группы. «брак» ответом на человека, бесплатные свадьбы ещё есть. {a} кто зовёт, {b} кого зовут, {which} какая по счёту, {free} сколько бесплатных, {minutes} сколько минут висит заявка. «Согласиться» и «Отказать» жмёт тот, кого позвали. «Отменить заявку» — кто написал «брак».

    "ask_paid": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} зовёт {b}</b>
        <i>{price} кут. Свадьба {which}. Лимит дня делится пополам: доброе слово добавляет искры вам. «Согласиться» «Отказать» «Отменить заявку». {minutes} мин.</i>
        """,
        buttons=[
            [
                b(text="Отказать", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="no", data="mrg:no:{book_id}"),
                b(text="Согласиться", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="yes", data="mrg:yes:{book_id}"),
            ],
            [
                b(text="Отменить заявку", color="primary", go="stop", data="mrg:stop:{book_id}"),
            ],
        ],
    ),
    # Чат группы. То же, когда бесплатные свадьбы кончились. {price} спишется с того, кто написал «брак», в момент согласия. До согласия куты не трогают.

    "wed_free": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b} вместе</b>
        {spark} <i>Бесплатно. Каждому по {each} искр в свою половину лимита. «Слово паре» — и день горит, когда половину набрали оба.</i>
        """,
    ),
    # Чат группы, сразу после «Согласиться», свадьба бесплатная. {each} — сколько искр легло каждому в свою половину лимита.

    "wed_paid": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b} вместе</b>
        {spark} <i>{price} кут. Каждому по {each} искр в свою половину лимита. «Слово паре» — и день горит, когда половину набрали оба.</i>
        """,
    ),
    # Чат группы, сразу после «Согласиться», свадьба платная. Куты уже списаны и не возвращаются. {each} — искры каждому.

    "leave_ask": msg(
        emoji=HEART,
        text="""
        {heart} <b>Расторгнуть брак с {b}?</b>
        <i>Куты не вернутся.</i>
        """,
        buttons=[
            [
                b(text="Остаться", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="stay", data="mrg:stay:{token}"),
                b(text="Развестись", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="leave", data="mrg:leave:{token}"),
            ],
        ],
    ),
    # Чат, после кнопки «Расторгнуть брак» или команды развода. {b} партнёр. «Остаться» закрывает вопрос. «Развестись» заканчивает брак.

    "private": msg(emoji=HEART, text=_line("""<b>Отношения живут в группе.</b>""")),
    # Личка бота. «брак», «мой брак», +браки или -браки написали не в группе.
    "project_off": msg(emoji=HEART, text=_line("""<b>Отношения в проекте выключены.</b>""")),
    # Чат. Браки выключены на весь проект во вкладке «Браки».
    "off": msg(emoji=HEART, text=_line("""<b>В этой группе отношения выключены.</b>""")),
    # Чат. В этой группе браки выключены командой -браки.
    "on_ok": msg(emoji=HEART, text=_line("""<b>Отношения в группе включены.</b>""")),
    # Чат. Создатель группы написал +браки, браки в группе включились.
    "off_ok": msg(emoji=HEART, text=_line("""<b>Отношения в группе выключены.</b>""")),
    # Чат. Создатель группы написал -браки, браки в группе выключились.
    "on_already": msg(emoji=HEART, text=_line("""<i>Отношения здесь уже включены.</i>""")),
    # Чат. Создатель снова написал +браки, а они уже включены.
    "off_already": msg(emoji=HEART, text=_line("""<i>Отношения здесь уже выключены.</i>""")),
    # Чат. Создатель снова написал -браки, а они уже выключены.
    "creator_only": msg(emoji=HEART, text=_line("""<b>+браки и -браки пишет создатель группы.</b>""")),
    # Чат. +браки или -браки написал не создатель группы.
    "need_reply": msg(emoji=HEART, text=_line("""<b>Ответьте «брак» на сообщение.</b> <i>Лимит дня пополам, доброе слово добавляет искры вам. {minutes} мин.</i>""")),
    # Чат. «брак» без ответа на сообщение человека. {minutes} — сколько потом будет висеть заявка.
    "not_found": msg(emoji=HEART, text=_line("""<b>Не вижу, кого звать.</b>""")),
    # Чат. Ответ есть, но бот не понял, кого звать.
    "bot": msg(emoji=HEART, text=_line("""<b>Бота в брак не зовут.</b>""")),
    # Чат. «брак» ответом на сообщение бота.
    "self": msg(emoji=HEART, text=_line("""<b>Себя позвать нельзя.</b>""")),
    # Чат. «брак» ответом на своё сообщение.

    "already_you": msg(emoji=HEART, text=_line("""<b>Вы уже в браке с {b}.</b>""")),
    # Чат. У написавшего уже есть брак с {b}.
    "already_them": msg(emoji=HEART, text=_line("""<b>{b} уже в браке.</b>""")),
    # Чат. {b} уже в браке с другим человеком.
    "busy": msg(emoji=HEART, text=_line("""<b>Сейчас заявка уже есть.</b>""")),
    # Чат. У одного из двоих уже висит заявка, вторую открыть нельзя.
    "poor": msg(emoji=HEART, text=_line("""<b>Нужно {price} кут, у вас {have}.</b>""")),
    # Чат, до заявки. Платная свадьба, кут не хватает. {price} нужно, {have} есть сейчас.
    "poor_late": msg(emoji=HEART, text=_line("""<b>К согласию не хватило {price} кут.</b>""")),
    # Чат, в момент «Согласиться». Пока заявка висела, кут перестало хватать. Заявка закрывается, ничего не списано.
    "not_married": msg(emoji=HEART, text=_line("""<b>Брака нет.</b> <i>«брак» на человека. Лимит дня пополам: доброе слово добавляет искры вам.</i>""")),
    # Чат. «Мой брак», развод или слово паре, а брака нет.
    "tone_old": msg(emoji=HEART, text=_line("""<b>Этот брак из старой книги.</b>""")),
    # Чат или кнопка. Брак из старой книги: карточка искры не открывается.

    "expired": msg(emoji=HEART, text=_line("""<b>{minutes} мин. Заявка закрыта.</b>""")),
    # Чат. За {minutes} минут заявку никто не принял. Куты не списаны.
    "stopped": msg(emoji=HEART, text=_line("""<b>Заявку отменили. Куты не списаны.</b>""")),
    # Чат. Кто написал «брак», нажал «Отменить заявку». Куты не списаны.
    "refused": msg(emoji=HEART, text=_line("""<b>{b} отказал(а). Куты не списаны.</b>""")),
    # Чат. Кого позвали, нажал «Отказать». {b} — этот человек. Куты не списаны.
    "skip_ok": msg(emoji=HEART, text=_line("""<i>Жест не отправлен.</i>""")),
    # Чат. На вопросе о платном слове нажали «Не сейчас». Слово не ушло, куты не списаны.
    "stay_ok": msg(emoji=HEART, text=_line("""<b>Вы остались вместе.</b>""")),
    # Чат. На вопросе о разводе нажали «Остаться». Брак на месте.

    "till_closed": msg(emoji=HEART, text=_line("""<b>Куты не приняты. Заявка закрыта.</b>""")),
    # Чат. Куты за свадьбу принять не удалось, заявка закрылась.
    "leave_ok": msg(emoji=HEART, text=_line("""<b>{a} и {b} больше не вместе.</b>""")),
    # Чат группы. Развод состоялся. {a} кто развёл, {b} партнёр.
    "leave_them": msg(emoji=HEART, text=_line("""<b>{a} расторг(ла) брак.</b>""")),
    # Личное сообщение партнёру о разводе. В группе его этим текстом не зовут. {a} кто развёл.
    "rp_tomorrow": msg(emoji=HEART, text=_line("""<b>{title} уже было сегодня.</b>""")),
    # Чат. Это доброе слово сегодня уже давало искры. {title} — его название. Повтор анимацию не запускает.
    "rp_poor": msg(emoji=HEART, text=_line("""<b>{title}: {price} кут, у вас {have}.</b>""")),
    # Чат. Платное доброе слово, кут не хватает. {title} слово, {price} нужно, {have} есть.
    "rp_pay": msg(
        emoji=HEART,
        text=_line("""<b>{title} · {price} кут</b>"""),
        buttons=[
            [
                b(text="Списать {amount} кут", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="pay", data="mrg:pay:{verb_id}"),
            ],
            [
                b(text="Не сейчас", color="default", go="skip", data="mrg:skip:{verb_id}"),
            ],
        ],
    ),
    # Чат. Платное слово, вопрос перед списанием. «Списать» забирает кут и даёт искры. «Не сейчас» ничего не делает. Цена слова задаётся во вкладке «Браки».

    "top_empty": msg(emoji=HEART, text=_line("""<b>В этой группе пока нет пар.</b>""")),
    # Чат. Команда списка пар, а в группе ещё нет браков.
    "top": msg(
        emoji=HEART,
        text=_line("""<b>Кто вместе дольше</b>"""),
        buttons=[
            [
                b(text="Мой брак", color="default", go="mine", data="mrg:mine:0"),
                b(text="Пары группы", color="primary", go="list", data="mrg:list:0"),
            ],
        ],
    ),
    # Заголовок списка «кто вместе дольше». Под ним строки TOP_ROW. Кнопки ведут в свой брак и в полный список.
    "list": msg(
        emoji=HEART,
        text=_line("""<b>Пары этой группы</b>"""),
        buttons=[
            [
                b(text="Мой брак", color="default", go="mine", data="mrg:mine:0"),
                b(text="Кто дольше", color="primary", go="top", data="mrg:top:0"),
            ],
        ],
    ),
    # Заголовок списка всех пар группы. Под ним строки LIST_ROW.

    "rp_need": msg(emoji=HEART, text=_line("""<b>Сначала брак.</b> <i>«брак» на сообщение. Потом «Слово паре» добавит искры в вашу половину.</i>""")),
    # Чат. Доброе слово написали без брака.
    "rp_pair": msg(emoji=HEART, text=_line("""<b>Только своей паре.</b>""")),
    # Чат. Доброе слово ответом не на свою пару. Чужому искры не идут.
    "rp_done": msg(emoji=HEART, text=_line("""<b>Это слово уже было.</b>""")),
    # Чат. Это слово сегодня уже засчитано.
    "rp_wait": msg(
        emoji=HEART,
        text=_line("""<b>{title}</b> <i>снова через {left}.</i>"""),
    ),
    # Чат. Пауза между повторами этого слова ещё не прошла. {title} слово, {left} сколько осталось. Минуты паузы задаются во вкладке «Браки».

    "what": msg(
        emoji=HEART,
        text=_line("""
        <b>Что даёт брак</b>
        Огонёк один на двоих. Лимит дня — это искры, и они делятся пополам: вам половина, паре половина.
        Доброе слово (обнять, поцеловать, похвалить) добавляет искры только вам.
        <i>Оба набрали свою половину — день горит. Длиннее серия — выше лимит и награды. В профиле видно, что вы пара.</i>
        """),
        buttons=[
            [b(text="Как кормить огонёк", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="how", data="mrg:use:0")],
            [b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="default", go="fire", data="mrg:fire:0", when="play")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Кнопка «Что даёт брак» на карточке пары. «Лимит дня» на этом экране виден только при живом браке (when=play).
    "how": msg(
        emoji=HEART,
        text=_line("""
        <b>Как кормить огонёк</b>
        Нажмите «Слово паре» и выберите доброе слово. Искры прибавятся вам, не паре.
        Ваша половина лимита набрана — вы готовы. День горит, только когда готовы оба.
        <i>Искры сверх половины копятся в запас и могут засчитать следующий день.</i>
        """),
        buttons=[
            [b(text="Слово паре", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="care", data="mrg:care:0", when="play")],
            [b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="default", go="fire", data="mrg:fire:0", when="play")],
            [
                b(text="Что даёт брак", color="default", go="what", data="mrg:what:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    # Кнопка «Как кормить огонёк». «Слово паре» здесь тоже только при живом браке.
    "hold": msg(
        emoji=HEART,
        text=_line("""
        <b>Если день сорвался</b>
        Каждый день оба должны набрать свою половину искр. Срок написан на «Лимит дня».
        Не успели — огонёк гаснет, лимит и награды возвращаются к началу.
        <i>До 12:00 вчерашнюю половину ещё можно добрать добрым словом.</i>
        """),
        buttons=[
            [b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="primary", go="fire", data="mrg:fire:0", when="play")],
            [
                b(text="Как кормить огонёк", color="default", go="how", data="mrg:use:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    # Кнопка «Если день сорвался». Объясняет, что будет, если до срока не набрали обе половины.
    "gest_help": msg(
        emoji=HEART,
        text="<b>Слово паре</b>\nСлово добавит искры только в вашу половину сегодняшнего лимита.\n<i>Когда половину набрали оба, день горит. То же слово второй раз сегодня искр не даёт.</i>",
        buttons=[
            [
                b(text="Если день сорвался", color="default", go="hold", data="mrg:hold:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    # Текст над списком слов, когда нажали «Слово паре». Сами слова — кнопки экрана gest.

    # «Праздник» виден, когда праздник открыт. «Расторгнуть» — когда брак можно закрыть.
    # Строки под именами — CARD_HEAD и дальше, в этом же файле.
    "card": msg(
        emoji=HEART,
        text="""
        {heart} <b>{a} и {b}</b>
        """,
        buttons=[
            [b(text="Дар праздника", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="feast", data="mrg:feast:0", when="feast")],
            [
                b(text="Слово паре", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="gest", data="mrg:gest:{token}"),
                b(text="Магазин пары", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="bag", data="mrg:bag:0"),
            ],
            [
                b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="default", go="fire", data="mrg:fire:0"),
                b(text="Награды за дни", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [
                b(text="Что даёт брак", color="default", go="what", data="mrg:what:0"),
                b(text="Как кормить огонёк", color="default", go="how", data="mrg:use:0"),
            ],
            [
                b(text="Если день сорвался", color="default", go="hold", data="mrg:hold:0"),
                b(text="Все искры", color="default", go="stat", data="mrg:stat:0"),
            ],
            [b(text="Лента в профиле", color="default", go="rib", data="mrg:rib:0")],
            [b(text="Расторгнуть брак", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="warn", data="mrg:warn:{token}", when="leave")],
        ],
    ),
    # Кнопки карточки «Мой брак». Текст этой карточки сюда не берётся: его собирают строки HOME_*, FLAME_* и LIMIT_HEAD ниже. when=feast показывает «Дар праздника», when=leave — «Расторгнуть брак».

    "tone": msg(
        emoji=SPARK,
        text="""
        {spark} <b>Лимит</b>
        <i>Доброе слово добавляет искры в вашу половину лимита. Оба набрали — день горит, лимит и награды выше.</i>
        """,
        buttons=[
            [b(text="Обнять", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="hug", data="mrg:act:hug:{token}")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # В чат этот текст не уходит. Живой экран лимита — строки FIRE_* и кнопки spark_nav. Кнопка «Обнять» здесь нужна коду, её подпись можно сменить.

    "gest": msg(
        emoji=SPARK,
        text="""
        {emoji} <b>{a}</b> {does} <b>{b}</b>{note}
        """,
        buttons=[
            [
                b(text="Обнять", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="hug", data="mrg:act:hug:{token}"),
                b(text="Поцеловать", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="kiss", data="mrg:act:kiss:{token}"),
            ],
            [
                b(text="Чмок", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="peck", data="mrg:act:peck:{token}"),
                b(text="Воздушный", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="air", data="mrg:act:air:{token}"),
            ],
            [
                b(text="Похвалить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="praise", data="mrg:act:praise:{token}"),
                b(text="Погладить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="stroke", data="mrg:act:stroke:{token}"),
            ],
            [
                b(text="Роза", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="rose", data="mrg:act:rose:{token}"),
                b(text="Комплимент", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="compliment", data="mrg:act:compliment:{token}"),
            ],
            [
                b(text="За руку", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="hand", data="mrg:act:hand:{token}"),
                b(text="На ночь", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="night", data="mrg:act:night:{token}"),
            ],
            [
                b(text="Если день сорвался", color="default", go="hold", data="mrg:hold:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    # Строка в чат после доброго слова: {a} кто сделал, {does} что сделал, {b} пара, {note} хвост фразы. Кнопки этого экрана — список на «Слово паре». Если слово платное, к кнопке само допишется цена.

    # Кнопки экранов с числами. Сам текст собирается из строк ниже: числа пары живые.
    "spark_nav": msg(
        emoji=SPARK,
        text=_line("""<b>Лимит</b> <i>Искры на сегодня делятся пополам. Оба набрали свою половину — день горит.</i>"""),
        buttons=[
            [b(text="Слово паре", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="care", data="mrg:care:0", when="play")],
            [
                b(text="Как кормить огонёк", color="default", go="how", data="mrg:use:0"),
                b(text="Награды за дни", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Кнопки под экраном «Лимит дня». Текст экрана — строки FIRE_* ниже, эта фраза в чат не уходит. «Слово паре» только при живом браке.
    "level_nav": msg(
        emoji=SPARK,
        text=_line("""<b>Награды</b> <i>Чем дольше огонёк, тем выше лимит дня. Лимит всегда делится пополам.</i>"""),
        buttons=[
            [
                b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="default", go="fire", data="mrg:fire:0"),
                b(text="Что даёт брак", color="default", go="what", data="mrg:what:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Кнопки под экраном «Награды за дни». Текст экрана — LEVEL_* и HOLIDAY_* ниже, эта фраза в чат не уходит.
    "stat_nav": msg(
        emoji=HEART,
        text=_line("""<b>Всего</b> <i>Сколько искр уже вложено. Больше дней подряд — выше лимит.</i>"""),
        buttons=[
            [
                b(text="Лимит дня", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="default", go="fire", data="mrg:fire:0"),
                b(text="Награды за дни", color="default", go="lvl", data="mrg:lvl:0"),
            ],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Кнопки под экраном «Все искры». Текст экрана — STATS_LINE ниже, эта фраза в чат не уходит.

    "ribbon_ask": msg(
        emoji=HEART,
        text="""
        🎀 <b>Снять ленту?</b>
        <i>Брак останется.</i>
        """,
        buttons=[
            [
                b(text="Снять с профиля", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="riboff", data="mrg:rib:off"),
                b(text="Оставить ленту", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="ribstay", data="mrg:rib:stay"),
            ],
        ],
    ),
    # Вопрос перед снятием ленты. Брак от этого не кончается. «Снять с профиля» убирает знак, «Оставить ленту» закрывает вопрос.
    "ribbon_worn": msg(
        emoji=HEART,
        text="""
        🎀 <b>Лента на вас</b>
        """,
        buttons=[
            [b(text="Снять ленту", icon="""<tg-emoji emoji-id='5226660202035554522'>❌</tg-emoji>""", color="danger", go="ribask", data="mrg:rib:ask")],
            [
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
                b(text="Магазин пары", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="default", go="bag", data="mrg:bag:0"),
            ],
        ],
    ),
    # Экран ленты, когда она уже на вас. «Снять ленту» открывает вопрос ribbon_ask.
    "ribbon_none": msg(
        emoji=HEART,
        text="""
        🎀 <b>Ленты нет</b>
        <i>Она в магазине.</i>
        """,
        buttons=[
            [
                b(text="Магазин пары", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="default", go="bag", data="mrg:bag:0"),
                b(text="К паре", color="default", go="mine", data="mrg:mine:0"),
            ],
        ],
    ),
    # Экран ленты, когда её нет. Ведёт в магазин пары.
    "back": msg(
        emoji=HEART,
        text="""
        К паре
        """,
        buttons=[
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Текст в чат не уходит. Кнопка «К паре» дописывается к чужим экранам и возвращает карточку.

    "shop": msg(
        emoji=HEART,
        text="""
        <blockquote><b>магазин</b>
        <i>цена как в общем магазине</i></blockquote>
        """,
        buttons=[
            [b(text="Искры к лимиту", icon="""<tg-emoji emoji-id='5337017423906226569'>🔴</tg-emoji>""", color="primary", go="shelf_fire", data="mrg:bag:fire")],
            [
                b(text="Знаки пары", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="default", go="shelf_mark", data="mrg:bag:mark"),
                b(text="Ужин вместе", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="default", go="shelf_meal", data="mrg:bag:meal"),
            ],
            [b(text="Тихий день", color="default", go="shelf_quiet", data="mrg:bag:quiet")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Первая страница магазина пары. Кнопки открывают полки. Цены предметов — как в общем магазине.
    "shop_back": msg(
        emoji=HEART,
        text="""
        Все предметы
        """,
        buttons=[
            [b(text="Все полки", color="primary", go="shop", data="mrg:bag:0")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Текст в чат не уходит. Эти две кнопки стоят внизу полки и карточки предмета.

    "feast": msg(
        emoji=HEART,
        text="""
        {heart} <b>{name}</b>
        <i>{aura} Один дар, когда оба выберут одно.</i>
        """,
        buttons=[
            [b(text="Конверт", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="envelope", data="mrg:wish:envelope")],
            [b(text="Забота", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="care_prize", data="mrg:wish:care")],
            [b(text="Лента в дар", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="ribbon_prize", data="mrg:wish:ribbon")],
            [b(text="Премиум 3 мес.", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="premium3", data="mrg:wish:premium3")],
            [b(text="Премиум 6 мес.", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="premium6", data="mrg:wish:premium6", when="late")],
            [b(text="К паре", color="default", go="mine", data="mrg:mine:0")],
        ],
    ),
    # Экран праздника, кнопка «Дар праздника» на карточке. {name} имя дня, {aura} короткая подпись. Дар открывается, когда оба выбрали одно и то же. «Премиум 6 мес.» виден только с 30-го дня (when=late).


    # ===========================================================================
    # Предметы. У каждого: сообщение, под ним кнопки, used= — фраза, когда сработал.
    # ===========================================================================

    "item_glow": msg(
        emoji="""🎇""",
        text="""
        🎇 <b>Блик брака</b>
        <i>+{n} {acc} для лимита поддержки.</i>
        """,
        buttons=[
            [
                b(text="Купить блик", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:glow"),
                b(text="Зажечь", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:glow"),
            ],
        ],
        used="Вам добавилось 3 заботы.",
        title="Блик брака",
        name1="mrgglow",
        price=12,
        care=3,
        effect="self",
    ),
    # Карточка предмета, полка «Искры к лимиту». Курсив — описание в магазине. used= — фраза, когда предмет сработал. Кнопки купить и использовать берутся отсюда. Если в общем магазине своё описание, в чат уйдёт оно.

    "item_candle": msg(
        emoji="""🕯""",
        text="""
        🕯 <b>Свеча брака</b>
        <i>+{n} {acc} к лимиту поддержки.</i>
        """,
        buttons=[
            [
                b(text="Купить свечу", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:candle"),
                b(text="Зажечь", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:candle"),
            ],
        ],
        used="Вам добавилось 8 забот.",
        title="Свеча брака",
        name1="mrgcandle",
        price=25,
        care=8,
        effect="self",
    ),
    # Карточка предмета, полка «Искры к лимиту». Больше искр, чем у блика. Курсив — описание, used= — фраза после использования.

    "item_hearth": msg(
        emoji="""🎆""",
        text="""
        🎆 <b>Очаг брака</b>
        <i>+{n} {acc} к вашему лимиту.</i>
        """,
        buttons=[
            [
                b(text="Купить очаг", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:hearth"),
                b(text="Разжечь", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:hearth"),
            ],
        ],
        used="Вам добавилось 20 забот.",
        title="Очаг брака",
        name1="mrghearth",
        price=70,
        care=20,
        effect="self",
    ),
    # Карточка предмета, полка «Искры к лимиту». Самая большая пачка искр в свою половину. Курсив — описание, used= — фраза после использования.

    "item_match": msg(
        emoji="""🪔""",
        text="""
        🪔 <b>Спичка брака</b>
        <i>Закрывает вчера, если не успели.</i>
        """,
        buttons=[
            [
                b(text="Купить спичку", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:match"),
                b(text="Чиркнуть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:match"),
            ],
        ],
        used="Вчерашняя половина лимита набрана.",
        title="Спичка брака",
        name1="mrgmatch",
        price=80,
        care=0,
        effect="gap",
    ),
    # Карточка предмета, полка «Искры к лимиту». Спасает вчера, если свою половину не успели. В обычный день не тратится.

    "item_ribbon": msg(
        emoji="""🎀""",
        text="""
        🎀 <b>Лента брака</b>
        <i>В профиле видно, что вы в браке.</i>
        """,
        buttons=[
            [
                b(text="Купить ленту", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:ribbon"),
                b(text="Надеть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:ribbon"),
            ],
        ],
        used="Лента теперь на вас. В профиле видно, что вы в браке.",
        title="Лента брака",
        name1="mrribbon",
        price=150,
        care=0,
        effect="mark",
    ),
    # Карточка предмета, полка «Знаки пары». Надевается только на вас, в профиле видно брак. У партнёра своя лента.

    "item_tulip": msg(
        emoji="""🌷""",
        text="""
        🌷 <b>Тюльпан брака</b>
        <i>+{n} {acc} к лимиту поддержки партнёра.</i>
        """,
        buttons=[
            [
                b(text="Купить тюльпан", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:tulip"),
                b(text="Отдать", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:tulip"),
            ],
        ],
        used="Партнёру добавилось 5 забот. Цветок теперь в руках партнёра.",
        title="Тюльпан брака",
        name1="mrgtulip",
        price=18,
        care=5,
        effect="other",
    ),
    # Карточка предмета, полка «Знаки пары». Искры получает партнёр, не вы.

    "item_honey": msg(
        emoji="""🍯""",
        text="""
        🍯 <b>Мёд брака</b>
        <i>+{n} {acc} к лимиту поддержки двоих.</i>
        """,
        buttons=[
            [
                b(text="Купить мёд", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:honey"),
                b(text="Открыть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:honey"),
            ],
        ],
        used="Вам и партнёру добавилось по 4 заботы.",
        title="Мёд брака",
        name1="mrghoney",
        price=30,
        care=4,
        effect="both",
    ),
    # Карточка предмета, полка «Ужин вместе». Искры получают оба.

    "item_moon": msg(
        emoji="""🌙""",
        text="""
        🌙 <b>Луна брака</b>
        <i>С {moon_from} до {moon_to}. Медленно закрывает сегодня.</i>
        """,
        buttons=[
            [
                b(text="Купить луну", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:moon"),
                b(text="Поставить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:moon"),
            ],
        ],
        used="Ночь. Ваша половина лимита на сегодня набрана.",
        title="Луна брака",
        name1="mrgmoon",
        price=95,
        care=0,
        effect="norm",
    ),
    # Карточка предмета, полка «Искры к лимиту». Работает только ночью и добивает сегодняшнюю половину, лишнего не кладёт. Часы — из вкладки «Браки», здесь {moon_from} и {moon_to}.

    "item_dawn": msg(
        emoji="""🌄""",
        text="""
        🌄 <b>Рассвет брака</b>
        <i>Если вчера ещё можно спасти. +{n} {nom}.</i>
        """,
        buttons=[
            [
                b(text="Купить рассвет", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:dawn"),
                b(text="Встретить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:dawn"),
            ],
        ],
        used="Утро. Вам добавилось 6 забот.",
        title="Рассвет брака",
        name1="mrgdawn",
        price=32,
        care=6,
        effect="dawn",
    ),
    # Карточка предмета, полка «Искры к лимиту». Утро, и только если вчера ещё можно спасти. Часы — {dawn_from} и {dawn_to}.

    "item_vow": msg(
        emoji="""📃""",
        text="""
        📃 <b>Клятва брака</b>
        <i>Один раз. Ответьте на сообщение пары.</i>
        """,
        buttons=[
            [
                b(text="Купить клятву", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:vow"),
                b(text="Прочитать", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:vow"),
            ],
        ],
        used="Клятва прочитана. Это можно сделать только один раз.",
        title="Клятва брака",
        name1="mrgvow",
        price=48,
        care=0,
        effect="vow",
    ),
    # Карточка предмета, полка «Знаки пары». Один раз за весь брак, после ответа паре. Добивает вашу половину на сегодня.

    "item_propose": msg(
        emoji="""💠""",
        text="""
        💠 <b>Предложение</b>
        <i>Предложение паре.</i>
        """,
        buttons=[
            [
                b(text="Купить предложение", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:propose"),
                b(text="Сказать", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:propose"),
            ],
        ],
        used="Вы сделали предложение. Теперь можно подарить кольцо.",
        title="Предложение",
        name1="mrgpropose",
        price=60,
        care=0,
        effect="propose",
    ),
    # Карточка предмета, полка «Знаки пары». Один раз открывает статус «сделал предложение». После этого можно дарить кольцо.

    "item_band": msg(
        emoji="""💎""",
        text="""
        💎 <b>Брачное кольцо</b>
        <i>Предложение. После него вы семья.</i>
        """,
        buttons=[
            [
                b(text="Купить кольцо", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:band"),
                b(text="Надеть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:band"),
            ],
        ],
        used="Кольцо теперь у партнёра. Вы стали семьёй.",
        title="Брачное кольцо",
        name1="mrgband",
        price=180,
        care=0,
        effect="ring",
    ),
    # Карточка предмета, полка «Знаки пары». Только после предложения. Кольцо остаётся у второго, статус становится «семья».

    "item_seedcuke": msg(
        emoji="""🌱🥒""",
        text="""
        🌱🥒 <b>Саженец огурца</b>
        <i>На ферму. Потом — в крафт.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:seedcuke"),
                b(text="На ферму", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:seedcuke"),
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
    # Карточка саженца, полка «Ужин вместе». В чате не тратится: кнопка «На ферму» открывает ферму. Вырастет огурец.

    "item_seedtom": msg(
        emoji="""🌱🍅""",
        text="""
        🌱🍅 <b>Саженец помидора</b>
        <i>На ферму. Потом — в крафт.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:seedtom"),
                b(text="На ферму", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:seedtom"),
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
    # Карточка саженца, полка «Ужин вместе». Кнопка ведёт на ферму. Вырастет помидор.

    "item_seedcab": msg(
        emoji="""🌱🥬""",
        text="""
        🌱🥬 <b>Саженец капусты</b>
        <i>На ферму. Потом — в крафт.</i>
        """,
        buttons=[
            [
                b(text="Купить саженец", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:seedcab"),
                b(text="На ферму", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:seedcab"),
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
    # Карточка саженца, полка «Ужин вместе». Кнопка ведёт на ферму. Вырастет капуста.

    "item_cuke": msg(
        emoji="""🥒""",
        text="""
        🥒 <b>Огурец</b>
        <i>Еда для крафта.</i>
        """,
        buttons=[
            [
                b(text="Купить огурец", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:cuke"),
                b(text="В крафт", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:cuke"),
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
    # Карточка урожая, полка «Ужин вместе». Сам искры не даёт. Кнопка «В крафт» открывает крафт.

    "item_tom": msg(
        emoji="""🍅""",
        text="""
        🍅 <b>Помидор</b>
        <i>Еда для крафта.</i>
        """,
        buttons=[
            [
                b(text="Купить помидор", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:tom"),
                b(text="В крафт", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:tom"),
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
    # Карточка урожая, полка «Ужин вместе». Сам искры не даёт, нужен для крафта.

    "item_cab": msg(
        emoji="""🥬""",
        text="""
        🥬 <b>Капуста</b>
        <i>Еда для крафта.</i>
        """,
        buttons=[
            [
                b(text="Купить капусту", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:cab"),
                b(text="В крафт", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:cab"),
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
    # Карточка урожая, полка «Ужин вместе». Сам искры не даёт, нужен для крафта.

    "item_juice": msg(
        emoji="""🥤""",
        text="""
        🥤 <b>Сок вдвоём</b>
        <i>Вместе. Обоим +{food_from}–{food_to} {food_word}.</i>
        """,
        buttons=[
            [
                b(text="Купить сок", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:juice"),
                b(text="Выпить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:juice"),
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
    # Карточка еды, полка «Ужин вместе». Едят вместе, искры получают оба. Пока on=False, в магазине скрыт.

    "item_soup": msg(
        emoji="""🍲""",
        text="""
        🍲 <b>Суп вдвоём</b>
        <i>Вместе. Обоим +{food_from}–{food_to} {food_word}.</i>
        """,
        buttons=[
            [
                b(text="Купить суп", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:soup"),
                b(text="Съесть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:soup"),
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
    # Карточка еды, полка «Ужин вместе». Едят вместе, искры получают оба. Пока on=False, в магазине скрыт.

    "item_salad": msg(
        emoji="""🥗""",
        text="""
        🥗 <b>Салат вдвоём</b>
        <i>Вместе. Обоим +{food_from}–{food_to} {food_word}.</i>
        """,
        buttons=[
            [
                b(text="Купить салат", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:salad"),
                b(text="Съесть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:salad"),
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
    # Карточка еды, полка «Ужин вместе». Едят вместе, искры получают оба. Пока on=False, в магазине скрыт.

    # Обряды. Кнопка одна: предмет уже у человека, покупать его не нужно.

    "rite_bouquet": msg(
        emoji="""💐""",
        text="""
        💐 <b>Букет</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Отдать букет", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:bouquet"),
            ],
        ],
        used="",
        title="Букет",
        name1="mrgbouquet",
        rite=True,
        effect="bouquet",
    ),
    # Обряд, не покупка. Кнопка видна, только если букет уже есть. Открывает букетный период на карточке.

    "rite_propose": msg(
        emoji="""💠""",
        text="""
        💠 <b>Колечко</b>
        <i>Предложение паре.</i>
        """,
        buttons=[
            [
                b(text="Сделать предложение", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:propose"),
            ],
        ],
        used="",
        title="Колечко",
        name1="mrgpropose",
        rite=True,
        effect="propose",
    ),
    # Обряд. Кнопка видна, если колечко уже есть. Ставит статус «сделал предложение».

    "rite_wedring": msg(
        emoji="""💎""",
        text="""
        💎 <b>Обручальное</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Надеть кольцо", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:wedring"),
            ],
        ],
        used="",
        title="Обручальное",
        name1="mrgring",
        rite=True,
        effect="family",
    ),
    # Обряд. Кнопка видна, если кольцо уже есть и предложение сделано. Ставит статус «семья».

    "rite_thread": msg(
        emoji="""🧵""",
        text="""
        🧵 <b>Красная нить</b>
        <i></i>
        """,
        buttons=[
            [
                b(text="Связать нить", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:thread"),
            ],
        ],
        used="",
        title="Красная нить",
        name1="mrgthread",
        rite=True,
        effect="thread",
    ),
    # Обряд. Кнопка видна, если нить уже есть. На карточке появится «Нить на месте»: пара держится, даже если огонёк погас.

    "item_quiet": msg(
        emoji="""🤫""",
        text="""
        🤫 <b>Тихий день</b>
        <i>Раз в неделю добивает вашу половину лимита.</i>
        """,
        buttons=[
            [
                b(text="Купить тихий день", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="success", go="gbuy", data="mrg:gbuy:quiet"),
                b(text="Затихнуть", icon="""<tg-emoji emoji-id='5388870246243274946'>❤</tg-emoji>""", color="primary", go="guse", data="mrg:guse:quiet"),
            ],
        ],
        used="Тихий день закрыл вашу половину.",
        title="Тихий день",
        name1="mrgquiet",
        price=40,
        care=0,
        effect="quiet",
    ),
    # Карточка предмета, полка «Тихий день». Раз в неделю добивает вашу половину, если не успели сами.
}


def screen_of_item(kind: str) -> str:
    """Экран предмета. Кнопки магазина читаются с него, а не из отдельного списка."""
    token = ":" + str(kind or "")
    found = ""
    for name, body in SCREENS.items():
        for row in iter_button_rows(body.get("buttons")):
            for button in row:
                data = str(button.get("data") or "")
                if not data.endswith(token):
                    continue
                if ":gbuy:" in data:
                    return name
                if ":guse:" in data:
                    found = found or name
    return found


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
TOP_ROW = "{n}. {a} и {b} · {span}"  # Одна строка списка «кто дольше». {n} место, {a} и {b} имена, {span} сколько вместе.
LIST_ROW = "{n}. {a} и {b} · {meta}"  # Одна строка списка всех пар. {meta} короткая пометка пары.
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
    "retry": "Не прошло. Нажмите ещё раз.",  # Всплывающее окно на кнопке, если действие не вышло. Тегов нет: Telegram их тут не рисует.
    "not_invited": "Отвечает только тот, кого позвали.",  # Всплывающее окно. «Согласиться» или «Отказать» нажал не тот, кого позвали.
    "not_payer": "Отменяет тот, кто написал «брак».",  # Всплывающее окно. «Отменить заявку» нажал не тот, кто написал «брак».
    "not_pair": "Это чужая пара.",  # Всплывающее окно. Кнопку чужой пары нажал посторонний.
    "closed": "Заявка уже закрыта.",  # Всплывающее окно. Заявку уже закрыли, кнопка опоздала.
    "expired": "Время вышло. Куты не списаны.",  # Всплывающее окно. Время заявки вышло. Куты не списаны.
    "busy": "Кто-то из двоих уже занят заявкой.",  # Всплывающее окно. У одного из двоих уже есть другая заявка.
    "till": "Куты не списаны. Попробуйте позже.",  # Всплывающее окно. Куты за свадьбу не списались, можно попробовать ещё раз.
    "till_rp": "Куты не списаны. Нажмите ещё раз.",  # Всплывающее окно. Куты за платное слово не списались.
    "no_marriage": "Брака нет. Ответьте «брак» на сообщение.",  # Всплывающее окно. Кнопку брака нажали без брака.
    "off": "Отношения выключены.",  # Всплывающее окно. В группе браки выключены, кнопка не работает.
    "rp_today": "Этот жест сегодня уже был.",  # Всплывающее окно. Это доброе слово сегодня уже было.
    "poor_gift": "Кутов не хватает. Предмет не куплен.",  # Всплывающее окно. Кутов не хватило, предмет не куплен.
    "ribbon_locked": "Лента открывается в новом браке.",  # Всплывающее окно. Лента в старом браке не открывается.
    "ribbon_toast": "Лента снята.",  # Всплывающее окно сразу после снятия ленты.
    "ribbon_note": "Лента на вас.",  # Короткая пометка, что лента уже на вас.
    "player": "игрок",  # Имя, если у человека нет имени в базе.
    "partner": "партнёром",  # Слово «партнёром» в старых фразах тонуса.
    "keeper": "создатель",  # Слово «создатель», когда праздничный дар передаёт создатель.
    "item": "Предмет",  # Запасное название предмета, если своего нет.
    "buy": "Купить",  # Запасная подпись «Купить», если у предмета нет своей кнопки.
    "use": "Использовать",  # Запасная подпись «Использовать».
    "take": "Взять",  # Запасная подпись «Взять» на кнопке использования.
    "buy_price": "Купить {price}",  # К кнопке покупки само дописывается цена, если в подписи её ещё нет. {price} — число.
    "farm": "На ферму",  # Подпись кнопки саженца. Живой текст — кнопка «На ферму» у саженца выше, эта строка подхватывается оттуда.
    "craft": "В крафт",  # Подпись кнопки урожая. Живой текст — кнопка «В крафт» у огурца выше.
    "level": "Уровень",  # Слово «Уровень» в старых строках.
    "support": "Поддержал отношения с {name}",  # История жеста: кто поддержал отношения. {name} партнёр. В чат как отдельное сообщение не уходит.
    "tone_ready": "Тонус {score} · сегодня уже учтён",  # Старая строка тонуса: сегодня уже учтён. {score} число.
    "tone_now": "Тонус {score} · {label}",  # Старая строка тонуса. {score} число, {label} одно из слов ниже.
    "tone_high": "в тонусе",  # Подпись тонуса, когда он высокий.
    "tone_mid": "спокойно",  # Подпись тонуса посередине.
    "tone_low": "тихо",  # Подпись тонуса, когда он низкий.
    "tone_cold": "остывает",  # Подпись тонуса, когда он остывает.
    "tone_up": "Жест сегодня поднимет тонус до {n}.",  # Подсказка, что жест поднимет тонус. {n} новое число.
    "tone_held": "Сегодня тонус уже {n}.",  # Подсказка, что тонус сегодня уже поднят. {n} текущее число.
    "spark_fading": "искра гаснет",  # Короткая пометка истории: искра гаснет.
    "spark_out": "искра погасла",  # Короткая пометка истории: искра погасла.
    "spark_day": "искра {days}",  # Короткая пометка истории: искра и число дней. {days}.
    "spark_new": "новая искра",  # Короткая пометка истории: искра только началась.
    "spark_family": "семья",  # Короткая пометка статуса «семья».
    "quiet_closed": "Тихий день закрыл вашу половину.",  # Фраза, когда тихий день закрыл вашу половину.
    "rite_ready": "Готово.",  # Короткая фраза, когда обряд сработал и своего текста нет.
    "no_bond": "Брака нет.",  # Короткая фраза, если обряд нажали без брака.
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
    "bouquet": "Букетный период открыт.",  # Чат, сразу после «Отдать букет».
    "propose": "Вы сделали предложение.",  # Чат, сразу после «Сделать предложение».
    "family": "Теперь у вас семейная жизнь.",  # Чат, сразу после «Надеть кольцо».
    "thread": "Нить держит пару, даже если искра погаснет.",  # Чат, сразу после «Связать нить».
    "ahead": "Эта ступень уже открыта.",  # Всплывающее окно. Этот обряд уже сделан.
}


# --- отказ предмета. {moon_from} и часы рассвета подставляются из панели ---

GIFT_ALERT = {
    "old": "Предметы откроются, когда брак будет новый.",  # Всплывающее окно. Предмет от старого брака, пока брак не новый.
    "bad": "Такого предмета нет.",  # Всплывающее окно. Такого предмета в браке нет.
    "none": "Этого предмета у вас нет.",  # Всплывающее окно. Предмета нет в инвентаре.
    "calm": "Спичка нужна, только если вчера не успели.",  # Спичка. Вчера всё успели, спасать нечего.
    "full": "Вчерашняя половина лимита уже набрана.",  # Спичка. Вчерашняя половина уже набрана.
    "worn": "Лента уже надета на вас.",  # Лента. Она уже надета.
    "fade": "Сейчас этот предмет не поможет.",  # Предмет не помогает в текущем состоянии огонька.
    "ahead": "Это уже сделано.",  # Всплывающее окно. Это действие уже сделано.
    "week": "Тихий день можно взять только один раз в неделю.",  # Тихий день. На этой неделе он уже был.
    "late": "Рассвет работает, только если вчерашний день ещё можно спасти.",  # Рассвет. Вчерашний день спасти уже нельзя.
    "day": "Сегодня это уже было.",  # Сегодня этот предмет уже использовали.
    "silent": "Сначала ответьте партнёру.",  # Сначала нужен ответ партнёру обычным сообщением.
    "done": "Ваша половина лимита на сегодня уже набрана.",  # Ваша половина на сегодня уже набрана, предмет не нужен.
    "night": "Луна работает только с {moon_from} до {moon_to} по Москве.",  # Луна днём. {moon_from} и {moon_to} — часы из вкладки «Браки».
    "sun": "Рассвет работает только с {dawn_from} до {dawn_to} по Москве.",  # Рассвет не в свои часы. {dawn_from} и {dawn_to} — из вкладки «Браки».
    "sworn": "Клятву можно прочитать только один раз за весь брак.",  # Клятву уже читали в этом браке.
    "behind": "Партнёр и так не отстаёт.",  # Партнёр не отстаёт, передавать ему нечего.
    "empty": "У вас ещё нет своей заботы.",  # Своих искр ещё нет, делить нечего.
    "spare": "Лишней заботы нет.",  # Лишних искр сверх половины нет.
    "held": "Этот предмет уже работает.",  # Предмет уже действует.
    "alive": "Ваши дни вместе ещё не пропали.",  # Дни вместе ещё не сгорали, возвращать нечего.
    "gone": "Возвращать уже нечего.",  # Возвращать уже нечего.
    "early": "Рано. Сначала вы оба должны закрыть сегодняшний день.",  # Рано: сегодня оба ещё не закрыли день.
    "heard": "Ответ уже есть.",  # Ответ паре сегодня уже есть.
    "cold": "Дни вместе уже пропали.",  # Дни вместе уже пропали, этот предмет их не вернёт.
    "said": "Предложение уже сказано.",  # Предложение уже сказано.
    "wait": "Сначала сделайте предложение.",  # Кольцо раньше предложения.
    "giver": "Кольцо дарит тот, кто сделал предложение.",  # Кольцо может отдать только тот, кто делал предложение.
    "kept": "Кольцо уже у вас.",  # Кольцо уже у этого человека.
    "home": "Вы уже семья.",  # Вы уже семья, шаг не нужен.
    "away": "Партнёра ещё нет в игре.",  # Партнёра ещё нет в игре, предмет не на кого применить.
    "field": "Саженец сажают на ферме.",  # Саженец. В чате он не тратится, его сажают на ферме.
    "cook": "Сначала приготовьте еду. Само оно заботу не даёт.",  # Урожай. Сам искры не даёт, сначала крафт.
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

FOOD_SAME = "Еда, которую вы едите вместе. Обоим добавится {food_to} {food_word} в отношениях."  # Описание общей еды, если у блюда нет своего курсива.

# Кто, кому и сколько. Число и слово «забота» подставляются.
CARE_YOU, CARE_MATE, CARE_BOTH = "Вам", "Партнёру", "Вам и партнёру"  # Начало фразы после предмета: кому легли искры.
CARE_ONE, CARE_FEW, CARE_MANY = "забота", "заботы", "забот"  # Склонение слова «забота» по числу.
CARE_GOT = "{who} добавилось {n} {word}."  # Чат после предмета, искры одному. {who} вам или партнёру, {n} число.
CARE_GOT_EACH = "{who} добавилось по {n} {word}."  # Чат после предмета, искры обоим.
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
    7: "Семь дней.",  # Подставляется в {aura} экрана feast на 7-й день серии.
    14: "Две недели.",  # {aura} на 14-й день.
    30: "Месяц.",  # {aura} на 30-й день.
    100: "Сто дней.",  # {aura} на 100-й день.
}
FEAST_TITLE = "Праздник"  # Короткий заголовок праздника.
FEAST_DAY = "День пары"  # Запасное имя дня, если своего нет.
FEAST_GIFT = "Дар"  # Запасное слово дара.
FEAST_REACHED = "Вы дошли до этого дня вместе."  # Чат, когда праздник только открылся.
FEAST_PICK = "Один дар. Откроется, когда оба выберут одно."  # Подсказка на экране праздника.
FEAST_NONE = "Между праздниками тихо."  # Кнопку праздника нажали, а дня ещё нет.
FEAST_EARLY = "Этот дар — с месяца вместе."  # Премиум на 6 месяцев раньше 30-го дня.
FEAST_WAIT = "Ждём тот же выбор пары."  # Вы уже выбрали, партнёр ещё нет или выбрал другое.
FEAST_DIFFER = "Выборы разные. Нужно одно и то же."  # Вы и пара назвали разные дары.
FEAST_OFF = "Этот дар сейчас закрыт."  # Создатель выключил этот приз.
FEAST_BOOK = "Книга праздников сейчас закрыта."  # Праздники выключены целиком.
FEAST_FUND_SHORT = "Праздничный фонд ещё не покрывает этот дар."  # В фонде не хватает кут на конверт.
FEAST_KEEPER_EMPTY = "Премиум ещё не готов. Создатель видит это."  # Приза премиума нет на складе.
FEAST_ENVELOPE = "Праздничный конверт из фонда: {amount} кут."  # Чат, когда паре выдали куты. {amount} сумма.
FEAST_SORRY = "Дар не успели приготовить. Вместо него праздничный конверт."  # Приз не собрался, вместо него куты.
FEAST_READY = "Праздничный дар уже у вас."  # Этот дар уже выдан.
FEAST_KEEPER_OK = "Премиум готовит @{name}. Это торжественный дар проекта."  # Паре: кто передаст премиум. {name} создатель.
FEAST_KEEPER_HOLD = "{heart} <b>Праздник · {name}</b>\nПредмет премиума уже у вас. Передайте его паре сами. Бот Telegram Premium не используется."  # Личное создателю: предмет уже у него, бот премиум не выдаёт.
FEAST_KEEPER_MISS = "{heart} <b>Праздник · {name}</b>\nПредмета премиума нет на складе или фонд его не покрыл. Передайте свой, если решите. Бот Telegram Premium не используется."  # Личное создателю: предмета нет.

PRIZE_COPY = {
    "envelope": "Праздничный конверт. Если дар не успели приготовить, пара получает куты.",  # Описание приза «Конверт» на экране праздника.
    "care": "Праздничная забота. Блик, свеча или очаг — каждому из двоих.",  # Описание приза «Забота».
    "ribbon": "Праздничная лента. В профиле останется знак этих отношений.",  # Описание приза «Лента в дар».
    "premium3": "Торжественный дар проекта на три месяца. Его передаёт создатель.",  # Описание премиума на 3 месяца.
    "premium6": "Большой праздник. Дар на шесть месяцев тоже передаёт создатель.",  # Описание премиума на 6 месяцев. Виден с 30-го дня.
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


# Старые описания из базы. Эти строки человек не редактирует: по ним код узнаёт старый текст и подменяет курсивом карточки предмета.
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
    "{heart} <code>" + HELP_CMD + "</code>\n"
    "<i>{pay} «{yes}» «{no}» · {ladder}</i>\n"
    "{spark} искра тонус «{level}» — по {each}\n"
    "<i>Доброе слово добавляет искры в вашу половину лимита. Оба набрали — выше лимит и награды.</i>"
)
# Справка по команде помощи брака. {pay} кто платит, {yes} и {no} подписи кнопок заявки, {ladder} уровни, {each} искры каждому, {level} имя первого уровня.
PROFILE_EMPTY = "{heart} Брака нет. «брак» на человека. Лимит дня пополам, доброе слово добавляет искры вам."  # Строка в профиле, когда брака нет. Одной строкой, без переноса.
PROFILE_WITH = "{mark} В браке с <b>{name}</b> · {span}"  # Строка в профиле, когда брак есть. {name} партнёр, на имя можно нажать. {span} сколько вместе. {mark} лента.
PROFILE_TONE = " · {tone}"  # Хвост строки профиля, если к ней дописывается тонус.
TONE_LINE = "{spark} <b>Тонус {score} · {label}</b>{tail}"  # Старая строка тонуса. При включённом огоньке карточка берёт FLAME_*, не эту строку.
PAIR_LINE = "Вы {you} из {need} · {partner} {other} из {need}"  # Старая строка «вы N из M». Живая карточка показывает полоски METER_*.
SPARE_LINE = "Запас: ты {yours} · {partner} {theirs}"  # Карточка «Мой брак» и «Лимит дня», если у обоих есть искры сверх половины. {yours} ваши лишние, {theirs} лишние пары.
SPARE_DAYS = " · ещё {ahead} дн."  # Хвост запаса, если лишних искр хватает ещё на целые дни. {ahead} сколько дней.
LIMIT_LINE = "<i>Лимит {goal}. Половина каждому {need}.</i>"  # Старая строка лимита. Живая карточка берёт LIMIT_HEAD.
LIMIT_HEAD = "<b>Лимит {goal}</b> · каждому {need} искр"  # Карточка «Мой брак». {goal} лимит дня, {need} сколько искр нужно каждому. Слово «Лимит» и число стоят вплотную.
BAR_ON = "●"  # Закрашенная клетка полоски искр на карточке и на «Лимит дня».
BAR_OFF = "○"  # Пустая клетка той же полоски.
METER_YOU = "🙂"  # Значок слева у вашей полоски.
METER_THEM = "💗"  # Значок слева у полоски пары.
METER_LINE = "{mark} <b>{who}</b> — {bar}"  # Одна полоска. {who} — «Вы» или имя пары, {bar} клетки и хвост.
METER_READY = "половина есть"  # Хвост полоски, когда половина уже набрана.
METER_LEFT = "ещё {left} искр"  # Хвост полоски, когда искр не хватает. {left} сколько ещё.
METER_EXTRA = "+{extra}"  # Хвост полоски, когда искр больше половины. {extra} лишние.
STEP_YOU = "<i>вам ещё {left} искр до половины · «Слово паре»</i>"  # Низ карточки в обычный день: вам не хватает искр. {left} сколько.
STEP_THEM = "<i>ваша половина есть · паре ещё {left} искр</i>"  # Низ карточки: ваша половина есть, паре ещё нет. {left} сколько паре.
STEP_FIRST_YOU = "<i>{when} · вам ещё {left} искр до половины · первый огонёк</i>"  # Низ карточки, огонька ещё не было и вчера можно спасти: не хватает вам. {when} — «сегодня до 12:00».
STEP_FIRST_THEM = "<i>{when} · паре ещё {left} искр до половины · ваша есть · первый огонёк</i>"  # То же, но не хватает паре, ваша половина уже есть.
STEP_FIRST_BOTH = "<i>{when} · вам ещё {you} искр · паре ещё {them} · первый огонёк</i>"  # То же, не хватает обоим. {you} и {them} — сколько каждому.
STEP_FIRST_WAIT = "<i>{when} · обе половины лимита уже набраны</i>"  # То же, обе половины уже набраны, ждём срок.
STEP_OPEN_YOU = "<i>{when} · вам ещё {left} искр до половины · иначе огонёк тухнет</i>"  # Низ карточки, серия уже была и сейчас гаснет: не хватает вам. Если не успеть, огонёк тухнет.
STEP_OPEN_THEM = "<i>{when} · паре ещё {left} искр · ваша половина есть</i>"  # Серия гаснет, ваша половина есть, не хватает паре.
STEP_OPEN_BOTH = "<i>{when} · вам ещё {you} искр · паре ещё {them}</i>"  # Серия гаснет, не хватает обоим.
STEP_OPEN_WAIT = "<i>{when} · обе половины лимита уже набраны</i>"  # Серия гаснет, но обе половины уже набраны.
HOME_YOU = "<i>Вам ещё {left} искр до половины. «Слово паре».</i>"  # Запасная фраза. Живая карточка берёт STEP_*.
HOME_THEM = "<i>Ваша половина есть. Ждём половину пары.</i>"  # Запасная фраза. Живая карточка берёт STEP_*.
NEXT_GIFT = "<i>дар</i> — день {day} · {name}"  # Строка карточки: ближайший праздник. {day} день серии, {name} его имя.
WAS_LINE = "<i>серия была {n} {word}.</i> Вы уже не чужие."  # Старая фраза, если серия уже сгорала.
WAS_SHORT = "<i>было {n} {word}.</i> Вы уже не чужие."  # Карточка, если серия уже сгорала. {n} сколько дней было.
HOME_TOGETHER = "<i>вместе</i> — <b>{span}</b>"  # Карточка «Мой брак»: сколько вместе по календарю. Это не длина огонька.
HOME_LEVEL = "<i>уровень</i> — <b>{name}</b>"  # Карточка: имя текущего уровня. Имена уровней задаются во вкладке «Браки».
CARD_HEAD = "{heart} <b>{a} и {b}</b>"  # Первая строка карточки. {a} и {b} имена, на них можно нажать.
CARD_TOGETHER = "<b>Вместе {span}</b>"  # Запасная карточка без огонька: сколько вместе.
CARD_DATE = "<i>{date}</i>"  # Запасная карточка: дата свадьбы.
CARD_TONE = "<i>{tone}</i>"  # Запасная карточка: строка тонуса.
CLOCK_WORD = "12:00"  # Час спасения вчера, если во вкладке «Браки» час не задан.
WHEN_TODAY = "сегодня до {clock}"  # Подставляется в {when}. Получается «сегодня до 12:00».
SPARK_ZERO = "{spark} <b>С нуля · {level}</b>"  # Старая шапка искры. Живой экран берёт FLAME_* и FIRE_*.
SPARK_FADE = "{spark} <b>Гаснет · {days}</b>"  # Старая шапка «гаснет». На карточке при нуле дней её нет.
SPARK_YESTERDAY = "<i>До {clock} закройте вчерашнюю половину.</i>"  # Старая строка про вчера. Живой экран берёт FIRE_YESTERDAY.
SPARK_LIVE = "{spark} <b>{days} · {level}</b>"  # Старая шапка живой серии.
SPARK_MIDNIGHT = "<i>Обе половины есть. В полночь серия длиннее.</i>"  # Старая строка: обе половины есть, серия вырастет в полночь.
FLAME_MARK = "🔥"  # Клетка полоски дней: в этот день огонёк горел.
FLAME_TODAY = "◌"  # Клетка сегодня, если день ещё не закрыт.
FLAME_OFF = "·"  # Клетка прошлого дня без огонька.
FLAME_NOW = "сегодня"  # Слово справа от полоски дней на карточке.
FLAME_NAMES = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")  # Дни недели. На карточку не выводятся.
FLAME_COUNT = "<i>огонёк</i> — <b>{days} {word}</b>"  # Карточка: строка «огонёк — N дней». {days} длина серии.
FLAME_OPEN = "◌ ещё можно зажечь"  # Под полоской, если сегодня ещё можно зажечь огонёк.
FLAME_LIT = "сегодня уже горит"  # Под полоской, если сегодня огонёк уже горит.
FLAME_FIRST = ""  # Пусто специально: при первом дне лишняя фраза не пишется.
FLAME_RISK = ""  # Пусто специально: отдельная фраза «гаснет» на карточку не выводится.
FLAME_ZERO = "◌ пока пусто"  # Под полоской, если огонька ещё нет.
SPARK_COAT = "<i>пальто</i> — бережёт один пропуск"  # Карточка, если надето пальто: один пропуск дня не сжигает серию.
LEVELS_TITLE = "<b>награды</b>"  # Первая строка экрана «Награды за дни».
LEVEL_LEAD = "<i>больше дней — выше лимит. Лимит делится пополам</i>"  # Вторая строка экрана наград: зачем копить дни.
LEVEL_NOW = " · сейчас"  # Хвост строки уровня, на котором пара стоит сейчас.
LEVEL_ROW = "<b>{name}</b> · {days} дн. · лимит {goal}, каждому {share}{mark}"  # Одна строка уровня. {name} {days} {goal} лимит, {share} сколько каждому. Числа приходят из вкладки «Браки».
LEVEL_NEXT = "до «{name}» ещё {days} дн. · лимит {goal}, каждому {share}"  # Строка следующего уровня: сколько дней осталось.
HOLIDAY_HEAD = "<b>дары</b>"  # Заголовок списка праздников на экране наград.
HOLIDAY_NOTE = "оба выбирают один дар"  # Пояснение под заголовком: дар один, выбрать его должны оба.
HOLIDAY_LINE = "<b>день {day}</b> · {name} · {gift}{mark}"  # Одна строка праздника. {gift} берётся из HOLIDAY_GIFT. {mark} — стрелка у ближайшего.
HOLIDAY_SOON = " ← скоро"  # Стрелка у ближайшего праздника, которого ещё нет.
HOLIDAY_GIFT = {
    7: "блик +3, куты или лента",  # Текст дара на экране наград, день 7.
    14: "свеча +8, куты или лента",  # День 14.
    30: "очаг +20 или премиум",  # День 30.
    100: "большой дар",  # День 100.
}
FIRE_FADE = "{spark} <i>вчера ещё живо</i> — {days}"  # Шапка «Лимит дня», когда вчера ещё можно спасти. {days} длина серии.
FIRE_YESTERDAY = "<i>сегодня до {clock}</i> · каждому ещё {need} искр за вчера"  # Под шапкой, когда вчера живо. {clock} час из панели, {need} сколько искр нужно было каждому.
FIRE_HEAD = "<b>{name}</b> · день {days}"  # Шапка «Лимит дня» в обычный день. {name} уровень, {days} день серии.
FIRE_SPLIT = "<b>Лимит {goal}</b> · каждому {need} искр"  # Строка лимита на экране «Лимит дня». «Лимит» и число стоят вплотную.
FIRE_DO = "<i>вам ещё {left} искр</i> · «Слово паре»"  # Низ «Лимит дня»: вам ещё не хватает искр. {left} сколько.
FIRE_WAIT = "<i>ваша половина есть</i> · ждём пару"  # Низ «Лимит дня»: ваша половина есть, ждём пару.
FIRE_DONE = "<i>обе половины лимита набраны</i>"  # Низ «Лимит дня»: обе половины набраны.
FIRE_TODAY = "Лимит {goal}. Половина каждому: {need}."  # Запасная фраза лимита, если экран не собрался.
CARE_SAVED = "<b>+{n}</b> · вчерашняя половина набрана"  # Сразу после слова или предмета, если закрылось вчера. {n} сколько искр пришло.
CARE_FADING = "<b>+{n}</b> искр вам · паре ещё нужна своя половина"  # Сразу после слова, если серия ещё гаснет и паре нужна своя половина.
CARE_PLUS = "<b>+{n}</b> искр в вашу половину лимита"  # Сразу после слова в обычный день: искры легли в вашу половину.
BOND_FAMILY = "{heart} <b>Семья</b>"  # Низ карточки, статус «семья».
BOND_YOU = "{heart} <b>Вы сделали предложение</b>"  # Низ карточки: предложение сделали вы.
BOND_THEM = "{heart} <b>Вам сделали предложение</b>"  # Низ карточки: предложение сделали вам.
BOND_BOUQUET = "{heart} <b>Букет</b>"  # Низ карточки: открыт букет.
TALK_BOTH = "{spark} <i>вы уже написали друг другу</i>"  # Низ карточки: сегодня вы уже написали друг другу обычным ответом.
TALK_YOU = "{spark} <i>вы написали</i> · ждём пару"  # Низ карточки: написали вы, пара ещё нет.
TALK_THEM = "{spark} <i>пара написала</i> · ответьте хоть слово"  # Низ карточки: написала пара, вы ещё нет.
TALK_NONE = "{spark} <i>напишите паре хоть слово</i> · и паре тоже"  # Низ карточки: сегодня ещё никто не написал.
STATS_LINE = "<b>{name}</b>\n{pair}\n<i>всего искр</i> — {total}"  # Весь экран «Все искры». {name} уровень, {pair} полоски, {total} сколько искр за всё время.
SHOP_HOME = SCREENS["shop"]["text"]
GIFT_TITLE = "<blockquote><b>магазин</b>\n<i>цена как в общем магазине</i></blockquote>"  # Старый заголовок магазина. Живая первая страница — экран shop.
GIFT_STOCK = " · у вас {have}"  # Хвост строки предмета: сколько уже лежит у человека. {have}.
GIFT_ROW = "{emoji} <b>{name}</b> — {price} кут\n<i>{about}{stock}</i>"  # Старая строка предмета с ценой, если полка рисуется текстом, а не кнопками.
GIFT_FREE = "{emoji} <b>{name}</b>\n<i>{about}{stock}</i>"  # Та же строка, если цены нет.
SHOP_FIRE = "<blockquote><b>искры</b> — добрать свою половину лимита</blockquote>"  # Шапка полки «Искры к лимиту».
SHOP_MARK = "<blockquote><b>знак</b> — лента и кольца</blockquote>"  # Шапка полки «Знаки пары».
SHOP_MEAL = "<blockquote><b>ужин</b> — вместе</blockquote>"  # Шапка полки «Ужин вместе».
SHOP_QUIET = "<blockquote><b>тихий день</b> — добивает вашу половину лимита</blockquote>"  # Шапка полки «Тихий день».
GIFT_RIBBON = "🎀 <i>Лента уже на вас.</i>"  # Пометка на полке, если лента уже надета.
GIFT_EMPTY = "<i>Пока пусто.</i>"  # Полка, на которой пока нет предметов.
RIBBON_ON = SCREENS["ribbon_worn"]["text"]
RIBBON_OFF_HOME = SCREENS["ribbon_none"]["text"]
RIBBON_ASK = SCREENS["ribbon_ask"]["text"]
RIBBON_GONE = "🎀 <b>Лента снята</b>"  # Сообщение сразу после того, как ленту сняли.
VERB_PRICE = "{label} · {price}"  # Дописывается к кнопке доброго слова, если оно стоит кут. {label} слово, {price} цена.
RP_LINE = SCREENS["gest"]["text"]

TODAY_WORD = "сегодня"  # Слово «сегодня» в сроке «вместе», если брак начался сегодня.
HALF_YEAR = "полгода"  # Срок «вместе»: полгода.
ONE_YEAR = "год"  # Срок «вместе»: год.
YEAR_AND_HALF = "полтора года"  # Срок «вместе»: полтора года.
SPAN_SEC = ("секунду", "секунды", "секунд")  # Склонение секунд в сроке «вместе» и в паузе слова.
SPAN_MIN = ("минуту", "минуты", "минут")  # Склонение минут.
SPAN_HOUR = ("час", "часа", "часов")  # Склонение часов.
SPAN_DAY = ("день", "дня", "дней")  # Склонение дней огонька и срока «вместе».
SPAN_WEEK = ("неделю", "недели", "недель")  # Склонение недель.
SPAN_MONTH = ("месяц", "месяца", "месяцев")  # Склонение месяцев.
SPAN_YEAR = ("год", "года", "лет")  # Склонение лет.

SEED_PREFIX = "Саженец "  # Начало имени саженца в магазине. От него отрезается показ короткого имени.
NAME_TAIL = " брака"  # Хвост « брака» в имени предмета. В коротком имени отрезается.
PAIR_TAIL = " вдвоём"  # Хвост « вдвоём» в имени предмета. В коротком имени отрезается.
SEED_FRUIT = {"огурца": "Огурец", "помидора": "Помидор", "капусты": "Капуста"}  # Короткое имя саженца на кнопке: «Саженец огурца» показывается как «Огурец».


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
