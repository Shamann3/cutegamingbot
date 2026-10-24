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
    skip = "команды и игры"
    if block_dup:
        skip = "команды, игры и одно и то же сообщение, отправленное подряд"
    parts = [
        f"{emoji(EMOJI)} <b>Огонёк сообщений</b>",
        "Это серия дней. Каждый закрытый день делает её длиннее на 1 день и открывает награды, которые назначены на этот срок.",
        "",
        f"{emoji('5438440765908874600', '🎁')} <b>Награды за дни</b>",
    ]
    if rewards:
        parts.append(
            "Награда приходит <b>один раз</b> и сразу <b>в личку</b>, "
            "в тот момент, когда жизнь огонька доходит до этого срока."
        )
        parts.extend(rewards)
    else:
        parts.append("<i>Награды за дни скоро появятся. Серию уже можно копить.</i>")
    parts += [
        "",
        f"{emoji('5321021153219732362', '⚡️')} <b>Как работает</b>",
        (
            "Для того чтобы начать получать награды, достигая определённых дней жизни огонька, "
            f"вам нужно написать <b>{int(base)}</b> сообщений в <b>официальных группах</b>. "
            f"В каждом сообщении — не меньше <b>{int(words)}</b> слов."
        ),
        (
            "Сутки считаются по Москве: с <b>00:00</b> до следующей <b>00:00</b>. "
            "Как только за эти сутки норма набрана, огонёк <b>сразу</b> продлевается на <b>1 день</b>. "
            "Ждать полуночи не нужно."
        ),
        (
            "Если до <b>00:00</b> по Москве сообщений не хватило, огонёк <b>гаснет</b>. "
            "Серия начинается заново, с нуля."
        ),
        f"В норму не идут {skip}.",
    ]
    if not enabled:
        parts += ["", "<i>Сейчас огонёк выключен. Сообщения серию не копят, пока его снова не включат.</i>"]
    if rises:
        parts += [
            "",
            "<i>Норма сообщений для продлевания огонька будет расти со временем</i>",
        ]
    if titles:
        parts += [
            "",
            f"{emoji('5233479338791281256', '⭐️')} <b>Статус в профиле</b>",
            "Это подпись рядом с именем, пока огонёк горит. На награды она не влияет. Берётся самая старшая из тех, до которых серия уже дошла.",
            *titles,
        ]
    if warm_on:
        parts += [
            "",
            f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>",
            (
                f"Это отдельная награда, не вместо дня серии. Она открывается, когда огонёк уже живёт "
                f"<b>{warm_from}</b>. В одни сутки по Москве выбирается один час. "
                f"Каждые <b>{warm_every}</b> ваших сообщений в этот час дают ещё одну награду. "
                f"За сутки таких наград не больше <b>{warm_cap}</b>."
            ),
        ]
        if warm_hour:
            parts.append(f"Сегодня этот час: <code>{warm_hour}</code> МСК.")
    if gift_on:
        try:
            from flame_bonus_plus_copy import help_block
            parts += ["", help_block(mult=int(gift_mult or 1), item_count=int(gift_item_count or 1))]
        except Exception:
            mult_bit = f" ×{gift_mult}." if int(gift_mult or 1) > 1 else ""
            parts += [
                "",
                f"{emoji('5438458242130806642', '🎁')} <b>Бонус +</b>",
                "Напишите «использовать 🎁», нажмите «Открыть Бонус +» и выберите одну клетку. "
                f"Что внутри — только после выбора.{mult_bit} В имени нужна приписка <code>Cute</code>.",
            ]
    if restore_line:
        parts += [
            "",
            f"{emoji(EMOJI)} <b>Вернуть огонёк</b>",
            restore_line,
        ]
    parts += [
        "",
        "<i>Держите серию каждый день до 00:00 по Москве — награды за дни ваши.</i>",
    ]
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
        f"Если огонёк погас, напишите «<b>вернуть огонёк</b>» в течение <b>{int(days)}</b> дн. "
        f"Серия поднимется на столько дней, сколько сгорело. Цена: {price}.\n"
        "Новая серия сжигает старую: начать заново — значит, прошлую уже не вернуть. "
        "После возврата сегодняшнюю норму всё равно нужно закрыть до 00:00 по Москве."
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
        "<blockquote>Норма сообщений за сегодня закрыта.\n"
        "Огонёк сразу продлён на <b>1 день</b>.\n"
        "Завтра до <b>00:00</b> по Москве снова напишите норму. "
        "Если не напишете — огонёк погаснет.</blockquote>"
        f"{extra}"
    )


def screen_warm(label: str) -> str:
    return (
        f"{emoji('5296561370303592127', '🌟')} <b>Тёплый час</b>\n"
        "<blockquote>Вы написали сообщение в удачный час суток.\n"
        "Это отдельная награда. День серии она не заменяет и не продлевает.</blockquote>\n"
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
            f"{emoji('5321021153219732362', '⚡️')} Норма за сегодня <b>закрыта</b>. "
            "Этот день уже засчитан: серия длиннее на 1 день. "
            "Завтра до 00:00 по Москве снова напишите норму, иначе огонёк погаснет."
        )
    else:
        state = (
            f"{emoji('5467519850576354798', '❕')} Норма за сегодня <b>ещё не закрыта</b>. "
            "Напишите нужное число сообщений в официальных группах до 00:00 по Москве. "
            "Если не успеете — огонёк погаснет."
        )
    return (
        f"{emoji(EMOJI)} <b>Ваш огонёк сегодня</b>\n{head}"
        f"<blockquote>Серия сейчас: <b>{streak}</b>.\n"
        f"В списке лучших огоньков вы на месте <b>#{rank}</b>.\n"
        f"{state}</blockquote>"
        f"{next_line}{loot_line}"
    )


def profit_next(day_label: str, left: int, day_word: str, gift: str) -> str:
    return (
        f"\n{emoji('5438440765908874600', '🎁')} "
        f"До награды за <b>{day_label}</b> осталось ещё <b>{left}</b> {day_word}. "
        f"В тот день вы получите: {gift}."
    )


def profit_next_done() -> str:
    return (
        "\n<i>Все награды за уже назначенные дни вы получили. "
        "Дальше каждый закрытый день просто делает огонёк длиннее.</i>"
    )


def profit_loot(labels: list[str]) -> str:
    if not labels:
        return ""
    body = " · ".join(f"<b>{label}</b>" for label in labels)
    return f"\nСегодня вы уже получили: {body}."


def screen_top_empty() -> str:
    return (
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>\n"
        "<blockquote>Здесь самые длинные живые серии.\n"
        "<i>Пока никого нет. Напишите норму сообщений за сегодня — и ваш огонёк появится в списке.</i></blockquote>"
    )


def screen_top(rows: list[str]) -> str:
    head = [
        f"{emoji('5354962501643578130')} <b>Лучшие огоньки</b>",
        "<i>Самые длинные серии, которые ещё горят. Погасшие сюда не попадают.</i>",
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
        f"<blockquote>Погасшая серия была <b>{label}</b>.\n"
        f"Вернуть её можно {window}, пока вы не начали новую.\n"
        "Новая серия сжигает старую: после этого вернуть прошлую уже нельзя.\n"
        "После возврата сегодня до 00:00 по Москве всё равно закройте норму сообщений. "
        "Иначе огонёк погаснет снова.</blockquote>\n"
        f"Цена: {ways}."
    )


def screen_restore_done(label: str) -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк снова горит</b>\n"
        f"<blockquote>Серия <b>{label}</b> снова на месте.\n"
        "Сегодня до <b>00:00</b> по Москве закройте норму сообщений. "
        "Если не закрыть — огонёк погаснет ещё раз.</blockquote>"
    )


def screen_restore_alive() -> str:
    return (
        f"{emoji(EMOJI)} <b>Огонёк уже горит</b>\n"
        "<blockquote>Возвращать нечего: серия жива.\n"
        "Закройте сегодняшнюю норму сообщений до 00:00 по Москве.</blockquote>"
    )


def screen_restore_none() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возвращать нечего</b>\n"
        "<blockquote>Погасшей серии нет.\n"
        "Когда огонёк погаснет, напишите «вернуть огонёк» — если возврат будет открыт.</blockquote>"
    )


def screen_restore_late() -> str:
    return (
        f"{emoji(EMOJI)} <b>Срок прошёл</b>\n"
        "<blockquote>Этот огонёк уже не поднять: времени на возврат не осталось.\n"
        "Новую серию можно начать сегодня. Для этого закройте норму сообщений до 00:00 по Москве.</blockquote>"
    )


def screen_restore_off() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат выключен</b>\n"
        "<blockquote>Сейчас погасший огонёк вернуть нельзя.\n"
        "Новую серию начинайте обычной нормой сообщений.</blockquote>"
    )


def screen_restore_poor(price: int) -> str:
    return (
        f"{emoji(EMOJI)} <b>Не хватает кут</b>\n"
        f"<blockquote>Чтобы вернуть огонёк, нужно <b>{int(price)}</b> кут с вашего баланса.\n"
        "Их не хватило. Ничего не списано, серия не поднялась.</blockquote>"
    )


def screen_restore_no_item(name: str, count: int) -> str:
    piece = name if int(count or 1) == 1 else f"{name} ×{int(count)}"
    return (
        f"{emoji(EMOJI)} <b>Нет предмета</b>\n"
        f"<blockquote>Чтобы вернуть огонёк, нужен <b>{piece}</b> из вашего инвентаря.\n"
        "Предмета не хватило. Ничего не списано, серия не поднялась.</blockquote>"
    )


def screen_restore_busy() -> str:
    return "Этот возврат уже сделан или срок прошёл. Куты и предметы не списаны."


def screen_restore_cancel() -> str:
    return (
        f"{emoji(EMOJI)} <b>Возврат отменён</b>\n"
        "<blockquote>Огонёк остался погасшим.\n"
        "Куты и предметы не списаны.</blockquote>"
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
