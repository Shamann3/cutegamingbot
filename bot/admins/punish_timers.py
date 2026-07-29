# -*- coding: utf-8 -*-
"""
Persistent registry of punishment expiry timers (Redis GameStore).

PostgreSQL remains the source of truth for active punishments; this module
mirrors upcoming expiries so a single async worker can lift them after restarts.

Store name: mod_punish_timers
Keys: mute:{user_id} | ban:{user_id} | warn:{warn_id}
"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bot.db_create.pklcode import GameStore

_STORE_NAME = "mod_punish_timers"
_FOREVER_THRESHOLD_SEC = 365 * 24 * 3600 * 100
_WORKER_INTERVAL_SEC = 5.0

_store: Optional[GameStore] = None
_worker_started = False
_reconcile_done = False


def _get_store() -> GameStore:
  global _store
  if _store is None:
    # TTL is declared in pklcode.STORE_EXPIRY_OVERRIDES and applied when the
    # store is constructed. Setting expiry_seconds here (as before) left a
    # window where the sweeper saw the default 2 hours and silently lifted
    # every punishment older than that - with boot warmup the window lasts
    # until this module is first used.
    # Do NOT add to EXCLUDED_STORES - we need del store[key] on lift/expiry.
    _store = GameStore(_STORE_NAME)
  return _store


def _expires_ts(expires_at: datetime) -> float:
  dt = expires_at
  if dt.tzinfo is not None:
    dt = dt.replace(tzinfo=None)
  try:
    return dt.timestamp()
  except (OSError, OverflowError, ValueError):
    return float(2_147_483_647)


def _is_forever_delta(until: datetime) -> bool:
  return (until - datetime.now()).total_seconds() >= _FOREVER_THRESHOLD_SEC


def schedule(key: str, expires_at: datetime, payload: Dict[str, Any]) -> None:
  """Register or replace a timer entry."""
  if _is_forever_delta(expires_at):
    cancel(key)
    return
  store = _get_store()
  entry = dict(payload)
  entry["expires_at"] = _expires_ts(expires_at)
  entry["scheduled_at"] = time.time()
  store[key] = entry


def cancel(key: str) -> None:
  store = _get_store()
  if key in store:
    del store[key]


def cancel_warn(warn_id: int) -> None:
  cancel(f"warn:{warn_id}")


def cancel_mute(user_id: int) -> None:
  cancel(f"mute:{user_id}")


def cancel_ban(user_id: int) -> None:
  cancel(f"ban:{user_id}")


def cancel_warns_for_user(user_id: int) -> None:
  prefix = "warn:"
  store = _get_store()
  for key in list(store.keys()):
    sk = str(key)
    if not sk.startswith(prefix):
      continue
    entry = store.get(key)
    if entry and int(entry.get("user_id") or 0) == user_id:
      del store[key]


def iter_due(now: Optional[float] = None) -> List[Tuple[str, Dict[str, Any]]]:
  store = _get_store()
  now = time.time() if now is None else now
  due: List[Tuple[str, Dict[str, Any]]] = []
  for key, entry in list(store.items()):
    exp = float(entry.get("expires_at") or 0)
    if exp and exp <= now:
      due.append((str(key), entry))
  due.sort(key=lambda item: float(item[1].get("expires_at") or 0))
  return due


def register_mute(
  user_id: int,
  mute_until: datetime,
  *,
  target_name: str,
  target_username: Optional[str] = None,
  source_chat_id: int = 0,
  scope: str = "chat",
) -> None:
  schedule(
    f"mute:{user_id}",
    mute_until,
    {
      "kind": "mute",
      "user_id": user_id,
      "target_name": target_name,
      "target_username": target_username,
      "source_chat_id": source_chat_id,
      "scope": scope,
    },
  )


def register_ban(
  user_id: int,
  ban_until: datetime,
  *,
  target_name: str,
  target_username: Optional[str] = None,
  source_chat_id: int = 0,
  scope: str = "chat",
) -> None:
  schedule(
    f"ban:{user_id}",
    ban_until,
    {
      "kind": "ban",
      "user_id": user_id,
      "target_name": target_name,
      "target_username": target_username,
      "source_chat_id": source_chat_id,
      "scope": scope,
    },
  )


def register_warn(
  warn_id: int,
  expires_at: datetime,
  *,
  user_id: int,
  target_name: str,
  target_username: Optional[str] = None,
  source_chat_id: int = 0,
  scope: str = "chat",
  mode: str = "chat",
  admin_name: Optional[str] = None,
  admin_role: Optional[str] = None,
  reason: Optional[str] = None,
) -> None:
  schedule(
    f"warn:{warn_id}",
    expires_at,
    {
      "kind": "warn",
      "warn_id": warn_id,
      "user_id": user_id,
      "target_name": target_name,
      "target_username": target_username,
      "source_chat_id": source_chat_id,
      "scope": scope,
      "mode": mode,
      "admin_name": admin_name,
      "admin_role": admin_role,
      "reason": reason,
    },
  )


async def _dispatch_entry(key: str, entry: Dict[str, Any]) -> bool:
  kind = entry.get("kind") or key.split(":", 1)[0]
  try:
    if kind == "mute":
      from bot.admins.mute import _auto_unmute_user, _db
      uid = int(entry["user_id"])
      chat_id = int(entry.get("source_chat_id") or 0)
      name = entry.get("target_name") or await _db().get_firstname_by_user_id(uid) or str(uid)
      await _auto_unmute_user(chat_id, uid, name, notify=True)
      return True
    if kind == "ban":
      from bot.admins.ban import expire_bans_from_timer
      await expire_bans_from_timer(entry)
      return True
    if kind == "warn":
      from bot.admins.warn import expire_timed_warn
      warn_id = int(entry.get("warn_id") or key.split(":", 1)[1])
      await expire_timed_warn(warn_id, entry)
      return True
  except Exception:
    traceback.print_exc()
    return False
  return False


async def _expiry_loop() -> None:
  while True:
    try:
      await asyncio.sleep(_WORKER_INTERVAL_SEC)
      for key, entry in iter_due():
        ok = await _dispatch_entry(key, entry)
        if ok:
          cancel(key)
    except asyncio.CancelledError:
      break
    except Exception:
      traceback.print_exc()


def start_expiry_worker() -> None:
  global _worker_started
  if _worker_started:
    return
  try:
    asyncio.get_running_loop()
  except RuntimeError:
    return
  _worker_started = True
  asyncio.create_task(_expiry_loop())


async def reconcile_from_db() -> None:
  """Rebuild timer registry from PostgreSQL (source of truth)."""
  global _reconcile_done
  from bot.admins.mute import _db, _db_acquire, DbUnavailableError

  if not await _db().ensure_pool():
    return

  store = _get_store()
  with store.bulk():
    store.clear()
    store.timestamps.clear()
    store._expire_heap.clear()

  # --- mutes ---
  try:
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT user_id, mute_until, first_name, username
        FROM users
        WHERE mute_until IS NOT NULL AND mute_until > NOW()
        """,
      )
    for row in rows:
      uid = int(row["user_id"])
      register_mute(
        uid,
        row["mute_until"],
        target_name=row["first_name"] or str(uid),
        target_username=row["username"],
      )
  except DbUnavailableError:
    pass
  except Exception:
    traceback.print_exc()

  # --- chat-scope mutes (active_mutes) ---
  # users.mute_until покрывает только охват «all»; муты «только эта группа»
  # хранятся в active_mutes, поэтому восстанавливаем их таймеры отдельно.
  try:
    from bot.admins.mute import _ensure_mute_schema
    await _ensure_mute_schema()
    async with _db_acquire() as conn:
      rows = await conn.fetch(
        """
        SELECT user_id, chat_id, mute_until, target_name, target_username, scope
        FROM active_mutes
        WHERE mute_until > NOW()
        ORDER BY mute_until
        """,
      )
    # Мут на пользователя один (ключ mute:{uid}); если рядов несколько,
    # берём с самым поздним сроком и предпочитаем конкретную группу нулевой.
    best: Dict[int, Dict[str, Any]] = {}
    for row in rows:
      uid = int(row["user_id"])
      cur = best.get(uid)
      if cur is None:
        best[uid] = dict(row)
        continue
      if row["mute_until"] > cur["mute_until"]:
        best[uid] = dict(row)
      elif row["mute_until"] == cur["mute_until"] and int(cur.get("chat_id") or 0) == 0:
        best[uid] = dict(row)
    for uid, row in best.items():
      register_mute(
        uid,
        row["mute_until"],
        target_name=row["target_name"] or str(uid),
        target_username=row["target_username"],
        source_chat_id=int(row["chat_id"] or 0),
        scope=row["scope"] or "chat",
      )
  except DbUnavailableError:
    pass
  except Exception:
    traceback.print_exc()

  # --- timed bans ---
  try:
    from bot.admins.ban import _ensure_ban_schema, _ban_schema_ready
    await _ensure_ban_schema()
    if _ban_schema_ready:
      async with _db_acquire() as conn:
        rows = await conn.fetch(
          """
          SELECT user_id,
                 MAX(ban_until) AS ban_until,
                 MAX(target_name) AS target_name,
                 MAX(target_username) AS target_username,
                 MAX(scope) AS scope
          FROM active_bans
          WHERE ban_until > NOW()
          GROUP BY user_id
          """,
        )
      for row in rows:
        uid = int(row["user_id"])
        register_ban(
          uid,
          row["ban_until"],
          target_name=row["target_name"] or str(uid),
          target_username=row["target_username"],
          scope=row["scope"] or "chat",
        )
  except DbUnavailableError:
    pass
  except Exception:
    traceback.print_exc()

  # --- timed warns ---
  try:
    from bot.admins.warn import _ensure_warn_schema, _warn_schema_ready
    await _ensure_warn_schema()
    if _warn_schema_ready:
      async with _db_acquire() as conn:
        rows = await conn.fetch(
          """
          SELECT w.id, w.user_id, w.expires_at, w.chat_id, w.admin_name,
                 w.admin_role, w.reason, w.scope, w.mode,
                 u.first_name, u.username
          FROM active_warns w
          LEFT JOIN users u ON u.user_id = w.user_id
          WHERE w.expires_at IS NOT NULL AND w.expires_at > NOW()
          """,
        )
      for row in rows:
        wid = int(row["id"])
        uid = int(row["user_id"])
        register_warn(
          wid,
          row["expires_at"],
          user_id=uid,
          target_name=row["first_name"] or str(uid),
          target_username=row["username"],
          source_chat_id=int(row["chat_id"] or 0),
          scope=row["scope"] or "chat",
          mode=row["mode"] or ("all" if (row["scope"] or "chat") == "all" else "chat"),
          admin_name=row["admin_name"],
          admin_role=row["admin_role"],
          reason=row["reason"],
        )
  except DbUnavailableError:
    pass
  except Exception:
    traceback.print_exc()

  _reconcile_done = True


async def start_moderation_workers() -> None:
  """Call once at bot startup (event loop must be running)."""
  await reconcile_from_db()
  start_expiry_worker()
  from bot.admins.punish_proof import ensure_proof_pending_worker
  ensure_proof_pending_worker()
  from bot.admins.mute import _ensure_expiry_worker
  _ensure_expiry_worker()
  from bot.admins.ban import _ensure_ban_expiry_worker
  _ensure_ban_expiry_worker()
