"""WebSocket менеджер для мгновенных событий в админ-панели."""

from __future__ import annotations

import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)

_connections: set[WebSocket] = set()


async def ws_connect(ws: WebSocket) -> None:
    await ws.accept()
    _connections.add(ws)
    logger.debug("admin_ws: connected, total=%d", len(_connections))


def ws_disconnect(ws: WebSocket) -> None:
    _connections.discard(ws)
    logger.debug("admin_ws: disconnected, total=%d", len(_connections))


async def broadcast_to_admins(data: dict) -> None:
    if not _connections:
        return
    payload = json.dumps(data, ensure_ascii=False, default=str)
    dead: set[WebSocket] = set()
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _connections.discard(ws)
