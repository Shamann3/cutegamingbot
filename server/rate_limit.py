import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request

from auth import get_user_id
from config import BAN_CHECK_CACHE_SECONDS, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW

# NOTE: In-process only. With multiple uvicorn workers (--workers N) each process
# has its own _buckets, so effective limit is RATE_LIMIT_MAX * N per window.
# For horizontal scaling behind a load balancer, use Redis-backed rate limiting.
_buckets: dict[int, list[float]] = defaultdict(list)
_BUCKET_CLEANUP_EVERY = 500
_request_counter = 0

# Cache stores (banned, mute_until_timestamp_or_None)
_ban_cache: dict[int, tuple[float, bool, float | None]] = {}
_BAN_CACHE_CLEANUP_EVERY = 1000


def _maybe_cleanup_buckets(window: float) -> None:
    global _request_counter
    _request_counter += 1
    if _request_counter % _BUCKET_CLEANUP_EVERY != 0:
        return
    cutoff = time.time() - window
    stale = [uid for uid, hits in _buckets.items() if not any(t >= cutoff for t in hits)]
    for uid in stale:
        del _buckets[uid]


def _maybe_cleanup_ban_cache() -> None:
    if _request_counter % _BAN_CACHE_CLEANUP_EVERY != 0:
        return
    cutoff = time.monotonic() - BAN_CHECK_CACHE_SECONDS * 2
    stale = [uid for uid, (ts, *_) in _ban_cache.items() if ts < cutoff]
    for uid in stale:
        _ban_cache.pop(uid, None)


def invalidate_ban_cache(user_id: int) -> None:
    _ban_cache.pop(int(user_id), None)


async def _check_user_status(user_id: int) -> tuple[bool, float | None]:
    """Returns (is_banned, mute_until_timestamp_or_None)."""
    now_mono = time.monotonic()
    cached = _ban_cache.get(user_id)
    if cached is not None and now_mono - cached[0] < BAN_CHECK_CACHE_SECONDS:
        return cached[1], cached[2]

    from db import db

    row = await db.pool.fetchrow(
        "SELECT banned, mute_until FROM users WHERE user_id = $1",
        user_id,
    )
    banned = bool(row["banned"]) if row else False
    mute_until: float | None = None
    if row and row["mute_until"] is not None:
        mute_until = row["mute_until"].timestamp()

    _ban_cache[user_id] = (now_mono, banned, mute_until)
    _maybe_cleanup_ban_cache()
    return banned, mute_until


async def rate_limit(request: Request, user_id: int = Depends(get_user_id)) -> int:
    request.state.user_id = user_id
    now = time.time()
    window = RATE_LIMIT_WINDOW
    hits = _buckets[user_id]
    hits[:] = [t for t in hits if now - t < window]
    _maybe_cleanup_buckets(window)

    if len(hits) >= RATE_LIMIT_MAX:
        from error_reporter import schedule_security_alert

        schedule_security_alert(
            "ERR_SEC_RATE_ABUSE",
            request=request,
            user_id=user_id,
            message=f"{len(hits)} запросов за {window} сек",
            status=429,
        )
        raise HTTPException(
            status_code=429,
            detail="Слишком много действий. Пожалуйста, подождите 10 секунд",
        )

    hits.append(now)

    try:
        banned, mute_until = await _check_user_status(user_id)
        if banned:
            raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
        if mute_until is not None and now < mute_until:
            until_dt = datetime.fromtimestamp(mute_until, tz=timezone.utc)
            until_str = until_dt.strftime("%H:%M %d.%m.%Y")
            raise HTTPException(status_code=403, detail=f"Вы замучены до {until_str} (UTC)")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Ошибка проверки аккаунта")

    # Profile/client sync moved to /api/presence — not on every API call.

    return user_id
