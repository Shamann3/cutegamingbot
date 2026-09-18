# -*- coding: utf-8 -*-
"""Мост бота к учёту себестоимости предметов (server/item_lots.py).

Логика учёта одна на оба процесса — здесь только подключение к ней из
бота (server/ добавляется в sys.path так же, как в bot/funcs/tiktok_earn.py)
и удобные обёртки «взять соединение из пула и провести операцию».

Как и на сервере, ни одна функция отсюда не бросает наружу: учёт не имеет
права помешать игровой операции.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import item_lots  # noqa: E402

log = logging.getLogger("item_cost")

SOURCE_SHOP = item_lots.SOURCE_SHOP
SOURCE_GIFT = item_lots.SOURCE_GIFT
SOURCE_REWARD = item_lots.SOURCE_REWARD
SOURCE_ADMIN = item_lots.SOURCE_ADMIN
SOURCE_CRAFT = item_lots.SOURCE_CRAFT

REASON_CASE_OPEN = item_lots.REASON_CASE_OPEN
REASON_ITEM_USED = item_lots.REASON_ITEM_USED
REASON_ADMIN_TAKE = item_lots.REASON_ADMIN_TAKE
REASON_GIFT_SENT = item_lots.REASON_GIFT_SENT


async def ensure_schema(pool) -> bool:
    """Поднять схему учёта. Зовётся один раз при старте бота, не в хот-пате."""
    try:
        return await item_lots.ensure_item_cost_schema(pool)
    except Exception:
        log.exception("item cost schema init failed")
        return False


async def consume_cost_lots(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
) -> None:
    """Списать лоты на УЖЕ взятом соединении (обычно в той же транзакции,
    что и запись инвентаря). Наружу не бросает."""
    if conn is None or int(quantity or 0) <= 0:
        return
    await item_lots.record_consume(
        conn,
        user_id,
        item_ref,
        quantity,
        reason=reason,
        destroyed=destroyed,
        ref_kind=ref_kind,
        ref_id=ref_id,
    )


async def acquire_cost_lot(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    unit_cost: int | None,
    source: str,
    ref_kind: str = "",
    ref_id: str = "",
) -> None:
    """Завести лот на УЖЕ взятом соединении. Наружу не бросает."""
    if conn is None or int(quantity or 0) <= 0:
        return
    await item_lots.record_acquire(
        conn,
        user_id,
        item_ref,
        quantity,
        unit_cost=unit_cost,
        source=source,
        ref_kind=ref_kind,
        ref_id=ref_id,
    )


async def record_purchase(
    pool,
    user_id: int,
    item_ref: Any,
    quantity: int,
    total_paid: int,
    *,
    ref_kind: str = "shop",
    ref_id: str = "",
) -> None:
    """Себестоимость купленного = фактически уплаченная сумма."""
    if pool is None or int(quantity or 0) <= 0:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_acquire_parts(
                    conn,
                    user_id,
                    item_ref,
                    item_lots.split_cost(total_paid, quantity),
                    source=item_lots.SOURCE_SHOP,
                    ref_kind=ref_kind,
                    ref_id=ref_id,
                )
    except Exception:
        log.exception("record_purchase failed user=%s item=%s", user_id, item_ref)


async def record_grant(
    pool,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    source: str,
    unit_cost: int | None,
    ref_kind: str = "",
    ref_id: str = "",
) -> None:
    """Награда, админская выдача и прочий приход без сделки."""
    if pool is None or int(quantity or 0) <= 0:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_acquire(
                    conn,
                    user_id,
                    item_ref,
                    quantity,
                    unit_cost=unit_cost,
                    source=source,
                    ref_kind=ref_kind,
                    ref_id=ref_id,
                )
    except Exception:
        log.exception("record_grant failed user=%s item=%s", user_id, item_ref)


async def record_loss(
    pool,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
) -> None:
    """Расход предметов: списание по FIFO + запись в журнал выбытия."""
    if pool is None or int(quantity or 0) <= 0:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_consume(
                    conn,
                    user_id,
                    item_ref,
                    quantity,
                    reason=reason,
                    destroyed=destroyed,
                    ref_kind=ref_kind,
                    ref_id=ref_id,
                )
    except Exception:
        log.exception("record_loss failed user=%s item=%s", user_id, item_ref)


async def record_losses(
    pool,
    user_id: int,
    items: Mapping[Any, int],
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
) -> None:
    """Расход нескольких предметов одной операцией (кейс + ключ и т.п.)."""
    if pool is None or not items:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_consume_many(
                    conn,
                    user_id,
                    items,
                    reason=reason,
                    destroyed=destroyed,
                    ref_kind=ref_kind,
                    ref_id=ref_id,
                )
    except Exception:
        log.exception("record_losses failed user=%s reason=%s", user_id, reason)


async def record_gift(
    pool,
    from_user_id: int,
    to_user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    ref_kind: str = "gift",
    ref_id: str = "",
) -> None:
    """Передача предмета: себестоимость переезжает к получателю как есть."""
    if pool is None or int(quantity or 0) <= 0:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_gift(
                    conn,
                    from_user_id,
                    to_user_id,
                    item_ref,
                    quantity,
                    ref_kind=ref_kind,
                    ref_id=ref_id or str(to_user_id),
                )
    except Exception:
        log.exception("record_gift failed %s → %s item=%s", from_user_id, to_user_id, item_ref)


async def record_transfer(
    pool,
    from_user_id: int,
    to_user_id: int,
    items: Sequence[tuple[Any, int]],
    *,
    total_paid: int = 0,
    ref_kind: str = "p2p",
    ref_id: str = "",
) -> None:
    """Передача предметов между игроками одной операцией.

    Бесплатная передача — подарок: себестоимость КОПИРУЕТСЯ из списанных
    лотов дарителя, поэтому цепочка «купил → подарил → подарил дальше»
    разворачивается сама собой, без рекурсии и лишних запросов.

    Платная сделка — как на бирже: для покупателя себестоимость это цена
    сделки. Цена назначается за всю корзину сразу, поэтому распределяем её
    по единицам поровну; у продавца выбытие пишется с его реальной
    себестоимостью — по ней потом считается его прибыль.
    """
    rows = [(ref, int(qty or 0)) for ref, qty in (items or ()) if int(qty or 0) > 0]
    if pool is None or not rows:
        return
    total_units = sum(qty for _, qty in rows)
    total_paid = max(0, int(total_paid or 0))
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for item_ref, qty in rows:
                    if total_paid <= 0:
                        await item_lots.record_gift(
                            conn,
                            from_user_id,
                            to_user_id,
                            item_ref,
                            qty,
                            ref_kind=ref_kind,
                            ref_id=ref_id or str(to_user_id),
                        )
                        continue
                    await item_lots.record_consume(
                        conn,
                        from_user_id,
                        item_ref,
                        qty,
                        reason=item_lots.REASON_TRADE_SOLD,
                        destroyed=False,
                        ref_kind=ref_kind,
                        ref_id=ref_id or str(to_user_id),
                    )
                    paid_for_row = total_paid * qty // total_units
                    await item_lots.record_acquire_parts(
                        conn,
                        to_user_id,
                        item_ref,
                        item_lots.split_cost(paid_for_row, qty),
                        source=item_lots.SOURCE_TRADE,
                        ref_kind=ref_kind,
                        ref_id=ref_id or str(from_user_id),
                    )
    except Exception:
        log.exception("record_transfer failed %s → %s", from_user_id, to_user_id)


async def record_craft(
    pool,
    user_id: int,
    ingredients: Mapping[Any, int],
    *,
    success: bool,
    result_ref: Any = None,
    result_quantity: int = 1,
    ref_id: str = "",
) -> None:
    """Крафт в боте: ингредиенты списываются, при успехе их цена — в результат."""
    if pool is None or not ingredients:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await item_lots.record_craft(
                    conn,
                    user_id,
                    ingredients,
                    success=success,
                    result_ref=result_ref,
                    result_quantity=result_quantity,
                    ref_id=ref_id,
                )
    except Exception:
        log.exception("record_craft failed user=%s", user_id)
