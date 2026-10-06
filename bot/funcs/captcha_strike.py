# -*- coding: utf-8 -*-
"""Одно наказание, когда капча не пройдена заданное число раз подряд."""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("captcha_strike")

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from captcha_penalty import penalty_fires, penalty_needs_until  # noqa: E402

_MUTE_OFF = {
    "can_send_messages": False,
    "can_send_audios": False,
    "can_send_documents": False,
    "can_send_photos": False,
    "can_send_videos": False,
    "can_send_video_notes": False,
    "can_send_voice_notes": False,
    "can_send_polls": False,
    "can_send_other_messages": False,
    "can_add_web_page_previews": False,
}
_VOICE_OFF = {
    "can_send_messages": True,
    "can_send_audios": False,
    "can_send_documents": True,
    "can_send_photos": True,
    "can_send_videos": True,
    "can_send_video_notes": False,
    "can_send_voice_notes": False,
    "can_send_polls": True,
    "can_send_other_messages": True,
    "can_add_web_page_previews": True,
}
_WIDE = {"muteall", "kickall", "banall", "banfull"}


def _until_ts(seconds: int) -> Optional[int]:
    if int(seconds or 0) <= 0:
        return None
    return int(time.time()) + int(seconds)


def _until_dt(seconds: int) -> datetime:
    if int(seconds or 0) <= 0:
        return datetime.now() + timedelta(days=3650)
    return datetime.now() + timedelta(seconds=int(seconds))


async def _policy(pool) -> dict:
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_captcha_penalty (
            id INT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            strikes INT NOT NULL DEFAULT 5,
            action TEXT NOT NULL DEFAULT 'mute',
            seconds INT NOT NULL DEFAULT 3600
        )
        """
    )
    await pool.execute(
        "INSERT INTO epsilon_captcha_penalty (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
    )
    await pool.execute(
        """
        ALTER TABLE group_captcha_challenges
            ADD COLUMN IF NOT EXISTS penalized BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    row = await pool.fetchrow(
        "SELECT enabled, strikes, action, seconds FROM epsilon_captcha_penalty WHERE id = 1"
    )
    if not row:
        return {"enabled": False, "strikes": 5, "action": "mute", "seconds": 3600}
    return {
        "enabled": bool(row["enabled"]),
        "strikes": int(row["strikes"] or 5),
        "action": row["action"] or "",
        "seconds": int(row["seconds"] or 0),
    }


async def _target_chats(action: str, chat_id: int) -> list[int]:
    if action not in _WIDE:
        return [int(chat_id)]
    from bot.admins.mute import live_staff_chat_ids, refresh_official_chats
    await refresh_official_chats()
    ids = list(live_staff_chat_ids())
    if int(chat_id) not in ids:
        ids.insert(0, int(chat_id))
    return ids


async def _restrict(bot, chat_id: int, user_id: int, perms: dict, until: Optional[int]) -> bool:
    from aiogram.types import ChatPermissions
    kwargs = {
        "chat_id": int(chat_id),
        "user_id": int(user_id),
        "permissions": ChatPermissions(**perms),
    }
    if until:
        kwargs["until_date"] = until
    await bot.restrict_chat_member(**kwargs)
    return True


async def _ban(bot, chat_id: int, user_id: int, until: Optional[int]) -> bool:
    kwargs = {"chat_id": int(chat_id), "user_id": int(user_id)}
    if until:
        kwargs["until_date"] = until
    await bot.ban_chat_member(**kwargs)
    return True


async def _kick(bot, chat_id: int, user_id: int) -> bool:
    await bot.ban_chat_member(chat_id=int(chat_id), user_id=int(user_id))
    await bot.unban_chat_member(chat_id=int(chat_id), user_id=int(user_id), only_if_banned=True)
    return True


async def _record(pool, sql: str, *args) -> None:
    try:
        await pool.execute(sql, *args)
    except Exception:
        log.exception("captcha strike record failed")


async def _mirror(pool, *, action: str, chat_id: int, user_id: int, name: str, seconds: int, reason: str) -> None:
    until = _until_dt(seconds)
    if action in {"mute", "voice"}:
        await _record(
            pool,
            """
            INSERT INTO active_mutes
              (user_id, chat_id, mute_until, target_name, admin_user_id, admin_name, reason, scope)
            VALUES ($1, $2, $3, $4, 0, 'Капча', $5, $6)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
              mute_until = EXCLUDED.mute_until, reason = EXCLUDED.reason, scope = EXCLUDED.scope
            """,
            int(user_id), int(chat_id), until, name or str(user_id), reason, action,
        )
    elif action in {"muteall"}:
        await _record(
            pool,
            """
            INSERT INTO active_mutes
              (user_id, chat_id, mute_until, target_name, admin_user_id, admin_name, reason, scope)
            VALUES ($1, $2, $3, $4, 0, 'Капча', $5, 'all')
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
              mute_until = EXCLUDED.mute_until, reason = EXCLUDED.reason, scope = EXCLUDED.scope
            """,
            int(user_id), int(chat_id), until, name or str(user_id), reason,
        )
    elif action in {"ban", "banall", "banfull"}:
        mode = {"ban": "chat", "banall": "all", "banfull": "full"}[action]
        scope = "chat" if action == "ban" else "all"
        await _record(
            pool,
            """
            INSERT INTO active_bans
              (user_id, chat_id, ban_until, target_name, admin_user_id, admin_name, reason, scope, mode)
            VALUES ($1, $2, $3, $4, 0, 'Капча', $5, $6, $7)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
              ban_until = EXCLUDED.ban_until, reason = EXCLUDED.reason,
              scope = EXCLUDED.scope, mode = EXCLUDED.mode
            """,
            int(user_id), int(chat_id), until, name or str(user_id), reason, scope, mode,
        )
    elif action in {"warn", "warnall", "warnfull"}:
        mode = {"warn": "chat", "warnall": "all", "warnfull": "full"}[action]
        scope = "chat" if action == "warn" else "all"
        exp = until if seconds else None
        await _record(
            pool,
            """
            INSERT INTO active_warns
              (user_id, chat_id, admin_user_id, admin_name, reason, expires_at, scope, mode)
            VALUES ($1, $2, 0, 'Капча', $3, $4, $5, $6)
            """,
            int(user_id), int(chat_id), reason, exp, scope, mode,
        )
    minutes = max(1, int(round(int(seconds) / 60))) if seconds else None
    scope = {
        "muteall": "all", "kickall": "all", "warnall": "all", "banall": "all",
        "warnfull": "full", "banfull": "full",
    }.get(action, "chat")
    await _record(
        pool,
        """
        INSERT INTO staff_actions
          (admin_user_id, admin_name, target_player_id, action_type, reason,
           chat_id, scope, duration_minutes, created_at)
        VALUES (0, 'Капча', $1, $2, $3, $4, $5, $6, NOW())
        """,
        int(user_id), action, reason, int(chat_id), scope, minutes,
    )


async def apply_captcha_strike(
    bot,
    pool,
    *,
    chat_id: int,
    user_id: int,
    name: str = "",
    username: str = "",
    attempts: int,
    challenge_id: int,
) -> bool:
    """Ставит наказание один раз на эту карточку. Повторные ошибки его не дублируют."""
    if pool is None:
        return False
    from bot.admins.mute import is_protected_creator
    if is_protected_creator(user_id) or int(user_id) == int(getattr(bot, "id", 0) or 0):
        return False
    try:
        policy = await _policy(pool)
    except Exception:
        log.exception("captcha strike policy failed chat=%s", chat_id)
        return False
    if not penalty_fires(attempts, policy):
        return False
    try:
        claimed = await pool.fetchrow(
            """
            UPDATE group_captcha_challenges
            SET penalized = TRUE
            WHERE id = $1 AND COALESCE(penalized, FALSE) = FALSE
            RETURNING id
            """,
            int(challenge_id),
        )
    except Exception:
        log.exception("captcha strike claim failed id=%s", challenge_id)
        return False
    if not claimed:
        return False
    action = str(policy["action"])
    seconds = int(policy["seconds"] or 0) if penalty_needs_until(action) else 0
    reason = f"Капча: {int(attempts)} ошибок подряд"
    until = _until_ts(seconds)
    ok = False
    try:
        chats = await _target_chats(action, int(chat_id))
        if action in {"mute", "muteall"}:
            stored = "mute" if action == "mute" else "muteall"
            for cid in chats:
                try:
                    ok = await _restrict(bot, cid, user_id, _MUTE_OFF, until) or ok
                    await _mirror(pool, action=stored, chat_id=cid, user_id=user_id, name=name, seconds=seconds, reason=reason)
                except Exception:
                    log.exception("captcha strike mute failed chat=%s user=%s", cid, user_id)
        elif action == "voice":
            ok = await _restrict(bot, int(chat_id), user_id, _VOICE_OFF, until)
            await _mirror(pool, action="voice", chat_id=int(chat_id), user_id=user_id, name=name, seconds=seconds, reason=reason)
        elif action in {"ban", "banall", "banfull"}:
            for cid in chats:
                try:
                    ok = await _ban(bot, cid, user_id, until) or ok
                    await _mirror(pool, action=action, chat_id=cid, user_id=user_id, name=name, seconds=seconds, reason=reason)
                except Exception:
                    log.exception("captcha strike ban failed chat=%s user=%s", cid, user_id)
            if action == "banfull":
                from bot.admins.ban import _apply_full_project_block
                if await _apply_full_project_block(int(user_id), name or str(user_id), username, reason):
                    ok = True
        elif action in {"kick", "kickall"}:
            for cid in chats:
                try:
                    ok = await _kick(bot, cid, user_id) or ok
                except Exception:
                    log.exception("captcha strike kick failed chat=%s user=%s", cid, user_id)
            await _mirror(pool, action=action, chat_id=int(chat_id), user_id=user_id, name=name, seconds=0, reason=reason)
        elif action in {"warn", "warnall", "warnfull"}:
            await _mirror(pool, action=action, chat_id=int(chat_id), user_id=user_id, name=name, seconds=seconds, reason=reason)
            ok = True
    except Exception:
        log.exception("captcha strike apply failed chat=%s user=%s", chat_id, user_id)
        ok = False
    if not ok:
        try:
            await pool.execute(
                "UPDATE group_captcha_challenges SET penalized = FALSE WHERE id = $1",
                int(challenge_id),
            )
        except Exception:
            log.exception("captcha strike release failed id=%s", challenge_id)
    return ok
