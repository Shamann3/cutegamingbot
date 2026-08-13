# -*- coding: utf-8 -*-
"""Расчёт следующего soft-restart и нормализация конфига расписания.

Синхрон с bot/funcs/sr_schedule.py — логика должна совпадать.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

MODES = ("interval", "hourly", "times")

DEFAULT_CONDITIONS: Dict[str, Any] = {
    "min_uptime_sec": 120.0,
    "require_supervisor": False,
    "max_restarts_per_day": 48,
    "quiet_start": "",
    "quiet_end": "",
}

DEFAULT_CFG: Dict[str, Any] = {
    "enabled": False,
    "test": False,
    "mode": "interval",
    "interval_sec": 3600.0,
    "initial_delay_sec": 3600.0,
    "grace_sec": 3.0,
    "timezone": "Europe/Moscow",
    "hourly_minute": 0,
    "daily_times": ["03:00"],
    "weekdays": [0, 1, 2, 3, 4, 5, 6],
    "conditions": dict(DEFAULT_CONDITIONS),
    "notify_creator": True,
}


def _tz(name: str):
    key = (name or "Europe/Moscow").strip() or "Europe/Moscow"
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(key)
    except Exception:
        try:
            return ZoneInfo("Europe/Moscow")
        except Exception:
            return None


def _parse_hhmm(value: Any) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or ":" not in s:
        return None
    try:
        hh_s, mm_s = s.split(":", 1)
        hh, mm = int(hh_s), int(mm_s)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
    except Exception:
        return None
    return None


def _norm_times(raw: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    if isinstance(raw, str):
        items: Sequence[Any] = [p.strip() for p in raw.split(",") if p.strip()]
    elif isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = DEFAULT_CFG["daily_times"]
    for it in items:
        parsed = _parse_hhmm(it)
        if not parsed:
            continue
        label = f"{parsed[0]:02d}:{parsed[1]:02d}"
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
    out.sort()
    return out or ["03:00"]


def _norm_weekdays(raw: Any) -> List[int]:
    if not isinstance(raw, (list, tuple)) or not raw:
        return list(range(7))
    out = []
    for x in raw:
        try:
            d = int(x)
        except Exception:
            continue
        if 0 <= d <= 6 and d not in out:
            out.append(d)
    return sorted(out) or list(range(7))


def _norm_conditions(raw: Any) -> Dict[str, Any]:
    base = dict(DEFAULT_CONDITIONS)
    if isinstance(raw, dict):
        for k in base:
            if k in raw:
                base[k] = raw[k]
    base["min_uptime_sec"] = max(0.0, float(base["min_uptime_sec"] or 0))
    base["require_supervisor"] = bool(base["require_supervisor"])
    base["max_restarts_per_day"] = max(1, int(base["max_restarts_per_day"] or 1))
    qs = _parse_hhmm(base.get("quiet_start"))
    qe = _parse_hhmm(base.get("quiet_end"))
    base["quiet_start"] = f"{qs[0]:02d}:{qs[1]:02d}" if qs else ""
    base["quiet_end"] = f"{qe[0]:02d}:{qe[1]:02d}" if qe else ""
    return base


def normalize_config(raw: Optional[Dict[str, Any]], *, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = dict(defaults or DEFAULT_CFG)
    if isinstance(raw, dict):
        for k in list(base.keys()):
            if k in raw:
                base[k] = raw[k]
    base["enabled"] = bool(base["enabled"])
    base["test"] = bool(base["test"])
    mode = str(base.get("mode") or "interval").strip().lower()
    if mode not in MODES:
        mode = "interval"
    base["mode"] = mode
    base["interval_sec"] = max(60.0, float(base["interval_sec"]))
    base["initial_delay_sec"] = max(30.0, float(base["initial_delay_sec"]))
    base["grace_sec"] = max(0.5, float(base["grace_sec"]))
    base["timezone"] = str(base.get("timezone") or "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        hm = int(base.get("hourly_minute") or 0)
    except Exception:
        hm = 0
    base["hourly_minute"] = max(0, min(59, hm))
    base["daily_times"] = _norm_times(base.get("daily_times"))
    base["weekdays"] = _norm_weekdays(base.get("weekdays"))
    base["conditions"] = _norm_conditions(base.get("conditions"))
    base["notify_creator"] = bool(base.get("notify_creator", True))
    return base


def _now_tz(tz_name: str) -> datetime:
    tz = _tz(tz_name)
    if tz is None:
        return datetime.now().astimezone()
    return datetime.now(tz)


def _in_quiet_window(now: datetime, cond: Dict[str, Any]) -> bool:
    qs = _parse_hhmm(cond.get("quiet_start"))
    qe = _parse_hhmm(cond.get("quiet_end"))
    if not qs or not qe:
        return False
    cur = now.hour * 60 + now.minute
    a = qs[0] * 60 + qs[1]
    b = qe[0] * 60 + qe[1]
    if a == b:
        return False
    if a < b:
        return a <= cur < b
    return cur >= a or cur < b


def conditions_block_reason(
    cfg: Dict[str, Any],
    *,
    uptime_sec: float,
    supervisor: bool,
    restarts_today: int,
    now: Optional[datetime] = None,
) -> Optional[str]:
    c = _norm_conditions(cfg.get("conditions"))
    if uptime_sec < float(c["min_uptime_sec"]):
        return f"min_uptime ({uptime_sec:.0f}s < {c['min_uptime_sec']:.0f}s)"
    if c["require_supervisor"] and not supervisor:
        return "require_supervisor"
    if restarts_today >= int(c["max_restarts_per_day"]):
        return f"max_restarts_per_day ({restarts_today}/{c['max_restarts_per_day']})"
    n = now or _now_tz(str(cfg.get("timezone") or "Europe/Moscow"))
    if _in_quiet_window(n, c):
        return "quiet_hours"
    return None


def compute_next_at(
    cfg: Dict[str, Any],
    *,
    now_ts: Optional[float] = None,
    started_at: float,
    first_cycle: bool = True,
) -> Optional[float]:
    import time as _time

    cfg = normalize_config(cfg)
    if not cfg["enabled"]:
        return None
    now = float(now_ts if now_ts is not None else _time.time())
    earliest = started_at + float(cfg["initial_delay_sec"])
    mode = cfg["mode"]
    if mode == "interval":
        if first_cycle or now < earliest:
            return max(now, earliest)
        return now + float(cfg["interval_sec"])
    anchor = max(now, earliest)
    tz = _tz(cfg["timezone"])
    if tz is None:
        local = datetime.fromtimestamp(anchor).astimezone()
    else:
        local = datetime.fromtimestamp(anchor, tz)
    if mode == "hourly":
        minute = int(cfg["hourly_minute"])
        cand = local.replace(minute=minute, second=0, microsecond=0)
        if cand <= local:
            cand = cand + timedelta(hours=1)
            cand = cand.replace(minute=minute, second=0, microsecond=0)
        return cand.timestamp()
    times = [t for t in (_parse_hhmm(x) for x in cfg["daily_times"]) if t]
    weekdays = set(cfg["weekdays"])
    if not times:
        times = [(3, 0)]
    for day_offset in range(0, 8):
        day = (local + timedelta(days=day_offset)).date()
        if day.weekday() not in weekdays:
            continue
        for hh, mm in times:
            cand = datetime(day.year, day.month, day.day, hh, mm, 0, 0, tzinfo=local.tzinfo)
            if cand.timestamp() > anchor:
                return cand.timestamp()
    hh, mm = times[0]
    day = (local + timedelta(days=1)).date()
    cand = datetime(day.year, day.month, day.day, hh, mm, 0, 0, tzinfo=local.tzinfo)
    return cand.timestamp()


def preview_next_runs(
    cfg: Dict[str, Any],
    *,
    started_at: float,
    count: int = 8,
    now_ts: Optional[float] = None,
) -> List[Dict[str, Any]]:
    import time as _time

    cfg = normalize_config(cfg)
    if not cfg["enabled"]:
        return []
    now = float(now_ts if now_ts is not None else _time.time())
    out: List[Dict[str, Any]] = []
    cursor_started = started_at
    first = True
    t = now
    for _ in range(max(1, min(24, count))):
        nxt = compute_next_at(cfg, now_ts=t, started_at=cursor_started, first_cycle=first)
        if nxt is None:
            break
        if out and nxt <= out[-1]["at"]:
            t = nxt + 1.0
            first = False
            nxt = compute_next_at(cfg, now_ts=t, started_at=cursor_started, first_cycle=False)
            if nxt is None:
                break
        tz = _tz(cfg["timezone"])
        dt = datetime.fromtimestamp(nxt, tz) if tz else datetime.fromtimestamp(nxt).astimezone()
        out.append(
            {
                "at": nxt,
                "iso": dt.isoformat(timespec="seconds"),
                "label": dt.strftime("%d.%m %H:%M"),
                "in_sec": max(0.0, nxt - now),
            }
        )
        t = nxt + 1.0
        first = False
        if cfg["mode"] == "interval":
            cursor_started = nxt
            first = True
            t = nxt + 0.01
    return out


def mode_label(mode: str) -> str:
    return {
        "interval": "Каждые N секунд",
        "hourly": "Каждый час",
        "times": "В выбранное время",
    }.get(mode, mode)
