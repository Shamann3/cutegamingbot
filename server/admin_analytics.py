"""Аналитические запросы для admin-панели.

Источники данных:
  - game_events   — ферма (plant/harvest/water/wither) и квесты (accept/complete)
  - audit_events  — крафт (craft_success/craft_fail), рынок (market_sell/market_buy)
  - market_listings — история сделок, цены
  - users         — регистрации, баланс, last_seen_at
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db import db


def _pool():
    return db.pool


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _rows(records) -> list[dict]:
    return [dict(r) for r in records]


# ---------------------------------------------------------------------------
# Квесты
# ---------------------------------------------------------------------------

async def get_quest_analytics(days: int = 30) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        # Взятия и выполнения по каждому квесту
        per_quest = await conn.fetch(
            """
            SELECT
                details->>'quest_id' AS quest_id,
                COUNT(*) FILTER (WHERE event_type = 'quest_accept')   AS accepted,
                COUNT(*) FILTER (WHERE event_type = 'quest_complete')  AS completed
            FROM game_events
            WHERE event_type IN ('quest_accept', 'quest_complete')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY details->>'quest_id'
            ORDER BY accepted DESC
            """,
            str(days),
        )

        # Среднее время выполнения по периоду (accept→ближайший complete)
        avg_by_period = await conn.fetch(
            """
            SELECT
                a.details->>'period' AS period,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (c.created_at - a.created_at))
                ))::int AS avg_seconds,
                COUNT(*) AS sample_count
            FROM game_events a
            JOIN LATERAL (
                SELECT created_at
                FROM game_events c
                WHERE c.user_id = a.user_id
                  AND c.event_type = 'quest_complete'
                  AND c.details->>'quest_id' = a.details->>'quest_id'
                  AND c.created_at > a.created_at
                  AND c.created_at < a.created_at + INTERVAL '8 days'
                ORDER BY c.created_at
                LIMIT 1
            ) c ON TRUE
            WHERE a.event_type = 'quest_accept'
              AND a.created_at > NOW() - ($1 || ' days')::interval
            GROUP BY a.details->>'period'
            """,
            str(days),
        )

        # График взятий/выполнений по дням
        by_day = await conn.fetch(
            """
            SELECT
                (created_at AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) FILTER (WHERE event_type = 'quest_accept')   AS accepted,
                COUNT(*) FILTER (WHERE event_type = 'quest_complete')  AS completed
            FROM game_events
            WHERE event_type IN ('quest_accept', 'quest_complete')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            str(days),
        )

    quest_rows = []
    for r in per_quest:
        acc = int(r["accepted"] or 0)
        comp = int(r["completed"] or 0)
        quest_rows.append({
            "questId": r["quest_id"],
            "accepted": acc,
            "completed": comp,
            "rate": round(comp / acc * 100, 1) if acc > 0 else 0,
        })

    return {
        "perQuest": quest_rows,
        "avgByPeriod": [
            {
                "period": r["period"],
                "avgSeconds": int(r["avg_seconds"] or 0),
                "sampleCount": int(r["sample_count"] or 0),
            }
            for r in avg_by_period
        ],
        "byDay": [
            {
                "day": str(r["day"]),
                "accepted": int(r["accepted"] or 0),
                "completed": int(r["completed"] or 0),
            }
            for r in by_day
        ],
    }


# ---------------------------------------------------------------------------
# Ферма
# ---------------------------------------------------------------------------

async def get_farm_analytics(days: int = 30) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        # Соотношение посажено/собрано/засохло
        ratios = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'farm_plant')    AS planted,
                COUNT(*) FILTER (WHERE event_type = 'farm_harvest')  AS harvested,
                COUNT(*) FILTER (WHERE event_type = 'farm_wither')   AS withered,
                COUNT(*) FILTER (WHERE event_type = 'farm_water')    AS watered
            FROM game_events
            WHERE event_type IN ('farm_plant', 'farm_harvest', 'farm_wither', 'farm_water')
              AND created_at > NOW() - ($1 || ' days')::interval
            """,
            str(days),
        )

        # Топ культур по посадкам
        top_crops = await conn.fetch(
            """
            SELECT
                details->>'crop_id' AS crop_id,
                COUNT(*) AS plants
            FROM game_events
            WHERE event_type = 'farm_plant'
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1
            ORDER BY plants DESC
            LIMIT 15
            """,
            str(days),
        )

        # Среднее количество грядок на игрока (текущее)
        avg_plots = await conn.fetchval(
            """
            SELECT ROUND(AVG(plot_count), 1)
            FROM (
                SELECT user_id, COUNT(*) AS plot_count
                FROM farm_plots
                GROUP BY user_id
            ) t
            """
        )

        # Тепловая карта: действия по дням недели и часам (UTC)
        heatmap = await conn.fetch(
            """
            SELECT
                EXTRACT(DOW  FROM created_at AT TIME ZONE 'UTC')::int AS dow,
                EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC')::int AS hour,
                COUNT(*) AS count
            FROM game_events
            WHERE event_type IN ('farm_plant', 'farm_harvest', 'farm_water')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            str(days),
        )

        # Активность по дням для графика
        by_day = await conn.fetch(
            """
            SELECT
                (created_at AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) FILTER (WHERE event_type = 'farm_plant')    AS planted,
                COUNT(*) FILTER (WHERE event_type = 'farm_harvest')  AS harvested,
                COUNT(*) FILTER (WHERE event_type = 'farm_water')    AS watered
            FROM game_events
            WHERE event_type IN ('farm_plant', 'farm_harvest', 'farm_water')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            str(days),
        )

    planted = int(ratios["planted"] or 0)
    harvested = int(ratios["harvested"] or 0)
    withered = int(ratios["withered"] or 0)

    return {
        "ratios": {
            "planted": planted,
            "harvested": harvested,
            "withered": withered,
            "watered": int(ratios["watered"] or 0),
            "lossRate": round((planted - harvested) / planted * 100, 1) if planted > 0 else 0,
        },
        "topCrops": [
            {"cropId": r["crop_id"], "plants": int(r["plants"])}
            for r in top_crops
        ],
        "avgPlotsPerPlayer": float(avg_plots or 0),
        "heatmap": [
            {"dow": r["dow"], "hour": r["hour"], "count": int(r["count"])}
            for r in heatmap
        ],
        "byDay": [
            {
                "day": str(r["day"]),
                "planted": int(r["planted"] or 0),
                "harvested": int(r["harvested"] or 0),
                "watered": int(r["watered"] or 0),
            }
            for r in by_day
        ],
    }


# ---------------------------------------------------------------------------
# Биржа
# ---------------------------------------------------------------------------

async def get_market_analytics(days: int = 30, item_id: str | None = None) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        # Топ предметов по объёму продаж
        top_items = await conn.fetch(
            """
            SELECT
                item_id,
                COUNT(*)               AS transactions,
                SUM(quantity)          AS total_qty,
                SUM(price * quantity)  AS total_kut
            FROM market_listings
            WHERE status = 'sold'
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY item_id
            ORDER BY total_kut DESC NULLS LAST
            LIMIT 15
            """,
            str(days),
        )

        # Топ продавцов
        top_sellers = await conn.fetch(
            """
            SELECT
                seller_id,
                COUNT(*)               AS transactions,
                SUM(price * quantity)  AS total_kut
            FROM market_listings
            WHERE status = 'sold'
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY seller_id
            ORDER BY total_kut DESC NULLS LAST
            LIMIT 10
            """,
            str(days),
        )

        # Общие цифры
        totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'sold')        AS sold_count,
                COUNT(*) FILTER (WHERE status = 'active')      AS active_count,
                COUNT(*) FILTER (WHERE status = 'cancelled')   AS cancelled_count,
                SUM(price * quantity) FILTER (WHERE status = 'sold') AS total_volume
            FROM market_listings
            WHERE created_at > NOW() - ($1 || ' days')::interval
            """,
            str(days),
        )

        # История сделок (последние 100)
        history = await conn.fetch(
            """
            SELECT id, seller_id, item_id, quantity, price,
                   (price * quantity) AS total,
                   created_at
            FROM market_listings
            WHERE status = 'sold'
              AND created_at > NOW() - ($1 || ' days')::interval
            ORDER BY created_at DESC
            LIMIT 100
            """,
            str(days),
        )

        # График цены предмета по дням
        price_chart: list = []
        if item_id:
            price_chart = await conn.fetch(
                """
                SELECT
                    (created_at AT TIME ZONE 'UTC')::date AS day,
                    ROUND(AVG(price))::int   AS avg_price,
                    MIN(price)               AS min_price,
                    MAX(price)               AS max_price,
                    COUNT(*)                 AS trades
                FROM market_listings
                WHERE status = 'sold'
                  AND item_id = $1
                  AND created_at > NOW() - ($2 || ' days')::interval
                GROUP BY 1
                ORDER BY 1
                """,
                item_id,
                str(days),
            )

        # График сделок по дням (для выбранного предмета или всех)
        volume_by_day = await conn.fetch(
            """
            SELECT
                (created_at AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) AS transactions,
                SUM(price * quantity) AS volume
            FROM market_listings
            WHERE status = 'sold'
              AND ($1::text IS NULL OR item_id = $1)
              AND created_at > NOW() - ($2 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            item_id,
            str(days),
        )

    return {
        "totals": {
            "soldCount": int(totals["sold_count"] or 0),
            "activeCount": int(totals["active_count"] or 0),
            "cancelledCount": int(totals["cancelled_count"] or 0),
            "totalVolume": int(totals["total_volume"] or 0),
        },
        "topItems": [
            {
                "itemId": r["item_id"],
                "transactions": int(r["transactions"]),
                "totalQty": int(r["total_qty"] or 0),
                "totalKut": int(r["total_kut"] or 0),
            }
            for r in top_items
        ],
        "topSellers": [
            {
                "sellerId": r["seller_id"],
                "transactions": int(r["transactions"]),
                "totalKut": int(r["total_kut"] or 0),
            }
            for r in top_sellers
        ],
        "history": [
            {
                "id": r["id"],
                "sellerId": r["seller_id"],
                "itemId": r["item_id"],
                "quantity": r["quantity"],
                "price": r["price"],
                "total": int(r["total"] or 0),
                "createdAt": _iso(r["created_at"]),
            }
            for r in history
        ],
        "priceChart": [
            {
                "day": str(r["day"]),
                "avgPrice": int(r["avg_price"] or 0),
                "minPrice": int(r["min_price"] or 0),
                "maxPrice": int(r["max_price"] or 0),
                "trades": int(r["trades"]),
            }
            for r in price_chart
        ],
        "volumeByDay": [
            {
                "day": str(r["day"]),
                "transactions": int(r["transactions"] or 0),
                "volume": int(r["volume"] or 0),
            }
            for r in volume_by_day
        ],
    }


# ---------------------------------------------------------------------------
# Крафт
# ---------------------------------------------------------------------------

async def get_craft_analytics(days: int = 30) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        # Топ рецептов + реальный процент успеха (из audit_events)
        per_recipe = await conn.fetch(
            """
            SELECT
                details->>'recipe_id'    AS recipe_id,
                details->>'recipe_key'   AS recipe_key,
                details->>'result_name'  AS result_name,
                details->>'result_emoji' AS result_emoji,
                COUNT(*) FILTER (WHERE event_type = 'craft_success') AS successes,
                COUNT(*) FILTER (WHERE event_type = 'craft_fail')    AS fails,
                COUNT(*)                                              AS total,
                ROUND(
                    COUNT(*) FILTER (WHERE event_type = 'craft_success')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1
                ) AS real_rate
            FROM audit_events
            WHERE event_type IN ('craft_success', 'craft_fail')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1, 2, 3, 4
            ORDER BY total DESC
            LIMIT 20
            """,
            str(days),
        )

        # Общие итоги
        totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'craft_success') AS successes,
                COUNT(*) FILTER (WHERE event_type = 'craft_fail')    AS fails,
                COUNT(*)                                              AS total
            FROM audit_events
            WHERE event_type IN ('craft_success', 'craft_fail')
              AND created_at > NOW() - ($1 || ' days')::interval
            """,
            str(days),
        )

        # График крафтов по дням
        by_day = await conn.fetch(
            """
            SELECT
                (created_at AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) FILTER (WHERE event_type = 'craft_success') AS successes,
                COUNT(*) FILTER (WHERE event_type = 'craft_fail')    AS fails
            FROM audit_events
            WHERE event_type IN ('craft_success', 'craft_fail')
              AND created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            str(days),
        )

    total = int(totals["total"] or 0)
    successes = int(totals["successes"] or 0)

    return {
        "totals": {
            "total": total,
            "successes": successes,
            "fails": int(totals["fails"] or 0),
            "overallRate": round(successes / total * 100, 1) if total > 0 else 0,
        },
        "perRecipe": [
            {
                "recipeId": r["recipe_id"],
                "recipeKey": r["recipe_key"],
                "resultName": r["result_name"],
                "resultEmoji": r["result_emoji"],
                "successes": int(r["successes"] or 0),
                "fails": int(r["fails"] or 0),
                "total": int(r["total"]),
                "realRate": float(r["real_rate"] or 0),
            }
            for r in per_recipe
        ],
        "byDay": [
            {
                "day": str(r["day"]),
                "successes": int(r["successes"] or 0),
                "fails": int(r["fails"] or 0),
            }
            for r in by_day
        ],
    }


# ---------------------------------------------------------------------------
# Удержание игроков
# ---------------------------------------------------------------------------

async def get_retention_analytics(days: int = 30) -> dict[str, Any]:
    pool = _pool()
    async with pool.acquire() as conn:
        # Новые регистрации по дням
        new_by_day = await conn.fetch(
            """
            SELECT
                (created_at AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) AS registrations
            FROM users
            WHERE created_at > NOW() - ($1 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            str(days),
        )

        # Day-1 / Day-7 / Day-30 retention
        cohort_total = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '35 days'"
        )
        cohort_total = int(cohort_total or 0)

        retention_raw = await conn.fetch(
            """
            WITH cohort AS (
                SELECT user_id, created_at
                FROM users
                WHERE created_at > NOW() - INTERVAL '35 days'
            )
            SELECT
                bucket.retention_day,
                COUNT(DISTINCT c.user_id) AS returned
            FROM cohort c
            CROSS JOIN (VALUES (1),(7),(30)) AS bucket(retention_day)
            WHERE EXISTS (
                SELECT 1 FROM game_events ge
                WHERE ge.user_id = c.user_id
                  AND ge.created_at >= c.created_at + ((bucket.retention_day - 1) || ' days')::interval
                  AND ge.created_at <  c.created_at + ((bucket.retention_day + 1) || ' days')::interval
            )
            GROUP BY bucket.retention_day
            ORDER BY bucket.retention_day
            """
        )
        retention = [(r["retention_day"], int(r["returned"]), cohort_total) for r in retention_raw]

        # Распределение по балансу (гистограмма)
        balance_dist = await conn.fetch(
            """
            SELECT
                CASE
                    WHEN balance < 100    THEN '0–100'
                    WHEN balance < 500    THEN '100–500'
                    WHEN balance < 1000   THEN '500–1k'
                    WHEN balance < 5000   THEN '1k–5k'
                    WHEN balance < 10000  THEN '5k–10k'
                    WHEN balance < 50000  THEN '10k–50k'
                    ELSE '50k+'
                END AS bucket,
                COUNT(*) AS player_count
            FROM users
            GROUP BY 1
            ORDER BY MIN(balance) NULLS LAST
            """
        )

        # Когортный анализ по неделям регистрации
        cohort_weekly = await conn.fetch(
            """
            SELECT
                DATE_TRUNC('week', created_at AT TIME ZONE 'UTC') AS cohort_week,
                COUNT(*) AS registered,
                COUNT(*) FILTER (
                    WHERE last_seen_at IS NOT NULL
                      AND last_seen_at > created_at + INTERVAL '1 day'
                ) AS retained_d1,
                COUNT(*) FILTER (
                    WHERE last_seen_at IS NOT NULL
                      AND last_seen_at > created_at + INTERVAL '7 days'
                ) AS retained_d7
            FROM users
            WHERE created_at > NOW() - INTERVAL '90 days'
            GROUP BY 1
            ORDER BY 1
            """,
        )

        # Общие числа
        totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                         AS total_players,
                COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '1 day') AS active_1d,
                COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '7 days') AS active_7d,
                COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '30 days') AS active_30d
            FROM users
            """
        )

    return {
        "totals": {
            "totalPlayers": int(totals["total_players"] or 0),
            "active1d": int(totals["active_1d"] or 0),
            "active7d": int(totals["active_7d"] or 0),
            "active30d": int(totals["active_30d"] or 0),
        },
        "newByDay": [
            {"day": str(r["day"]), "registrations": int(r["registrations"])}
            for r in new_by_day
        ],
        "retention": [
            {
                "day": day,
                "returned": returned,
                "total": total,
                "rate": round(returned / total * 100, 1) if total > 0 else 0,
            }
            for day, returned, total in retention
        ],
        "balanceDist": [
            {"bucket": r["bucket"], "count": int(r["player_count"])}
            for r in balance_dist
        ],
        "cohortWeekly": [
            {
                "week": _iso(r["cohort_week"]),
                "registered": int(r["registered"]),
                "retainedD1": int(r["retained_d1"] or 0),
                "retainedD7": int(r["retained_d7"] or 0),
            }
            for r in cohort_weekly
        ],
    }
