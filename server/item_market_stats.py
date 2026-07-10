"""Статистика цен и наличия предметов: магазин, биржа, продажи."""

from __future__ import annotations

import statistics

import asyncpg

from market_rules import is_market_listable
from shop_catalog import effective_price, item_price_row


def _median(values: list[float]) -> float | None:
    cleaned = [float(v) for v in values if v is not None and float(v) > 0]
    if not cleaned:
        return None
    return float(statistics.median(cleaned))


def _int_price(value: float | int | None) -> int | None:
    if value is None:
        return None
    try:
        rounded = int(round(float(value)))
        return rounded if rounded > 0 else None
    except (TypeError, ValueError):
        return None


def _shop_payload(remains: int, price: int, discount: int) -> dict:
    remains = max(0, int(remains or 0))
    prices = item_price_row(int(price or 0), int(discount or 0))
    effective = effective_price(prices["price"], prices["salePrice"] or 0)
    return {
        "inShop": remains > 0,
        "remains": remains,
        "price": prices["price"],
        "salePrice": prices["salePrice"],
        "effectivePrice": effective,
    }


async def reference_prices_by_item(
    pool: asyncpg.Pool,
    item_ids: frozenset[str] | None = None,
) -> dict[str, dict]:
    """Эталонная цена: медиана продаж за 7 д → медиана лотов → цена в магазине."""
    sale_rows = await pool.fetch(
        """
        SELECT
            details->>'item_id' AS item_id,
            (details->>'paid')::float / GREATEST((details->>'quantity')::int, 1) AS unit_price
        FROM audit_events
        WHERE event_type = 'market_buy'
          AND created_at >= NOW() - INTERVAL '7 days'
          AND details ? 'item_id'
          AND details ? 'paid'
          AND details ? 'quantity'
        """
    )
    sale_buckets: dict[str, list[float]] = {}
    for row in sale_rows:
        item_id = str(row["item_id"] or "").strip()
        if not item_id or (item_ids is not None and item_id not in item_ids):
            continue
        sale_buckets.setdefault(item_id, []).append(float(row["unit_price"] or 0))

    active_rows = await pool.fetch(
        """
        SELECT item_id, price
        FROM market_listings
        WHERE status = 'active' AND quantity > 0
        """
    )
    active_buckets: dict[str, list[float]] = {}
    for row in active_rows:
        item_id = str(row["item_id"])
        if item_ids is not None and item_id not in item_ids:
            continue
        active_buckets.setdefault(item_id, []).append(float(row["price"] or 0))

    if item_ids is not None:
        dex_rows = await pool.fetch(
            """
            SELECT id, price, dis
            FROM dex
            WHERE id::text = ANY($1::text[])
            """,
            list(item_ids),
        )
    else:
        dex_rows = await pool.fetch("SELECT id, price, dis FROM dex")

    dex_prices: dict[str, float] = {}
    for row in dex_rows:
        dex_prices[str(row["id"])] = float(
            effective_price(int(row["price"] or 0), int(row["dis"] or 0))
        )

    all_items = set(sale_buckets) | set(active_buckets) | set(dex_prices)
    if item_ids is not None:
        all_items |= set(item_ids)

    refs: dict[str, dict] = {}
    for item_id in all_items:
        recent_median = _median(sale_buckets.get(item_id, []))
        active_median = _median(active_buckets.get(item_id, []))
        dex_price = dex_prices.get(item_id)
        reference = recent_median or active_median or dex_price
        refs[item_id] = {
            "recentMedian": recent_median,
            "activeMedian": active_median,
            "dexPrice": dex_price,
            "reference": reference,
        }
    return refs


async def fetch_inventory_item_economy(
    pool: asyncpg.Pool,
    item_ids: list[str],
    user_id: int,
) -> dict[str, dict]:
    """Магазин, биржа и эталонные цены для предметов в рюкзаке."""
    if not item_ids:
        return {}

    ids = list(dict.fromkeys(str(item_id) for item_id in item_ids if item_id))
    id_set = frozenset(ids)

    dex_rows = await pool.fetch(
        """
        SELECT id::text AS item_id, remains, price, dis
        FROM dex
        WHERE id::text = ANY($1::text[])
        """,
        ids,
    )
    shop_by_id: dict[str, dict] = {}
    for row in dex_rows:
        shop_by_id[str(row["item_id"])] = _shop_payload(
            int(row["remains"] or 0),
            int(row["price"] or 0),
            int(row["dis"] or 0),
        )

    market_rows = await pool.fetch(
        """
        SELECT
            item_id,
            SUM(quantity)::int AS market_quantity,
            COUNT(*)::int AS listing_count,
            MIN(price)::int AS min_price,
            MAX(price)::int AS max_price,
            CASE
                WHEN SUM(quantity) > 0
                THEN (SUM(price * quantity)::float / SUM(quantity))::int
                ELSE NULL
            END AS avg_price
        FROM market_listings
        WHERE status = 'active'
          AND quantity > 0
          AND item_id = ANY($1::text[])
        GROUP BY item_id
        """,
        ids,
    )
    market_by_id: dict[str, dict] = {}
    listing_prices: dict[str, list[float]] = {}
    for row in market_rows:
        item_id = str(row["item_id"])
        market_by_id[item_id] = {
            "quantity": int(row["market_quantity"] or 0),
            "listingCount": int(row["listing_count"] or 0),
            "minPrice": _int_price(row["min_price"]),
            "maxPrice": _int_price(row["max_price"]),
            "avgPrice": _int_price(row["avg_price"]),
        }

    price_rows = await pool.fetch(
        """
        SELECT item_id, price
        FROM market_listings
        WHERE status = 'active'
          AND quantity > 0
          AND item_id = ANY($1::text[])
        """,
        ids,
    )
    for row in price_rows:
        item_id = str(row["item_id"])
        listing_prices.setdefault(item_id, []).append(float(row["price"] or 0))

    own_rows = await pool.fetch(
        """
        SELECT item_id, SUM(quantity)::int AS listed_qty
        FROM market_listings
        WHERE status = 'active'
          AND quantity > 0
          AND seller_id = $1
          AND item_id = ANY($2::text[])
        GROUP BY item_id
        """,
        user_id,
        ids,
    )
    own_by_id = {str(row["item_id"]): int(row["listed_qty"] or 0) for row in own_rows}

    refs = await reference_prices_by_item(pool, id_set)

    economy: dict[str, dict] = {}
    for item_id in ids:
        listable = is_market_listable(item_id)
        shop = shop_by_id.get(item_id, _shop_payload(0, 0, 0))
        market_row = market_by_id.get(item_id, {})
        ref = refs.get(item_id, {})
        median_price = _int_price(_median(listing_prices.get(item_id, [])))
        reference_price = _int_price(ref.get("reference"))
        recent_median = _int_price(ref.get("recentMedian"))

        market = {
            "listable": listable,
            "quantity": int(market_row.get("quantity") or 0),
            "listingCount": int(market_row.get("listingCount") or 0),
            "minPrice": market_row.get("minPrice"),
            "maxPrice": market_row.get("maxPrice"),
            "avgPrice": market_row.get("avgPrice"),
            "medianPrice": median_price,
            "referencePrice": reference_price,
            "recentMedianPrice": recent_median,
        }

        economy[item_id] = {
            "shop": shop,
            "market": market,
            "listedByYou": int(own_by_id.get(item_id, 0)),
        }

    return economy
