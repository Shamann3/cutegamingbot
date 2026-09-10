# -*- coding: utf-8 -*-
"""
Общий Фонд Роста - комиссия игры и её честное распределение.

Идея одной фразой: небольшой процент с ХОДА игры (не с баланса "просто так")
уходит на 3 адреса - обратно в баланс группы, в Фонд Роста (копится на будущие
дивиденды активным игрокам) и на развитие проекта. Всё открыто: игрок в любой
момент видит сумму, процент и куда именно она делась (кнопка "Комиссия игры").

Все проценты и переключатели - в bot/config/config.py (GROWTH_FUND_*).
Здесь - только расчёт и запись, без завязки на конкретную игру.

Как этим пользоваться из файла игры (пример):

    from bot.funcs.growth_fund import apply_commission

    result = await apply_commission(
        db, bot,
        chat_id=chat_id, user_id=winner_id, game="kosti",
        pot=total_pot, round_id=str(game_id),
    )
    payout = total_pot - (result["commission"] if result else 0)
    # ...обычная выплата payout победителю...
    # result сохрани в состояние игры, чтобы при показе результата добавить
    # кнопку "Комиссия игры: −{result['commission']} Kut" (см. build_commission_button).

apply_commission() ничего не платит игроку и не трогает bot-логику самой игры -
только считает комиссию, списывает её долю в баланс группы/фонд и пишет аудит.
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
) -> Optional[Dict[str, Any]]:
    """
    Считает и ПРИМЕНЯЕТ комиссию игры за один раунд:
      1) баланс группы (chat.chatbalance)   - через db.add_to_chatbalance (кэш/фастлейн не трогаем сами)
      2) Фонд Роста этой группы (growth_fund_pool) - копится на будущие дивиденды
      3) доля проекта - только фиксируется в журнале (growth_fund_ledger), отдельного кошелька нет
    плюс пишет:
      • growth_fund_ledger        - 1 строка на каждое событие (аудит)
      • growth_fund_user_stats    - обновляет лайфтайм-сумму игрока (для профиля/экрана статистики)

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

    # 1) Баланс группы - через существующую защищённую функцию (кэш/фастлейн внутри неё).
    if to_chat > 0:
        try:
            await db.add_to_chatbalance(bot, chat_id, to_chat)
        except Exception as e:
            _vdbg(f"[ФОНД РОСТА] add_to_chatbalance fail chat={chat_id} amount={to_chat}: {e!r}")

    # 2) Пул Фонда Роста этой группы + 3) журнал + 4) лайфтайм-статистика игрока.
    # Всё в одной транзакции - это НАШИ собственные новые таблицы, тут атомарность
    # обязательна (деньги не должны "потеряться" при обрыве соединения).
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
                    chat_id, to_fund,
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
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА] запись ledger/pool/stats fail chat={chat_id} user={user_id}: {e!r}")
        # Баланс группы уже пополнен (шаг 1) - это единственная часть, которая
        # может "не совпасть" при сбое именно здесь. Осознанный компромисс:
        # лучше группа получит чуть больше, чем застрять с недоплаченной игрой.

    return result


async def use_ticket(db, user_id: int, *, amount: Optional[int] = None) -> int:
    """
    «Купон Возможностей»: просто начисляет demo существующим, ничем не
    изменённым механизмом (db.add_demo_amount). Дальше решает штатная логика
    каждой игры - ровно так же, как для любого другого источника demo
    (подарок новичку, «дать» и т.д.). Мы намеренно не вводим отдельную
    вероятность и отдельное отслеживание купона - это цена того, что не
    трогаем и не усложняем то, что уже проверено и работает.

    Возвращает фактически начисленную сумму (для текста подтверждения).
    """
    import bot.config.config as cfg

    amount = int(amount if amount is not None else getattr(cfg, "GROWTH_FUND_TICKET_DEMO_AMOUNT", 10000))
    try:
        await db.add_demo_amount(user_id, amount)
    except Exception as e:
        _vdbg(f"[ФОНД РОСТА][КУПОН] add_demo_amount fail user={user_id}: {e!r}")
    return amount


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


def build_commission_button(result: Dict[str, Any], *, callback_data: str):
    """Готовая инлайн-кнопка «Комиссия игры: −N Kut» под результатом раунда."""
    from aiogram.types import InlineKeyboardButton

    amount = result["commission"]
    return InlineKeyboardButton(
        text=f"Комиссия игры: −{amount} Kut",
        callback_data=callback_data,
        style="primary",
        icon_custom_emoji_id=COMMISSION_BUTTON_ICON_ID,
    )
