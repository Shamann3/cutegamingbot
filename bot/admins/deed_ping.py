"""Сообщает панели, что наказание уже записано.

Вкладка «Работа» подхватывает его сразу. Если ключа нет или панель
не отвечает, карточка всё равно появится на ближайшем опросе.
Ключ и адрес в сообщения об ошибках не попадают.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request

_TASKS: set[asyncio.Task] = set()


async def _post(action_id: int) -> None:
    key = os.environ.get("INTERNAL_API_KEY", "").strip()
    if not key:
        return
    url = os.environ.get(
        "DEED_NOTIFY_URL",
        "http://127.0.0.1:8000/admin/api/moderation/notify",
    ).strip()
    body = json.dumps({"logId": int(action_id)}).encode()

    def send() -> None:
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Internal-Key": key,
            },
        )
        with urllib.request.urlopen(request, timeout=1.5) as response:
            response.read()

    try:
        await asyncio.to_thread(send)
    except Exception:
        return


def note_punishment(action_id: int | None) -> None:
    """После записи наказания. Не ждёт ответ панели и не мешает выдаче."""
    if not action_id:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_post(int(action_id)))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
