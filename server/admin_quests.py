"""Admin: задания NPC Cute."""

from __future__ import annotations

import re
from typing import Any

from admin_users import insert_admin_audit
from db import db
from dex_catalog import dex_catalog
from quest_registry import (
    VALID_ACTIONS,
    VALID_PERIODS,
    VALID_SCOPES,
    get_quest_by_id,
    quest_admin_meta,
    quest_to_admin_dict,
    reload_quest_registry,
)

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
_VALID_RECURRENCES = frozenset({"daily", "weekly"})
_UNSET = object()  # sentinel for optional update fields


def _validate_key(key: str) -> str:
    key = (key or "").strip().lower()
    if not _KEY_RE.match(key):
        raise ValueError("Ключ: латиница, цифры, _, от 2 символов (a-z)")
    return key


def _validate_period(period: str) -> str:
    period = (period or "").strip().lower()
    if period not in VALID_PERIODS:
        raise ValueError("Период: hourly, daily или weekly")
    return period


def _validate_action(action: str) -> str:
    action = (action or "").strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(f"Действие: {', '.join(sorted(VALID_ACTIONS))}")
    return action


def _validate_recurrence(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v not in _VALID_RECURRENCES:
        raise ValueError("Повторение: daily или weekly")
    return v


def _validate_scope(scope: str) -> str:
    scope = (scope or "any").strip().lower()
    if scope not in VALID_SCOPES:
        raise ValueError("Цель: any, item, crop или random")
    return scope


async def _validate_target_fields(
    *,
    action: str,
    target_scope: str,
    target_crop_key: str | None,
    target_item_id: str | None,
) -> tuple[str, str | None, str | None]:
    from content_registry import enabled_crops

    scope = _validate_scope(target_scope)
    crop_key = (target_crop_key or "").strip().lower() or None
    item_id = (target_item_id or "").strip() or None

    if action in {"water", "claim_daily_seed"}:
        if scope != "any":
            raise ValueError("Для полива и бесплатного семени цель должна быть «любой»")
        return "any", None, None

    if scope == "any":
        return scope, None, None

    if scope == "random":
        if action not in {"harvest", "plant", "craft"}:
            raise ValueError("Случайная цель доступна для сбора, посадки и крафта")
        return scope, None, None

    if scope == "crop":
        if action not in {"harvest", "plant"}:
            raise ValueError("Культура задаётся только для сбора и посадки")
        if not crop_key:
            raise ValueError("Выберите культуру")
        known = {crop.key for crop in enabled_crops()}
        if crop_key not in known:
            raise ValueError(f"Культура «{crop_key}» не найдена")
        return scope, crop_key, None

    if scope == "item":
        if action not in {"harvest", "plant", "craft"}:
            raise ValueError("Предмет задаётся для сбора, посадки и крафта")
        if not item_id:
            raise ValueError("Укажите id предмета dex")
        item_id = await _ensure_dex_item(item_id, "Цель задания")
        return scope, None, item_id

    return scope, crop_key, item_id


async def _ensure_dex_item(item_id: str, label: str) -> str:
    canon = dex_catalog.canonical_key(str(item_id).strip())
    if not canon:
        raise ValueError(f"{label}: укажите id предмета")
    if not dex_catalog.get(canon):
        raise ValueError(f"{label}: предмет {canon} не найден в dex")
    return canon


def _validate_rewards(rewards: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for idx, reward in enumerate(rewards or []):
        kind = str(reward.get("kind") or "").strip().lower()
        if kind not in {"kut", "item"}:
            raise ValueError(f"Награда #{idx + 1}: kind = kut или item")
        try:
            amount = max(1, int(reward.get("amount") or 1))
        except (TypeError, ValueError):
            raise ValueError(f"Награда #{idx + 1}: укажите количество")
        item_id = None
        if kind == "item":
            raw_item = str(reward.get("item_id") or reward.get("itemId") or "").strip()
            if not raw_item:
                raise ValueError(f"Награда #{idx + 1}: укажите предмет dex")
            item_id = raw_item
        cleaned.append({"kind": kind, "amount": amount, "item_id": item_id, "sort_order": idx})
    return cleaned


async def _replace_quest_rewards(conn, quest_id: int, rewards: list[dict]) -> None:
    await conn.execute("DELETE FROM quest_rewards WHERE quest_id = $1", quest_id)
    for reward in rewards:
        item_id = reward["item_id"]
        if item_id:
            item_id = await _ensure_dex_item(item_id, "Награда")
        await conn.execute(
            """
            INSERT INTO quest_rewards (quest_id, kind, amount, item_id, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            """,
            quest_id,
            reward["kind"],
            reward["amount"],
            item_id,
            reward["sort_order"],
        )


async def _invalidate_quests() -> None:
    await reload_quest_registry(db.pool)


async def list_quests_admin() -> list[dict]:
    from quest_registry import all_quests

    return [quest_to_admin_dict(quest) for quest in all_quests()]


async def create_quest(
    *,
    key: str,
    period: str,
    action: str,
    target: int,
    title: str,
    description: str = "",
    emoji: str = "📋",
    enabled: bool = True,
    target_scope: str = "any",
    target_crop_key: str | None = None,
    target_item_id: str | None = None,
    rewards: list[dict] | None = None,
    active_from: Any | None = None,
    active_until: Any | None = None,
    recurrence: str | None = None,
    recurrence_end: Any | None = None,
    admin_user_id: int,
) -> dict:
    key = _validate_key(key)
    period = _validate_period(period)
    action = _validate_action(action)
    target = max(1, min(9999, int(target)))
    title = (title or key).strip()
    if not title:
        raise ValueError("Укажите название задания")

    scope, crop_key, item_id = await _validate_target_fields(
        action=action,
        target_scope=target_scope,
        target_crop_key=target_crop_key,
        target_item_id=target_item_id,
    )

    exists = await db.pool.fetchval("SELECT 1 FROM quests WHERE key = $1", key)
    if exists:
        raise ValueError(f"Задание с ключом «{key}» уже есть")

    cleaned_rewards = _validate_rewards(rewards or [])
    for reward in cleaned_rewards:
        if reward["item_id"]:
            reward["item_id"] = await _ensure_dex_item(reward["item_id"], "Награда")

    sort_order = int(
        await db.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM quests") or 0
    )

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            validated_recurrence = _validate_recurrence(recurrence)
            quest_id = await conn.fetchval(
                """
                INSERT INTO quests (
                    key, period, action, target, title, description, emoji,
                    target_scope, target_crop_key, target_item_id,
                    enabled, sort_order,
                    active_from, active_until, recurrence, recurrence_end
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
                """,
                key,
                period,
                action,
                target,
                title,
                (description or "").strip(),
                (emoji or "📋").strip() or "📋",
                scope,
                crop_key,
                item_id,
                bool(enabled),
                sort_order,
                active_from,
                active_until,
                validated_recurrence,
                recurrence_end,
            )
            await _replace_quest_rewards(conn, int(quest_id), cleaned_rewards)

    await insert_admin_audit(
        0,
        "admin_quest_create",
        admin_user_id=admin_user_id,
        details={"quest_id": int(quest_id), "key": key},
    )
    await _invalidate_quests()
    quest = get_quest_by_id(int(quest_id))
    if not quest:
        raise ValueError("Задание создано, но не загрузилось")
    return quest_to_admin_dict(quest)


async def update_quest(
    quest_id: int,
    *,
    period: str | None = None,
    action: str | None = None,
    target: int | None = None,
    title: str | None = None,
    description: str | None = None,
    emoji: str | None = None,
    enabled: bool | None = None,
    target_scope: str | None = None,
    target_crop_key: str | None = None,
    target_item_id: str | None = None,
    rewards: list[dict] | None = None,
    active_from: Any | None = _UNSET,
    active_until: Any | None = _UNSET,
    recurrence: str | None = _UNSET,
    recurrence_end: Any | None = _UNSET,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow(
        """
        SELECT id, key, action, target_scope, target_crop_key, target_item_id
        FROM quests WHERE id = $1
        """,
        quest_id,
    )
    if row is None:
        raise ValueError("Задание не найдено")

    sets: list[str] = ["updated_at = NOW()"]
    params: list[Any] = [quest_id]

    if period is not None:
        params.append(_validate_period(period))
        sets.append(f"period = ${len(params)}")
    if action is not None:
        params.append(_validate_action(action))
        sets.append(f"action = ${len(params)}")
    if target is not None:
        params.append(max(1, min(9999, int(target))))
        sets.append(f"target = ${len(params)}")
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
        params.append((emoji or "📋").strip() or "📋")
        sets.append(f"emoji = ${len(params)}")
    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")

    if active_from is not _UNSET:
        params.append(active_from)
        sets.append(f"active_from = ${len(params)}")
    if active_until is not _UNSET:
        params.append(active_until)
        sets.append(f"active_until = ${len(params)}")
    if recurrence is not _UNSET:
        params.append(_validate_recurrence(recurrence) if recurrence else None)
        sets.append(f"recurrence = ${len(params)}")
    if recurrence_end is not _UNSET:
        params.append(recurrence_end)
        sets.append(f"recurrence_end = ${len(params)}")

    current_action = action if action is not None else str(row["action"])
    if (
        target_scope is not None
        or target_crop_key is not None
        or target_item_id is not None
        or action is not None
    ):
        scope, crop_key, item_id = await _validate_target_fields(
            action=current_action,
            target_scope=target_scope if target_scope is not None else str(row["target_scope"] or "any"),
            target_crop_key=(
                target_crop_key
                if target_crop_key is not None
                else (str(row["target_crop_key"]) if row["target_crop_key"] else None)
            ),
            target_item_id=(
                target_item_id
                if target_item_id is not None
                else (str(row["target_item_id"]) if row["target_item_id"] else None)
            ),
        )
        params.append(scope)
        sets.append(f"target_scope = ${len(params)}")
        params.append(crop_key)
        sets.append(f"target_crop_key = ${len(params)}")
        params.append(item_id)
        sets.append(f"target_item_id = ${len(params)}")

    cleaned_rewards = None
    if rewards is not None:
        cleaned_rewards = _validate_rewards(rewards)
        for reward in cleaned_rewards:
            if reward["item_id"]:
                reward["item_id"] = await _ensure_dex_item(reward["item_id"], "Награда")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if len(sets) > 1:
                await conn.execute(
                    f"UPDATE quests SET {', '.join(sets)} WHERE id = $1",
                    *params,
                )
            if cleaned_rewards is not None:
                await _replace_quest_rewards(conn, quest_id, cleaned_rewards)

    await insert_admin_audit(
        0,
        "admin_quest_update",
        admin_user_id=admin_user_id,
        details={"quest_id": quest_id, "key": row["key"]},
    )
    await _invalidate_quests()
    quest = get_quest_by_id(quest_id)
    if not quest:
        raise ValueError("Задание не найдено после сохранения")
    return quest_to_admin_dict(quest)


async def delete_quest(quest_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT id, key, title FROM quests WHERE id = $1", quest_id)
    if row is None:
        raise ValueError("Задание не найдено")

    await db.pool.execute("DELETE FROM quests WHERE id = $1", quest_id)
    await insert_admin_audit(
        0,
        "admin_quest_delete",
        admin_user_id=admin_user_id,
        details={"quest_id": quest_id, "key": row["key"], "title": row["title"]},
    )
    await _invalidate_quests()
    return {"ok": True, "key": row["key"]}
