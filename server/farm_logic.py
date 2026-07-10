from datetime import datetime, timedelta, timezone

from farm_crops import grow_seconds_for_crop


def now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _water_events_for_grow(grow_sec: int) -> int:
    from farm_settings import get_water_interval_seconds

    interval = max(1, int(get_water_interval_seconds()))
    if grow_sec <= interval:
        return 0
    return max(0, (int(grow_sec) - 1) // interval)


def _fix_grow_timers(row: dict, current: datetime | None = None) -> bool:
    """Привести длительность роста к значению культуры на грядке."""
    planted_at = _as_utc(row.get("planted_at"))
    ripe_at = _as_utc(row.get("ripe_at"))
    if not planted_at or not ripe_at:
        return False

    expected = grow_seconds_for_crop(row.get("crop_id"))
    duration = (ripe_at - planted_at).total_seconds()
    if abs(duration - expected) <= 30:
        return False

    row["planted_at"] = planted_at
    row["ripe_at"] = planted_at + timedelta(seconds=expected)

    if current is not None and not row.get("autowater_active"):
        row["waters_remaining"] = _water_events_for_grow(expected)
        _schedule_next_dry(row, current)

    return True


def _schedule_next_dry(row: dict, current: datetime) -> None:
    from farm_settings import get_water_interval_seconds

    if row.get("autowater_active"):
        row["dry_at"] = None
        return

    remaining = int(row.get("waters_remaining") or 0)
    ripe_at = _as_utc(row.get("ripe_at"))
    current = _as_utc(current) or now()
    if remaining <= 0 or not ripe_at or current >= ripe_at:
        row["dry_at"] = None
        return

    next_dry = current + timedelta(seconds=get_water_interval_seconds())
    if next_dry >= ripe_at:
        row["dry_at"] = None
        return
    row["dry_at"] = next_dry


def sync_growing_plot(row: dict, current: datetime) -> dict:
    if row["status"] != "GROWING":
        return row

    current = _as_utc(current) or now()
    _fix_grow_timers(row, current)

    ripe_at = _as_utc(row.get("ripe_at"))
    dry_at = _as_utc(row.get("dry_at"))
    wilt_at = _as_utc(row.get("wilt_at"))
    needs_water = row.get("needs_water", False)
    waters_left = int(row.get("waters_remaining") or 0)

    if ripe_at and current >= ripe_at:
        row["status"] = "READY"
        row["needs_water"] = False
        row["wilt_at"] = None
        row["dry_at"] = None
        return row

    if row.get("autowater_active"):
        row["needs_water"] = False
        row["wilt_at"] = None
        row["dry_at"] = None
        return row

    if wilt_at and current >= wilt_at:
        row["status"] = "WITHERED"
        return row

    if (
        waters_left > 0
        and dry_at
        and current >= dry_at
        and not needs_water
    ):
        row["needs_water"] = True
        if not row.get("wilt_at"):
            from farm_settings import get_wilt_grace_seconds

            row["wilt_at"] = current + timedelta(seconds=get_wilt_grace_seconds())

    return row


def is_dry(row: dict, current: datetime) -> bool:
    if row["status"] != "GROWING":
        return False
    if row.get("autowater_active"):
        return False
    if row.get("needs_water"):
        return True
    dry_at = _as_utc(row.get("dry_at"))
    waters_left = int(row.get("waters_remaining") or 0)
    current = _as_utc(current) or now()
    if waters_left <= 0:
        return False
    return dry_at is not None and current >= dry_at


def plot_to_json(row: dict) -> dict:
    from content_registry import get_crop_for_plot

    result = {"id": row["plot_id"], "status": row["status"]}
    crop_id = row.get("crop_id")
    if crop_id:
        result["cropId"] = str(crop_id)
        crop = get_crop_for_plot(str(crop_id))
        if crop:
            result["cropKey"] = crop.key
            result["cropLabel"] = crop.display_name
    planted_at = _as_utc(row.get("planted_at"))
    ripe_at = _as_utc(row.get("ripe_at"))
    dry_at = _as_utc(row.get("dry_at"))
    wilt_at = _as_utc(row.get("wilt_at"))
    if planted_at:
        result["plantedAt"] = planted_at.isoformat()
    if ripe_at:
        result["ripeAt"] = ripe_at.isoformat()
    if dry_at:
        result["dryAt"] = dry_at.isoformat()
    result["needsWater"] = bool(row.get("needs_water"))
    result["wiltAt"] = wilt_at.isoformat() if wilt_at else None
    result["watersRemaining"] = int(row.get("waters_remaining") or 0)
    if row.get("autowater_active"):
        result["autowaterActive"] = True
    return result


def apply_plant(row: dict, current: datetime, crop_id: str | None = None) -> dict:
    current = _as_utc(current) or now()
    grow_sec = grow_seconds_for_crop(crop_id)
    row["status"] = "GROWING"
    row["planted_at"] = current
    row["ripe_at"] = current + timedelta(seconds=grow_sec)
    row["waters_remaining"] = _water_events_for_grow(grow_sec)
    row["needs_water"] = False
    row["wilt_at"] = None
    row["autowater_active"] = False
    row["crop_id"] = crop_id
    _schedule_next_dry(row, current)
    return row


def apply_water(row: dict, current: datetime) -> dict:
    current = _as_utc(current) or now()
    row["needs_water"] = False
    row["wilt_at"] = None
    remaining = int(row.get("waters_remaining") or 0)
    if remaining > 0:
        row["waters_remaining"] = remaining - 1
    _schedule_next_dry(row, current)
    return row


def apply_autowater(row: dict, current: datetime) -> dict:
    current = _as_utc(current) or now()
    row["autowater_active"] = True
    row["needs_water"] = False
    row["wilt_at"] = None
    row["dry_at"] = None
    row["waters_remaining"] = 0
    return row


def apply_harvest(row: dict) -> dict:
    row["status"] = "EMPTY"
    row["planted_at"] = None
    row["ripe_at"] = None
    row["dry_at"] = None
    row["needs_water"] = False
    row["wilt_at"] = None
    row["waters_remaining"] = 0
    row["crop_id"] = None
    row["autowater_active"] = False
    return row


def normalize_grow_row(row: dict, current: datetime | None = None) -> bool:
    """Публичная нормализация таймера — для миграции при старте сервера."""
    if row.get("status") != "GROWING":
        return False
    return _fix_grow_timers(row, current or now())
