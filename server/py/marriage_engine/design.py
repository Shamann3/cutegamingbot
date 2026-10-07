# -*- coding: utf-8 -*-
"""Браки. Цены, фразы, тексты и жесты правятся здесь.

Сообщения короткие. Кто что нажимает, видно по кнопкам.
Красный знак во всех текстах — одно премиум-сердце.

Куда уходят куты, здесь не переключается: свадьба и платный жест
садятся в ту же кассу, что и комиссия игр.
"""
from __future__ import annotations

import textwrap


def t(text) -> str:
    if text is None:
        return ""
    return textwrap.dedent(str(text)).strip("\n")


def emo(emoji_id: str, fallback: str) -> str:
    return f"<tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji>"


# --- Деньги. Первые FREE свадьбы того, кто зовёт, бесплатны.
FREE_WEDDINGS = 3
FIRST_PAID = 15
DOUBLE_UNTIL = 300
AFTER_PERCENT = 15

PROPOSAL_MINUTES = 10
RP_PER_VERB_A_DAY = 1
SHOW_EMPTY_PROFILE = True
TOP_LIMIT = 10

# Красные знаки. Сердце — то же, что на кнопке «Отношения» и на «красном» в рулетке.
# Точка — красная ячейка шкалы предупреждений.
RED_ID = "5388870246243274946"
DOT_ID = "5337017423906226569"
NO_ID = "5226660202035554522"
HEART = emo(RED_ID, "❤")
SPARK = emo(DOT_ID, "🔴")
RING = HEART
DOVE = HEART
NO = HEART

# Сколько часов после полуночи ещё можно спасти вчерашнюю искру.
RESCUE_HOURS = 12

# Предметы брака. Полка магазина — сердца. Имя в рюкзаке совпадает с dex.name.
# Блик, свеча и очаг кладут разное число заботы только нажавшему.
# Лишнее остаётся и каждый день сгорает на его половину нормы.
HEARTS_SHELF = "💕"
GIFTS = (
    {"id": "glow", "name": "Блик брака", "name1": "mrgglow", "emoji": "🎇", "price": 12, "care": 3, "buy": "Купить блик", "use": "Блеснуть"},
    {"id": "candle", "name": "Свеча брака", "name1": "mrgcandle", "emoji": "🕯", "price": 25, "care": 8, "buy": "Купить свечу", "use": "Зажечь"},
    {"id": "hearth", "name": "Очаг брака", "name1": "mrghearth", "emoji": "🎆", "price": 70, "care": 20, "buy": "Купить очаг", "use": "Разжечь"},
    {"id": "match", "name": "Спичка брака", "name1": "mrgmatch", "emoji": "🪔", "price": 80, "care": 0, "buy": "Купить спичку", "use": "Чиркнуть"},
    {"id": "ribbon", "name": "Лента брака", "name1": "mrribbon", "emoji": "🎀", "price": 150, "care": 0, "buy": "Купить ленту", "use": "Надеть"},
)


def gift_names():
    return frozenset(item["name"] for item in GIFTS)


def gift_text(rows, ribbon: bool = False) -> str:
    lines = [
        f"{HEART} <b>Предметы пары</b>",
        "<i>Та же полка сердец, что в магазине. Куты уходят в кассу игр.</i>",
    ]
    for row in rows:
        plus = int(row.get("care") or 0)
        mark = f" · +{plus}" if plus else ""
        lines.append(
            f"{row['emoji']} <b>{row['name']}</b> · <u>{int(row['price'])} кут</u>{mark} · у вас {int(row['have'])}"
        )
    lines.append("<i>Блик, свеча и очаг кладут разную заботу только вам. Лишнее остаётся и каждый день сгорает на вашу половину. Спичка закрывает только вчера. Лента — знак в профиле.</i>")
    if ribbon:
        lines.append(f"{SPARK} <b>Лента уже на этой паре.</b>")
    return "\n".join(lines)


GIFT_ALERT = {
    "fade": "Свеча на сегодня. Сначала спасите вчера.",
    "full": "Ваша доля уже закрыта.",
    "calm": "Спичка только пока искра гаснет.",
    "worn": "Лента на этой паре уже надета.",
    "none": "Этого предмета нет. Купите его здесь или в магазине.",
    "old": "Этот брак из старой книги. Предметы откроются в новом.",
    "bad": "Такого предмета нет.",
}


def gift_by_id(kind: str):
    for item in GIFTS:
        if item["id"] == kind:
            return item
    return None


# Серия в днях, имя уровня, забота пары за день. С каждого — половина, оба обязаны.
LEVELS = (
    {"id": 1, "days": 0, "name": "Знакомство", "goal": 10},
    {"id": 2, "days": 3, "name": "Тепло", "goal": 16},
    {"id": 3, "days": 7, "name": "Близость", "goal": 22},
    {"id": 4, "days": 14, "name": "Пара", "goal": 30},
    {"id": 5, "days": 30, "name": "Союз", "goal": 40},
)

# Кнопки. В подписи нет тегов. Текст кнопки совпадает со смыслом, не с абзацем.
BTN_NO = "Отказать"
BTN_YES = "Согласиться"
BTN_STOP = "Отменить"
BTN_STAY = "Остаться"
BTN_LEAVE = "Развестись"
BTN_CARD_LEAVE = "Расторгнуть"
BTN_TONE = "Искра"
BTN_GEST = "Поддержать"
BTN_LEVEL = "Уровень"
BTN_WHAT = "Что это?"
BTN_HOW = "Как пользоваться?"
BTN_HOLD = "Как держать искру?"
BTN_STAT = "Статистика"
BTN_GIFT = "Предметы"
BTN_BACK = "К паре"
BTN_MINE = "Мой брак"
BTN_TOP = "Топ"
BTN_LIST = "Пары"
BTN_SKIP = "Не сейчас"

VERB_LABEL = {
    "hug": "Обнять",
    "kiss": "Поцеловать",
    "peck": "Чмок",
    "air": "Воздушный",
    "praise": "Похвалить",
    "stroke": "Погладить",
    "rose": "Роза",
    "compliment": "Комплимент",
    "hand": "За руку",
    "night": "На ночь",
}

# Жесты. Длинная фраза важнее короткой: это проверяет код.
# price — кут. 0 значит бесплатно.
RP = (
    {"id": "hug", "verbs": ("обнять", "обними", "обнимаю", "обнимашки"), "emoji": HEART, "does": "обнимает", "price": 0, "care": 4},
    {"id": "kiss", "verbs": ("поцеловать", "поцелуй", "поцелую"), "emoji": HEART, "does": "целует", "price": 0, "care": 4},
    {"id": "peck", "verbs": ("чмокнуть", "чмок"), "emoji": HEART, "does": "чмокает", "price": 0, "care": 2},
    {"id": "air", "verbs": ("воздушный поцелуй",), "emoji": HEART, "does": "шлёт воздушный поцелуй", "price": 0, "care": 2},
    {"id": "praise", "verbs": ("похвалить", "хвалю"), "emoji": HEART, "does": "хвалит", "price": 0, "care": 3},
    {"id": "stroke", "verbs": ("погладить", "погладь"), "emoji": HEART, "does": "гладит", "price": 0, "care": 2},
    {"id": "rose", "verbs": ("подарить розу", "роза", "розу"), "emoji": HEART, "does": "дарит розу", "price": 0, "care": 5},
    {"id": "compliment", "verbs": ("сказать комплимент", "комплимент"), "emoji": HEART, "does": "говорит комплимент", "price": 0, "care": 3},
    {"id": "hand", "verbs": ("взять за руку", "держать за руку", "за руку"), "emoji": HEART, "does": "берёт за руку", "price": 0, "care": 2},
    {"id": "night", "verbs": ("спокойной ночи", "доброй ночи"), "emoji": HEART, "does": "желает спокойной ночи", "price": 0, "care": 3},
)

# Эти слова уже есть в общем рп. Если ответ не своей паре, общее рп не перехватываем.
SHARED_WITH_GENERAL_RP = frozenset({
    "обнять", "поцеловать", "чмок", "воздушный поцелуй", "похвалить", "погладить",
})

WED_WORDS = (
    "выйти замуж", "предложение руки", "рука и сердце",
    "бракосочетание", "пожениться", "поженится", "поженимся",
    "женитьба", "жениться", "женимся", "свадьба", "замуж",
    "предложение", "брак",
)
CARD_WORDS = (
    "карточка брака", "статус брака", "мой брак", "наш брак",
    "моя пара", "наша пара",
)
TONE_WORDS = (
    "тонус брака", "тонус пары", "наш тонус", "мой тонус", "тонус",
    "наша искра", "моя искра", "искра",
)
LEAVE_WORDS = (
    "расторгнуть брак", "развод брака", "развестись", "разведемся", "разведёмся",
    "разводимся", "разведись", "расторгнуть", "расторжение", "развод",
)
TOP_WORDS = ("топ браков", "топ браки", "топ брака", "топ пар")
LIST_WORDS = (
    "список браков", "браки чата", "браки группы", "кто в браке",
    "пары чата", "браки",
)
ON_WORDS = ("+браки", "+ браки", "включить браки")
OFF_WORDS = ("-браки", "- браки", "выключить браки")
HELP_TAIL = ("хелп", "помощь", "help")


def verb_button(verb_id: str, price: int = 0, care: int = 0) -> str:
    label = VERB_LABEL.get(str(verb_id), str(verb_id))
    try:
        amount = int(price)
    except (TypeError, ValueError):
        amount = 0
    try:
        plus = int(care)
    except (TypeError, ValueError):
        plus = 0
    if amount > 0:
        return f"{label} · {amount}"
    if plus > 0:
        return f"{label} +{plus}"
    return label


def pay_label(amount) -> str:
    return f"Списать {amount} кут"


ALERT_RETRY = "Не получилось. Нажмите ещё раз."
ALERT_NOT_INVITED = "Отказать и согласиться может только тот, кого позвали."
ALERT_NOT_PAYER = "Отменить может только тот, кто написал «брак»."
ALERT_NOT_PAIR = "Это может нажать только тот, кто в этом браке."
ALERT_CLOSED = "Заявка уже закрыта. Если брак нужен, напишите «брак» ещё раз."
ALERT_EXPIRED = "Время вышло. Куты не списаны."
ALERT_BUSY = "Сейчас нельзя: кто-то из двоих уже в браке или в другой заявке."
ALERT_TILL = "Куты не списаны. Проект их не принял. Попробуйте чуть позже."
ALERT_TILL_RP = "Куты не списаны. Нажмите ещё раз чуть позже."
ALERT_NO_MARRIAGE = "Брака нет. Ответьте «брак» на сообщение человека."
ALERT_OFF = "Отношения выключены. Куты не списаны."
ALERT_RP_TODAY = "Этот жест сегодня уже был. Другой можно сейчас."


def help_page(settings=None) -> str:
    src = settings if isinstance(settings, dict) else {}
    free = int(src.get("freeWeddings", FREE_WEDDINGS))
    first = int(src.get("firstPaid", FIRST_PAID))
    cap = int(src.get("doubleUntil", DOUBLE_UNTIL))
    percent = int(src.get("afterPercent", AFTER_PERCENT))
    minutes = int(src.get("proposalMinutes", PROPOSAL_MINUTES))
    per = int(src.get("rpPerDay", RP_PER_VERB_A_DAY))
    daily = "один раз в сутки" if per <= 1 else f"до {per} раз в сутки"
    rows = src.get("levels") if isinstance(src.get("levels"), list) and src.get("levels") else LEVELS
    first_row = rows[0] if isinstance(rows[0], dict) else {"name": "Знакомство", "goal": 10}
    goal = int(first_row.get("goal") or 10)
    each = max(1, (max(2, goal) + 1) // 2)
    level_name = str(first_row.get("name") or "Знакомство")
    return t(f"""
    {HEART} <b>Отношения</b>
    <i>Один брак на весь Кут. В профиле он под активностью.</i>

    <b>Команды</b>
    <blockquote><b><code>брак</code> ответом на сообщение
    <code>Мой брак</code> карточка и кнопки
    <code>Искра</code> кто уже дал заботу сегодня
    <code>Развод</code> спросит ещё раз
    <code>Браки</code> пары этой группы
    <code>Топ браков</code> кто вместе дольше</b></blockquote>
    <i>То же самое: жениться, развестись, наш брак, тонус.</i>

    <b>Цена</b>
    <blockquote><b><i>Платит тот, кто написал «брак».
    Первые <u>{free}</u> свадьбы бесплатно, затем <u>{first}</u> кут.
    Дальше цена удваивается до <u>{cap}</u>, потом каждая новая <u>+{percent}%</u>.
    Куты уходят проекту только после «{BTN_YES}».
    «{BTN_NO}» и молчание ничего не списывают.
    Заявка живёт <u>{minutes}</u> мин.</i></b></blockquote>

    {SPARK} <b>Искра</b>
    <blockquote><b><i>Серия дней, как огонёк. Оба каждый день дают свою заботу.
    Уровень 1 «{level_name}» — <u>{goal}</u> заботы вместе, по {each} с каждого.
    С уровнем норма растёт. Один за двоих день не закрывает.
    Если день сорвался, искру можно спасти несколько часов после полуночи.
    Один и тот же жест можно {daily}. Кнопка «{BTN_GEST}» делает то же, что слово.
    Блик, свеча и очаг дают разную заботу. Лишнее остаётся и сгорает каждый день на вашу половину.
    Спичка и лента тоже на полке сердец и в кнопке «{BTN_GIFT}».</i></b></blockquote>

    <i>+браки и -браки пишет создатель группы.</i>
    """)


_WHO = t(f"""
<i>«{BTN_NO}» и «{BTN_YES}» нажимает только тот, кого позвали. «{BTN_STOP}» — тот, кто звал.</i>
""")

PROPOSE_FREE = t(f"""
{{heart}} <b>{{b}}, вам предложение.</b>
<b>{{a}} зовёт в брак.</b>
<i>Бесплатно · свадьба <u>{{which}}</u> из <u>{{free}}</u> · {{minutes}} мин.</i>
{_WHO}
""")

PROPOSE_PAID = t(f"""
{{heart}} <b>{{b}}, вам предложение.</b>
<b>{{a}} зовёт в брак · <u>{{price}} кут</u>.</b>
<i>Спишутся только после согласия · {{minutes}} мин. Платит {{a}}.</i>
{_WHO}
""")

WED_OK_FREE = t("""
{heart} <b>{a} и {b} в браке.</b>
{spark} <i>Куты не списывались. Искру держат оба: сегодня по {each} заботы.</i>
""")

WED_OK_PAID = t("""
{heart} <b>{a} и {b} в браке.</b>
{spark} <i>Списано <u>{price} кут</u> с того, кто звал. Искру держат оба: сегодня по {each} заботы.</i>
""")


def card_text(a: str, b: str, span: str, date: str, tone: str) -> str:
    lines = [f"{HEART} <b>{a} и {b}</b>", f"<b>Вместе {span}</b>"]
    if date:
        lines.append(f"<i>{date}</i>")
    if tone:
        lines.append(f"<b>{tone}</b>")
    return "\n".join(lines)


def _pair_line(you: int, need: int, partner_name: str, partner_care: int) -> str:
    return f"Ты {int(you)}/{int(need)} · {partner_name} {int(partner_care)}/{int(need)}"


def _spare_line(you: int, partner_care: int, need: int, partner_name: str) -> str:
    yours = max(0, int(you) - int(need))
    theirs = max(0, int(partner_care) - int(need))
    if yours <= 0 and theirs <= 0:
        return ""
    return f"Запас: ты {yours} · {partner_name} {theirs}. Каждый день сгорает по {int(need)}."


def spark_home(a: str, b: str, span: str, date: str, view: dict, you: int, partner_care: int, partner_name: str) -> str:
    level = str((view.get("level") or {}).get("name") or "Знакомство")
    days = int((view.get("state") or {}).get("spark_days") or 0)
    need = int(view.get("need") or 0)
    lines = [f"{HEART} <b>{a} и {b}</b>", f"<b>Вместе {span}</b>"]
    if date:
        lines.append(f"<i>{date}</i>")
    if int(view.get("lost") or 0) > 0:
        lines.append(f"{SPARK} <b>Искра погасла. Серия с нуля.</b>")
        lines.append(f"<i>Снова «{level}». Сегодня по {need} с каждого.</i>")
        lines.append(f"<b>{_pair_line(you, need, partner_name, partner_care)}</b>")
    elif view.get("fading"):
        lines.append(f"{SPARK} <b>Искра гаснет · серия {days}</b>")
        lines.append(f"<i>До {view.get('clock') or 'полудня'} оба добирают вчера.</i>")
        lines.append(f"<b>{_pair_line(you, need, partner_name, partner_care)}</b>")
    else:
        lines.append(f"{SPARK} <b>Искра {days} · {level}</b>")
        lines.append(f"<b>{_pair_line(you, need, partner_name, partner_care)}</b>")
        spare = _spare_line(you, partner_care, need, partner_name)
        if spare:
            lines.append(f"<i>{spare}</i>")
        if view.get("both_done"):
            lines.append("<i>Сегодня оба добрали. День зачтётся в полночь.</i>")
    return "\n".join(lines)


def spark_fire(view: dict, you: int, partner_care: int, partner_name: str, hours: int) -> str:
    need = int(view.get("need") or 0)
    goal = int(view.get("goal") or 0)
    name = str((view.get("level") or {}).get("name") or "Знакомство")
    days = int((view.get("state") or {}).get("spark_days") or 0)
    if view.get("fading"):
        head = f"{SPARK} <b>Вчера не закрыт. Серия {days} ещё жива.</b>"
        sub = f"До {view.get('clock') or 'дедлайна'} каждый добирает свои {need}."
    else:
        head = f"{SPARK} <b>Искра {days} дней · {name}</b>"
        sub = f"Сегодня вместе {goal} заботы. С каждого по {need}."
    spare = _spare_line(you, partner_care, need, partner_name)
    lines = [
        head,
        f"<b>{_pair_line(you, need, partner_name, partner_care)}</b>",
        f"<i>{sub} Один за двоих не считается. Если день сорвётся, спасти можно {int(hours)} ч. после полуночи.</i>",
    ]
    if spare:
        lines.append(f"<i>{spare}</i>")
    return "\n".join(lines)


def spark_level(view: dict) -> str:
    current = int((view.get("level") or {}).get("id") or 1)
    rows = view.get("table") if isinstance(view.get("table"), list) and view.get("table") else LEVELS
    lines = [f"{SPARK} <b>Уровни искры</b>", "<i>Норма — забота пары за день. По половине с каждого.</i>"]
    for row in rows:
        mark = " · сейчас" if int(row["id"]) == current else ""
        each = (int(row["goal"]) + 1) // 2
        lines.append(f"<b>{row['id']}. {row['name']}</b> <i>с {row['days']} дн. · {row['goal']} вместе · по {each}{mark}</i>")
    nxt = view.get("next")
    if nxt:
        left = int(view.get("days_left") or 0)
        lines.append(f"<i>До «{nxt['name']}»: ещё {left} дн. искры.</i>")
    else:
        lines.append("<i>Это верхний уровень. Норма больше не растёт.</i>")
    return "\n".join(lines)


def spark_stats(view: dict, you: int, partner_care: int, partner_name: str) -> str:
    state = view.get("state") or {}
    level = view.get("level") or {}
    need = int(view.get("need") or 0)
    lines = [
        f"{HEART} <b>Статистика пары</b>",
        f"{SPARK} <b>Искра {int(state.get('spark_days') or 0)} · лучшая {int(state.get('spark_best') or 0)}</b>",
        f"<b>Уровень {int(level.get('id') or 1)} · {level.get('name') or 'Знакомство'}</b>",
        f"<i>{_pair_line(you, need, partner_name, partner_care)}</i>",
        f"<i>Всего заботы: {int(state.get('care_total') or 0)}</i>",
    ]
    spare = _spare_line(you, partner_care, need, partner_name)
    if spare:
        lines.append(f"<i>{spare}</i>")
    nxt = view.get("next")
    if nxt:
        lines.append(f"<i>До «{nxt['name']}»: ещё {int(view.get('days_left') or 0)} дн.</i>")
    return "\n".join(lines)


WHAT_TEXT = t(f"""
{HEART} <b>Что это</b>
{SPARK} <i>Искра — серия вашей пары. Она горит, пока оба каждый день дают заботу.
Уровень растёт вместе с серией. С уровнем растёт и норма заботы.</i>
""")

HOW_TEXT = t(f"""
{HEART} <b>Как пользоваться</b>
<i>Откройте «мой брак».
«{BTN_GEST}» — жест, он даёт заботу.
Или ответьте на сообщение пары: обнять, роза.
«{BTN_TONE}» показывает, кто уже дал свою часть.</i>
""")

HOLD_TEXT = t(f"""
{SPARK} <b>Как держать искру</b>
<i>Оба в один день добирают свою половину.
Один человек не может закрыть день за двоих.
Если дать больше нормы, лишнее остаётся и каждый день сгорает ровно на вашу половину.
Чем длиннее серия, тем выше уровень и тем больше заботы нужно.
Сорванный день можно спасти только до дедлайна. Потом серия с нуля.</i>
""")


def care_line(amount: int, you: int, need: int, partner_care: int, saved: bool, both: bool, fading: bool) -> str:
    left = int(you)
    whole = int(need)
    spare = max(0, left - whole)
    if saved:
        stock = f" У тебя осталось {left}." if left else ""
        return f"{SPARK} <b>Искру спасли.</b>\n<i>Серия на месте. Этот жест закрыл вчера.{stock}</i>"
    if fading:
        return (
            f"{SPARK} <b>+{int(amount)} заботы во вчера.</b>\n"
            f"<i>Ты {left}/{whole} · пара {int(partner_care)}/{whole}</i>"
        )
    tail = "Сегодня оба добрали." if both else "Пара тоже должна дать свою часть."
    stock = f" Лишнее {spare} останется." if spare else ""
    return (
        f"{SPARK} <b>+{int(amount)} заботы · ты {left}/{whole}</b>\n"
        f"<i>{tail}{stock}</i>"
    )


def tone_text(score: int, label: str, hint: str) -> str:
    return t(f"""
    {HEART} <b>Тонус {int(score)} из 100 · {label}</b>
    <i>{hint}</i>
    """)


NEED_REPLY = t("""
{heart} <b>Ответьте «брак» на сообщение человека.</b>
<i>Второй нажмёт «Согласиться». Заявка живёт {minutes} мин.</i>
""")

PRIVATE = t("""
{heart} <b>Это делается в группе.</b>
<i>Ответьте там «брак» на сообщение человека.</i>
""")

OFF = t("""
{heart} <b>В этой группе браки выключены.</b>
<i>Включит создатель: +браки. «Мой брак» и «развод» у пары остаются.</i>
""")

ALREADY_YOU = t("""
{heart} <b>Вы уже в браке с {b}.</b>
<i>Второй брак не открывается. Карточка: «мой брак».</i>
""")

ALREADY_THEM = t("""
{heart} <b>{b} уже в браке.</b>
<i>Пока тот брак не расторгнут, предложение не уйдёт.</i>
""")

SELF = t("""
{heart} <b>С самим собой в брак не вступают.</b>
<i>Ответьте «брак» на сообщение другого человека.</i>
""")

BOT = t("""
{heart} <b>Боту предложение не отправляют.</b>
<i>Ответьте «брак» на сообщение человека.</i>
""")

NOT_FOUND = t("""
{heart} <b>Этого человека в Куте ещё нет.</b>
<i>Пусть напишет боту любое сообщение. Потом «брак» ещё раз.</i>
""")

POOR = t("""
{heart} <b>Нужно <u>{price} кут</u>, у вас {have}.</b>
<i>Платит тот, кто пишет «брак». Ничего не списано.</i>
""")

POOR_LATE = t("""
{heart} <b>Нужно <u>{price} кут</u>, их уже нет.</b>
<i>Заявка закрыта. Ничего не списано.</i>
""")

TILL_CLOSED = t("""
{heart} <b>Куты не списаны.</b>
<i>Проект их сейчас не принял. Заявку можно отправить ещё раз.</i>
""")

BUSY = t("""
{heart} <b>Прошлое предложение ещё ждёт.</b>
<i>На том сообщении есть «Отменить». Новую заявку пока нельзя.</i>
""")

REFUSED = t("""
{heart} <b>{b} в этот брак не вступает.</b>
<i>Куты не списаны.</i>
""")

STOPPED = t("""
{heart} <b>Заявка отменена.</b>
<i>Куты не списывались.</i>
""")

EXPIRED = t("""
{heart} <b>{minutes} мин. без ответа.</b>
<i>Заявка закрыта. Куты не списаны.</i>
""")

PROJECT_OFF = t("""
{heart} <b>Отношения сейчас выключены.</b>
<i>Новую заявку отправить нельзя. «Мой брак» и «развод» у пары остаются.</i>
""")

LEAVE_ASK = t("""
{heart} <b>Расторгнуть брак с {b}?</b>
<i>Дни обнулятся. Куты за свадьбу не вернутся.</i>
""")

STAY_OK = t("""
{heart} <b>Брак на месте.</b>
<i>Карточка по-прежнему открывается словами «мой брак».</i>
""")

LEAVE_OK = t("""
{heart} <b>{a} и {b} больше не в браке.</b>
<i>Дни обнулились. Куты за ту свадьбу не возвращаются.</i>
""")

LEAVE_THEM = t("""
{heart} <b>Брак расторгнут. Это решение {a}.</b>
<i>Новый брак снова начинается со слова «брак».</i>
""")

NOT_MARRIED = t("""
{heart} <b>Брака нет.</b>
<i>В группе ответьте «брак» на сообщение человека.</i>
""")

TONE_OLD = t("""
{heart} <b>У этого брака тонус ещё без числа.</b>
<i>Карточка открывается словами «мой брак».</i>
""")

RP_LINE = t("""
{emoji} <b>{a} {does} {b}</b>
""")

RP_NOTE = t("""
<blockquote><b><i>{note}</i></b></blockquote>
""")

RP_ONLY_PAIR = t("""
{heart} <b>Этот жест пишут своей паре.</b>
<i>Кто это, покажет «мой брак».</i>
""")

RP_NEED_WED = t("""
{heart} <b>Сначала брак.</b>
<i>Ответьте «брак» на сообщение человека.</i>
""")

RP_TOMORROW = t("""
{heart} <b>«{title}» сегодня уже было.</b>
<i>Такой же жест завтра. Другой можно сейчас.</i>
""")

RP_PAY_ASK = t("""
{heart} <b>«{title}» стоит <u>{price} кут</u>.</b>
<i>Спишутся с вас и уйдут проекту. Жест — раз в сутки.</i>
""")

RP_POOR = t("""
{heart} <b>Нужно <u>{price} кут</u>, у вас {have}.</b>
<i>Ничего не списано. Жест не сделан.</i>
""")

RP_DONE = t("""
<i>{tone}</i>
""")

SKIP_OK = t("""
{heart} <b>Жест не сделан.</b>
<i>Куты не списаны.</i>
""")

ON_OK = t("""
{heart} <b>Браки в этой группе включены.</b>
<i>«Брак» ответом на сообщение, второй нажимает «Согласиться».</i>
""")

OFF_OK = t("""
{heart} <b>Браки в этой группе выключены.</b>
<i>Новые предложения здесь не проходят. Пара может открыть «мой брак» и «развод».</i>
""")

ON_ALREADY = t("""
{heart} <b>Браки здесь уже включены.</b>
<i>Выключить: -браки. Это пишет создатель группы.</i>
""")

OFF_ALREADY = t("""
{heart} <b>Браки здесь уже выключены.</b>
<i>Включить: +браки</i>
""")

CREATOR_ONLY = t("""
{heart} <b>Это пишет только создатель группы.</b>
<i>+браки включает, -браки выключает.</i>
""")

TOP_TITLE = t("""
{heart} <b>Кто вместе дольше</b>
<i>Сверху те, кто поженился раньше.</i>
""")

LIST_TITLE = t("""
{heart} <b>Пары этой группы</b>
<i>Срок и тонус. Место кутами не покупается.</i>
""")

TOP_EMPTY = t("""
{heart} <b>В этой группе ещё нет браков.</b>
<i>Ответьте «брак» на сообщение человека.</i>
""")

TOP_ROW = t("""
<b>{n}. {a} и {b}</b>
<i>{span}</i>
""")

LIST_ROW = t("""
<b>{n}. {a} и {b}</b>
<i>{meta}</i>
""")

PROFILE_LINE = t("""
{ring} <b>В браке с {name} · {span}</b>
""")

PROFILE_EMPTY = t("""
{ring} <b>Брака нет · ответьте «брак» на сообщение</b>
""")
