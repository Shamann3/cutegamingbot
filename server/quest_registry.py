"""Задания NPC — загрузка из БД с кэшем."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from config import WATER_ITEM_KEY
from dex_catalog import dex_catalog

VALID_PERIODS = frozenset({"hourly", "daily", "weekly"})
VALID_ACTIONS = frozenset({
    "harvest",
    "water",
    "plant",
    "craft",
    "claim_daily_seed",
})

PERIOD_LABELS = {
    "hourly": "На час",
    "daily": "На день",
    "weekly": "На неделю",
}

VALID_SCOPES = frozenset({"any", "item", "crop", "random"})

SCOPE_LABELS = {
    "any": "Любой",
    "item": "Конкретный предмет",
    "crop": "Конкретная культура",
    "random": "Случайно при взятии",
}

ACTION_SCOPE_HINTS = {
    "harvest": "Урожай: любой, культура, предмет dex или случайная культура",
    "plant": "Семена: любые, культура, предмет dex или случайная культура",
    "craft": "Крафт: любой результат, предмет dex или случайный рецепт",
    "water": "Считается любой полив",
    "claim_daily_seed": "Пассивное задание без фильтра",
}

ACTION_LABELS = {
    "harvest": "Собрать урожай",
    "water": "Полить грядку",
    "plant": "Посадить семена",
    "craft": "Успешный крафт",
    "claim_daily_seed": "Бесплатное семя (пассивное)",
}


def _crop_by_key(crop_key: str):
    from content_registry import all_crops

    key = str(crop_key or "").strip().lower()
    for crop in all_crops():
        if crop.key == key:
            return crop
    return None


def resolve_random_filter(quest: "QuestDef") -> dict[str, str]:
    import random
    from content_registry import enabled_craft_recipes, enabled_crops

    if quest.action == "plant":
        crops = list(enabled_crops())
        if not crops:
            raise ValueError("Нет культур для случайного задания")
        crop = random.choice(crops)
        entry = dex_catalog.get(crop.seed_id)
        return {
            "kind": "plant",
            "itemId": dex_catalog.canonical_key(crop.seed_id),
            "cropKey": crop.key,
            "label": f"{entry.emoji if entry else '🌱'} {crop.display_name}",
        }
    if quest.action == "harvest":
        crops = list(enabled_crops())
        if not crops:
            raise ValueError("Нет культур для случайного задания")
        crop = random.choice(crops)
        entry = dex_catalog.get(crop.harvest_id)
        return {
            "kind": "harvest",
            "itemId": dex_catalog.canonical_key(crop.harvest_id),
            "cropKey": crop.key,
            "label": f"{entry.emoji if entry else '📦'} {crop.display_name}",
        }
    if quest.action == "craft":
        recipes = list(enabled_craft_recipes())
        if not recipes:
            raise ValueError("Нет рецептов для случайного задания")
        recipe = random.choice(recipes)
        entry = dex_catalog.get(recipe.result_id)
        return {
            "kind": "craft",
            "itemId": dex_catalog.canonical_key(recipe.result_id),
            "label": f"{entry.emoji if entry else '⚗️'} {recipe.display_name or recipe.key}",
        }
    raise ValueError("Случайная цель доступна для сбора, посадки и крафта")


def quest_target_hint(quest: "QuestDef", active_filter: dict | None = None) -> str:
    scope = quest.target_scope or "any"
    if scope == "random" and active_filter:
        return f"Цель: {active_filter.get('label', 'случайная')}"
    if scope == "crop" and quest.target_crop_key:
        crop = _crop_by_key(quest.target_crop_key)
        if crop:
            if quest.action == "plant":
                entry = dex_catalog.get(crop.seed_id)
                return f"Цель: {entry.emoji if entry else '🌱'} {crop.display_name}"
            if quest.action == "harvest":
                entry = dex_catalog.get(crop.harvest_id)
                return f"Цель: {entry.emoji if entry else '📦'} {crop.display_name}"
    if scope == "item" and quest.target_item_id:
        entry = dex_catalog.get(quest.target_item_id)
        name = entry.name if entry else quest.target_item_id
        emoji = entry.emoji if entry else "📦"
        return f"Цель: {emoji} {name}"
    if scope == "random":
        return "Цель определится при взятии задания"
    return ""


def quest_matches_items(
    quest: "QuestDef",
    item_ids: tuple[str, ...],
    *,
    active_filter: dict | None = None,
    bucket: dict[str, Any] | None = None,
) -> bool:
    if quest.action in {"water", "claim_daily_seed"}:
        return True

    scope = (quest.target_scope or "any").lower()
    if scope == "any":
        return bool(item_ids)

    wanted: str | None = None
    if scope == "random":
        filt = active_filter
        if filt is None and bucket is not None:
            filt = bucket.get("activeFilter")
        active = filt or {}
        wanted = active.get("itemId")
    elif scope == "item" and quest.target_item_id:
        wanted = quest.target_item_id
    elif scope == "crop" and quest.target_crop_key:
        crop = _crop_by_key(quest.target_crop_key)
        if not crop:
            return bool(item_ids)
        if quest.action == "plant":
            wanted = crop.seed_id
        elif quest.action == "harvest":
            wanted = crop.harvest_id
        elif quest.action == "craft":
            return bool(item_ids)

    if not wanted:
        return bool(item_ids)

    canon_want = dex_catalog.canonical_key(wanted)
    return any(dex_catalog.canonical_key(item_id) == canon_want for item_id in item_ids)


@dataclass(frozen=True)
class QuestRewardDef:
    kind: str
    amount: int
    item_id: str | None = None

    def for_client(self) -> dict:
        payload = {"kind": self.kind, "amount": self.amount}
        if self.item_id:
            payload["itemId"] = self.item_id
        return payload


@dataclass(frozen=True)
class QuestDef:
    db_id: int
    key: str
    period: str
    action: str
    target: int
    title: str
    description: str
    emoji: str
    rewards: tuple[QuestRewardDef, ...]
    target_scope: str = "any"
    target_crop_key: str | None = None
    target_item_id: str | None = None
    enabled: bool = True
    sort_order: int = 0
    # Scheduling / timed events
    active_from: Any = None   # datetime | None
    active_until: Any = None  # datetime | None
    recurrence: str | None = None  # 'daily' | 'weekly' | None
    recurrence_end: Any = None    # datetime | None

    @property
    def id(self) -> str:
        return self.key

    def for_client(
        self,
        *,
        progress: int,
        claimed: bool,
        ready: bool,
        accepted: bool = False,
        locked: bool = False,
        can_accept: bool = False,
        can_cancel: bool = False,
        active_quest_title: str | None = None,
        target_hint: str = "",
        period_ends_at_ms: int | None = None,
        timer_remaining_sec: int | None = None,
        accepted_at_ms: int | None = None,
    ) -> dict:
        return {
            "id": self.key,
            "period": self.period,
            "action": self.action,
            "target": self.target,
            "title": self.title,
            "description": self.description,
            "emoji": self.emoji,
            "progress": min(progress, self.target),
            "claimed": claimed,
            "ready": ready and not claimed,
            "accepted": accepted,
            "locked": locked,
            "canAccept": can_accept,
            "canCancel": can_cancel,
            "activeQuestTitle": active_quest_title,
            "targetHint": target_hint,
            "periodEndsAt": period_ends_at_ms,
            "timerRemainingSec": timer_remaining_sec,
            "acceptedAt": accepted_at_ms,
            "rewards": [reward.for_client() for reward in self.rewards],
        }


_registry_loaded = False
_quests: tuple[QuestDef, ...] = ()
_quest_by_key: dict[str, QuestDef] = {}


def _default_quest_rows() -> tuple[tuple[dict[str, Any], tuple[tuple[str, int, str | None], ...]], ...]:
    return (
        (
            {
                "key": "hourly_water",
                "period": "hourly",
                "action": "water",
                "target": 12,
                "title": "Режим полива",
                "description": "Полейте грядки 12 раз за час.",
                "emoji": "💧",
                "sort_order": 10,
            },
            (("kut", 12, None),),
        ),
        (
            {
                "key": "hourly_harvest",
                "period": "hourly",
                "action": "harvest",
                "target": 6,
                "title": "Час урожая",
                "description": "Соберите урожай с 6 грядок за час.",
                "emoji": "🧺",
                "sort_order": 20,
            },
            (("kut", 14, None),),
        ),
        (
            {
                "key": "hourly_plant",
                "period": "hourly",
                "action": "plant",
                "target": 4,
                "title": "Массовая посадка",
                "description": "Посадите семена на 4 грядки в течение часа.",
                "emoji": "🪴",
                "sort_order": 30,
            },
            (("kut", 12, None),),
        ),
        (
            {
                "key": "hourly_craft",
                "period": "hourly",
                "action": "craft",
                "target": 2,
                "title": "Лабораторный час",
                "description": "Успешно скрафтите 2 предмета за час.",
                "emoji": "⚗️",
                "sort_order": 40,
            },
            (("kut", 14, None),),
        ),
        (
            {
                "key": "hourly_crop_harvest",
                "period": "hourly",
                "action": "harvest",
                "target": 3,
                "title": "Урожай по заданию",
                "description": "Соберите урожай указанной культуры 3 раза. Цель выбирается при взятии.",
                "emoji": "🎯",
                "sort_order": 50,
                "target_scope": "random",
            },
            (("kut", 16, None),),
        ),
        (
            {
                "key": "hourly_crop_plant",
                "period": "hourly",
                "action": "plant",
                "target": 3,
                "title": "Посев по заданию",
                "description": "Посадите семена указанной культуры 3 раза. Культура случайная.",
                "emoji": "🌱",
                "sort_order": 60,
                "target_scope": "random",
            },
            (("kut", 16, None),),
        ),
        (
            {
                "key": "daily_free_seed",
                "period": "daily",
                "action": "claim_daily_seed",
                "target": 1,
                "title": "Семя дня",
                "description": "Семена: ценный ресурс. Заберите бесплатное семечко раз в день.",
                "emoji": "🌱",
                "sort_order": 5,
            },
            (),
        ),
        (
            {
                "key": "daily_water",
                "period": "daily",
                "action": "water",
                "target": 18,
                "title": "Ирригация",
                "description": "Полейте грядки 18 раз за день.",
                "emoji": "🚿",
                "sort_order": 15,
            },
            (("item", 2, WATER_ITEM_KEY), ("kut", 18, None)),
        ),
        (
            {
                "key": "daily_plant",
                "period": "daily",
                "action": "plant",
                "target": 6,
                "title": "Расширение посевов",
                "description": "Посадите семена на 6 грядок за день.",
                "emoji": "🪴",
                "sort_order": 25,
            },
            (("kut", 22, None),),
        ),
        (
            {
                "key": "daily_harvest",
                "period": "daily",
                "action": "harvest",
                "target": 14,
                "title": "Дневной сбор",
                "description": "Соберите урожай с 14 грядок за день.",
                "emoji": "🌾",
                "sort_order": 30,
            },
            (("kut", 28, None),),
        ),
        (
            {
                "key": "daily_craft",
                "period": "daily",
                "action": "craft",
                "target": 4,
                "title": "Алхимик дня",
                "description": "Успешно скрафтите 4 предмета за день.",
                "emoji": "⚗️",
                "sort_order": 35,
            },
            (("kut", 24, None),),
        ),
        (
            {
                "key": "weekly_harvest",
                "period": "weekly",
                "action": "harvest",
                "target": 90,
                "title": "Марафон урожая",
                "description": "Соберите урожай с 90 грядок за неделю. Стабильная работа каждый день.",
                "emoji": "🏆",
                "sort_order": 40,
            },
            (("kut", 120, None),),
        ),
        (
            {
                "key": "weekly_water",
                "period": "weekly",
                "action": "water",
                "target": 75,
                "title": "Водная неделя",
                "description": "Полейте грядки 75 раз за неделю.",
                "emoji": "🚿",
                "sort_order": 50,
            },
            (("kut", 90, None), ("item", 3, WATER_ITEM_KEY)),
        ),
    )


def _quest_scope(quest_data: dict[str, Any]) -> str:
    return str(quest_data.get("target_scope") or "any")


async def _insert_default_quest_row(
    pool: asyncpg.Pool,
    quest_data: dict[str, Any],
    rewards: tuple[tuple[str, int, str | None], ...],
) -> int:
    quest_id = await pool.fetchval(
        """
        INSERT INTO quests (
            key, period, action, target, title, description, emoji,
            target_scope, enabled, sort_order
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, $9)
        RETURNING id
        """,
        quest_data["key"],
        quest_data["period"],
        quest_data["action"],
        quest_data["target"],
        quest_data["title"],
        quest_data["description"],
        quest_data["emoji"],
        _quest_scope(quest_data),
        quest_data["sort_order"],
    )
    for sort_order, (kind, amount, item_id) in enumerate(rewards):
        await pool.execute(
            """
            INSERT INTO quest_rewards (quest_id, kind, amount, item_id, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            """,
            quest_id,
            kind,
            amount,
            item_id,
            sort_order,
        )
    return int(quest_id)


async def _fetch_quests(pool: asyncpg.Pool) -> tuple[QuestDef, ...]:
    rows = await pool.fetch(
        """
        SELECT id, key, period, action, target, title, description, emoji,
               target_scope, target_crop_key, target_item_id, enabled, sort_order,
               active_from, active_until, recurrence, recurrence_end
        FROM quests
        ORDER BY sort_order, id
        """
    )
    if not rows:
        return ()

    quest_ids = [int(row["id"]) for row in rows]
    reward_rows = await pool.fetch(
        """
        SELECT quest_id, kind, amount, item_id, sort_order
        FROM quest_rewards
        WHERE quest_id = ANY($1::int[])
        ORDER BY quest_id, sort_order, id
        """,
        quest_ids,
    )
    rewards_by_quest: dict[int, list[QuestRewardDef]] = {quest_id: [] for quest_id in quest_ids}
    for reward in reward_rows:
        rewards_by_quest[int(reward["quest_id"])].append(
            QuestRewardDef(
                kind=str(reward["kind"]),
                amount=int(reward["amount"]),
                item_id=str(reward["item_id"]) if reward["item_id"] else None,
            )
        )

    quests: list[QuestDef] = []
    for row in rows:
        quest_id = int(row["id"])
        quests.append(
            QuestDef(
                db_id=quest_id,
                key=str(row["key"]),
                period=str(row["period"]),
                action=str(row["action"]),
                target=int(row["target"]),
                title=str(row["title"]),
                description=str(row["description"] or ""),
                emoji=str(row["emoji"] or "📋"),
                rewards=tuple(rewards_by_quest.get(quest_id, [])),
                target_scope=str(row["target_scope"] or "any"),
                target_crop_key=str(row["target_crop_key"]) if row["target_crop_key"] else None,
                target_item_id=str(row["target_item_id"]) if row["target_item_id"] else None,
                enabled=bool(row["enabled"]),
                sort_order=int(row["sort_order"] or 0),
                active_from=row["active_from"],
                active_until=row["active_until"],
                recurrence=str(row["recurrence"]) if row["recurrence"] else None,
                recurrence_end=row["recurrence_end"],
            )
        )
    return tuple(quests)


def _rebuild_indexes() -> None:
    global _quest_by_key
    _quest_by_key = {quest.key: quest for quest in _quests}


async def load_quest_registry(pool: asyncpg.Pool) -> None:
    global _registry_loaded, _quests
    _quests = await _fetch_quests(pool)
    _rebuild_indexes()
    _registry_loaded = True


async def reload_quest_registry(pool: asyncpg.Pool) -> None:
    await load_quest_registry(pool)


async def seed_default_quests(pool: asyncpg.Pool) -> None:
    count = int(await pool.fetchval("SELECT COUNT(*)::int FROM quests") or 0)
    if count > 0:
        await ensure_default_quest_pool(pool)
        await sync_default_quest_balance(pool)
        return

    for quest_data, rewards in _default_quest_rows():
        await _insert_default_quest_row(pool, quest_data, rewards)


async def ensure_default_quest_pool(pool: asyncpg.Pool) -> int:
    """Добавляет недостающие шаблоны из _default_quest_rows (для существующих БД)."""
    added = 0
    for quest_data, rewards in _default_quest_rows():
        exists = await pool.fetchval(
            "SELECT 1 FROM quests WHERE key = $1",
            quest_data["key"],
        )
        if exists:
            continue
        await _insert_default_quest_row(pool, quest_data, rewards)
        added += 1
    return added


async def sync_default_quest_balance(pool: asyncpg.Pool) -> int:
    """Обновляет цели и тексты штатных заданий по ключу (без трогания кастомных)."""
    updated = 0
    for quest_data, _rewards in _default_quest_rows():
        status = await pool.execute(
            """
            UPDATE quests SET
                period = $2,
                action = $3,
                target = $4,
                title = $5,
                description = $6,
                emoji = $7,
                target_scope = $8,
                sort_order = $9
            WHERE key = $1
            """,
            quest_data["key"],
            quest_data["period"],
            quest_data["action"],
            quest_data["target"],
            quest_data["title"],
            quest_data["description"],
            quest_data["emoji"],
            _quest_scope(quest_data),
            quest_data["sort_order"],
        )
        if status.endswith("1"):
            updated += 1
    return updated


def all_quests() -> tuple[QuestDef, ...]:
    return _quests


def enabled_quests() -> tuple[QuestDef, ...]:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    result = []
    for quest in _quests:
        if not quest.enabled:
            continue
        if quest.active_from is not None and now < quest.active_from:
            continue
        if quest.active_until is not None and now > quest.active_until:
            continue
        result.append(quest)
    return tuple(result)


def quest_by_key(key: str) -> QuestDef | None:
    return _quest_by_key.get(str(key).strip())


def get_quest_by_id(db_id: int) -> QuestDef | None:
    for quest in _quests:
        if quest.db_id == int(db_id):
            return quest
    return None


def quests_for_period(period: str) -> list[QuestDef]:
    return [quest for quest in enabled_quests() if quest.period == period]


def quest_to_admin_dict(quest: QuestDef) -> dict:
    rewards = []
    for reward in quest.rewards:
        row = {
            "kind": reward.kind,
            "amount": reward.amount,
            "itemId": reward.item_id,
            "label": "",
        }
        if reward.kind == "kut":
            row["label"] = f"+{reward.amount} КУТ"
        elif reward.item_id:
            entry = dex_catalog.get(reward.item_id)
            emoji = entry.emoji if entry else "📦"
            name = entry.name if entry else reward.item_id
            row["label"] = f"+{reward.amount} {emoji} {name}".strip()
            row["itemName"] = name
            row["itemEmoji"] = emoji
        rewards.append(row)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    is_timed = quest.active_from is not None or quest.active_until is not None
    if is_timed:
        if quest.active_from and now < quest.active_from:
            sched_status = "pending"
        elif quest.active_until and now > quest.active_until:
            sched_status = "ended"
        else:
            sched_status = "active"
    else:
        sched_status = None

    return {
        "id": quest.db_id,
        "key": quest.key,
        "period": quest.period,
        "periodLabel": PERIOD_LABELS.get(quest.period, quest.period),
        "action": quest.action,
        "actionLabel": ACTION_LABELS.get(quest.action, quest.action),
        "target": quest.target,
        "title": quest.title,
        "description": quest.description,
        "emoji": quest.emoji,
        "enabled": quest.enabled,
        "sortOrder": quest.sort_order,
        "targetScope": quest.target_scope,
        "targetScopeLabel": SCOPE_LABELS.get(quest.target_scope, quest.target_scope),
        "targetCropKey": quest.target_crop_key,
        "targetItemId": quest.target_item_id,
        "targetHint": quest_target_hint(quest),
        "rewards": rewards,
        "activeFrom": quest.active_from.isoformat() if quest.active_from else None,
        "activeUntil": quest.active_until.isoformat() if quest.active_until else None,
        "recurrence": quest.recurrence,
        "recurrenceEnd": quest.recurrence_end.isoformat() if quest.recurrence_end else None,
        "schedStatus": sched_status,
        "isTimed": is_timed,
    }


def quest_admin_meta() -> dict:
    from content_registry import enabled_crops

    crops = []
    for crop in enabled_crops():
        crops.append({
            "key": crop.key,
            "label": crop.display_name,
            "seedId": crop.seed_id,
            "harvestId": crop.harvest_id,
        })

    return {
        "periods": [{"id": key, "label": PERIOD_LABELS[key]} for key in ("hourly", "daily", "weekly")],
        "actions": [{"id": key, "label": ACTION_LABELS[key]} for key in sorted(VALID_ACTIONS)],
        "scopes": [{"id": key, "label": SCOPE_LABELS[key]} for key in ("any", "item", "crop", "random")],
        "scopeLabels": SCOPE_LABELS,
        "actionScopeHints": ACTION_SCOPE_HINTS,
        "crops": crops,
    }
