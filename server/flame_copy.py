# -*- coding: utf-8 -*-
"""Огонёк — все тексты, которые видит человек.

Как править
-----------
Этот файл — единственное место со словами. Бот и справка берут фразы отсюда.
Каждый экран — функция ниже. Слоты в фигурных скобках подставляются сами.
Эмодзи телеграма лежит в той же строке: не выносите его в другой файл.

Где остальное
- Вкладка «Огонёк»: включение, норма, награды, цены и срок возврата.
- server/flame_engine.py: серия, полночь и окно возврата (функция restore_view).

Цены, предметы и срок возврата задаются во вкладке, не здесь.
После правки этого файла перезапустите бота.
"""
from __future__ import annotations

EMOJI = "5355118129783553944"
STATUS_EMOJI = "5355118129783553944"


def emoji(eid: str, fallback: str = "⚫️") -> str:
    return f"<tg-emoji emoji-id='{eid}'>{fallback}</tg-emoji>"


def kind_words(kind: str, amount: int, item: str = "") -> str:
    """Короткая подпись награды. Её же бот пишет в историю полученных наград."""
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
    if title:
        mark = emoji(emoji_id or STATUS_EMOJI)
        return f"{mark} <b>{title}</b> · огонёк <b>{label}</b>"
    return f"{emoji(EMOJI)} <b>Огонёк уже {label}</b>"


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
) -> str:
    parts = [
        f"{emoji(EMOJI)} <b>Огонёк сообщений</b>",
        "",
        f"{emoji('5438440765908874600', '🎁')} <b>Награды за дни</b>",
    ]
    if rewards:
        parts.append("<i>Один раз · сразу в личку</i>")
        parts.extend(rewards)
    else:
        parts.append("<i>Награды скоро появятся</i>")
    parts += [
        "",
        "<blockquote>"
        f"В <b>официальных группах</b>: <b>{base}</b> сообщений от <b>{words}</b> слов за сутки (МСК).\n"
        "Не считаются команды, игры и один текст подряд."
        "</blockquote>",
        "",
        f"{emoji('5321021153219732362', '⚡️')} <b>Как работает</b>",
        "· норма закрыта → в 00:00 серия <b>+1</b>",
        "· день пропущен → огонёк <b>гаснет</b>",
    ]
    if not enabled:
        parts += ["", "<i>Сейчас огонёк выключен</i>"]
    if rises:
        parts += [
            "",
            f"{emoji('5438449312893792440', '🚀')} <b>Норма растёт</b>",
            " · ".join(rises),
        ]
    if titles:
        parts += [
            "",
            f"{emoji('5233479338791281256', '⭐️')} <b>Статус в профиле</b>",
            *titles,
        ]
    if warm_on:
        parts += [
            "",
            f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>",
            f"С <b>{warm_from}</b>: каждые <b>{warm_every}</b> сообщений в удачный час "
            f"— ещё награда (до <b>{warm_cap}</b>/день).",
        ]
        if warm_hour:
            parts.append(f"Сегодня: <code>{warm_hour}</code> МСК")
    if gift_on:
        try:
            from flame_bonus_plus_copy import help_block
            parts += ["", help_block(mult=int(gift_mult or 1), item_count=int(gift_item_count or 1))]
        except Exception:
            mult_bit = f" ×{gift_mult}." if int(gift_mult or 1) > 1 else ""
            parts += [
                "",
                f"{emoji('5438458242130806642', '🎁')} <b>Бонус +</b>",
                f"«использовать 🎁» — улучшенный бонус.{mult_bit}",
                "Нужна приписка <code>Cute</code>.",
            ]
    if restore_line:
        parts += [
            "",
            f"{emoji(EMOJI)} <b>Вернуть огонёк</b>",
            restore_line,
        ]
    parts += ["", "<i>Держите серию — награды ваши</i>"]
    return "\n".join(parts)


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
        f"«<b>вернуть огонёк</b>» — в течение <b>{int(days)}</b> дн. после того, как погас. "
        f"Цена: {price}.\n"
        "Новая серия сжигает старую — успейте раньше."
    )


def screen_streak(label: str, title: str, gifts: str) -> str:
    head = f"<b>{title}</b>\n" if title else ""
    extra = (
        f"\n\n{emoji('5438440765908874600', '🎁')} Вам: <b>{gifts}</b>"
        if gifts
        else ""
    )
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже {label}</b>\n"
        f"{head}"
        "<blockquote>День закрыт.\n"
        "Завтра снова наберите норму.</blockquote>"
        f"{extra}"
    )


def screen_warm(label: str) -> str:
    return (
        f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>\n"
        "<blockquote>Вы писали в удачный час.</blockquote>\n"
        f"{emoji('5438440765908874600', '🎁')} <b>{label}</b>"
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
    head = f"<b>{title}</b>\n" if title else ""
    state = (
        f"{emoji('5321021153219732362', '⚡️')} норма <b>закрыта</b>"
        if kept
        else f"{emoji('5467519850576354798', '❕')} норма <b>ещё открыта</b>"
    )
    return (
        f"{emoji(EMOJI)} <b>Ваш огонёк сегодня</b>\n{head}"
        f"<blockquote>Серия: <b>{streak}</b> · место: <b>#{rank}</b>\n"
        f"{state}</blockquote>"
        f"{next_line}{loot_line}"
    )


def profit_next(day_label: str, left: int, day_word: str, gift: str) -> str:
    return (
        f"\n{emoji('5438440765908874600', '🎁')} "
        f"До <b>{day_label}</b> — ещё <b>{left}</b> {day_word}: {gift}"
    )


def profit_next_done() -> str:
    return "\n<i>Все дневные награды собраны — держите серию</i>"


def profit_loot(labels: list[str]) -> str:
    if not labels:
        return ""
    body = " · ".join(f"<b>{label}</b>" for label in labels)
    return f"\nСегодня: {body}"


def screen_top_empty() -> str:
    return (
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>\n"
        "<blockquote>Самые длинные серии.\n"
        "<i>Пока пусто — закройте норму дня.</i></blockquote>"
    )


def screen_top(rows: list[str]) -> str:
    head = [
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>",
        "<i>Самые длинные живые серии</i>",
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
    window = "сегодня" if int(days_left) <= 1 else f"ещё {int(days_left)} дн."
    return (
        f"{emoji(EMOJI)} <b>Вернуть огонёк</b>\n"
        f"<blockquote>Погасшая серия: <b>{label}</b>.\n"
        f"Можно {window}, пока не начнёте новую.</blockquote>\n"
        f"Цена: {ways}"
    )


def screen_restore_done(label: str) -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк снова горит</b>\n"
        f"<blockquote>Серия <b>{label}</b> на месте.\n"
        "Сегодня ещё закройте норму — иначе погаснет снова.</blockquote>"
    )


def screen_restore_alive() -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже горит</b>\n"
        "<blockquote>Возвращать нечего. Держите норму.</blockquote>"
    )


def screen_restore_none() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возвращать нечего</b>\n"
        "<blockquote>Погасшей серии нет.\n"
        "Когда огонёк погаснет — «вернуть огонёк».</blockquote>"
    )


def screen_restore_late() -> str:
    return (
        f"{emoji(EMOJI)} <b>Срок прошёл</b>\n"
        "<blockquote>Этот огонёк уже не поднять.\n"
        "Новую серию можно начать с сегодняшней нормы.</blockquote>"
    )


def screen_restore_off() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат выключен</b>\n"
        "<blockquote>Сейчас погасший огонёк нельзя вернуть.</blockquote>"
    )


def screen_restore_poor(price: int) -> str:
    return (
        f"{emoji(EMOJI)} <b>Не хватает кут</b>\n"
        f"<blockquote>Нужно <b>{int(price)}</b> кут. Списание не прошло.</blockquote>"
    )


def screen_restore_no_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return (
        f"{emoji(EMOJI)} <b>Нет предмета</b>\n"
        f"<blockquote>Нужен <b>{piece}</b>. Ничего не списано.</blockquote>"
    )


def screen_restore_busy() -> str:
    return "Уже вернули или срок прошёл. Списание отменено."


def screen_restore_cancel() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат отменён</b>\n"
        "<blockquote>Огонёк погас. Куты и предметы не списаны.</blockquote>"
    )


def button_kuty(price: int) -> str:
    return f"За {int(price)} кут"


def button_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"За {piece}"


def button_cancel() -> str:
    return "Отказаться"


def alert_stranger() -> str:
    return "Эта кнопка не ваша."


def alert_poor(price: int) -> str:
    return f"Нужно {int(price)} кут."


def alert_no_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"Нет предмета: {piece}."


RESTORE_COMMANDS = (
    "вернуть огонек",
    "восстановить огонек",
)


def is_restore_command(text: str) -> bool:
    folded = " ".join((text or "").lower().replace("ё", "е").replace("Ё", "е").split())
    return folded in RESTORE_COMMANDS


def button_help() -> str:
    return "Огонёк сообщений"


def button_top() -> str:
    return "Лучшие огоньки"


def alert_top_failed() -> str:
    return "Не удалось открыть огоньки."


HISTORY_GRANT = "огонёк"
HISTORY_RESTORE = "вернуть огонёк"
