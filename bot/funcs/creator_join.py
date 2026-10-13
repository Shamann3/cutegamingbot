# -*- coding: utf-8 -*-
"""Заявка создателя проекта в группу, где уже есть куты.

Смотрится только сам факт кут в группе. Правила баланса группы
здесь не участвуют: публичность, заявки и срок на снятие не решают,
пускать создателя или нет.
"""
from __future__ import annotations

PROJECT_CREATOR_ID = 6801702632
_bound = False


def is_project_creator(user_id) -> bool:
    try:
        return int(user_id) == PROJECT_CREATOR_ID
    except (TypeError, ValueError):
        return False


async def cute_in_group(db, chat_id: int):
    """Сколько кут лежит в группе. None — прочитать не удалось."""
    try:
        async with db.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT COALESCE(chatbalance, 0) + COALESCE(dexbalance, 0)
                FROM chat
                WHERE chat_id = $1
                """,
                int(chat_id),
            )
    except Exception as exc:
        print(f"[JOIN] cute read fail chat={chat_id} {type(exc).__name__}")
        return None
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def admit_creator_request(bot, db, chat_id: int, user_id: int) -> str:
    """Принять заявку создателя в группу с кутами. Чужого не трогаем."""
    if not is_project_creator(user_id):
        return "skip"
    cute = await cute_in_group(db, int(chat_id))
    if cute == 0:
        print(f"[JOIN] creator request stays chat={chat_id}")
        return "empty"
    try:
        await bot.approve_chat_join_request(chat_id=int(chat_id), user_id=int(user_id))
    except Exception as exc:
        text = str(exc)
        if "ALREADY_PARTICIPANT" in text:
            print(f"[JOIN] creator already in chat={chat_id}")
            return "admit"
        print(f"[JOIN] creator admit fail chat={chat_id} {type(exc).__name__}: {text[:160]}")
        return "fail"
    print(f"[JOIN] creator admitted chat={chat_id}")
    return "admit"


def bind(dp) -> None:
    global _bound
    if _bound:
        return
    _bound = True
    from aiogram import F

    @dp.chat_join_request(F.from_user.id == PROJECT_CREATOR_ID)
    async def on_creator_join(event):
        chat = getattr(event, "chat", None)
        user = getattr(event, "from_user", None)
        chat_id = getattr(chat, "id", None)
        user_id = getattr(user, "id", None)
        if chat_id is None or not is_project_creator(user_id):
            return
        from main import bot1, db
        try:
            await admit_creator_request(bot1, db, int(chat_id), int(user_id))
        except Exception as exc:
            print(f"[JOIN] creator join chat={chat_id} {type(exc).__name__}")
