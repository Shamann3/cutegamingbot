"""Правила «Купона на скидку»: сколько скидывает и что можно вернуть продажей.

Модуль намеренно не знает про базу: здесь только арифметика, которую обязаны
считать одинаково WebApp и текстовый бот. Хранение брони и себестоимости живёт
в server/db.py и bot/db_create/db.py, инварианты продублированы в schema.sql.
"""

from __future__ import annotations

import random

from config import (
    COUPON_DISCOUNT_MAX_PERCENT,
    COUPON_DISCOUNT_MIN_PERCENT,
    COUPON_RESERVATION_TTL_SECONDS,
)

# Купон действует на одну единицу предмета. Раньше он скидывал всю корзину, то
# есть до 99 штук за один купон в WebApp и до 1000 в текстовом боте.
COUPON_DISCOUNTED_UNITS = 1


def discount_bounds() -> tuple[int, int]:
    """Диапазон скидки, приведённый к разумным границам."""
    low = max(1, min(99, int(COUPON_DISCOUNT_MIN_PERCENT)))
    high = max(1, min(99, int(COUPON_DISCOUNT_MAX_PERCENT)))
    if low > high:
        low, high = high, low
    return low, high


def roll_discount_percent() -> int:
    low, high = discount_bounds()
    return random.randint(low, high)


def clamp_discount_percent(percent) -> int:
    """Процент из БД тоже проверяем: запись могла остаться от старого диапазона."""
    low, high = discount_bounds()
    try:
        value = int(percent)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def reservation_ttl_seconds() -> int:
    return max(60, int(COUPON_RESERVATION_TTL_SECONDS))


def discounted_units(quantity) -> int:
    """Сколько единиц из покупки попадает под скидку."""
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return 0
    return max(0, min(qty, COUPON_DISCOUNTED_UNITS))


def apply_coupon_to_cost(unit_cost, quantity, percent) -> tuple[int, int]:
    """Стоимость покупки со скидкой на COUPON_DISCOUNTED_UNITS единиц.

    Возвращает (итого к оплате, сколько сэкономлено). Скидка считается от одной
    единицы, остальные штуки идут по полной цене.
    """
    unit_cost = max(0, int(unit_cost))
    quantity = max(0, int(quantity))
    full_cost = unit_cost * quantity

    units = discounted_units(quantity)
    if units <= 0:
        return full_cost, 0

    percent = clamp_discount_percent(percent)
    discounted_unit_cost = unit_cost - round(unit_cost * percent / 100)
    discounted_unit_cost = max(0, min(discounted_unit_cost, unit_cost))

    cost = discounted_unit_cost * units + unit_cost * (quantity - units)
    cost = max(0, min(cost, full_cost))
    return cost, full_cost - cost


def cap_sell_payout(payout, unit_paid) -> int:
    """Ограничить выплату за одну единицу тем, что за неё реально заплатили.

    Купон даёт купить за 25% цены, а продажа возвращает 25-45%, поэтому без
    ограничения цикл «купил по купону — продал» создавал куты из воздуха.
    """
    payout = max(0, int(payout))
    if unit_paid is None:
        return payout
    return min(payout, max(0, int(unit_paid)))
