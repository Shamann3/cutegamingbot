"""Прогресс заданий: периоды, ротация, награды."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from config import ANALYTICS_TZ
from quest_registry import (
    QuestDef,
    enabled_quests,
    quest_by_key,
    quest_matches_items,
    quest_target_hint,
    resolve_random_filter,
)
from quest_rotation import (
    PERIOD_ACCEPT_LIMIT,
    PERIOD_SLOT_LIMITS,
    event_quests,
    is_event_quest,
    quest_in_current_rotation,
    visible_quest_keys_for_period,
)
from seed_economy import local_today
from dex_catalog import merge_items_for_storage, normalize_items
from user_items import add_item

PERIODS = ("hourly", "daily", "weekly")


def _analytics_tz():
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(ANALYTICS_TZ)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _now() -> datetime:
    return datetime.now(_analytics_tz())


def period_key(period: str, *, today: date | None = None) -> str:
    now = _now()
    if period == "hourly":
        return now.strftime("%Y-%m-%dT%H")
    if period == "weekly":
        ref = today or local_today()
        iso = ref.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    ref = today or local_today()
    return ref.isoformat()


def period_ends_at(period: str, *, today: date | None = None) -> datetime:
    tz = _analytics_tz()
    now = _now()
    if period == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if period == "daily":
        ref = today or local_today()
        return datetime(ref.year, ref.month, ref.day, tzinfo=tz) + timedelta(days=1)
    ref = today or local_today()
    weekday = ref.isoweekday()
    days_until_monday = (8 - weekday) % 7 or 7
    next_monday = ref + timedelta(days=days_until_monday)
    return datetime(next_monday.year, next_monday.month, next_monday.day, tzinfo=tz)


def _period_timer(period: str) -> tuple[int | None, int | None]:
    ends = period_ends_at(period)
    remaining = max(0, int((ends - _now()).total_seconds()))
    return int(ends.timestamp() * 1000), remaining


def _empty_bucket() -> dict[str, Any]:
    return {
        "periodKey": "",
        "progress": {},
        "claimed": [],
        "activeQuests": [],
    }


def empty_progress_store() -> dict[str, dict[str, Any]]:
    return {period: _empty_bucket() for period in PERIODS}


def _normalize_active_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    quest_id = str(raw.get("questId") or raw.get("quest_id") or "").strip()
    if not quest_id:
        return None
    filt = raw.get("activeFilter")
    return {
        "questId": quest_id,
        "acceptedAt": str(raw["acceptedAt"]) if raw.get("acceptedAt") else None,
        "activeFilter": dict(filt) if isinstance(filt, dict) else None,
    }


def _get_active_quests(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    raw_list = bucket.get("activeQuests")
    if isinstance(raw_list, list) and raw_list:
        entries = [_normalize_active_entry(item) for item in raw_list]
        return [e for e in entries if e is not None]

    legacy_id = bucket.get("acceptedQuestId")
    if legacy_id:
        return [
            {
                "questId": str(legacy_id),
                "acceptedAt": str(bucket["acceptedAt"]) if bucket.get("acceptedAt") else None,
                "activeFilter": dict(bucket["activeFilter"])
                if isinstance(bucket.get("activeFilter"), dict)
                else None,
            }
        ]
    return []


def _set_active_quests(bucket: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    bucket["activeQuests"] = entries
    bucket.pop("acceptedQuestId", None)
    bucket.pop("acceptedAt", None)
    bucket.pop("activeFilter", None)


def _is_quest_active(bucket: dict[str, Any], quest_id: str) -> bool:
    return any(e["questId"] == quest_id for e in _get_active_quests(bucket))


def _active_filter_for(bucket: dict[str, Any], quest_id: str) -> dict | None:
    for entry in _get_active_quests(bucket):
        if entry["questId"] == quest_id:
            return entry.get("activeFilter")
    return None


def _active_count(bucket: dict[str, Any]) -> int:
    return len(_get_active_quests(bucket))


def _accepted_at_ms_for(bucket: dict[str, Any], quest_id: str) -> int | None:
    for entry in _get_active_quests(bucket):
        if entry["questId"] != quest_id:
            continue
        raw = entry.get("acceptedAt")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_analytics_tz())
            return int(parsed.timestamp() * 1000)
        except (TypeError, ValueError):
            return None
    return None


def _lock_hint_title(bucket: dict[str, Any], limit: int) -> str | None:
    active = _get_active_quests(bucket)
    if not active:
        return None
    if _active_count(bucket) >= limit:
        first = quest_by_key(active[0]["questId"])
        if len(active) == 1 and first:
            return first.title
        return f"занято {_active_count(bucket)}/{limit}"
    return None


def _parse_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    progress = bucket.get("progress")
    claimed = bucket.get("claimed")
    parsed = {
        "periodKey": str(bucket.get("periodKey") or ""),
        "progress": dict(progress) if isinstance(progress, dict) else {},
        "claimed": [str(item) for item in (claimed or [])],
        "activeQuests": [],
    }
    if isinstance(bucket.get("activeQuests"), list):
        for item in bucket["activeQuests"]:
            entry = _normalize_active_entry(item)
            if entry:
                parsed["activeQuests"].append(entry)
    elif bucket.get("acceptedQuestId"):
        parsed["activeQuests"] = _get_active_quests(bucket)
    return parsed


def parse_progress_store(raw: Any) -> dict[str, dict[str, Any]]:
    store = empty_progress_store()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return store
    if not isinstance(raw, dict):
        return store
    for period in PERIODS:
        bucket = raw.get(period)
        if isinstance(bucket, dict):
            store[period] = _parse_bucket(bucket)
    return store


def normalize_progress_store(store: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    today = local_today()
    normalized = empty_progress_store()
    for period in PERIODS:
        bucket = store.get(period) or _empty_bucket()
        current_key = period_key(period, today=today)
        if bucket.get("periodKey") != current_key:
            normalized[period] = {
                "periodKey": current_key,
                "progress": {},
                "claimed": [],
                "activeQuests": [],
            }
            continue

        progress_dict = {
            str(key): max(0, int(value or 0))
            for key, value in (bucket.get("progress") or {}).items()
        }
        claimed_list = [str(item) for item in (bucket.get("claimed") or [])]
        active_quests = _get_active_quests(bucket)
        accept_limit = PERIOD_ACCEPT_LIMIT.get(period, 1)
        if len(active_quests) > accept_limit:
            active_quests = active_quests[:accept_limit]

        normalized[period] = {
            "periodKey": current_key,
            "progress": progress_dict,
            "claimed": claimed_list,
            "activeQuests": active_quests,
        }
    return normalized


def progress_store_to_db(store: dict[str, dict[str, Any]]) -> dict:
    return {
        period: {
            "periodKey": store[period]["periodKey"],
            "progress": store[period]["progress"],
            "claimed": store[period]["claimed"],
            "activeQuests": store[period]["activeQuests"],
        }
        for period in PERIODS
    }


def _quest_progress_value(
    quest: QuestDef,
    bucket: dict[str, Any],
    *,
    daily_seed_claimed_on: date | None,
) -> int:
    if quest.action == "claim_daily_seed":
        return 1 if daily_seed_claimed_on == local_today() else 0
    return int(bucket.get("progress", {}).get(quest.id, 0) or 0)


def _quests_to_render(store: dict[str, dict[str, Any]]) -> list[QuestDef]:
    today = local_today()
    visible_keys: set[str] = set()
    for period in PERIODS:
        pk = period_key(period, today=today)
        visible_keys.update(visible_quest_keys_for_period(period, pk))
    for quest in event_quests():
        visible_keys.add(quest.key)

    quests = [q for q in enabled_quests() if q.key in visible_keys]
    return sorted(quests, key=lambda item: (item.period, item.sort_order, item.key))


def build_quests_state(
    raw_store: Any,
    *,
    daily_seed_claimed_on: date | None,
) -> dict:
    store = normalize_progress_store(parse_progress_store(raw_store))
    sections: dict[str, list[dict]] = {
        "hourly": [],
        "daily": [],
        "weekly": [],
        "events": [],
    }
    ready_count = 0
    period_timers: dict[str, dict[str, int | None]] = {}
    today = local_today()

    for period in PERIODS:
        ends_ms, remaining = _period_timer(period)
        period_timers[period] = {
            "periodEndsAt": ends_ms,
            "timerRemainingSec": remaining,
        }

    for quest in _quests_to_render(store):
        bucket = store[quest.period]
        section_key = "events" if is_event_quest(quest) else quest.period
        limit = PERIOD_ACCEPT_LIMIT.get(quest.period, 1)
        active_count = _active_count(bucket)
        is_passive_daily = quest.action == "claim_daily_seed"
        is_accepted = _is_quest_active(bucket, quest.id)
        active_filter = _active_filter_for(bucket, quest.id) if is_accepted else None
        target_hint = quest_target_hint(quest, active_filter)
        period_ends_ms, period_remaining = _period_timer(quest.period)

        if is_passive_daily:
            progress = _quest_progress_value(quest, bucket, daily_seed_claimed_on=daily_seed_claimed_on)
            claimed = progress >= quest.target
            ready = not claimed
            accepted = False
            locked = False
            can_accept = False
            can_cancel = False
            active_title = None
            accepted_at_ms = None
            quest_ends_ms = None
            quest_remaining = None
        else:
            claimed = quest.id in bucket.get("claimed", [])
            slots_full = active_count >= limit and not is_accepted
            is_locked = slots_full
            can_accept = (
                not claimed
                and not is_accepted
                and not slots_full
                and quest_in_current_rotation(quest, bucket["periodKey"])
            )
            can_cancel = is_accepted and not claimed
            progress = (
                _quest_progress_value(quest, bucket, daily_seed_claimed_on=daily_seed_claimed_on)
                if is_accepted
                else 0
            )
            ready = is_accepted and progress >= quest.target
            accepted = is_accepted
            locked = is_locked
            active_title = _lock_hint_title(bucket, limit) if is_locked else None
            accepted_at_ms = _accepted_at_ms_for(bucket, quest.id) if is_accepted else None
            quest_ends_ms = period_ends_ms if is_accepted else None
            quest_remaining = period_remaining if is_accepted else None

        if ready and not claimed and (is_passive_daily or accepted):
            ready_count += 1

        sections[section_key].append(
            quest.for_client(
                progress=progress,
                claimed=claimed,
                ready=ready,
                accepted=accepted,
                locked=locked,
                can_accept=can_accept,
                can_cancel=can_cancel,
                active_quest_title=active_title,
                target_hint=target_hint,
                period_ends_at_ms=quest_ends_ms,
                timer_remaining_sec=quest_remaining,
                accepted_at_ms=accepted_at_ms,
            ),
        )

    return {
        "sections": sections,
        "readyCount": ready_count,
        "npcName": "Задания",
        "npcEmoji": "📜",
        "periodLabels": {
            "hourly": "На час",
            "daily": "На день",
            "weekly": "На неделю",
            "events": "Ивенты",
        },
        "periodTimers": period_timers,
        "acceptRules": dict(PERIOD_ACCEPT_LIMIT),
        "slotLimits": dict(PERIOD_SLOT_LIMITS),
    }


def accept_quest(store: dict[str, dict[str, Any]], quest_id: str) -> dict[str, dict[str, Any]]:
    store = normalize_progress_store(store)
    quest = quest_by_key(str(quest_id).strip())
    if not quest:
        raise ValueError("Задание не найдено")
    if quest.action == "claim_daily_seed":
        raise ValueError("Это задание не нужно брать. Просто забери семя")
    if is_event_quest(quest):
        pass  # ивенты вне ротации, но с тем же лимитом периода
    bucket = store[quest.period]
    if quest.id in bucket["claimed"]:
        raise ValueError("Награда по этому заданию уже получена")
    if _is_quest_active(bucket, quest.id):
        return store

    limit = PERIOD_ACCEPT_LIMIT.get(quest.period, 1)
    if _active_count(bucket) >= limit:
        raise ValueError(
            f"На этот период можно взять не больше {limit} заданий. Сначала выполни или отмени активные."
        )
    if not quest_in_current_rotation(quest, bucket["periodKey"]):
        raise ValueError("Это задание сейчас недоступно. Дождись обновления списка")

    active_filter = None
    scope = (quest.target_scope or "any").lower()
    if scope == "random":
        active_filter = resolve_random_filter(quest)
    elif scope == "crop" and not quest.target_crop_key:
        raise ValueError("У задания не указана культура")
    elif scope == "item" and not quest.target_item_id:
        raise ValueError("У задания не указан предмет")

    entries = _get_active_quests(bucket)
    entries.append(
        {
            "questId": quest.id,
            "acceptedAt": _now().isoformat(),
            "activeFilter": active_filter,
        }
    )
    _set_active_quests(bucket, entries)
    bucket["progress"].setdefault(quest.id, 0)
    return store


def cancel_quest(store: dict[str, dict[str, Any]], quest_id: str) -> dict[str, dict[str, Any]]:
    store = normalize_progress_store(store)
    quest = quest_by_key(str(quest_id).strip())
    if not quest:
        raise ValueError("Задание не найдено")
    if quest.action == "claim_daily_seed":
        raise ValueError("Это задание нельзя отменить")
    bucket = store[quest.period]
    if not _is_quest_active(bucket, quest.id):
        raise ValueError("Это задание сейчас не активно")
    if quest.id in bucket["claimed"]:
        raise ValueError("Награда уже получена. Отменить нельзя")

    current_progress = int(bucket["progress"].get(quest.id, 0) or 0)
    if current_progress >= quest.target:
        raise ValueError("Задание уже выполнено — сначала получи награду")

    bucket["progress"].pop(quest.id, None)
    entries = [e for e in _get_active_quests(bucket) if e["questId"] != quest.id]
    _set_active_quests(bucket, entries)
    return store


def bump_progress(
    store: dict[str, dict[str, Any]],
    action: str,
    amount: int = 1,
    *,
    item_ids: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    store = normalize_progress_store(store)
    amount = max(1, int(amount))
    for quest in enabled_quests():
        if quest.action != action or quest.action == "claim_daily_seed":
            continue
        bucket = store[quest.period]
        if quest.id in bucket["claimed"]:
            continue
        for entry in _get_active_quests(bucket):
            if entry["questId"] != quest.id:
                continue
            filt = entry.get("activeFilter")
            if not quest_matches_items(quest, item_ids, active_filter=filt):
                continue
            current = int(bucket["progress"].get(quest.id, 0) or 0)
            bucket["progress"][quest.id] = current + amount
    return store


def mark_quest_claimed(store: dict[str, dict[str, Any]], quest_id: str) -> dict[str, dict[str, Any]]:
    store = normalize_progress_store(store)
    quest = quest_by_key(quest_id)
    if not quest:
        raise ValueError("Задание не найдено")
    bucket = store[quest.period]
    if quest_id in bucket["claimed"]:
        raise ValueError("Награда уже получена")
    if quest.action != "claim_daily_seed":
        if not _is_quest_active(bucket, quest_id):
            raise ValueError("Сначала возьми это задание")
        progress = int(bucket["progress"].get(quest_id, 0) or 0)
        if progress < quest.target:
            raise ValueError("Задание ещё не выполнено")
    bucket["claimed"].append(quest_id)
    entries = [e for e in _get_active_quests(bucket) if e["questId"] != quest_id]
    _set_active_quests(bucket, entries)
    return store


def apply_quest_rewards(raw_items: dict, quest: QuestDef) -> tuple[dict, int]:
    kut_reward = 0
    game_items = normalize_items(raw_items)
    for reward in quest.rewards:
        if reward.kind == "kut":
            kut_reward += max(0, int(reward.amount))
        elif reward.kind == "item" and reward.item_id:
            game_items = add_item(game_items, reward.item_id, max(1, int(reward.amount)))
    stored = merge_items_for_storage(raw_items, game_items)
    return stored, kut_reward


def reward_summary(quest: QuestDef) -> list[dict]:
    from dex_catalog import dex_catalog

    summary = []
    for reward in quest.rewards:
        if reward.kind == "kut":
            summary.append({"kind": "kut", "amount": reward.amount, "label": f"+{reward.amount} КУТ"})
        elif reward.kind == "item" and reward.item_id:
            entry = dex_catalog.get(reward.item_id)
            emoji = entry.emoji if entry else "📦"
            name = entry.name if entry else reward.item_id
            summary.append(
                {
                    "kind": "item",
                    "amount": reward.amount,
                    "itemId": reward.item_id,
                    "label": f"+{reward.amount} {emoji} {name}".strip(),
                }
            )
    return summary
