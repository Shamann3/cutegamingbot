"""Отложенное обновление групп/участников не блокирует ответ бота."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

_GROUP_TOUCH_INTERVAL_SEC = 1800.0
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
        from main import add_or_update_group_info, check_and_add_user

        # update_group_info_periodically() раньше вызывалась и тут - убрана: она
        # запускает бесконечный while-True с asyncio.sleep(900), защищённый
        # ОДНИМ глобальным флагом (main.py::group_info_updating), а не per-chat_id.
        # На практике это значило, что периодический цикл навсегда занимала
        # первая группа, дошедшая сюда после рестарта бота, и ни одна из
        # остальных groups никогда не получала свой цикл (флаг уже занят). При
        # этом сама add_or_update_group_info() ниже и так обновляет инфо о ЛЮБОЙ
        # активной группе при каждом её "касании" - update_group_info_periodically
        # была чистым дублированием работы для одной "счастливой" группы и
        # источником лишних запросов к Telegram (GetChat/GetChatAdministrators/
        # GetChatMemberCount) вперемешку с обработкой реальных сообщений на
        # одном event loop. См. переписку про нагрузку 2026-07-16.
        await add_or_update_group_info(bot1, chat_id, db)
        await check_and_add_user(message, db)
    except Exception as e:
        print(f"[GROUP_TOUCH][WARN] chat_id={chat_id}: {type(e).__name__}: {e}")
