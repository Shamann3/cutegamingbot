# -*- coding: utf-8 -*-
"""
Общий Фонд Роста - комиссия игры и её честное распределение.

Идея одной фразой: небольшой процент с ХОДА игры (не с баланса "просто так")
целиком зачисляется на баланс единой группы-резерва GROWTH_FUND_HOUSE_CHAT_ID
(-1003855337972), одинаково для PvE и PvP. Всё открыто: игрок видит сумму
и процент (кнопка "Комиссия игры"), владелец получает личное уведомление
о КАЖДОМ событии + статистику по периодам (команда "статистика комиссий").

Все проценты и переключатели - в bot/config/config.py (GROWTH_FUND_*).
Здесь - только расчёт и запись, без завязки на конкретную игру.

Как этим пользоваться из файла игры (пример, PvE - против баланса группы):

    from bot.funcs.growth_fund import apply_commission

    result = await apply_commission(
        db, bot,
        chat_id=chat_id, user_id=winner_id, game="kosti",
        pot=total_pot, round_id=str(game_id),
    )
    payout = total_pot - (result["commission"] if result else 0)
    # ...обычная выплата payout победителю...
    # result сохрани в состояние игры, чтобы при показе результата добавить
    # кнопку "Комиссия игры: −{result['commission']} кут" (см. build_commission_button).

Для PvP (банк формируют сами игроки, есть проигравшие) - используй
apply_commission_pvp() вместо apply_commission() (см. её докстринг ниже).

apply_commission() ничего не платит игроку и не трогает bot-логику самой игры -
только считает комиссию, зачисляет её целиком в единый резерв и пишет аудит
(плюс шлёт владельцу личное уведомление - см. _notify_owner_commission).
Вычитание из пота/payout остаётся на стороне вызывающей игры (в каждой игре
свой порядок раздачи денег, лезть туда отсюда нельзя).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from bot.funcs.group_balance_level import get_chat_level_async

# Тексты и ID эмодзи для кнопки раскрытия комиссии - фиксированные (утверждены).
COMMISSION_BUTTON_ICON_ID = "5379965108296394740"


def _vdbg(msg: str) -> None:
    print(msg)


def _clamp_level(level: Any) -> int:
    try:
        lvl = int(level)
    except Exception:
        lvl = 0
    return max(0, min(5, lvl))


# ============================================================================
# ШКАЛА ФОНДА РОСТА (прогресс до "Купона Возможностей")
# ============================================================================

def get_milestone_target(tier: int) -> int:
    """
    Порог (в кут личного вклада), который нужно набрать на текущем "круге"
    шкалы, чтобы получить награду. tier - 0-based номер круга (0 = первый
    порог из GROWTH_FUND_MILESTONE_THRESHOLDS, и так далее по списку, а после
    списка - шаг GROWTH_FUND_MILESTONE_STEP_AFTER_CAP за каждый следующий круг).
    """
    import bot.config.config as cfg

    thresholds = getattr(cfg, "GROWTH_FUND_MILESTONE_THRESHOLDS", [100, 200, 350, 500, 750, 1000]) or [1000]
    step = int(getattr(cfg, "GROWTH_FUND_MILESTONE_STEP_AFTER_CAP", 250) or 250)

    tier = max(0, int(tier))
    if tier < len(thresholds):
        return int(thresholds[tier])
    extra_steps = tier - len(thresholds) + 1
    return int(thresholds[-1]) + step * extra_steps


def format_milestone_bar(progress: int, target: int, *, width: int = 10) -> str:
    """Текстовый прогресс-бар '███████░░░' для показа в профиле.

    Рендерится жирным (<b>...</b>), БЕЗ <code></code> - так символы блоков
    выглядят крупнее и аккуратнее, а не мелким моноширинным шрифтом.
    """
    progress = max(0, int(progress))
    target = max(1, int(target))
    ratio = min(1.0, progress / target)
    filled = int(round(ratio * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


async def _advance_milestone(db, bot, user_id: int, *, tier: int, progress: int, gained: int) -> Dict[str, Any]:
    """
    Добавляет gained (личный вклад за этот раунд) к прогрессу шкалы и
    пересекает столько порогов, сколько наберётся (обычно 0 или 1 за раз -
    комиссия одного раунда почти всегда меньше порога, но цикл защищает и
    от редкого случая огромной ставки за один раз).

    За КАЖДОЕ пересечение выдаёт 1 "Купон Возможностей" в инвентарь и
    отправляет игроку честное уведомление личным сообщением от бота.

    Возвращает новое состояние: {"tier", "progress", "crossed", "target"}.
    """
    import bot.config.config as cfg

    crossed = 0
    new_tier = int(tier)
    new_progress = int(progress) + int(gained)

    while new_progress >= get_milestone_target(new_tier):
        new_progress -= get_milestone_target(new_tier)
        new_tier += 1
        crossed += 1

    # ВАЖНО: прогресс сохраняем в БД ВСЕГДА, а не только когда порог
    # пересечён - раньше (баг) запись обновлялась только при crossed > 0,
    # из-за чего вся комиссия, которая НЕ дотягивала до пересечения порога
    # за один раз, просто пропадала - шкала в профиле навсегда оставалась
    # на 0, сколько бы игрок ни платил комиссии. UPSERT (а не UPDATE) - на
    # случай, если строки в growth_fund_user_stats ещё вообще не было.
    try:
        await db.pool.execute(
            """
            INSERT INTO growth_fund_user_stats
                (user_id, milestone_tier, milestone_progress, milestone_coupons_earned, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                milestone_tier = $2,
                milestone_progress = $3,
                milestone_coupons_earned = growth_fund_user_stats.milestone_coupons_earned + $4,
                updated_at = NOW()
            """,
            int(user_id), new_tier, new_progress, crossed,
        )
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][ШКАЛА] update fail user={user_id}: {e!r}")

    if crossed > 0:
        item_name = getattr(cfg, "GROWTH_FUND_MILESTONE_REWARD_ITEM", "Купон возможностей")
        qty_per_cross = int(getattr(cfg, "GROWTH_FUND_MILESTONE_REWARD_QTY", 1) or 1)
        try:
            await db.add_item_to_inventory(int(user_id), item_name, qty=qty_per_cross * crossed)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][ШКАЛА] add_item_to_inventory fail user={user_id}: {e!r}")

        if bot is not None:
            try:
                next_target = get_milestone_target(new_tier)
                times_word = "раз" if crossed == 1 else "раза"
                coupon_word = "купон" if qty_per_cross * crossed == 1 else "купона"
                bar = format_milestone_bar(new_progress, next_target)
                await bot.send_message(
                    int(user_id),
                    (
                        "<tg-emoji emoji-id='5438262026549876196'>🥳</tg-emoji> <b>Новая отметка на шкале Фонда Роста!</b>\n\n"
                        f"<b>Вы получили «👑 Купон Возможностей»</b>\n"
                        f"⤷ Он повышает шансы на победу в следующей игре!\n\n"
                        f"<tg-emoji emoji-id='5317000922096769303'>🎁</tg-emoji> <b>Шкала Фонда Роста : {_fmt(new_progress)}/{_fmt(next_target)} кут</b>\n"
                        f"<b>{bar} → 👑 Купон Возможностей</b>\n\n"
                        '<blockquote><b>Для использования купона, напишите "<code>Использовать 💸</code>"</b></blockquote>'
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                _vdbg(f"[ФОНД РОСТА][ШКАЛА] notify fail user={user_id}: {e!r}")

    return {
        "tier": new_tier,
        "progress": new_progress,
        "crossed": crossed,
        "target": get_milestone_target(new_tier),
    }


def _fmt(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


# Красивые человеческие названия игр для текстов (панель комиссии игроку,
# уведомления и статистика владельцу) - вместо сырых внутренних идентификаторов
# типа "tic_tac_toe" или "fortuna_lobby". Ключи - те же строки, что в
# GROWTH_FUND_GAME_MULTIPLIER (bot/config/config.py); если игру когда-то
# добавят без обновления этого словаря - _game_display() красиво откатится
# на исходное имя, ничего не сломается.
GAME_DISPLAY_NAMES: Dict[str, str] = {
    # --- PvP ---
    "kosti": "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> Кости",
    "orel": "<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> Орёл или решка",
    "knb": "<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Камень-ножницы-бумага",
    "duel": "<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> Дуэль",
    "scah": "<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> Шашки",
    "mines": "<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> Мины",
    "memory": "<tg-emoji emoji-id='5188239353045868629'>🪵</tg-emoji> Мемори",
    "tic_tac_toe": "<tg-emoji emoji-id='5226660202035554522'>☑️</tg-emoji> Крестики-нолики",
    # "words" (Слова) - НАМЕРЕННО без комиссии, игра осталась в исходном
    # состоянии без Фонда Роста (по прямой просьбе владельца проекта).
    "fortuna_lobby": "<tg-emoji emoji-id='5226711870492126219'>🎡</tg-emoji> Фортуна",
    "bingo": "<tg-emoji emoji-id='5370783443175086955'>🍪</tg-emoji> Бинго",
    # --- PvE ---
    "trade": "<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji> Трейд",
    "balls": "<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji> Шарик",
    "risk": "<tg-emoji emoji-id='5438449312893792440'>🌴</tg-emoji> Риск",
    "tank": "<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji> Башня",
    "plate": "<tg-emoji emoji-id='5246916607833304803'>💫</tg-emoji> Плиты",
    "bombs": "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji> Бомбы",
    "provoda": "<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji>    Провода",
    "fortuna_solo": "<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji> Рулетка",
    "slots": "<tg-emoji emoji-id='5891135206580031104'>🎰</tg-emoji> Слоты",
    "kube": "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> Куб",
    "darts": "<tg-emoji emoji-id='5890815115552362075'>🎯</tg-emoji> Дартс",
    "basket": "<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji> Баскетбол",
    "bowling": "<tg-emoji emoji-id='5891120371762990493'>🎳</tg-emoji> Боулинг",
    "soccer": "<tg-emoji emoji-id='5890787425898205095'>⚽️</tg-emoji> Футбол",
}


def _game_display(game: Optional[str]) -> str:
    """Красивое имя игры для текста; неизвестным именам - честный fallback."""
    if not game:
        return "🎮 Игра"
    return GAME_DISPLAY_NAMES.get(str(game), f"🎮 {str(game).capitalize()}")


async def get_user_milestone_state(db, user_id: int) -> Dict[str, Any]:
    """
    Для профиля: текущее состояние шкалы игрока -
    {"tier", "progress", "target", "bar"}. Если строки ещё нет (игрок ни
    разу не платил комиссию) - возвращает самый первый порог, progress=0.
    """
    tier, progress = 0, 0
    if getattr(db, "pool", None):
        try:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT milestone_tier, milestone_progress FROM growth_fund_user_stats WHERE user_id = $1",
                    int(user_id),
                )
            if row:
                tier = int(row["milestone_tier"] or 0)
                progress = int(row["milestone_progress"] or 0)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][ШКАЛА] get_user_milestone_state fail user={user_id}: {e!r}")

    target = get_milestone_target(tier)
    return {
        "tier": tier,
        "progress": progress,
        "target": target,
        "bar": format_milestone_bar(progress, target),
    }


def compute_commission(
    *,
    pot: int,
    level: int,
    game: str,
) -> Optional[Dict[str, Any]]:
    """
    Чистый расчёт без обращения к БД - удобно для тестов и предпросмотра
    ("сколько будет комиссия, если...") без похода в базу.

    Возвращает None, если комиссия в этом раунде не берётся (выключена,
    пот меньше минимума, ставка/множитель дают 0).
    Иначе - dict с полями:
      rate, level, commission, to_chat_balance, to_growth_fund, to_project, net_pot
    Сумма to_chat_balance + to_growth_fund + to_project ВСЕГДА равна commission
    (остаток от округления отдаём в project, чтобы куты не терялись и не
    появлялись из воздуха - это критично для денежной логики).
    """
    import bot.config.config as cfg

    if not getattr(cfg, "GROWTH_FUND_ENABLED", False):
        return None

    pot = int(pot or 0)
    min_pot = int(getattr(cfg, "GROWTH_FUND_MIN_POT_FOR_COMMISSION", 0) or 0)
    if pot < min_pot:
        return None

    lvl = _clamp_level(level)
    rate_by_level = getattr(cfg, "GROWTH_FUND_RATE_BY_LEVEL", {}) or {}
    base_rate = float(rate_by_level.get(lvl, rate_by_level.get(str(lvl), 0.0)) or 0.0)

    multipliers = getattr(cfg, "GROWTH_FUND_GAME_MULTIPLIER", {}) or {}
    multiplier = float(multipliers.get(game, 1.0))

    rate = max(0.0, min(1.0, base_rate * multiplier))  # защита от кривого конфига
    if rate <= 0:
        return None

    commission = math.floor(pot * rate)
    if commission <= 0:
        return None

    split = getattr(cfg, "GROWTH_FUND_SPLIT", {}) or {}
    to_chat = math.floor(commission * float(split.get("chat_balance", 0.0)))
    to_fund = math.floor(commission * float(split.get("growth_fund", 0.0)))
    to_project = commission - to_chat - to_fund  # остаток округления - сюда

    return {
        "rate": rate,
        "level": lvl,
        "pot": pot,
        "commission": commission,
        "to_chat_balance": to_chat,
        "to_growth_fund": to_fund,
        "to_project": to_project,
        "net_pot": pot - commission,
    }


def _get_house_chat_id() -> int:
    """Единый технический резерв (см. GROWTH_FUND_HOUSE_CHAT_ID в config.py) -
    сюда уходит ВСЯ комиссия каждой игры, PvE и PvP одинаково."""
    import bot.config.config as cfg

    house = int(getattr(cfg, "GROWTH_FUND_HOUSE_CHAT_ID", 0) or 0)
    if house:
        return house
    return int(getattr(cfg, "GROWTH_FUND_PVP_HOUSE_CHAT_ID", 0) or 0)


async def _credit_house_kuts(db, bot, amount: int, *, dest_chat_id: Optional[int] = None) -> bool:
    """
    Зачисляет amount кут на баланс группы-резерва через add_to_chatbalance.
    Возвращает True только если баланс реально увеличен. При False комиссия
    уже могла быть вычтена из выплаты игроку — это пишется в лог громко.
    """
    house = int(dest_chat_id or _get_house_chat_id() or 0)
    try:
        amount = int(amount or 0)
    except Exception:
        amount = 0
    if not house or amount <= 0:
        _vdbg(f"[ФОНД РОСТА] house credit skip chat={house} amount={amount}")
        return False

    last_err = None
    for attempt in (1, 2):
        try:
            ok = await db.add_to_chatbalance(bot, house, amount)
            if ok:
                _vdbg(f"[ФОНД РОСТА] house credit ok chat={house} +{amount} attempt={attempt}")
                return True
            last_err = "add_to_chatbalance returned False"
        except Exception as e:
            last_err = e
        _vdbg(f"[ФОНД РОСТА] house credit fail chat={house} +{amount} attempt={attempt}: {last_err!r}")

    return False


async def apply_commission(
    db,
    bot,
    *,
    chat_id: int,
    user_id: int,
    game: str,
    pot: int,
    round_id: Optional[str] = None,
    level: Optional[int] = None,
    notify_owner: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Считает и ПРИМЕНЯЕТ комиссию игры за один раунд:
      1) ВСЯ сумма commission зачисляется на баланс GROWTH_FUND_HOUSE_CHAT_ID
         через db.add_to_chatbalance. Не доля, не сплит — вся удержанная сумма.
      2) Журнал (growth_fund_ledger / pool / stats) пишет разметку из
         GROWTH_FUND_SPLIT. При chat_balance=1.0 она совпадает с реальными кутами.
    плюс пишет:
      • growth_fund_ledger         - 1 строка на каждое событие (аудит; chat_id
                                      в строке - НАСТОЯЩАЯ группа, где сыграли,
                                      это отдельно от того, куда ушли деньги)
      • growth_fund_user_stats     - обновляет лайфтайм-сумму игрока (для профиля/экрана статистики)
      • growth_fund_global_totals  - лайфтайм-итог по ВСЕМ комиссиям сразу (для
                                      уведомления владельцу и экрана статистики)

    ★-уровень группы (chat_id), где реально сыграли раунд, всё так же
    определяет % комиссии (GROWTH_FUND_RATE_BY_LEVEL) - меняется только адрес,
    куда физически уходят куты, а не сама ставка комиссии.

    notify_owner=True (по умолчанию) - шлёт владельцу проекта личное
    уведомление об этом событии (см. _notify_owner_commission). PvP-обёртка
    apply_commission_pvp() сама делает более подробное PvP-уведомление и
    передаёт сюда notify_owner=False, чтобы не дублировать сообщение.

    Ничего не возвращает игроку деньгами - это делает вызывающая игра, используя
    result["net_pot"] / result["commission"] по своей обычной логике выплат.

    Возвращает None, если комиссия не применяется в этом раунде (тогда игра
    работает как раньше, кнопку "Комиссия игры" не показываем).
    """
    try:
        chat_id = int(chat_id)
        user_id = int(user_id)
        pot = int(pot or 0)
    except Exception:
        return None

    if level is None:
        try:
            level = await get_chat_level_async(chat_id, db=db)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА] не смог получить уровень группы chat={chat_id}: {e!r}")
            level = 0

    result = compute_commission(pot=pot, level=level, game=game)
    if result is None:
        return None

    if not getattr(db, "pool", None):
        _vdbg("[ФОНД РОСТА] db.pool отсутствует - комиссия НЕ применена (fail-safe: без изменений)")
        return None

    to_chat = result["to_chat_balance"]
    to_fund = result["to_growth_fund"]
    to_project = result["to_project"]

    # Единый резерв: вся комиссия, не доля split. Если конфиг вдруг не задан
    # (0/None) - fail-safe откат на настоящий chat_id, чтобы куты не терялись.
    money_chat_id = _get_house_chat_id() or chat_id
    credited = await _credit_house_kuts(
        db, bot, result["commission"], dest_chat_id=money_chat_id,
    )
    result["house_chat_id"] = money_chat_id
    result["house_credited"] = bool(credited)
    if not credited:
        _vdbg(
            f"[ФОНД РОСТА] ВНИМАНИЕ: комиссия {result['commission']} кут удержана, "
            f"но НЕ зачислена в группу {money_chat_id}"
        )

    # 2) Пул Фонда Роста (единый резерв) + 3) журнал (настоящий chat_id - аудит)
    # + 4) лайфтайм-статистика игрока + 5) лайфтайм-итог по ВСЕМ комиссиям.
    # Всё в одной транзакции - это НАШИ собственные новые таблицы, тут атомарность
    # обязательна (деньги не должны "потеряться" при обрыве соединения).
    lifetime_totals: Optional[Dict[str, int]] = None
    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO growth_fund_pool (chat_id, balance, total_ever_added, updated_at)
                    VALUES ($1, $2, $2, NOW())
                    ON CONFLICT (chat_id) DO UPDATE SET
                        balance = growth_fund_pool.balance + $2,
                        total_ever_added = growth_fund_pool.total_ever_added + $2,
                        updated_at = NOW()
                    """,
                    money_chat_id, to_fund,
                )

                await conn.execute(
                    """
                    INSERT INTO growth_fund_ledger
                        (chat_id, user_id, game, round_id, pot, level, rate,
                         commission, to_chat_balance, to_growth_fund, to_project)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    chat_id, user_id, str(game), str(round_id) if round_id is not None else None,
                    result["pot"], result["level"], result["rate"],
                    result["commission"], to_chat, to_fund, to_project,
                )

                await conn.execute(
                    """
                    INSERT INTO growth_fund_user_stats
                        (user_id, total_contributed, total_to_chat_balance, total_to_growth_fund, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        total_contributed = growth_fund_user_stats.total_contributed + $2,
                        total_to_chat_balance = growth_fund_user_stats.total_to_chat_balance + $3,
                        total_to_growth_fund = growth_fund_user_stats.total_to_growth_fund + $4,
                        updated_at = NOW()
                    """,
                    user_id, result["commission"], to_chat, to_fund,
                )

                totals_row = await conn.fetchrow(
                    """
                    INSERT INTO growth_fund_global_totals
                        (id, total_commission, total_to_chat_balance, total_to_growth_fund, total_to_project, total_events, updated_at)
                    VALUES (1, $1, $2, $3, $4, 1, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        total_commission = growth_fund_global_totals.total_commission + $1,
                        total_to_chat_balance = growth_fund_global_totals.total_to_chat_balance + $2,
                        total_to_growth_fund = growth_fund_global_totals.total_to_growth_fund + $3,
                        total_to_project = growth_fund_global_totals.total_to_project + $4,
                        total_events = growth_fund_global_totals.total_events + 1,
                        updated_at = NOW()
                    RETURNING total_commission, total_events
                    """,
                    result["commission"], to_chat, to_fund, to_project,
                )
                if totals_row:
                    lifetime_totals = {
                        "total_commission": int(totals_row["total_commission"]),
                        "total_events": int(totals_row["total_events"]),
                    }
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА] запись ledger/pool/stats fail chat={chat_id} user={user_id}: {e!r}")
        # Баланс резерва уже пополнен (шаг 1) - это единственная часть, которая
        # может "не совпасть" при сбое именно здесь. Осознанный компромисс:
        # лучше резерв получит чуть больше, чем застрять с недоплаченной игрой.

    if lifetime_totals:
        result["lifetime_total_commission"] = lifetime_totals["total_commission"]
        result["lifetime_total_events"] = lifetime_totals["total_events"]

    # 6) Шкала до "Купона Возможностей" - двигаем ПОСЛЕ основной транзакции
    # (независимый шаг: даже если тут что-то пойдёт не так, деньги уже
    # честно распределены выше - шкала это только "надстройка"-награда).
    try:
        milestone_before = await get_user_milestone_state(db, user_id)
        milestone = await _advance_milestone(
            db, bot, user_id,
            tier=milestone_before["tier"],
            progress=milestone_before["progress"],
            gained=result["commission"],
        )
        result["milestone"] = milestone
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][ШКАЛА] advance fail user={user_id}: {e!r}")

    # 7) Личное уведомление владельцу проекта - о КАЖДОЙ комиссии (PvE и PvP).
    if notify_owner:
        try:
            await _notify_owner_commission(db, bot, game=game, user_id=user_id, result=result, is_pvp=False)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][УВЕДОМЛЕНИЕ] notify fail user={user_id}: {e!r}")

    return result


async def get_global_totals(db) -> Dict[str, int]:
    """
    Лайфтайм-итоги по ВСЕМ комиссиям сразу (PvE + PvP), одной строкой из
    growth_fund_global_totals - для уведомления владельцу и экрана
    статистики "за всё время", без дорогого SUM() по growth_fund_ledger.
    """
    empty = {
        "total_commission": 0, "total_to_chat_balance": 0,
        "total_to_growth_fund": 0, "total_to_project": 0, "total_events": 0,
    }
    if not getattr(db, "pool", None):
        return empty
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT total_commission, total_to_chat_balance, total_to_growth_fund, "
                "total_to_project, total_events FROM growth_fund_global_totals WHERE id = 1"
            )
        if row:
            return {
                "total_commission": int(row["total_commission"] or 0),
                "total_to_chat_balance": int(row["total_to_chat_balance"] or 0),
                "total_to_growth_fund": int(row["total_to_growth_fund"] or 0),
                "total_to_project": int(row["total_to_project"] or 0),
                "total_events": int(row["total_events"] or 0),
            }
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][ИТОГИ] get_global_totals fail: {e!r}")
    return empty


async def _notify_owner_commission(
    db,
    bot,
    *,
    game: str,
    user_id: int,
    result: Dict[str, Any],
    is_pvp: bool = False,
    winner_id: Optional[int] = None,
    loser_ids: Any = None,
) -> None:
    """
    Личное уведомление владельцу проекта о КАЖДОЙ собранной комиссии - и PvE,
    и PvP, единым форматом (открытый аудит-лог). Показывает разбор ЭТОГО
    раунда + лайфтайм-итог "собрано всего с начала работы" - владельцу не
    обязательно открывать отдельный экран статистики, чтобы видеть рост.
    Чисто информационный хук - ошибки никогда не влияют на игру (вызывающие
    функции оборачивают вызов в try/except).
    """
    import bot.config.config as cfg

    owner_id = int(getattr(cfg, "GROWTH_FUND_OWNER_NOTIFY_USER_ID", 0) or 0)
    if not owner_id or bot is None:
        return

    pot = int(result.get("pot", 0))
    commission = int(result.get("commission", 0))
    pct = (commission / pot * 100.0) if pot > 0 else 0.0
    pct_str = f"{pct:.1f}".rstrip("0").rstrip(".") if pct else "0"

    lines = [f"<tg-emoji emoji-id='5388581564311417657'>💠</tg-emoji> <b>Комиссия собрана · {_game_display(game)}</b>"]

    if is_pvp:
        try:
            loser_list = [int(u) for u in (loser_ids or [])]
        except Exception:
            loser_list = []
        losers_str = ", ".join(f"<code>{u}</code>" for u in loser_list) if loser_list else "—"
        label = "Проигравший" if len(loser_list) == 1 else "Проигравшие"
        lines.append(
            f"<tg-emoji emoji-id='5408935401442267103'>⚔️</tg-emoji> <b>PvP · Победитель <code>{int(winner_id if winner_id is not None else user_id)}</code> </b>"
            f"<b>→ {label.lower()} {losers_str}</b>"
        )
    else:
        lines.append(f"<tg-emoji emoji-id='5386473766161238258'>🎮</tg-emoji> <b>PvE · Игрок <code>{int(user_id)}</code></b>")

    house_id = int(result.get("house_chat_id") or _get_house_chat_id() or 0)
    credited = result.get("house_credited")
    credit_note = "зачислено" if credited else "НЕ зачислено — проверь лог"

    lines.append("")
    lines.append(f"<b>Банк раунда : {_fmt(pot)} кут</b>")
    lines.append(f"<b>Комиссия : {_fmt(commission)} кут <i>({pct_str}%)</i></b>")
    lines.append("")
    lines.append(
        "<blockquote>"
        f"<tg-emoji emoji-id='5388581564311417657'>💠</tg-emoji> <b>В группу <code>{house_id}</code> : {_fmt(commission)} кут</b>\n"
        f"<i>{credit_note}</i>"
        "</blockquote>"
    )

    lifetime_total = result.get("lifetime_total_commission")
    lifetime_events = result.get("lifetime_total_events")
    if lifetime_total is None:
        totals = await get_global_totals(db)
        lifetime_total = totals["total_commission"]
        lifetime_events = totals["total_events"]

    lines.append("")
    lines.append(f"<tg-emoji emoji-id='5386726696785295704'>♾️</tg-emoji> <b>Всего с начала работы : {_fmt(lifetime_total)} кут <i>({_fmt(lifetime_events)} событий)</i></b>")

    kb = None
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть статистику", callback_data=f"{STATS_CALLBACK_PREFIX}|day", style="default" , icon_custom_emoji_id="5190806721286657692"),
        ]])
    except Exception:
        kb = None

    try:
        await bot.send_message(owner_id, "\n".join(lines), parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][УВЕДОМЛЕНИЕ] send_message owner fail: {e!r}")


async def apply_commission_pvp(
    db,
    bot,
    *,
    game: str,
    pot: int,
    winner_id: int,
    loser_ids: Optional[list] = None,
    round_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    PvP-версия apply_commission(). В PvP банк формируют САМИ игроки (не
    баланс группы), а часть PvP-игр работает в inline-режиме, где у бота
    физически нет chat_id переписки (Telegram inline API его не сообщает).

    Поэтому здесь: ВСЯ комиссия уходит в единый технический резерв
    GROWTH_FUND_HOUSE_CHAT_ID (см. config.py) вместо группы, где сыграли —
    одинаково для чат-версий и inline-версий игр. Уровень ★ для ставки
    комиссии тоже берётся у этого резерва (единый тариф для всех PvP).
    Туда же целиком уходят и все PvE-комиссии — см. apply_commission().

    Дополнительно шлёт владельцу проекта личное уведомление о раунде (со
    списком победителя/проигравших - см. _notify_owner_commission) - вместо
    generic-уведомления из apply_commission() (notify_owner=False ниже).

    Возвращает тот же формат, что apply_commission(), плюс result["is_pvp"]=True
    (используется build_commission_button/format_commission_explainer, чтобы
    честно показать игроку разбор комиссии).
    """
    house_chat_id = _get_house_chat_id()
    if not house_chat_id:
        return None

    result = await apply_commission(
        db, bot,
        chat_id=house_chat_id,
        user_id=int(winner_id),
        game=game,
        pot=pot,
        round_id=round_id,
        notify_owner=False,
    )
    if result:
        result["is_pvp"] = True
        try:
            await _notify_owner_commission(
                db, bot, game=game, user_id=int(winner_id), result=result,
                is_pvp=True, winner_id=winner_id, loser_ids=loser_ids,
            )
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][PVP] owner notify fail: {e!r}")
    return result


async def use_ticket(db, user_id: int, *, amount: Optional[int] = None) -> int:
    """
    «Купон Возможностей»: начисляет demo существующим, ничем не изменённым
    механизмом (db.add_demo_amount) - ПОЛЕ/исход раунда решает та же самая
    логика каждой игры, что и для любого другого источника demo.

    ДОПОЛНИТЕЛЬНО ставит в очередь гарантированный раунд
    (add_coupon_guarantee -> growth_fund_user_stats.coupon_guarantee_rounds).
    Это важно: обычный demo сам, вероятностно, решает force_win/force_loss
    (см. "РЕЖИМ DEMO" в jericho_check, main.py) и МОЖЕТ выдать force_loss
    несмотря на demo-баланс - без явной гарантии купон был бы неотличим от
    случайного подарка. Гарантия списывается детерминированно в
    consume_coupon_guarantee() - именно там, в самом начале jericho_check,
    ДО входа в любую вероятностную ветку ниже.

    Возвращает фактически начисленную сумму demo (для текста подтверждения).
    """
    import bot.config.config as cfg

    amount = int(amount if amount is not None else getattr(cfg, "GROWTH_FUND_TICKET_DEMO_AMOUNT", 10000))
    try:
        await db.add_demo_amount(user_id, amount)
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КУПОН] add_demo_amount fail user={user_id}: {e!r}")

    rounds = int(getattr(cfg, "GROWTH_FUND_TICKET_GUARANTEE_ROUNDS", 1) or 0)
    if rounds > 0:
        try:
            await add_coupon_guarantee(db, user_id, rounds=rounds)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][КУПОН] add_coupon_guarantee fail user={user_id}: {e!r}")

    return amount


async def add_coupon_guarantee(db, user_id: int, *, rounds: int = 1) -> int:
    """
    Ставит в очередь `rounds` гарантированных PvE-раундов для user_id
    (growth_fund_user_stats.coupon_guarantee_rounds += rounds). Вызывается
    ИЗ use_ticket() при использовании «Купона Возможностей» - отдельная
    прямая точка входа оставлена на случай, если в будущем гарантию нужно
    будет выдавать не только за купон (например, отдельным предметом или
    компенсацией поддержки).

    UPSERT (а не UPDATE) - на случай, если строки в growth_fund_user_stats
    для этого игрока ещё вообще не было (см. тот же паттерн в
    _advance_milestone выше).

    Возвращает итоговое количество гарантированных раундов в очереди после
    начисления (для логов/отладки); при ошибке БД - возвращает 0 и пишет в
    debug-лог, но НЕ бросает исключение дальше (начисление demo в
    use_ticket не должно откатываться из-за сбоя этого дополнительного
    счётчика).
    """
    rounds = int(rounds or 0)
    if rounds <= 0 or not getattr(db, "pool", None):
        return 0
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO growth_fund_user_stats (user_id, coupon_guarantee_rounds, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    coupon_guarantee_rounds = growth_fund_user_stats.coupon_guarantee_rounds + $2,
                    updated_at = NOW()
                RETURNING coupon_guarantee_rounds
                """,
                int(user_id), rounds,
            )
        return int(row["coupon_guarantee_rounds"]) if row else rounds
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КУПОН][ГАРАНТИЯ] add_coupon_guarantee fail user={user_id}: {e!r}")
        return 0


async def consume_coupon_guarantee(db, user_id: int) -> bool:
    """
    Проверяет и АТОМАРНО списывает один гарантированный раунд из очереди
    (growth_fund_user_stats.coupon_guarantee_rounds), если он там есть.

    Вызывается из jericho_check (main.py) В САМОМ НАЧАЛЕ, до любой
    вероятностной ветки - если возвращает True, раунд ОБЯЗАН завершиться
    force_win, независимо от того, что решила бы обычная demo/0demo логика.

    Списание одним UPDATE ... WHERE coupon_guarantee_rounds > 0 RETURNING -
    защищает от гонки двух параллельных раундов одного игрока (два разных
    чата/callback почти одновременно): если раунд уже кем-то списан, вторая
    попытка честно получит False, а не отрицательный счётчик.

    Возвращает True, если гарантированный раунд был найден и списан (значит
    ЭТОТ раунд обязан быть force_win); False, если очередь пуста (обычная
    вероятностная логика решает раунд как всегда), либо при ошибке БД
    (намеренно fail-safe - купон не должен ронять обработку раунда).
    """
    if not getattr(db, "pool", None):
        return False
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE growth_fund_user_stats
                SET coupon_guarantee_rounds = coupon_guarantee_rounds - 1,
                    updated_at = NOW()
                WHERE user_id = $1 AND coupon_guarantee_rounds > 0
                RETURNING coupon_guarantee_rounds
                """,
                int(user_id),
            )
        return row is not None
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КУПОН][ГАРАНТИЯ] consume_coupon_guarantee fail user={user_id}: {e!r}")
        return False


async def get_user_lifetime_contribution(db, user_id: int) -> int:
    """Для профиля: сколько кутов игрок внёс в комиссию игры за всё время."""
    if not getattr(db, "pool", None):
        return 0
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT total_contributed FROM growth_fund_user_stats WHERE user_id = $1",
                int(user_id),
            )
        return int(row["total_contributed"]) if row else 0
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА] get_user_lifetime_contribution fail user={user_id}: {e!r}")
        return 0


COMMISSION_CALLBACK_PREFIX = "gfund"


def build_commission_callback_data(result: Dict[str, Any]) -> str:
    """
    Кодирует разбивку комиссии этого конкретного раунда прямо в callback_data
    (без похода в БД при клике - раунд уже посчитан и применён, тут только
    показ). Формат: gfund|pot|commission|to_chat|to_fund|to_project|is_pvp
    Все значения - целые кут, укладываются далеко в лимит 64 байта Telegram.
    is_pvp (0/1) - PvP-раунды показывают другой честный текст про долю
    "группы" (см. format_commission_explainer), т.к. она уходит не в
    группу, где сыграли, а в общий технический резерв (apply_commission_pvp).
    """
    is_pvp = 1 if result.get("is_pvp") else 0
    return (
        f"{COMMISSION_CALLBACK_PREFIX}|{int(result['pot'])}|{int(result['commission'])}|"
        f"{int(result['to_chat_balance'])}|{int(result['to_growth_fund'])}|{int(result['to_project'])}|{is_pvp}"
    )


def build_commission_button(result: Dict[str, Any], *, callback_data: Optional[str] = None):
    """
    Готовая инлайн-кнопка «Комиссия игры: −N кут» под результатом раунда.
    callback_data можно не передавать - тогда соберётся автоматически через
    build_commission_callback_data (рекомендуемый способ, чтобы не собирать
    руками одну и ту же строку в каждом файле игры).
    """
    from aiogram.types import InlineKeyboardButton

    amount = result["commission"]
    return InlineKeyboardButton(
        text=f"Комиссия : −{amount} кут",
        callback_data=callback_data or build_commission_callback_data(result),
        style="primary",
        icon_custom_emoji_id=COMMISSION_BUTTON_ICON_ID,
    )


def format_commission_explainer(
    *,
    pot: int,
    commission: int,
    to_chat: int,
    to_fund: int,
    to_project: int,
    is_pvp: bool = False,
    game: Optional[str] = None,
    milestone: Optional[Dict[str, Any]] = None,
    lifetime_contrib: Optional[int] = None,
) -> str:
    """
    Короткий разбор комиссии ЭТОГО раунда для всплывающего окна Telegram
    (call.answer(text, show_alert=True)) по кнопке "Комиссия игры" - по
    решению владельца проекта клик НИКОГДА не создаёт и не редактирует
    отдельное сообщение в чате, только всплывающее окно.

    ВАЖНО (ограничения Telegram alert'ов, answerCallbackQuery.text):
      • НИКАКОГО HTML/Markdown - alert показывает чистый текст как есть,
        теги вроде <b> отрисуются буквально, поэтому здесь их нет вовсе;
      • жёсткий лимит 200 символов - текст ниже собран компактно и всё
        равно подрезается функцией-safety на случай очень больших чисел.

    Показывает игроку то, что касается лично его: сколько удержано и его
    личный прогресс к "Купону Возможностей". Внутреннюю разбивку (куда
    именно уходит комиссия внутри проекта) не показываем - игроку она не
    нужна, а для владельца та же информация есть в _notify_owner_commission
    и в экране статистики.

    to_chat / to_fund / to_project / is_pvp / game приняты для обратной
    совместимости вызова - в коротком тексте сейчас не используются.
    """
    pot = int(pot); commission = int(commission)
    pct = (commission / pot * 100.0) if pot > 0 else 0.0
    pct_str = f"{pct:.1f}".rstrip("0").rstrip(".") if pct else "0"

    lines = [f"🌱 Комиссия : −{_fmt(commission)} кут ({pct_str}% от {_fmt(pot)})"]

    if milestone:
        bar = milestone.get("bar") or format_milestone_bar(milestone.get("progress", 0), milestone.get("target", 1))
        progress = int(milestone.get("progress", 0))
        target = int(milestone.get("target", 1))
        lines.append("")
        lines.append(f"Шкала : {_fmt(progress)}/{_fmt(target)} кут")
        lines.append(f"{bar} → 👑 Купон")

    if lifetime_contrib is not None and int(lifetime_contrib) > 0:
        lines.append("")
        lines.append(f"Внесено всего : {_fmt(int(lifetime_contrib))} кут")

    text = "\n".join(lines)
    # Жёсткая защита от лимита Telegram (200 символов у answerCallbackQuery.text) -
    # на случай очень больших чисел с разделителями тысяч.
    if len(text) > 200:
        text = text[:197] + "..."
    return text


async def handle_commission_callback(call, db=None) -> None:
    """
    Обработчик клика по кнопке «Комиссия игры: −N кут» - показывает разбор
    ЭТОГО раунда ТОЛЬКО всплывающим окном Telegram (call.answer(text,
    show_alert=True)) - по явному решению владельца проекта клик НИКОГДА
    не отправляет и не редактирует отдельное сообщение в чате, при любом
    количестве повторных нажатий. Регистрируется в main.py (через обёртку,
    передающую db):

        dp.callback_query(F.data.startswith(COMMISSION_CALLBACK_PREFIX + "|"))(...)
    """
    try:
        parts = (call.data or "").split("|")
        # parts[0] == "gfund"
        pot, commission, to_chat, to_fund, to_project = (int(x) for x in parts[1:6])
        is_pvp = bool(int(parts[6])) if len(parts) > 6 else False
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КНОПКА] bad callback_data {call.data!r}: {e!r}")
        try:
            await call.answer("Не удалось показать разбор комиссии.", show_alert=True)
        except Exception:
            pass
        return

    from_user = getattr(call, "from_user", None)
    clicker_id = getattr(from_user, "id", None) if from_user else None

    milestone = None
    lifetime_contrib = None
    if db is not None and clicker_id:
        try:
            milestone = await get_user_milestone_state(db, clicker_id)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][КНОПКА] milestone fetch fail: {e!r}")
        try:
            lifetime_contrib = await get_user_lifetime_contribution(db, clicker_id)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА][КНОПКА] lifetime fetch fail: {e!r}")

    text = format_commission_explainer(
        pot=pot, commission=commission, to_chat=to_chat, to_fund=to_fund, to_project=to_project,
        is_pvp=is_pvp, milestone=milestone, lifetime_contrib=lifetime_contrib,
    )

    try:
        await call.answer(text, show_alert=True)
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КНОПКА] answer fail: {e!r}")


# ============================================================================
# СТАТИСТИКА КОМИССИИ ДЛЯ ВЛАДЕЛЬЦА ПРОЕКТА (день / неделя / месяц / год)
# ============================================================================
# Доступ только владельцу (GROWTH_FUND_OWNER_NOTIFY_USER_ID). Точка входа -
# текстовая команда (см. handle_commission_stats_command, регистрируется в
# main.py в общем текстовом роутере), дальше навигация - инлайн-кнопками
# периода (см. handle_commission_stats_callback, регистрируется в main.py
# рядом с обработчиком кнопки "Комиссия игры").

STATS_CALLBACK_PREFIX = "gfundstats"

STATS_TEXT_TRIGGERS = {
    "статистика комиссий",
    "статистика комиссии",
    "комиссии статистика",
    "статистика фонда роста",
    "gfund stats",
    "gfundstats",
    "/gfundstats",
}

_STATS_PERIOD_INTERVAL_SQL = {
    "day": "1 day",
    "week": "7 days",
    "month": "30 days",
    "year": "365 days",
    # "all" - без WHERE (весь growth_fund_ledger)
}

_STATS_PERIOD_LABELS = {
    "day": "📅 За день",
    "week": "🗓 За неделю",
    "month": "🗓 За месяц",
    "year": "🗓 За год",
    "all": "♾ За всё время",
}

_STATS_PERIOD_ORDER = ["day", "week", "month", "year", "all"]


def _is_commission_stats_owner(user_id: Any) -> bool:
    import bot.config.config as cfg

    owner_id = int(getattr(cfg, "GROWTH_FUND_OWNER_NOTIFY_USER_ID", 0) or 0)
    try:
        return bool(owner_id) and int(user_id) == owner_id
    except Exception:
        return False


async def get_commission_period_stats(db, *, period: str = "day") -> Dict[str, Any]:
    """
    Агрегаты по growth_fund_ledger за период (day/week/month/year/all) - для
    экрана статистики владельцу проекта.

    PvE и PvP различаем по chat_id самой записи в ledger: у PvP комиссия
    ВСЕГДА записывается с chat_id = единый резерв (см. apply_commission_pvp -
    туда передаётся house_chat_id как chat_id), а у PvE - с chat_id
    настоящей группы, где играли (см. apply_commission - ledger хранит
    настоящий chat_id, даже если деньги ушли в единый резерв). Поэтому
    "chat_id = резерв" однозначно значит PvP-раунд.
    """
    period = period if period in _STATS_PERIOD_LABELS else "day"
    house_chat_id = _get_house_chat_id()

    empty: Dict[str, Any] = {
        "period": period, "events": 0, "commission": 0, "to_chat": 0, "to_fund": 0, "to_project": 0,
        "pve_commission": 0, "pve_events": 0, "pvp_commission": 0, "pvp_events": 0,
        "prev_commission": None, "top_game": None, "top_game_commission": 0,
    }
    if not getattr(db, "pool", None):
        return empty

    where_sql = ""
    interval = _STATS_PERIOD_INTERVAL_SQL.get(period)
    if interval:
        where_sql = f"WHERE created_at >= NOW() - INTERVAL '{interval}'"

    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS events,
                    COALESCE(SUM(commission), 0) AS commission,
                    COALESCE(SUM(to_chat_balance), 0) AS to_chat,
                    COALESCE(SUM(to_growth_fund), 0) AS to_fund,
                    COALESCE(SUM(to_project), 0) AS to_project,
                    COALESCE(SUM(commission) FILTER (WHERE chat_id = $1), 0) AS pvp_commission,
                    COUNT(*) FILTER (WHERE chat_id = $1) AS pvp_events,
                    COALESCE(SUM(commission) FILTER (WHERE chat_id != $1), 0) AS pve_commission,
                    COUNT(*) FILTER (WHERE chat_id != $1) AS pve_events
                FROM growth_fund_ledger
                {where_sql}
                """,
                house_chat_id,
            )

            # "Топ игра" периода - какая игра принесла больше всего комиссии
            # (мелкий, но приятный аналитический штрих для владельца).
            top_row = await conn.fetchrow(
                f"""
                SELECT game, COALESCE(SUM(commission), 0) AS c
                FROM growth_fund_ledger
                {where_sql}
                GROUP BY game
                ORDER BY c DESC
                LIMIT 1
                """
            )

            # Сравнение с ПРЕДЫДУЩИМ равным по длине периодом (тренд ▲/▼) -
            # не считаем для "всё время", там сравнивать не с чем.
            prev_row = None
            if interval:
                prev_row = await conn.fetchrow(
                    f"""
                    SELECT COALESCE(SUM(commission), 0) AS commission
                    FROM growth_fund_ledger
                    WHERE created_at >= NOW() - INTERVAL '{interval}' - INTERVAL '{interval}'
                      AND created_at < NOW() - INTERVAL '{interval}'
                    """
                )
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][СТАТИСТИКА] query fail period={period}: {e!r}")
        return empty

    if not row:
        return empty

    return {
        "period": period,
        "events": int(row["events"] or 0),
        "commission": int(row["commission"] or 0),
        "to_chat": int(row["to_chat"] or 0),
        "to_fund": int(row["to_fund"] or 0),
        "to_project": int(row["to_project"] or 0),
        "pve_commission": int(row["pve_commission"] or 0),
        "pve_events": int(row["pve_events"] or 0),
        "pvp_commission": int(row["pvp_commission"] or 0),
        "pvp_events": int(row["pvp_events"] or 0),
        "top_game": str(top_row["game"]) if top_row and top_row["game"] else None,
        "top_game_commission": int(top_row["c"]) if top_row and top_row["c"] else 0,
        "prev_commission": int(prev_row["commission"]) if prev_row is not None else None,
    }


def build_commission_stats_keyboard(period: str):
    """Навигационные кнопки периода (День/Неделя/Месяц/Год/Всё время) -
    текущий период отмечен точками, клик переключает и обновляет тот же
    экран (см. handle_commission_stats_callback)."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    period = period if period in _STATS_PERIOD_LABELS else "day"
    buttons = []
    for p in _STATS_PERIOD_ORDER:
        label = _STATS_PERIOD_LABELS[p]
        text = f"• {label} •" if p == period else label
        buttons.append(InlineKeyboardButton(text=text, callback_data=f"{STATS_CALLBACK_PREFIX}|{p}"))

    return InlineKeyboardMarkup(inline_keyboard=[buttons[:3], buttons[3:]])


def format_commission_stats_text(stats: Dict[str, Any]) -> str:
    """
    Текст экрана статистики комиссии за выбранный период - полноценная
    аналитическая панель для владельца: итоги, разбивка по адресам и типу
    игр, топ-игра периода и тренд к предыдущему равному периоду (▲/▼).

    В конец добавлена метка времени обновления - помимо чисто косметической
    пользы, это гарантирует, что текст меняется при каждом клике даже если
    цифры совпали с прошлым разом (иначе Telegram отвечает ошибкой "message
    is not modified" на повторное редактирование одинакового текста).
    """
    import datetime as _dt

    period = stats.get("period", "day")
    label = _STATS_PERIOD_LABELS.get(period, period)

    events = stats.get("events", 0)
    commission = stats.get("commission", 0)
    to_chat = stats.get("to_chat", 0)
    to_fund = stats.get("to_fund", 0)
    to_project = stats.get("to_project", 0)
    pve_c = stats.get("pve_commission", 0)
    pve_n = stats.get("pve_events", 0)
    pvp_c = stats.get("pvp_commission", 0)
    pvp_n = stats.get("pvp_events", 0)
    avg = (commission // events) if events > 0 else 0

    prev_commission = stats.get("prev_commission")
    trend_line = ""
    if prev_commission is not None:
        if prev_commission > 0:
            change_pct = (commission - prev_commission) / prev_commission * 100.0
            arrow = "▲" if change_pct >= 0 else "▼"
            trend_line = f" <i>({arrow} {abs(change_pct):.0f}% к прошлому такому же периоду)</i>"
        elif commission > 0:
            trend_line = " <i>(▲ прошлый такой же период был пустым)</i>"

    top_game = stats.get("top_game")
    top_game_line = ""
    if top_game:
        top_game_commission = stats.get("top_game_commission", 0)
        top_game_line = f"\n<tg-emoji emoji-id='5424746623462823358'>🏅</tg-emoji> <b>Лидер периода : {_game_display(top_game)} - {_fmt(top_game_commission)} кут</b>"

    now_str = _dt.datetime.now().strftime("%H:%M:%S")

    return (
        f"<tg-emoji emoji-id='5190806721286657692'>📊</tg-emoji> <b>Статистика комиссии - {label}</b>\n"
        f"<i>Обновлено {now_str}</i>\n\n"
        f"<b>Событий с комиссией : {_fmt(events)}</b>\n"
        f"<b>Собрано за период : {_fmt(commission)} кут {trend_line}</b>\n"
        f"<b>Среднее за событие : {_fmt(avg)} кут {top_game_line}</b>\n\n"
        "<blockquote>"
        f"<tg-emoji emoji-id='5388581564311417657'>💠</tg-emoji> <b>На баланс резерва : {_fmt(to_chat)} кут</b>\n"
        f"<i>группа <code>{_get_house_chat_id()}</code></i>\n"
        f"<tg-emoji emoji-id='5235566774501525440'>🌱</tg-emoji> <b>Фонд Роста (старые строки) : {_fmt(to_fund)} кут</b>\n"
        f"<tg-emoji emoji-id='5389057356493511934'>🚀</tg-emoji> <b>Развитие (старые строки) : {_fmt(to_project)} кут</b>"
        "</blockquote>\n\n"
        "Разбивка по типу игр :\n"
        f"<b><tg-emoji emoji-id='5408830063074365909'>🎮</tg-emoji> PvE : {_fmt(pve_c)} кут <i>({_fmt(pve_n)} раунд.)</i></b>\n"
        f"<tg-emoji emoji-id='5454014806950429357'>⚔️</tg-emoji> <b>PvP : {_fmt(pvp_c)} кут <i>({_fmt(pvp_n)} раунд.)</i></b>\n\n"
        "<b><i>Навигация по периодам - кнопками ниже.</i></b>"
    )


async def handle_commission_stats_command(message, db) -> bool:
    """
    Точка входа: владелец проекта пишет боту одну из фраз из
    STATS_TEXT_TRIGGERS ("статистика комиссий" и т.п.) - получает экран
    статистики (по умолчанию - за день) с навигацией по периодам.

    Регистрируется вызовом из общего текстового роутера в main.py, например:

        if await handle_commission_stats_command(message, db):
            return True

    Возвращает True, если сообщение обработано (не наше - False, чтобы
    роутер продолжил искать другие совпадения).
    """
    try:
        from_user = getattr(message, "from_user", None)
        if not from_user or not _is_commission_stats_owner(from_user.id):
            return False

        text_low = (message.text or "").strip().lower()
        if text_low not in STATS_TEXT_TRIGGERS:
            return False

        stats = await get_commission_period_stats(db, period="day")
        await message.answer(
            format_commission_stats_text(stats),
            parse_mode="HTML",
            reply_markup=build_commission_stats_keyboard("day"),
        )
        return True
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][СТАТИСТИКА] command fail: {e!r}")
        return False


async def handle_commission_stats_callback(call, db) -> None:
    """
    Обработчик клика по навигационным кнопкам экрана статистики комиссии
    (День/Неделя/Месяц/Год/Всё время) - пересчитывает и редактирует то же
    сообщение под выбранный период. Регистрируется в main.py:

        dp.callback_query(F.data.startswith(STATS_CALLBACK_PREFIX + "|"))(...)
    """
    from_user = getattr(call, "from_user", None)
    if not from_user or not _is_commission_stats_owner(from_user.id):
        try:
            await call.answer("Недоступно.", show_alert=True)
        except Exception:
            pass
        return

    try:
        period = (call.data or "").split("|", 1)[1]
    except Exception:
        period = "day"
    if period not in _STATS_PERIOD_LABELS:
        period = "day"

    try:
        await call.answer()
    except Exception:
        pass

    try:
        stats = await get_commission_period_stats(db, period=period)
        await call.message.edit_text(
            format_commission_stats_text(stats),
            parse_mode="HTML",
            reply_markup=build_commission_stats_keyboard(period),
        )
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][СТАТИСТИКА] callback fail: {e!r}")
