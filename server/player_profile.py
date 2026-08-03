"""Публичные профили игроков (имя из Telegram)."""

from __future__ import annotations

from typing import Any


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if not row:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        value = row[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


def format_display_name(
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    display_name: str | None = None,
    user_id: int,
) -> str:
    cached = (display_name or "").strip()
    if cached:
        return cached

    parts: list[str] = []
    if first_name:
        parts.append(str(first_name).strip())
    if last_name:
        parts.append(str(last_name).strip())
    full = " ".join(parts).strip()
    if full:
        return full

    uname = (username or "").strip().lstrip("@")
    if uname:
        return f"@{uname}"

    tail = str(abs(int(user_id)))[-4:].rjust(4, "0")
    return f"Игрок #{tail}"


def seller_rank(sales_count: int) -> dict[str, Any]:
    sales = max(0, int(sales_count))
    if sales >= 50:
        return {
            "id": "tycoon",
            "label": "Магнат",
            "emoji": "👑",
            "nextAt": None,
            "progress": 1.0,
        }
    if sales >= 10:
        return {
            "id": "trader",
            "label": "Торговец",
            "emoji": "💼",
            "nextAt": 50,
            "progress": min(1.0, (sales - 10) / 40),
        }
    if sales >= 1:
        return {
            "id": "seller",
            "label": "Продавец",
            "emoji": "🤝",
            "nextAt": 10,
            "progress": min(1.0, sales / 10),
        }
    return {
        "id": "newcomer",
        "label": "Новичок",
        "emoji": "🌱",
        "nextAt": 1,
        "progress": 0.0,
    }


def profile_from_telegram_user(user: dict[str, Any]) -> dict[str, Any]:
    first_name = (user.get("first_name") or "").strip() or None
    last_name = (user.get("last_name") or "").strip() or None
    username = (user.get("username") or "").strip().lstrip("@") or None
    photo_url = (user.get("photo_url") or "").strip() or None
    user_id = int(user["id"])
    display_name = format_display_name(
        first_name=first_name,
        last_name=last_name,
        username=username,
        user_id=user_id,
    )
    return {
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "photo_url": photo_url,
        "display_name": display_name,
    }


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    except Exception:
        return None


def profile_row_to_client(
    row: dict[str, Any] | None,
    *,
    user_id: int,
    active_listings: int = 0,
    viewer_id: int | None = None,
) -> dict[str, Any]:
    sales_count = 0
    items_sold = 0
    harvest_count = 0
    craft_count = 0
    days_in_game = 0
    country = None
    balance = 0
    experience = 0
    referrals = 0
    wins = 0
    losses = 0
    win_amount = 0
    rep_plus = 0
    rep_minus = 0
    registered_at = None
    referer_name = None
    referer_user_id = None

    if row:
        sales_count = int(_row_get(row, "market_sales_count", 0) or 0)
        items_sold = int(_row_get(row, "market_items_sold", 0) or 0)
        harvest_count = int(_row_get(row, "harvest_count", 0) or 0)
        craft_count = int(_row_get(row, "craft_count", 0) or 0)
        days_in_game = int(_row_get(row, "days_in_game", 0) or 0)
        country_raw = _row_get(row, "country")
        country = str(country_raw).strip() if country_raw else None
        balance = int(_row_get(row, "balance", 0) or 0)
        experience = int(_row_get(row, "xpp", _row_get(row, "experience", 0)) or 0)
        referrals = int(_row_get(row, "refferals", _row_get(row, "referrals", 0)) or 0)
        wins = int(_row_get(row, "wins", 0) or 0)
        losses = int(_row_get(row, "loose", _row_get(row, "losses", 0)) or 0)
        win_amount = int(_row_get(row, "winamount", _row_get(row, "win_amount", 0)) or 0)
        rep_plus = int(_row_get(row, "rep_plus", 0) or 0)
        rep_minus = int(_row_get(row, "rep_minus", 0) or 0)
        registered_at = _iso_date(_row_get(row, "created_at"))
        referer_raw = _row_get(row, "referer_name")
        referer_name = str(referer_raw).strip() if referer_raw else None
        ref_id = _row_get(row, "refferer_id") or _row_get(row, "referer_user_id")
        if ref_id:
            try:
                referer_user_id = int(ref_id)
            except (TypeError, ValueError):
                referer_user_id = None

    rank = seller_rank(sales_count)
    is_self = viewer_id is not None and int(viewer_id) == int(user_id)

    base = {
        "userId": int(user_id),
        "activeListings": int(active_listings),
        "salesCount": sales_count,
        "itemsSold": items_sold,
        "harvestCount": harvest_count,
        "craftCount": craft_count,
        "daysInGame": days_in_game,
        "countryEmoji": country,
        "sellerRank": rank,
        "isSelf": is_self,
        # Публичная часть как в /api/me (без лимитов/бана/донатов)
        "balance": balance,
        "experience": experience,
        "referrals": referrals,
        "wins": wins,
        "losses": losses,
        "winAmount": win_amount,
        "repPlus": rep_plus,
        "repMinus": rep_minus,
        "registeredAt": registered_at,
        "refererName": referer_name,
        "refererUserId": referer_user_id,
        "marketSalesCount": sales_count,
        "marketItemsSold": items_sold,
    }

    if not row:
        display = format_display_name(user_id=user_id)
        return {
            **base,
            "displayName": display,
            "sellerLabel": display,
            "username": None,
            "photoUrl": None,
        }

    uid = int(_row_get(row, "user_id", user_id) or user_id)
    first_name = _row_get(row, "first_name")
    last_name = _row_get(row, "last_name")
    username = _row_get(row, "username")
    display = format_display_name(
        first_name=first_name,
        last_name=last_name,
        username=username,
        display_name=_row_get(row, "display_name"),
        user_id=uid,
    )
    uname = (username or "").strip().lstrip("@") or None
    photo = (_row_get(row, "photo_url") or "").strip() or None
    return {
        **base,
        "userId": uid,
        "displayName": display,
        "sellerLabel": display,
        "username": uname,
        "photoUrl": photo,
        "isSelf": viewer_id is not None and int(viewer_id) == int(uid),
    }


def seller_fields_from_row(row: dict[str, Any], *, viewer_id: int | None = None) -> dict[str, Any]:
    seller_id = int(_row_get(row, "seller_id") or _row_get(row, "user_id") or 0)
    has_profile = any(
        _row_get(row, key)
        for key in ("user_id", "first_name", "username", "display_name")
    )
    profile = profile_row_to_client(
        row if has_profile else None,
        user_id=seller_id,
        active_listings=0,
        viewer_id=viewer_id,
    )
    return {
        "sellerId": seller_id,
        "sellerLabel": profile["sellerLabel"],
        "sellerName": profile["displayName"],
        "sellerUsername": profile["username"],
        "sellerPhotoUrl": profile["photoUrl"],
    }
