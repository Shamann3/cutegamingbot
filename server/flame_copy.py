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
    block_dup: bool = True,
) -> str:
    _ = (gift_on, gift_mult, gift_item_count)
    skip = "Команды и игры не считаются."
    if block_dup:
        skip = "Команды, игры и одно и то же сообщение подряд не считаются."
    parts = [
        f"{emoji(EMOJI)} <b>Огонёк сообщений</b>",
        "Пишите, как обычно. Закрытый день сразу ваш — серия длиннее на 1 день.",
        "",
        f"{emoji('5438440765908874600', '🎁')} <b>Награды за дни</b>",
    ]
    if rewards:
        parts.append("Один раз, сразу в личку. Начните с ближайшего дня — остальное подождёт.")
        parts.extend(rewards)
    else:
        parts.append("<i>Награды за дни скоро появятся. Серию уже можно копить.</i>")
    parts += [
        "",
        f"{emoji('5321021153219732362', '⚡️')} <b>Как работает</b>",
        (
            f"<b>{int(base)}</b> сообщений в <b>официальных группах</b>, "
            f"в каждом от <b>{int(words)}</b> слов. Сутки — до <b>00:00</b> по Москве."
        ),
        "Норма набрана — день ваш сразу. Не набрана до 00:00 — огонёк гаснет, серия с нуля.",
        skip,
    ]
    if not enabled:
        parts += ["", "<i>Сейчас огонёк выключен. Когда включат — день снова можно закрыть.</i>"]
    if rises:
        parts += [
            "",
            "<i>Норма сообщений для продлевания огонька будет расти со временем</i>",
        ]
    if titles:
        parts += [
            "",
            f"{emoji('5233479338791281256', '⭐️')} <b>Статус в профиле</b>",
            "Короткая подпись у имени, пока огонёк горит. На подарки не влияет.",
            *titles,
        ]
    if warm_on:
        parts += [
            "",
            f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>",
            (
                f"С <b>{warm_from}</b> один час в сутках даёт ещё награду: "
                f"каждые <b>{warm_every}</b> сообщений, не больше <b>{warm_cap}</b> за день. "
                "День серии он не заменяет."
            ),
        ]
        if warm_hour:
            parts.append(f"Сегодня: <code>{warm_hour}</code> МСК.")
    if restore_line:
        parts += [
            "",
            f"{emoji(EMOJI)} <b>Вернуть огонёк</b>",
            restore_line,
        ]
    parts += ["", "<i>Один день ничего не стоит попробовать. Пропуск гасит серию.</i>"]
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
        f"Погас — «<b>вернуть огонёк</b>» в течение <b>{int(days)}</b> дн. Серия вернётся. Цена: {price}.\n"
        "Новая серия сжигает старую. После возврата закройте норму до 00:00 по Москве."
    )


def screen_streak(label: str, title: str, gifts: str) -> str:
    head = f"<b>{title}</b>\n" if title else ""
    extra = (
        f"\n\n{emoji('5438440765908874600', '🎁')} За этот день вам: <b>{gifts}</b>"
        if gifts
        else ""
    )
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже {label}</b>\n"
        f"{head}"
        "<blockquote>День ваш. Серия сразу длиннее на <b>1 день</b>.\n"
        "Завтра до <b>00:00</b> по Москве — ещё одна норма. Пропуск гасит огонёк.</blockquote>"
        f"{extra}"
    )


def screen_warm(label: str) -> str:
    return (
        f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>\n"
        "<blockquote>Вы попали в удачный час.\n"
        "Это отдельный подарок. День серии он не заменяет.</blockquote>\n"
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
    if kept:
        state = (
            f"{emoji('5321021153219732362', '⚡️')} День уже <b>ваш</b>. "
            "Завтра до 00:00 по Москве — новая норма, иначе огонёк погаснет."
        )
    else:
        state = (
            f"{emoji('5467519850576354798', '❕')} Норма ещё <b>открыта</b>. "
            "Успейте до 00:00 по Москве — день останется вашим."
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
        "\n<i>Назначенные награды уже у вас. Дальше каждый закрытый день просто растит серию.</i>"
    )


def profit_loot(labels: list[str]) -> str:
    if not labels:
        return ""
    body = " · ".join(f"<b>{label}</b>" for label in labels)
    return f"\nУже сегодня: {body}."


def screen_top_empty() -> str:
    return (
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>\n"
        "<blockquote>Самые длинные живые серии.\n"
        "<i>Пока пусто. Закройте норму сегодня — и вы в списке.</i></blockquote>"
    )


def screen_top(rows: list[str]) -> str:
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
    window = "сегодня" if int(days_left) <= 1 else f"ещё {int(days_left)} дн."
    return (
        f"{emoji(EMOJI)} <b>Вернуть огонёк</b>\n"
        f"<blockquote>Серия <b>{label}</b> ещё можно вернуть: {window}.\n"
        "Новая серия сжигает старую.\n"
        "Цена видна заранее. Отказ ничего не списывает.\n"
        "После возврата закройте норму до 00:00 по Москве.</blockquote>\n"
        f"Цена: {ways}."
    )


def screen_restore_done(label: str) -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк снова горит</b>\n"
        f"<blockquote>Серия <b>{label}</b> снова с вами.\n"
        "Сегодня до <b>00:00</b> по Москве закройте норму — иначе день снова потеряется.</blockquote>"
    )


def screen_restore_alive() -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже горит</b>\n"
        "<blockquote>Огонёк горит, возвращать нечего.\n"
        "Закройте норму до 00:00 по Москве.</blockquote>"
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
        "Новую серию можно начать сегодняшней нормой.</blockquote>"
    )


def screen_restore_off() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат выключен</b>\n"
        "<blockquote>Сейчас вернуть нельзя.\n"
        "Новую серию начинают обычной нормой.</blockquote>"
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
    return f"За {int(price)} кут"


def button_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"За {piece}"


def button_cancel() -> str:
    return "Отказаться"


def alert_stranger() -> str:
    return "Эта кнопка не ваша."


def alert_poor(price: int) -> str:
    return f"Чтобы вернуть огонёк, нужно {int(price)} кут."


def alert_no_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return f"Чтобы вернуть огонёк, нужен предмет: {piece}."


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
    return "Огонёк сообщений"


def button_top() -> str:
    return "Лучшие огоньки"


def alert_top_failed() -> str:
    return "Не удалось открыть список огоньков. Напишите ещё раз чуть позже."


HISTORY_GRANT = "огонёк"
HISTORY_RESTORE = "вернуть огонёк"
