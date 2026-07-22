"""Admin: розыгрыши призов."""
from __future__ import annotations

from typing import Any

from db import db

_VALID_RARITY = frozenset({"common", "rare", "legendary"})
_VALID_PRIZE_TYPE = frozenset({"kut", "manual"})
_VALID_ANIMATION_TYPE = frozenset({"webm", "lottie"})
_VALID_DRAW_TYPE = frozenset({"timer", "instant"})
_VALID_CONDITION_KIND = frozenset({
    "balance", "harvest_count", "item_count", "channel_sub", "referral_count",
})
_UNSET = object()


def _validate_rarity(value: str) -> str:
    value = (value or "").strip().lower()
    if value not in _VALID_RARITY:
        raise ValueError(f"Редкость: {', '.join(sorted(_VALID_RARITY))}")
    return value


def _validate_prize(
    prize_type: str, prize_kut_amount, prize_title, prize_emoji, prize_description,
    prize_animation_url=None, prize_animation_type=None,
):
    prize_type = (prize_type or "").strip().lower()
    if prize_type not in _VALID_PRIZE_TYPE:
        raise ValueError(f"Тип приза: {', '.join(sorted(_VALID_PRIZE_TYPE))}")

    # Анимация — витрина приза (webm-стикер или Lottie-json), не завязана на
    # prize_type: доступна и для КУТ-джекпота, и для ручного приза.
    animation_url = (prize_animation_url or "").strip() or None
    animation_type = (prize_animation_type or "").strip().lower() or None
    if animation_url and animation_type not in _VALID_ANIMATION_TYPE:
        raise ValueError(f"Тип анимации: {', '.join(sorted(_VALID_ANIMATION_TYPE))}")
    if not animation_url:
        animation_type = None

    if prize_type == "kut":
        amount = int(prize_kut_amount or 0)
        if amount < 1:
            raise ValueError("Укажите сумму КУТ")
        return prize_type, amount, None, None, None, animation_url, animation_type
    title = (prize_title or "").strip()
    if not title:
        raise ValueError("Укажите название приза")
    emoji = (prize_emoji or "🎁").strip() or "🎁"
    description = (prize_description or "").strip()
    return prize_type, None, title, emoji, description, animation_url, animation_type


def _validate_draw(draw_type: str, ends_at, starts_at=None):
    draw_type = (draw_type or "").strip().lower()
    if draw_type not in _VALID_DRAW_TYPE:
        raise ValueError(f"Тип розыгрыша: {', '.join(sorted(_VALID_DRAW_TYPE))}")
    if draw_type == "timer" and not ends_at:
        raise ValueError("Укажите дату окончания для розыгрыша по таймеру")
    if starts_at and ends_at and starts_at >= ends_at:
        raise ValueError("Дата начала должна быть раньше даты окончания")
    return draw_type


def _validate_conditions(conditions: list[dict]) -> list[dict]:
    cleaned = []
    for idx, cond in enumerate(conditions or []):
        kind = str(cond.get("kind") or "").strip().lower()
        if kind not in _VALID_CONDITION_KIND:
            raise ValueError(f"Условие #{idx + 1}: тип {', '.join(sorted(_VALID_CONDITION_KIND))}")
        try:
            target_value = max(1, int(cond.get("target_value") or cond.get("targetValue") or 1))
        except (TypeError, ValueError):
            raise ValueError(f"Условие #{idx + 1}: укажите значение")
        item_id = None
        if kind == "item_count":
            item_id = str(cond.get("item_id") or cond.get("itemId") or "").strip()
            if not item_id:
                raise ValueError(f"Условие #{idx + 1}: укажите предмет")
        elif kind == "channel_sub":
            # Принимаем и @username, и ссылку (https://t.me/name) — храним
            # чистый идентификатор, чтобы getChatMember и ссылка «Перейти»
            # работали одинаково.
            from telegram_membership import normalize_channel
            item_id = normalize_channel(cond.get("item_id") or cond.get("itemId"))
            if not item_id:
                raise ValueError(f"Условие #{idx + 1}: укажите канал (@username или ссылку)")
            target_value = 1
        cleaned.append({"kind": kind, "target_value": target_value, "item_id": item_id, "sort_order": idx})
    return cleaned


async def _replace_conditions(conn, giveaway_id: int, conditions: list[dict]) -> None:
    await conn.execute("DELETE FROM giveaway_conditions WHERE giveaway_id = $1", giveaway_id)
    for cond in conditions:
        await conn.execute(
            """
            INSERT INTO giveaway_conditions (giveaway_id, kind, target_value, item_id, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            """,
            giveaway_id, cond["kind"], cond["target_value"], cond["item_id"], cond["sort_order"],
        )


def _giveaway_to_admin_dict(row: dict, conditions: list[dict], entries_count: int) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "emoji": row["emoji"],
        "rarity": row["rarity"],
        "prizeType": row["prize_type"],
        "prizeKutAmount": row["prize_kut_amount"],
        "prizeTitle": row["prize_title"],
        "prizeEmoji": row["prize_emoji"],
        "prizeDescription": row["prize_description"],
        "prizeAnimationUrl": row["prize_animation_url"],
        "prizeAnimationType": row["prize_animation_type"],
        "drawType": row["draw_type"],
        "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
        "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
        "status": row["status"],
        "winnerUserId": row["winner_user_id"],
        "enabled": row["enabled"],
        "entriesCount": entries_count,
        "conditions": [
            {"kind": c["kind"], "targetValue": c["target_value"], "itemId": c["item_id"]}
            for c in conditions
        ],
    }


async def list_giveaways_admin() -> list[dict]:
    rows = await db.pool.fetch("SELECT * FROM giveaways ORDER BY sort_order, id DESC")
    result = []
    for row in rows:
        row = dict(row)
        conditions = await db.pool.fetch(
            "SELECT kind, target_value, item_id FROM giveaway_conditions WHERE giveaway_id = $1 ORDER BY sort_order",
            row["id"],
        )
        entries_count = int(
            await db.pool.fetchval(
                "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1", row["id"]
            ) or 0
        )
        result.append(_giveaway_to_admin_dict(row, [dict(c) for c in conditions], entries_count))
    return result


async def create_giveaway(
    *,
    title: str,
    description: str = "",
    emoji: str = "🎁",
    rarity: str,
    prize_type: str,
    prize_kut_amount: int | None = None,
    prize_title: str | None = None,
    prize_emoji: str | None = None,
    prize_description: str | None = None,
    prize_animation_url: str | None = None,
    prize_animation_type: str | None = None,
    draw_type: str,
    ends_at=None,
    starts_at=None,
    conditions: list[dict] | None = None,
    enabled: bool = True,
    admin_user_id: int,
) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("Укажите название розыгрыша")
    rarity = _validate_rarity(rarity)
    prize_type, kut_amount, p_title, p_emoji, p_desc, anim_url, anim_type = _validate_prize(
        prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description,
        prize_animation_url, prize_animation_type,
    )
    draw_type = _validate_draw(draw_type, ends_at, starts_at)
    cleaned_conditions = _validate_conditions(conditions or [])

    sort_order = int(
        await db.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM giveaways") or 0
    )

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            giveaway_id = await conn.fetchval(
                """
                INSERT INTO giveaways (
                    title, description, emoji, rarity, prize_type, prize_kut_amount,
                    prize_title, prize_emoji, prize_description, prize_animation_url,
                    prize_animation_type, draw_type, ends_at,
                    starts_at, enabled, sort_order
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
                """,
                title, (description or "").strip(), (emoji or "🎁").strip() or "🎁", rarity,
                prize_type, kut_amount, p_title, p_emoji, p_desc, anim_url, anim_type,
                draw_type, ends_at, starts_at, bool(enabled), sort_order,
            )
            await _replace_conditions(conn, int(giveaway_id), cleaned_conditions)

    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    return _giveaway_to_admin_dict(dict(row), cleaned_conditions, 0)


async def update_giveaway(
    giveaway_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    emoji: str | None = None,
    rarity: str | None = None,
    prize_type: str | None = None,
    prize_kut_amount: int | None = _UNSET,
    prize_title: str | None = _UNSET,
    prize_emoji: str | None = _UNSET,
    prize_description: str | None = _UNSET,
    prize_animation_url: str | None = _UNSET,
    prize_animation_type: str | None = _UNSET,
    draw_type: str | None = None,
    ends_at=_UNSET,
    starts_at=_UNSET,
    conditions: list[dict] | None = None,
    enabled: bool | None = None,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")

    sets: list[str] = ["updated_at = NOW()"]
    params: list[Any] = [giveaway_id]

    if title is not None:
        title_clean = title.strip()
        if not title_clean:
            raise ValueError("Название не может быть пустым")
        params.append(title_clean)
        sets.append(f"title = ${len(params)}")
    if description is not None:
        params.append(description.strip())
        sets.append(f"description = ${len(params)}")
    if emoji is not None:
        params.append((emoji or "🎁").strip() or "🎁")
        sets.append(f"emoji = ${len(params)}")
    if rarity is not None:
        params.append(_validate_rarity(rarity))
        sets.append(f"rarity = ${len(params)}")

    current_prize_type = prize_type if prize_type is not None else row["prize_type"]
    if (
        prize_type is not None or prize_kut_amount is not _UNSET or prize_title is not _UNSET
        or prize_animation_url is not _UNSET or prize_animation_type is not _UNSET
    ):
        resolved_amount = prize_kut_amount if prize_kut_amount is not _UNSET else row["prize_kut_amount"]
        resolved_title = prize_title if prize_title is not _UNSET else row["prize_title"]
        resolved_emoji = prize_emoji if prize_emoji is not _UNSET else row["prize_emoji"]
        resolved_desc = prize_description if prize_description is not _UNSET else row["prize_description"]
        resolved_anim_url = (
            prize_animation_url if prize_animation_url is not _UNSET else row["prize_animation_url"]
        )
        resolved_anim_type = (
            prize_animation_type if prize_animation_type is not _UNSET else row["prize_animation_type"]
        )
        prize_type_v, kut_amount_v, p_title_v, p_emoji_v, p_desc_v, anim_url_v, anim_type_v = _validate_prize(
            current_prize_type, resolved_amount, resolved_title, resolved_emoji, resolved_desc,
            resolved_anim_url, resolved_anim_type,
        )
        params.append(prize_type_v); sets.append(f"prize_type = ${len(params)}")
        params.append(kut_amount_v); sets.append(f"prize_kut_amount = ${len(params)}")
        params.append(p_title_v); sets.append(f"prize_title = ${len(params)}")
        params.append(p_emoji_v); sets.append(f"prize_emoji = ${len(params)}")
        params.append(p_desc_v); sets.append(f"prize_description = ${len(params)}")
        params.append(anim_url_v); sets.append(f"prize_animation_url = ${len(params)}")
        params.append(anim_type_v); sets.append(f"prize_animation_type = ${len(params)}")

    if draw_type is not None or ends_at is not _UNSET or starts_at is not _UNSET:
        resolved_ends_at = ends_at if ends_at is not _UNSET else row["ends_at"]
        resolved_starts_at = starts_at if starts_at is not _UNSET else row["starts_at"]
        draw_type_v = _validate_draw(
            draw_type if draw_type is not None else row["draw_type"],
            resolved_ends_at, resolved_starts_at,
        )
        params.append(draw_type_v); sets.append(f"draw_type = ${len(params)}")
        params.append(resolved_ends_at); sets.append(f"ends_at = ${len(params)}")
        params.append(resolved_starts_at); sets.append(f"starts_at = ${len(params)}")

    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")

    cleaned_conditions = _validate_conditions(conditions) if conditions is not None else None

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if len(sets) > 1:
                await conn.execute(f"UPDATE giveaways SET {', '.join(sets)} WHERE id = $1", *params)
            if cleaned_conditions is not None:
                await _replace_conditions(conn, giveaway_id, cleaned_conditions)

    updated = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    final_conditions = await db.pool.fetch(
        "SELECT kind, target_value, item_id FROM giveaway_conditions WHERE giveaway_id = $1 ORDER BY sort_order",
        giveaway_id,
    )
    entries_count = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1", giveaway_id
        ) or 0
    )
    return _giveaway_to_admin_dict(dict(updated), [dict(c) for c in final_conditions], entries_count)


async def cancel_giveaway(giveaway_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT id, title FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")
    await db.pool.execute(
        "UPDATE giveaways SET status = 'cancelled', updated_at = NOW() WHERE id = $1",
        giveaway_id,
    )
    return {"ok": True, "title": row["title"]}


async def complete_giveaway(giveaway_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow(
        "SELECT id, title, draw_type, status FROM giveaways WHERE id = $1", giveaway_id
    )
    if row is None:
        raise ValueError("Розыгрыш не найден")
    if row["draw_type"] != "instant":
        raise ValueError("Завершить вручную можно только мгновенный розыгрыш — таймерные завершаются сами")
    if row["status"] != "active":
        raise ValueError("Розыгрыш уже завершён или отменён")
    ok = await db.complete_instant_giveaway(giveaway_id)
    if not ok:
        raise ValueError("Не удалось завершить — розыгрыш уже изменился, обновите список")
    return {"ok": True, "title": row["title"]}
