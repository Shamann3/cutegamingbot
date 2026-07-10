"""Отложенное обновление групп/участников — не блокирует ответ бота."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

_GROUP_TOUCH_INTERVAL_SEC = 300.0
_group_touch_last: Dict[int, float] = {}


def schedule_deferred_group_touch(bot1, chat_id: int, message: Any, db) -> None:
    if int(chat_id) >= 0:
        return
    cid = int(chat_id)
    now = time.time()
    if now - _group_touch_last.get(cid, 0.0) < _GROUP_TOUCH_INTERVAL_SEC:
        return
    _group_touch_last[cid] = now
    asyncio.create_task(_run_group_touch(bot1, cid, message, db))


async def _run_group_touch(bot1, chat_id: int, message: Any, db) -> None:
    try:
        from main import (
            add_or_update_group_info,
            check_and_add_user,
            update_group_info_periodically,
        )

        await update_group_info_periodically(bot1, chat_id, db)
        await add_or_update_group_info(bot1, chat_id, db)
        await check_and_add_user(message, db)
    except Exception as e:
        print(f"[GROUP_TOUCH][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
