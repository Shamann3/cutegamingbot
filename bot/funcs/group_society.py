# -*- coding: utf-8 -*-
"""Умная «сила группы»: актив + донатеры → бонус к лимиту ставок и цене уровня.

Принципы:
- размер группы берём из таблицы chat.member;
- окно анализа — 30 дней;
- пороги и веса самонастраиваются по распределению внутри конкретной группы
  (без жёстких «магических» констант в духе «всем нужно ровно 10 сообщений»);
- донатер оценивается смесью: 60% сумма за всё время + 40% сумма за месяц
  (lifetime из users.donate, месяц из журнала public.donate);
- выводы сохраняются в шардированное надёжное хранилище + LRU в памяти
  (расчёт по требованию, не на все группы сразу → масштаб ~1M чатов);
- peak_* не падает: нельзя «обнулить» дороговизну после накачки общества;
- 1 донатер почти не даёт бонуса; толпа сильных донатеров — да;
- цены уровня растут от силы общества (донаты сильнее актива) + защита от
  соло-скупки всех уровней одним человеком в пустой группе.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _ROOT / "data" / "group_balance_level"
_SNAP_ROOT = _DATA_DIR / "society_snapshots"
_LOCK = threading.RLock()

# Память: горячие чаты (не грузим миллион файлов сразу)
_LRU_MAX = 8192
_lru: "OrderedDict[int, Dict[str, Any]]" = OrderedDict()

# Шардов на диске — равномерное распределение chat_id
_SHARDS = 1024

# Версия схемы снимка (инвалидация при смене логики)
_SCHEMA = 5

# Веса донатера (defaults; админка может переписать через settings)
DONOR_LIFE_WEIGHT = 0.6
DONOR_MONTH_WEIGHT = 0.4
DONOR_MONTH_DAYS = 30


def _donor_weights_from_cfg(cfg: Optional[Dict[str, Any]] = None) -> Tuple[float, float]:
    life = max(0.0, _as_float(_cfg_get(cfg, "donor_life_weight", DONOR_LIFE_WEIGHT), DONOR_LIFE_WEIGHT))
    month = max(0.0, _as_float(_cfg_get(cfg, "donor_month_weight", DONOR_MONTH_WEIGHT), DONOR_MONTH_WEIGHT))
    s = life + month
    if s <= 0:
        return DONOR_LIFE_WEIGHT, DONOR_MONTH_WEIGHT
    return life / s, month / s

# Singleflight: один пересчёт на chat_id, остальные ждут тот же Future
_inflight: Dict[int, "asyncio.Future[Dict[str, Any]]"] = {}
_inflight_guard = threading.Lock()
# Фоновый soft-refresh (stale-while-revalidate)
_bg_refresh: Dict[int, asyncio.Task] = {}


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _cfg_get(cfg: Optional[Dict[str, Any]], key: str, default: Any) -> Any:
    if not cfg:
        return default
    return cfg.get(key, default)


def society_ttl_sec(cfg: Optional[Dict[str, Any]] = None) -> float:
    return max(60.0, _as_float(_cfg_get(cfg, "society_snapshot_ttl_sec", 1800), 1800.0))


def _shard_dir(chat_id: int) -> Path:
    shard = abs(int(chat_id)) % _SHARDS
    return _SNAP_ROOT / f"{shard:04d}"


def _snap_path(chat_id: int) -> Path:
    return _shard_dir(chat_id) / f"{int(chat_id)}.json"


def peek_society_snapshot(chat_id: int) -> Optional[Dict[str, Any]]:
    """Быстрый sync-peek: память → диск. Без пересчёта."""
    cid = int(chat_id)
    with _LOCK:
        hit = _lru.get(cid)
        if hit is not None:
            _lru.move_to_end(cid)
            # shallow copy верхнего уровня — достаточно для чтения pct/price
            return dict(hit)
    path = _snap_path(cid)
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return None
        with _LOCK:
            _lru[cid] = raw
            _lru.move_to_end(cid)
            while len(_lru) > _LRU_MAX:
                _lru.popitem(last=False)
        return dict(raw)
    except Exception as e:
        print(f"[SOCIETY] peek fail chat={cid}: {e!r}")
        return None


def _write_snap_file(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except Exception as e:
        print(f"[SOCIETY] save fail path={path}: {e!r}")


def save_society_snapshot(chat_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Пишет в LRU сразу; диск — в фоне (не тормозит ответ «бч»)."""
    cid = int(chat_id)
    payload = dict(data or {})
    payload["chat_id"] = cid
    payload["schema"] = _SCHEMA
    payload["saved_at"] = time.time()
    path = _snap_path(cid)
    with _LOCK:
        _lru[cid] = payload
        _lru.move_to_end(cid)
        while len(_lru) > _LRU_MAX:
            _lru.popitem(last=False)
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _write_snap_file, path, dict(payload))
    except RuntimeError:
        _write_snap_file(path, payload)
    return dict(payload)


def snapshot_is_fresh(snap: Optional[Dict[str, Any]], cfg: Optional[Dict[str, Any]] = None) -> bool:
    if not snap or not isinstance(snap, dict):
        return False
    if _as_int(snap.get("schema"), 0) != _SCHEMA:
        return False
    age = time.time() - _as_float(snap.get("computed_at"), 0.0)
    return age >= 0 and age < society_ttl_sec(cfg)


def snapshot_is_usable_stale(
    snap: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
) -> bool:
    """Просроченный, но ещё годный для мгновенного ответа (SWR)."""
    if not snap or not isinstance(snap, dict):
        return False
    if _as_int(snap.get("schema"), 0) != _SCHEMA:
        return False
    ttl = society_ttl_sec(cfg)
    age = time.time() - _as_float(snap.get("computed_at"), 0.0)
    # до 4× TTL отдаём старое мгновенно и обновляем в фоне
    return age >= 0 and age < (ttl * 4.0)

def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    p = max(0.0, min(1.0, float(p)))
    idx = p * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    w = idx - lo
    return float(sorted_vals[lo]) * (1.0 - w) + float(sorted_vals[hi]) * w


def _soft_count(n: int, *, half_at: float) -> float:
    """1 ≈ мало; дальше насыщение. half_at подстраивается под группу."""
    n = max(0, int(n or 0))
    if n <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - math.exp(-float(n) / max(0.75, float(half_at)))))


def compute_activity_adaptive(
    *,
    member_count: int,
    user_messages: List[Tuple[int, int]],
) -> Dict[str, Any]:
    """Актив 0…1: порог сообщений = из распределения этой группы."""
    members = max(0, int(member_count or 0))
    pairs = [(int(u), int(m)) for u, m in (user_messages or []) if int(m) > 0]
    writers = len(pairs)
    if members <= 0:
        members = max(writers, 1)
    if not pairs:
        return {
            "score": 0.0,
            "members": members,
            "writers": 0,
            "qualified": 0,
            "msg_threshold": 1,
            "total_messages": 0,
            "intensity": 0.0,
            "coverage": 0.0,
        }

    msgs = sorted(float(m) for _, m in pairs)
    total_messages = int(sum(m for _, m in pairs))
    median = _percentile(msgs, 0.5)
    p35 = _percentile(msgs, 0.35)
    p80 = _percentile(msgs, 0.8)

    # Сам порог «живой»: ниже типичного шума группы, но не ноль
    thr = max(1, int(round(max(p35, median * 0.4))))
    qualified = [(u, m) for u, m in pairs if m >= thr]
    n_q = len(qualified)

    # Ожидаемая доля активных — от того, сколько уже пишут vs размер
    writer_share = writers / float(max(1, members))
    # Чем меньше группа относительно писавших — тем выше ожидаемая вовлечённость
    expect_ratio = max(0.08, min(0.55, 0.18 + 0.35 * (1.0 - min(1.0, members / 800.0))))
    # Подстройка под факт: если пишет мало людей — не требуем невозможного
    expect_ratio = min(expect_ratio, max(0.12, writer_share * 1.4))
    expect_n = max(1.0, members * expect_ratio)
    coverage = min(1.0, n_q / expect_n)

    if n_q > 0 and p80 > 0:
        avg_q = sum(m for _, m in qualified) / float(n_q)
        intensity = min(1.0, avg_q / max(p80, float(thr)))
    else:
        intensity = 0.0

    # half_at растёт с размером: в большой группе один активный весит меньше
    half_at = max(2.0, min(14.0, math.sqrt(float(members)) * 0.45))
    people = _soft_count(n_q, half_at=half_at)
    volume = min(1.0, math.log10(1.0 + float(total_messages)) / max(2.2, math.log10(1.0 + float(members) * 8.0)))

    score = max(0.0, min(1.0, 0.40 * coverage * people + 0.40 * intensity * people + 0.20 * volume * people))
    return {
        "score": round(score, 4),
        "members": members,
        "writers": writers,
        "qualified": n_q,
        "msg_threshold": thr,
        "total_messages": total_messages,
        "intensity": round(intensity, 4),
        "coverage": round(coverage, 4),
        "median_msgs": round(median, 2),
    }


def compute_donors_adaptive(
    *,
    member_count: int,
    donate_by_user: Dict[int, float],
    donate_life_by_user: Optional[Dict[int, float]] = None,
    donate_month_by_user: Optional[Dict[int, float]] = None,
    life_weight: float = DONOR_LIFE_WEIGHT,
    month_weight: float = DONOR_MONTH_WEIGHT,
) -> Dict[str, Any]:
    """Донатеры 0…1: иерархия по смешанной силе доната в группе.

    На вход обычно уже приходит blend = 0.6×lifetime + 0.4×month.
    Иерархия строится по blend относительно медианы группы.
    """
    members = max(1, int(member_count or 1))
    amounts = sorted(float(v) for v in (donate_by_user or {}).values() if float(v or 0) > 0)
    count = len(amounts)
    life_map = donate_life_by_user or {}
    month_map = donate_month_by_user or {}
    life_sum = float(sum(float(v) for v in life_map.values() if float(v or 0) > 0))
    month_sum = float(sum(float(v) for v in month_map.values() if float(v or 0) > 0))
    if count <= 0:
        return {
            "score": 0.0,
            "donators": 0,
            "donate_sum": 0.0,
            "donate_sum_life": round(life_sum, 2),
            "donate_sum_month": round(month_sum, 2),
            "top_donate": 0.0,
            "count_factor": 0.0,
            "quality": 0.0,
            "blend_weights": {
                "life": float(life_weight),
                "month": float(month_weight),
            },
        }

    donate_sum = float(sum(amounts))
    top_donate = float(amounts[-1])
    median = _percentile(amounts, 0.5) or 1.0
    p80 = _percentile(amounts, 0.8) or median

    # Относительные веса: кто сильно выше медианы группы — выше в иерархии
    rel_weights = []
    for a in amounts:
        rel = a / median
        # непрерывная кривая вместо фиксированных тиров
        rel_weights.append(math.log1p(rel) ** 1.35)

    tier_mass = float(sum(rel_weights))
    # Нормируем на «идеал»: ~sqrt(writers) сильных донатеров
    norm = max(1.0, math.sqrt(float(max(count, 1))) * math.log1p(p80 / median))
    quality = min(1.0, tier_mass / (norm * 2.8))

    # 1 донатер ≈ почти 0; half_at от размера группы
    half_at = max(2.5, min(16.0, math.sqrt(float(members)) * 0.55))
    count_factor = _soft_count(count, half_at=half_at)

    score = max(0.0, min(1.0, quality * count_factor))
    return {
        "score": round(score, 4),
        "donators": count,
        "donate_sum": round(donate_sum, 2),
        "donate_sum_life": round(life_sum, 2),
        "donate_sum_month": round(month_sum, 2),
        "top_donate": round(top_donate, 2),
        "count_factor": round(count_factor, 4),
        "quality": round(quality, 4),
        "median_donate": round(median, 2),
        "blend_weights": {
            "life": float(life_weight),
            "month": float(month_weight),
        },
        "month_donators": len([1 for v in month_map.values() if float(v or 0) > 0]),
        "life_donators": len([1 for v in life_map.values() if float(v or 0) > 0]),
    }


def combine_society(
    *,
    activity: Dict[str, Any],
    donors: Dict[str, Any],
    prev: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Склеивает актив/донаты → бонус лимита + давление на цены ★.

    Важно: 1–2 донатера в обычной группе НЕ разгоняют цены ★
    (нет войны «донатер пришёл — всем дороже»). Цены растут, когда
    донатерское ядро уже заметное для размера группы.
    """
    max_pct = max(0.0, _as_float(_cfg_get(cfg, "atmosphere_max_bonus_pct", 40), 40.0))
    a = max(0.0, min(1.0, _as_float((activity or {}).get("score"), 0.0)))
    d = max(0.0, min(1.0, _as_float((donors or {}).get("score"), 0.0)))
    donators = _as_int((donors or {}).get("donators"), 0)
    members = _as_int((activity or {}).get("members"), 1)

    act_share = max(0.0, _as_float(_cfg_get(cfg, "society_activity_share", 0.42), 0.42))
    don_share = max(0.0, _as_float(_cfg_get(cfg, "society_donor_share", 0.38), 0.38))
    syn_share = max(0.0, _as_float(_cfg_get(cfg, "society_synergy_share", 0.08), 0.08))
    curve = max(0.5, _as_float(_cfg_get(cfg, "society_activity_curve", 1.28), 1.28))

    # Лимит ставок: актив умеренный (кривая >1 — месяц усилий даёт рост, не максимум сразу).
    a_eff = a ** curve
    activity_pct = max_pct * act_share * a_eff
    donor_pct = max_pct * don_share * d
    synergy_pct = max_pct * syn_share * a_eff * d
    stake_bonus_pct = min(max_pct, activity_pct + donor_pct + synergy_pct)

    # Для ЦЕН ★: донатеры учитываются только если их уже «ядро», не гости
    min_donors_for_price = max(3, int(math.ceil(math.sqrt(float(max(1, members))) * 0.45)))
    if donators < min_donors_for_price:
        d_price = 0.0
    else:
        d_price = d

    # Актив влияет на цену слабее донатерского ядра
    price_pressure = max(0.0, min(1.0, 0.28 * a + 0.72 * d_price + 0.06 * a * d_price))

    prev = prev or {}
    peak_society = max(
        _as_float(prev.get("peak_society"), 0.0),
        max(a, d, (a + d) * 0.5),
    )
    peak_price_pressure = max(
        _as_float(prev.get("peak_price_pressure"), 0.0),
        price_pressure,
    )
    effective_price_pressure = max(price_pressure, peak_price_pressure)

    return {
        "pct": round(stake_bonus_pct, 2),
        "activity_pct": round(activity_pct, 2),
        "donor_pct": round(donor_pct, 2),
        "synergy_pct": round(synergy_pct, 2),
        "max_pct": max_pct,
        "activity": activity or {},
        "donors": donors or {},
        "price_pressure": round(price_pressure, 4),
        "effective_price_pressure": round(effective_price_pressure, 4),
        "peak_society": round(peak_society, 4),
        "peak_price_pressure": round(peak_price_pressure, 4),
        "society_score": round(max(0.0, min(1.0, 0.5 * a + 0.5 * d)), 4),
        "min_donors_for_price": min_donors_for_price,
    }


def price_multiplier_for_level(
    to_level: int,
    snap: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    """Множитель цены шага ★ (до ×3). Без соло-наценки за 1–2 донатера."""
    del to_level  # уровень не штрафует отдельно — только сила группы
    snap = snap or {}
    pressure = max(
        _as_float(snap.get("effective_price_pressure"), 0.0),
        _as_float(snap.get("peak_price_pressure"), 0.0),
        _as_float(snap.get("price_pressure"), 0.0),
    )
    pressure = max(0.0, min(1.0, pressure))
    max_mult = max(1.0, _as_float(_cfg_get(cfg, "society_price_max_mult", 3.0), 3.0))
    # Кривая круче у низа: малый pressure ≈ почти 1.0
    society_mult = 1.0 + (max_mult - 1.0) * (pressure ** 1.35)
    return max(1.0, min(max_mult, round(society_mult, 4)))


def effective_level_price(
    to_level: int,
    *,
    chat_id: int,
    base_price: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> int:
    base = max(0, int(base_price or 0))
    snap = peek_society_snapshot(chat_id) or {}
    mult = price_multiplier_for_level(to_level, snap, cfg)
    return max(base, int(math.ceil(base * mult)))


async def _members_from_chat_table(chat_id: int, *, db=None) -> int:
    """Только таблица chat.member — быстрый PK lookup (не COUNT по chatchange)."""
    if db is None:
        return 0
    # Важно: get_user_by_chat_id_count в db.py переопределён на медленный COUNT —
    # для общества используем только member из chat.
    for getter in ("get_member_count_by_chat_id",):
        if not hasattr(db, getter):
            continue
        try:
            raw = await getattr(db, getter)(int(chat_id))
            n = _as_int(raw, 0)
            if n > 0:
                return n
        except Exception:
            continue
    try:
        if hasattr(db, "pool") and db.pool is not None:
            async with db.pool.acquire() as conn:
                raw = await conn.fetchval(
                    "SELECT member FROM chat WHERE chat_id = $1",
                    int(chat_id),
                )
            return _as_int(raw, 0)
    except Exception:
        pass
    return 0


async def _recompute_society(
    chat_id: int,
    *,
    db=None,
    cfg: Optional[Dict[str, Any]] = None,
    prev: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Тяжёлый путь: БД → расчёт → LRU (+ диск в фоне)."""
    cid = int(chat_id)
    if prev and _as_int(prev.get("schema"), 0) < _SCHEMA:
        prev = {
            **prev,
            "peak_price_pressure": 0.0,
            "price_pressure": 0.0,
            "effective_price_pressure": 0.0,
        }

    members = 0
    user_messages: List[Tuple[int, int]] = []
    donate_by_user: Dict[int, float] = {}
    donate_life: Dict[int, float] = {}
    donate_month: Dict[int, float] = {}
    blend_weights = {"life": DONOR_LIFE_WEIGHT, "month": DONOR_MONTH_WEIGHT}
    try:
        w_life, w_month = _donor_weights_from_cfg(cfg)
        blend_weights = {"life": w_life, "month": w_month}
        if db is not None and hasattr(db, "fetch_society_bundle"):
            bundle = await db.fetch_society_bundle(
                cid,
                life_weight=w_life,
                month_weight=w_month,
                month_days=DONOR_MONTH_DAYS,
                writer_limit=500,
            ) or {}
            members = _as_int(bundle.get("members"), 0)
            user_messages = [
                (int(u), int(m)) for u, m in (bundle.get("user_messages") or [])
            ]
            parts = bundle.get("donate") or {}
            donate_by_user = dict(parts.get("blend") or {})
            donate_life = dict(parts.get("life") or {})
            donate_month = dict(parts.get("month") or {})
            if isinstance(parts.get("weights"), dict):
                blend_weights = {
                    "life": float(parts["weights"].get("life", w_life)),
                    "month": float(parts["weights"].get("month", w_month)),
                }
        else:
            members = await _members_from_chat_table(cid, db=db)
            if db is not None and hasattr(db, "get_chat_user_message_counts_30d"):
                raw = await db.get_chat_user_message_counts_30d(cid, limit=500)
                user_messages = [(int(u), int(m)) for u, m in (raw or [])]
            uids = [u for u, _ in user_messages]
            if db is not None and uids and hasattr(db, "get_users_donate_blend_map"):
                parts = await db.get_users_donate_blend_map(
                    uids,
                    life_weight=w_life,
                    month_weight=w_month,
                    month_days=DONOR_MONTH_DAYS,
                ) or {}
                donate_by_user = dict(parts.get("blend") or {})
                donate_life = dict(parts.get("life") or {})
                donate_month = dict(parts.get("month") or {})
    except Exception as e:
        print(f"[SOCIETY] recompute fail chat={cid}: {e!r}")
        if prev:
            return dict(prev)
        raise

    activity = compute_activity_adaptive(member_count=members, user_messages=user_messages)
    donors = compute_donors_adaptive(
        member_count=members,
        donate_by_user=donate_by_user,
        donate_life_by_user=donate_life,
        donate_month_by_user=donate_month,
        life_weight=float(blend_weights.get("life", DONOR_LIFE_WEIGHT)),
        month_weight=float(blend_weights.get("month", DONOR_MONTH_WEIGHT)),
    )
    combined = combine_society(activity=activity, donors=donors, prev=prev, cfg=cfg)
    snap = {
        **combined,
        "members": members,
        "donators": int((donors or {}).get("donators") or 0),
        "window_days": 30,
        "computed_at": time.time(),
    }
    return save_society_snapshot(cid, snap)


def _schedule_bg_refresh(
    chat_id: int,
    *,
    db=None,
    cfg: Optional[Dict[str, Any]] = None,
    prev: Optional[Dict[str, Any]] = None,
) -> None:
    cid = int(chat_id)
    task = _bg_refresh.get(cid)
    if task is not None and not task.done():
        return

    async def _run() -> None:
        try:
            await _singleflight_recompute(cid, db=db, cfg=cfg, prev=prev)
        except Exception as e:
            print(f"[SOCIETY] bg refresh fail chat={cid}: {e!r}")
        finally:
            cur = _bg_refresh.get(cid)
            if cur is not None and cur.done():
                _bg_refresh.pop(cid, None)

    try:
        loop = asyncio.get_running_loop()
        _bg_refresh[cid] = loop.create_task(_run())
    except RuntimeError:
        pass


async def _singleflight_recompute(
    chat_id: int,
    *,
    db=None,
    cfg: Optional[Dict[str, Any]] = None,
    prev: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Один пересчёт на чат: параллельные «бч» ждут тот же Future."""
    cid = int(chat_id)
    loop = asyncio.get_running_loop()
    with _inflight_guard:
        existing = _inflight.get(cid)
        if existing is not None and not existing.done():
            waiter = existing
        else:
            waiter = loop.create_future()
            _inflight[cid] = waiter
            existing = None

    if existing is not None:
        return dict(await existing)

    try:
        result = await _recompute_society(cid, db=db, cfg=cfg, prev=prev)
        if not waiter.done():
            waiter.set_result(result)
        return dict(result)
    except Exception as e:
        if not waiter.done():
            waiter.set_exception(e)
        raise
    finally:
        with _inflight_guard:
            if _inflight.get(cid) is waiter:
                _inflight.pop(cid, None)


async def ensure_society_snapshot(
    chat_id: int,
    *,
    db=None,
    cfg: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Быстрый путь: LRU → SWR → singleflight пересчёт."""
    from bot.funcs.group_balance_level import get_settings

    cfg = cfg or get_settings()
    cid = int(chat_id)
    empty = {
        "pct": 0.0,
        "activity_pct": 0.0,
        "donor_pct": 0.0,
        "synergy_pct": 0.0,
        "max_pct": _as_float(_cfg_get(cfg, "atmosphere_max_bonus_pct", 40), 40.0),
        "activity": {},
        "donors": {},
        "price_pressure": 0.0,
        "effective_price_pressure": 0.0,
        "peak_society": 0.0,
        "peak_price_pressure": 0.0,
        "society_score": 0.0,
        "members": 0,
        "donators": 0,
        "window_days": 30,
        "computed_at": time.time(),
    }

    if not cfg.get("atmosphere_enabled", True):
        return empty

    prev = peek_society_snapshot(cid)
    if not force and snapshot_is_fresh(prev, cfg):
        return dict(prev or empty)

    # Stale-while-revalidate: отвечаем сразу старым снимком, обновляем в фоне
    if not force and snapshot_is_usable_stale(prev, cfg):
        _schedule_bg_refresh(cid, db=db, cfg=cfg, prev=prev)
        return dict(prev or empty)

    try:
        return await _singleflight_recompute(cid, db=db, cfg=cfg, prev=prev)
    except Exception as e:
        print(f"[SOCIETY] ensure fail chat={cid}: {e!r}")
        if prev:
            return dict(prev)
        return empty


async def resolve_atmosphere_report(
    chat_id: int,
    *,
    db=None,
    bot=None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Совместимость со старым API бч."""
    del bot, use_cache  # bot не нужен: member только из chat
    return await ensure_society_snapshot(chat_id, db=db)


async def resolve_atmosphere_pct(chat_id: int, *, db=None, bot=None) -> float:
    report = await resolve_atmosphere_report(chat_id, db=db, bot=bot)
    return float(report.get("pct") or 0.0)


def format_society_hint(
    report: Optional[Dict[str, Any]],
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """Коротко на главном экране бч: что значит +%."""
    from bot.funcs.group_balance_level import get_settings

    cfg = cfg or get_settings()
    if not cfg.get("atmosphere_enabled", True):
        return "бонус к максимальной ставке от живой группы выключен"
    max_pct = _as_int(_cfg_get(cfg, "atmosphere_max_bonus_pct", 40), 40)
    report = report or {}
    pct = float(report.get("pct") or 0)
    if pct <= 0.05:
        return (
            f"живая группа может поднять макс. ставку до +{max_pct}% "
            f"(сейчас без бонуса) — подробнее в «Как это работает»"
        )
    return (
        f"+{pct:g}% к макс. ставке (до +{max_pct}%) — "
        f"можно ставить крупнее; подробнее в «Как это работает»"
    )


# старое имя — чтобы не ломать импорты
format_atmosphere_hint = format_society_hint
