"""Admin: карточка пользователя — устройство, IP, регистрация."""

from __future__ import annotations

import json

from config import ONLINE_WINDOW_SECONDS
from db import db
from geo_ip import lookup_ip_geo


def _parse_json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


async def search_accounts(query: str, *, limit: int = 20) -> list[dict]:
    raw = (query or "").strip()
    if not raw:
        return []

    limit = max(1, min(limit, 50))
    q = raw.lstrip("@")

    if q.isdigit():
        user_id = int(q)
        if user_id <= 0:
            return []
        row = await db.pool.fetchrow(
            """
            SELECT user_id, username, display_name, first_name, last_seen_at,
                   last_client_ip, last_platform, created_at, banned
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        return [_account_search_row(row)] if row else []

    if len(q) < 2:
        return []

    pattern = f"%{q}%"
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, display_name, first_name, last_seen_at,
               last_client_ip, last_platform, created_at, banned
        FROM users
        WHERE username ILIKE $1
           OR display_name ILIKE $1
           OR first_name ILIKE $1
        ORDER BY last_seen_at DESC NULLS LAST, user_id
        LIMIT $2
        """,
        pattern,
        limit,
    )
    return [_account_search_row(r) for r in rows]


async def list_recent_accounts(*, limit: int = 30) -> list[dict]:
    limit = max(1, min(limit, 50))
    window_sec = max(15, ONLINE_WINDOW_SECONDS)
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, display_name, first_name, last_seen_at,
               last_client_ip, last_platform, created_at, banned
        FROM users
        WHERE last_seen_at IS NOT NULL
          AND last_seen_at >= NOW() - ($1 * INTERVAL '1 second')
        ORDER BY last_seen_at DESC
        LIMIT $2
        """,
        window_sec,
        limit,
    )
    return [_account_search_row(r) | {"onlineNow": True} for r in rows]


def _account_search_row(row) -> dict:
    name = row["display_name"] or row["first_name"] or str(row["user_id"])
    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "displayName": name,
        "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
        "lastClientIp": row["last_client_ip"],
        "lastPlatform": row["last_platform"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "banned": bool(row["banned"]),
    }


async def get_account_profile(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name, last_name, display_name, photo_url,
               balance, banned, banned_at, banned_reason,
               created_at, last_seen_at, profile_updated_at,
               last_client_ip, last_user_agent, last_platform, last_app_version,
               last_language_code, is_premium, client_info, client_info_updated_at,
               market_sales_count, market_items_sold,
               onboarding_done
        FROM users WHERE user_id = $1
        """,
        user_id,
    )
    if not row:
        return None

    client_info = _parse_json(row["client_info"])
    window_sec = max(15, ONLINE_WINDOW_SECONDS)
    online_now = bool(
        row["last_seen_at"]
        and await db.pool.fetchval(
            """
            SELECT last_seen_at >= NOW() - ($1 * INTERVAL '1 second')
            FROM users WHERE user_id = $2
            """,
            window_sec,
            user_id,
        )
    )

    sessions = await db.pool.fetch(
        """
        SELECT id, created_at, client_ip, user_agent, platform, device_model,
               app_version, language_code, is_premium, screen_width, screen_height, timezone
        FROM user_login_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 25
        """,
        user_id,
    )

    geo = await lookup_ip_geo(row["last_client_ip"])

    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "displayName": row["display_name"] or row["first_name"] or str(row["user_id"]),
        "photoUrl": row["photo_url"],
        "balance": int(row["balance"] or 0),
        "banned": bool(row["banned"]),
        "bannedAt": row["banned_at"].isoformat() if row["banned_at"] else None,
        "bannedReason": row["banned_reason"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
        "profileUpdatedAt": row["profile_updated_at"].isoformat() if row["profile_updated_at"] else None,
        "onlineNow": online_now,
        "onboardingDone": bool(row["onboarding_done"]),
        "marketSalesCount": int(row["market_sales_count"] or 0),
        "marketItemsSold": int(row["market_items_sold"] or 0),
        "telegram": {
            "languageCode": row["last_language_code"],
            "isPremium": bool(row["is_premium"]) if row["is_premium"] is not None else None,
            "phoneAvailable": True,
            "phoneNote": "Telegram не передаёт номер телефона в Mini App — только через бота при отправке контакта.",
        },
        "device": {
            "platform": row["last_platform"],
            "appVersion": row["last_app_version"],
            "userAgent": row["last_user_agent"],
            "deviceModel": client_info.get("deviceModel"),
            "viewportWidth": client_info.get("viewportWidth"),
            "viewportHeight": client_info.get("viewportHeight"),
            "screenWidth": client_info.get("screenWidth"),
            "screenHeight": client_info.get("screenHeight"),
            "timezone": client_info.get("timezone"),
            "colorScheme": client_info.get("colorScheme"),
            "navigatorLanguage": client_info.get("navigatorLanguage"),
            "updatedAt": row["client_info_updated_at"].isoformat() if row["client_info_updated_at"] else None,
        },
        "network": {
            "lastIp": row["last_client_ip"],
            "geo": geo,
        },
        "loginHistory": [
            {
                "id": int(s["id"]),
                "createdAt": s["created_at"].isoformat(),
                "clientIp": s["client_ip"],
                "platform": s["platform"],
                "deviceModel": s["device_model"],
                "appVersion": s["app_version"],
                "languageCode": s["language_code"],
                "isPremium": s["is_premium"],
                "screenWidth": s["screen_width"],
                "screenHeight": s["screen_height"],
                "timezone": s["timezone"],
                "userAgent": s["user_agent"],
            }
            for s in sessions
        ],
    }
