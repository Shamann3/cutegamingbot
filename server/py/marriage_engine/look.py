# -*- coding: utf-8 -*-
"""Весь текст брака. Кнопки, экраны и ответ на «использовать» правятся здесь.

Правила (цены, искра, эффекты) живут в других файлах. Этот файл их не считает.
"""
from marriage_engine.m_ids import HEART, SPARK

# --- кнопки карточки ---
BTN_NO, BTN_YES, BTN_STOP = "Отказать", "Согласиться", "Отменить заявку"
BTN_STAY, BTN_LEAVE, BTN_CARD_LEAVE = "Остаться", "Развестись", "Расторгнуть"
BTN_TONE, BTN_GEST, BTN_LEVEL = "Искра", "Поддержать", "Уровень"
BTN_WHAT, BTN_HOW, BTN_HOLD = "Что это", "Как", "Держать"
BTN_STAT, BTN_BACK, BTN_MINE = "Статистика", "К паре", "Мой брак"
BTN_TOP, BTN_LIST, BTN_SKIP, BTN_GIFT = "Топ", "Пары", "Не сейчас", "Предметы"
BTN_FEAST = "Праздник"
BTN_RIBBON, BTN_RIBBON_OFF, BTN_RIBBON_DO, BTN_RIBBON_KEEP = "Лента", "Снять ленту", "Снять", "Оставить"

_YN = "«" + BTN_YES + "» «" + BTN_NO + "» «" + BTN_STOP + "»"
_YES_NO = "«" + BTN_YES + "» «" + BTN_NO + "»"

# --- помощь ---
HELP_PAY = "Платит тот, кто написал «брак»."

# --- заявка и свадьба ---
PROPOSE_FREE = "{heart} <b>{a} зовёт {b}</b>\n<i>Бесплатно. {which} из {free}. " + _YN + " · {minutes} мин.</i>"
PROPOSE_PAID = "{heart} <b>{a} зовёт {b}</b>\n<i>{price} кут. Свадьба {which}. " + _YES_NO + " · {minutes} мин.</i>"
WED_OK_FREE = "{heart} <b>{a} и {b} вместе</b>\n{spark} <i>Бесплатно. Сегодня по {each}.</i>"
WED_OK_PAID = "{heart} <b>{a} и {b} вместе</b>\n{spark} <i>{price} кут. Сегодня по {each}.</i>"
LEAVE_ASK = "{heart} <b>Расторгнуть брак с {b}?</b>\n<i>Куты не вернутся.</i>"

PRIVATE = HEART + " <b>Отношения живут в группе.</b>"
PROJECT_OFF = HEART + " <b>Отношения в проекте выключены.</b>"
OFF = HEART + " <b>В этой группе отношения выключены.</b>"
ON_OK = HEART + " <b>Отношения в группе включены.</b>"
OFF_OK = HEART + " <b>Отношения в группе выключены.</b>"
ON_ALREADY = HEART + " <i>Отношения здесь уже включены.</i>"
OFF_ALREADY = HEART + " <i>Отношения здесь уже выключены.</i>"
CREATOR_ONLY = HEART + " <b>+браки и -браки пишет создатель группы.</b>"
NEED_REPLY = HEART + " <b>Ответьте «брак» на сообщение.</b> <i>{minutes} мин.</i>"
NOT_FOUND = HEART + " <b>Не вижу, кого звать.</b>"
BOT = HEART + " <b>Бота в брак не зовут.</b>"
SELF = HEART + " <b>Себя позвать нельзя.</b>"

ALREADY_YOU = HEART + " <b>Вы уже в браке с {b}.</b>"
ALREADY_THEM = HEART + " <b>{b} уже в браке.</b>"
BUSY = HEART + " <b>Сейчас заявка уже есть.</b>"
POOR = HEART + " <b>Нужно {price} кут, у вас {have}.</b>"
POOR_LATE = HEART + " <b>К согласию не хватило {price} кут.</b>"
NOT_MARRIED = HEART + " <b>Брака нет.</b> <i>Ответьте «брак» на сообщение.</i>"
TONE_OLD = HEART + " <b>Этот брак из старой книги.</b>"

EXPIRED = HEART + " <b>{minutes} мин. Заявка закрыта.</b>"
STOPPED = HEART + " <b>Заявку отменили. Куты не списаны.</b>"
REFUSED = HEART + " <b>{b} отказал(а). Куты не списаны.</b>"
SKIP_OK = HEART + " <i>Жест не отправлен.</i>"
STAY_OK = HEART + " <b>Вы остались вместе.</b>"

TILL_CLOSED = HEART + " <b>Куты не приняты. Заявка закрыта.</b>"
LEAVE_OK = HEART + " <b>{a} и {b} больше не вместе.</b>"
LEAVE_THEM = HEART + " <b>{a} расторг(ла) брак.</b>"
RP_TOMORROW = HEART + " <b>{title} уже был сегодня.</b>"
RP_POOR = HEART + " <b>{title}: {price} кут, у вас {have}.</b>"
RP_PAY_ASK = HEART + " <b>{title} · {price} кут</b>"

TOP_EMPTY = HEART + " <b>В этой группе пока нет пар.</b>"
TOP_TITLE = HEART + " <b>Кто вместе дольше</b>"
LIST_TITLE = HEART + " <b>Пары этой группы</b>"
TOP_ROW = "{n}. {a} и {b} · {span}"
LIST_ROW = "{n}. {a} и {b} · {meta}"
RP_NEED_WED = HEART + " <b>Сначала брак.</b> <i>Ответьте «брак» на сообщение.</i>"
RP_ONLY_PAIR = HEART + " <b>Жест пишут своей паре.</b>"
RP_DONE = HEART + " <b>Жест уже был сегодня.</b>"
WHAT_TEXT = HEART + " <b>Один брак на весь Кут.</b>\n<i>Ответьте «брак» на сообщение человека.</i>"
HOW_TEXT = HEART + " <b>«Мой брак» — карточка.</b>\n<i>Жест пишут ответом партнёру.</i>"
HOLD_TEXT = HEART + " <b>Оба закрывают свою половину.</b>\n<i>И отвечают друг другу.</i>"

# --- короткие отказы кнопок ---
ALERT_RETRY = "Не прошло. Нажмите ещё раз."
ALERT_NOT_INVITED = "Отвечает только тот, кого позвали."
ALERT_NOT_PAYER = "Отменяет тот, кто написал «брак»."
ALERT_NOT_PAIR = "Это чужая пара."
ALERT_CLOSED = "Заявка уже закрыта."
ALERT_EXPIRED = "Время вышло. Куты не списаны."
ALERT_BUSY = "Кто-то из двоих уже занят заявкой."
ALERT_TILL = "Куты не списаны. Попробуйте позже."
ALERT_TILL_RP = "Куты не списаны. Нажмите ещё раз."
ALERT_NO_MARRIAGE = "Брака нет. Ответьте «брак» на сообщение."
ALERT_OFF = "Отношения выключены."
ALERT_RP_TODAY = "Этот жест сегодня уже был."

GIFT_ALERT = {
    "old": "Предметы откроются в новом браке.",
    "bad": "Такого предмета нет.",
    "none": "Этого нет в рюкзаке.",
    "calm": "Спичка нужна, когда искра гаснет.",
    "full": "Вчерашняя половина уже закрыта.",
    "worn": "Лента уже на вас.",
    "fade": "Сейчас это не поможет.",
    "ahead": "Эта ступень уже открыта.",
    "week": "Тихий день уже был на неделе.",
    "late": "Это только пока искра гаснет.",
    "day": "Сегодня это уже было.",
    "silent": "Сначала ответьте партнёру.",
    "done": "Ваша половина уже закрыта.",
    "night": "Луна с 21:00 до 6:00.",
    "sun": "Рассвет с 6:00 до 10:00.",
    "sworn": "Клятва уже прочитана.",
    "behind": "Партнёр не отстаёт.",
    "empty": "Своей заботы ещё нет.",
    "spare": "Лишнего запаса нет.",
    "held": "Это уже действует.",
    "alive": "Серия ещё жива.",
    "gone": "Возвращать нечего.",
    "early": "Печать ждёт, когда оба закроют день.",
    "heard": "Ответ уже есть.",
    "cold": "Серия уже погасла.",
    "said": "Предложение уже сказано.",
    "wait": "Сначала нужно предложение.",
    "giver": "Кольцо дарит тот, кто предложил.",
    "kept": "Кольцо уже у вас.",
    "home": "Семейная жизнь уже началась.",
    "away": "Партнёра нет в игре.",
    "field": "Этот саженец сажают на ферме.",
    "cook": "Сначала соберите блюдо в крафте.",
}

# Куда вести саженец и овощ. {name} подставляется.
SEED_LINE = "Сажают на ферме. 30 минут, 3 полива."
PANTRY_LINE = "Для крафта. Сам искру не даёт."
DISH_NEED = "Это едят вместе."
DISH_NEED_SUB = "Нужен живой брак."
DISH_OK = "Тепло взяли оба."


def _plain(text):
    return " ".join(str(text or "").replace("<", " ").replace(">", " ").split())


def use_card(emoji, title, line):
    """Ответ на использование: как у остальных предметов Кута. Знак, имя, короткая цитата."""
    mark = str(emoji or "").strip()
    head = ((mark + " ") if mark else "") + "<b>" + _plain(title or "Предмет") + "</b>"
    quote = _plain(line)
    if not quote:
        return head
    return head + "\n<blockquote><b>" + quote + "</b></blockquote>"
