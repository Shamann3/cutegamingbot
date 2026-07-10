"""In-memory push-канал для мгновенных уведомлений WebApp (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from config import NOTIFICATION_SSE_MAX_PER_USER, NOTIFICATION_SSE_MAX_TOTAL

logger = logging.getLogger(__name__)

_queues: dict[int, set[asyncio.Queue]] = defaultdict(set)
_total_connections = 0


def total_sse_connections() -> int:
    return _total_connections


def subscribe(user_id: int) -> asyncio.Queue | None:
    """Subscribe to SSE. Returns None if global or per-user limit is reached."""
    global _total_connections

    uid = int(user_id)
    existing = _queues[uid]

    if _total_connections >= NOTIFICATION_SSE_MAX_TOTAL:
        logger.warning(
            "notification_hub: global SSE limit reached (%d), rejecting user %s",
            NOTIFICATION_SSE_MAX_TOTAL,
            uid,
        )
        return None

    if len(existing) >= NOTIFICATION_SSE_MAX_PER_USER:
        oldest = min(existing, key=id)
        existing.discard(oldest)
        _total_connections = max(0, _total_connections - 1)
        logger.warning(
            "notification_hub: evicted SSE connection for user %s (per-user limit=%d)",
            uid,
            NOTIFICATION_SSE_MAX_PER_USER,
        )

    queue: asyncio.Queue = asyncio.Queue()
    existing.add(queue)
    _total_connections += 1
    return queue


def unsubscribe(user_id: int, queue: asyncio.Queue) -> None:
    global _total_connections

    subs = _queues.get(int(user_id))
    if not subs:
        return
    if queue in subs:
        subs.discard(queue)
        _total_connections = max(0, _total_connections - 1)
    if not subs:
        _queues.pop(int(user_id), None)


def publish(user_id: int, notification: dict) -> None:
    for queue in list(_queues.get(int(user_id), ())):
        try:
            queue.put_nowait(notification)
        except Exception:
            pass


def encode_sse(notification: dict) -> str:
    return f"data: {json.dumps(notification, ensure_ascii=False)}\n\n"
