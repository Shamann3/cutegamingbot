"""Admin: биржа — лоты, модерация, объём, подозрительные цены."""

from __future__ import annotations

import statistics
from datetime import datetime, time, timezone

from config import ANALYTICS_TZ
from market_rules import MARKET_MAX_PRICE, MARKET_MIN_PRICE
from db import db
from dex_catalog import dex_catalog
from admin_users import insert_admin_audit
from shop_catalog import effective_price
from user_items import add_shop_item_to_storage, items_to_db, parse_items

SUSPICIOUS_HIGH_RATIO = 3.0
SUSPICIOUS_LOW_RATIO = 3.0


def _analytics_tz():
    from zoneinfo import ZoneInfo

    return ZoneInfo(ANALYTICS_TZ)


def _day_start_utc() -> datetime:
    tz = _analytics_tz()
    local_today = datetime.now(tz).date()
    start_local = datetime.combine(local_today, time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc)


def _median(values: list[float]) -> float | None:
    cleaned = [float(v) for v in values if v is not None and float(v) > 0]
    if not cleaned:
        return None
    return float(statistics.median(cleaned))


async def get_market_overview() -> dict:
    day_start = _day_start_utc()
    tz = _analytics_tz()
    local_today = datetime.now(tz).date().isoformat()

    active_count = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM market_listings
            WHERE status = 'active' AND quantity > 0
            """
        )
        or 0
    )

    volume_row = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*)::int AS deals,
            COALESCE(SUM((details->>'paid')::bigint), 0)::bigint AS volume_kut,
            COALESCE(SUM((details->>'quantity')::int), 0)::int AS items_sold
        FROM audit_events
        WHERE event_type = 'market_buy'
          AND created_at >= $1
        """,
        day_start,
    )

    cancelled_today = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM audit_events
            WHERE event_type = 'admin_market_cancel'
              AND created_at >= $1
            """,
            day_start,
        )
        or 0
    )

    suspicious = await get_suspicious_listings(limit=25)
    item_filters = await get_market_item_filters()

    return {
        "date": local_today,
        "timezone": ANALYTICS_TZ,
        "activeListings": active_count,
        "today": {
            "deals": int(volume_row["deals"] or 0),
            "volumeKut": int(volume_row["volume_kut"] or 0),
            "itemsSold": int(volume_row["items_sold"] or 0),
            "adminCancelled": cancelled_today,
        },
        "suspicious": suspicious,
        "itemFilters": item_filters,
    }


async def get_market_item_filters() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT DISTINCT l.item_id, d.name, d.emoji,
               COUNT(*)::int AS listings
        FROM market_listings l
        LEFT JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
        WHERE l.status = 'active' AND l.quantity > 0
        GROUP BY l.item_id, d.name, d.emoji
        ORDER BY d.name NULLS LAST, l.item_id
        """
    )
    return [
        {
            "itemId": str(row["item_id"]),
            "name": (row["name"] or "").strip() or str(row["item_id"]),
            "emoji": (row["emoji"] or "").strip() or "📦",
            "listings": int(row["listings"] or 0),
        }
        for row in rows
    ]


async def _reference_prices_by_item() -> dict[str, dict]:
    from item_market_stats import reference_prices_by_item

    return await reference_prices_by_item(db.pool)


def _suspicious_reason(price: int, reference: float | None) -> str | None:
    price = int(price)
    if price < MARKET_MIN_PRICE or price > MARKET_MAX_PRICE:
        return "out_of_bounds"

    if reference is None or reference <= 0:
        if price >= 50_000:
            return "high_no_ref"
        return None

    ratio = price / reference
    if ratio >= SUSPICIOUS_HIGH_RATIO:
        return "high"
    if ratio <= 1 / SUSPICIOUS_LOW_RATIO:
        return "low"
    return None


def _listing_admin_row(row, refs: dict[str, dict]) -> dict:
    item_id = str(row["item_id"])
    price = int(row["price"] or 0)
    qty = int(row["quantity"] or 0)
    ref = refs.get(item_id, {})
    reference = ref.get("reference")
    reason = _suspicious_reason(price, reference)
    seller_name = row["seller_display_name"] or row["seller_first_name"] or str(row["seller_id"])

    return {
        "listingId": int(row["listing_id"]),
        "sellerId": int(row["seller_id"]),
        "sellerName": seller_name,
        "sellerUsername": row["seller_username"],
        "itemId": item_id,
        "itemName": (row["name"] or "").strip() or item_id,
        "emoji": (row["emoji"] or "").strip() or "📦",
        "quantity": qty,
        "price": price,
        "totalValue": price * qty,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "suspicious": reason is not None,
        "suspiciousReason": reason,
        "referencePrice": int(reference) if reference else None,
        "priceRatio": round(price / reference, 2) if reference and reference > 0 else None,
    }


async def list_active_listings(
    *,
    q: str = "",
    item_id: str = "",
    seller_id: int | None = None,
    suspicious_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    refs = await _reference_prices_by_item()

    params: list = []
    where = ["l.status = 'active'", "l.quantity > 0"]

    item_filter = (item_id or "").strip()
    if item_filter:
        params.append(item_filter)
        where.append(f"l.item_id = ${len(params)}")

    if seller_id is not None and seller_id > 0:
        params.append(int(seller_id))
        where.append(f"l.seller_id = ${len(params)}")

    search = (q or "").strip()
    if search:
        params.append(f"%{search}%")
        idx = len(params)
        where.append(
            f"(d.name ILIKE ${idx} OR d.name1 ILIKE ${idx} "
            f"OR CAST(d.id AS TEXT) ILIKE ${idx} OR l.item_id ILIKE ${idx} "
            f"OR u.display_name ILIKE ${idx} OR u.username ILIKE ${idx} "
            f"OR CAST(l.seller_id AS TEXT) ILIKE ${idx})"
        )

    where_sql = " AND ".join(where)
    rows = await db.pool.fetch(
        f"""
        SELECT
            l.id AS listing_id,
            l.seller_id,
            l.item_id,
            l.quantity,
            l.price,
            l.created_at,
            d.name,
            d.emoji,
            u.username AS seller_username,
            u.display_name AS seller_display_name,
            u.first_name AS seller_first_name
        FROM market_listings l
        LEFT JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
        LEFT JOIN users u ON u.user_id = l.seller_id
        WHERE {where_sql}
        ORDER BY l.created_at DESC
        LIMIT 500
        """,
        *params,
    )

    listings = [_listing_admin_row(row, refs) for row in rows]
    if suspicious_only:
        listings = [row for row in listings if row["suspicious"]]

    total = len(listings)
    page = listings[offset : offset + limit]

    return {
        "listings": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_suspicious_listings(*, limit: int = 25) -> list[dict]:
    data = await list_active_listings(suspicious_only=True, limit=500, offset=0)
    suspicious = data["listings"]
    suspicious.sort(
        key=lambda row: abs((row.get("priceRatio") or 1) - 1),
        reverse=True,
    )
    return suspicious[: max(1, min(limit, 100))]


async def admin_cancel_listing(
    listing_id: int,
    *,
    admin_user_id: int,
    reason: str = "",
) -> dict:
    listing_id = int(listing_id)
    reason_clean = reason.strip()

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, seller_id, item_id, quantity, price, status
                FROM market_listings
                WHERE id = $1
                FOR UPDATE
                """,
                listing_id,
            )
            if not row or row["status"] != "active":
                raise ValueError("Активный лот не найден")

            seller_id = int(row["seller_id"])
            qty = int(row["quantity"] or 0)
            if qty < 1:
                raise ValueError("Лот уже пуст")

            items_raw = await conn.fetchval(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                seller_id,
            )
            if items_raw is None:
                raise ValueError("Продавец не найден")

            raw_items = parse_items(items_raw)
            stored = add_shop_item_to_storage(raw_items, str(row["item_id"]), qty)
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                seller_id,
                items_to_db(stored),
            )
            await conn.execute(
                """
                UPDATE market_listings
                SET quantity = 0, status = 'cancelled'
                WHERE id = $1
                """,
                listing_id,
            )

    entry = dex_catalog.get(str(row["item_id"]))
    item_name = entry.name if entry else str(row["item_id"])
    emoji = entry.emoji if entry else "📦"

    await insert_admin_audit(
        seller_id,
        "admin_market_cancel",
        admin_user_id=admin_user_id,
        details={
            "listing_id": listing_id,
            "item_id": str(row["item_id"]),
            "name": item_name,
            "emoji": emoji,
            "quantity": qty,
            "price": int(row["price"] or 0),
            "reason": reason_clean or None,
        },
    )

    from admin_player_notify import notify_market_listing_removed

    notify_market_listing_removed(
        seller_id,
        listing_id=listing_id,
        item_name=item_name,
        emoji=emoji,
        quantity=qty,
        reason=reason_clean,
    )

    return {
        "ok": True,
        "listingId": listing_id,
        "sellerId": seller_id,
        "returnedQuantity": qty,
    }
