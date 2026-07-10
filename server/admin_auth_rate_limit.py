"""Rate limit for admin auth endpoints (invite/login brute force)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 300
_MAX_ATTEMPTS = 20
_buckets: dict[str, list[float]] = defaultdict(list)
_CLEANUP_EVERY = 100
_req_counter = 0


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _maybe_cleanup() -> None:
    global _req_counter
    _req_counter += 1
    if _req_counter % _CLEANUP_EVERY != 0:
        return
    cutoff = time.time() - _WINDOW_SECONDS
    stale = [ip for ip, hits in _buckets.items() if not hits or hits[-1] < cutoff]
    for ip in stale:
        del _buckets[ip]


def enforce_admin_auth_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    hits = _buckets[ip]
    hits[:] = [t for t in hits if now - t < _WINDOW_SECONDS]
    _maybe_cleanup()
    if len(hits) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток входа. Подождите 5 минут",
        )
    hits.append(now)
