# -*- coding: utf-8 -*-
"""
Единые настройки ожидания фото-доказательства для всех систем наказаний.

Мут, муталл, кик, кикалл, бан, банфулл, баналл, варн, варналл, варнфулл
шаг 2 (фото) всегда ограничен PROOF_TIMEOUT_SEC секундами (по умолчанию 5 минут).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Канонические константы (единственное место правки таймаута ожидания фото)
# ---------------------------------------------------------------------------

PROOF_TIMEOUT_SEC: int = 300  # 5 минут
PROOF_PENDING_WORKER_INTERVAL_SEC: float = 5.0  # проверка истечения каждые 5 сек.

PENDING_SYSTEMS: Tuple[str, ...] = ("mute", "kick", "ban", "warn")


def proof_timeout_seconds() -> int:
  """Длительность ожидания фото в секундах."""
  return PROOF_TIMEOUT_SEC


def proof_timeout_minutes() -> int:
  """Длительность ожидания фото в минутах (для подписей в сообщениях)."""
  minutes = PROOF_TIMEOUT_SEC // 60
  return max(1, minutes)


def proof_expires_at(*, now: Optional[float] = None) -> float:
  """Момент истечения ожидания (time.time() + PROOF_TIMEOUT_SEC)."""
  return (now if now is not None else time.time()) + PROOF_TIMEOUT_SEC


def is_proof_expired(expires_at: float, *, now: Optional[float] = None) -> bool:
  """True, если окно ожидания фото уже закрыто."""
  ts = now if now is not None else time.time()
  return float(expires_at or 0) < ts


def remaining_proof_seconds(expires_at: float, *, now: Optional[float] = None) -> int:
  """Сколько секунд осталось до истечения (не меньше 0)."""
  ts = now if now is not None else time.time()
  return max(0, int(float(expires_at or 0) - ts))


def coerce_telegram_user_id(value: Any) -> Optional[int]:
  """Приводит Telegram user_id к int (LazyGameStore иногда хранит str-ключи)."""
  if value is None or isinstance(value, bool):
    return None
  try:
    uid = int(value)
  except (TypeError, ValueError):
    return None
  return uid if uid > 0 else None


def new_pending_record(**fields: Any) -> Dict[str, Any]:
  """Базовые поля записи ожидания фото."""
  now = time.time()
  record = dict(fields)
  record.setdefault("created_at", now)
  record.setdefault("expires_at", proof_expires_at(now=now))
  return record


# ---------------------------------------------------------------------------
# Доступ к pending-хранилищам (ключи всегда int)
# ---------------------------------------------------------------------------

def _pending_store_dict(store: Any) -> Dict[Any, Any]:
  return store._load()


def normalize_pending_store(store: Any) -> None:
  """Сливает str/int-ключи одного admin_id в один int-ключ."""
  data = _pending_store_dict(store)
  migrations: List[Tuple[int, Any]] = []
  for key in list(data.keys()):
    uid = coerce_telegram_user_id(key)
    if uid is None:
      continue
    if key != uid:
      migrations.append((uid, key))

  for uid, old_key in migrations:
    if old_key not in data:
      continue
    incoming = data.pop(old_key)
    if uid in data:
      existing = data[uid]
      if float(incoming.get("expires_at") or 0) > float(existing.get("expires_at") or 0):
        data[uid] = incoming
    else:
      data[uid] = incoming


def pending_contains(store: Any, user_id: Any) -> bool:
  """True только если ожидание фото ещё не истекло (просроченное снимается тихо)."""
  return pending_get_active(store, user_id) is not None


def pending_get_active(store: Any, user_id: Any) -> Optional[Dict[str, Any]]:
  """Активное ожидание или None; просроченная запись удаляется без уведомления."""
  payload = pending_get(store, user_id)
  if not payload:
    return None
  if is_proof_expired(payload.get("expires_at", 0)):
    pending_pop(store, user_id)
    return None
  return payload


def pending_has_active(store: Any, user_id: Any) -> bool:
  return pending_get_active(store, user_id) is not None


def pending_get(store: Any, user_id: Any) -> Optional[Dict[str, Any]]:
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return None
  data = _pending_store_dict(store)
  if uid in data:
    return data[uid]
  str_key = str(uid)
  if str_key in data:
    payload = data.pop(str_key)
    data[uid] = payload
    return payload
  return None


def pending_set(store: Any, user_id: Any, payload: Dict[str, Any]) -> None:
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return
  data = _pending_store_dict(store)
  data.pop(str(uid), None)
  data[uid] = payload


def pending_pop(store: Any, user_id: Any) -> Optional[Dict[str, Any]]:
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return None
  data = _pending_store_dict(store)
  payload = data.pop(uid, None)
  if payload is None:
    payload = data.pop(str(uid), None)
  return payload


def pending_items(store: Any) -> List[Tuple[int, Dict[str, Any]]]:
  normalize_pending_store(store)
  data = _pending_store_dict(store)
  items: List[Tuple[int, Dict[str, Any]]] = []
  for key, payload in list(data.items()):
    uid = coerce_telegram_user_id(key)
    if uid is None:
      continue
    items.append((uid, payload))
  return items


def _pending_stores() -> Dict[str, Any]:
  from bot.admins.mute import _pending_mutes
  from bot.admins.ban import _pending_bans
  from bot.admins.kick import _pending_kicks
  from bot.admins.warn import _pending_warns
  return {
    "mute": _pending_mutes,
    "kick": _pending_kicks,
    "ban": _pending_bans,
    "warn": _pending_warns,
  }


def latest_pending_system_for(user_id: Any) -> Optional[str]:
  """Система с самым свежим ожиданием фото для администратора."""
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return None
  best_system: Optional[str] = None
  best_created = -1.0
  for system, store in _pending_stores().items():
    payload = pending_get_active(store, uid)
    if not payload:
      continue
    created = float(payload.get("created_at") or 0)
    if created >= best_created:
      best_created = created
      best_system = system
  return best_system


def clear_other_pending_proofs(user_id: Any, *, keep: str) -> None:
  """Тихо снимает ожидания фото в других системах (без уведомлений об истечении)."""
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return
  for system, store in _pending_stores().items():
    if system == keep:
      continue
    pending_pop(store, uid)


def admin_has_any_pending(user_id: Any) -> bool:
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return False
  return any(pending_has_active(store, uid) for store in _pending_stores().values())


def reconcile_admin_pending(user_id: Any) -> None:
  """Оставляет одно самое свежее активное ожидание фото (остальные снимает тихо)."""
  uid = coerce_telegram_user_id(user_id)
  if uid is None:
    return
  best_system: Optional[str] = None
  best_created = -1.0
  for system, store in _pending_stores().items():
    payload = pending_get(store, uid)
    if not payload or is_proof_expired(payload.get("expires_at", 0)):
      continue
    created = float(payload.get("created_at") or 0)
    if created >= best_created:
      best_created = created
      best_system = system
  if best_system is not None:
    for system, store in _pending_stores().items():
      if system != best_system:
        pending_pop(store, uid)


def reconcile_all_pending_admins() -> None:
  """Снимает дубликаты ожиданий (мут+бан+кик+варн одновременно у одного админа)."""
  uids: set[int] = set()
  for store in _pending_stores().values():
    normalize_pending_store(store)
    for uid, _payload in pending_items(store):
      uids.add(uid)
  for uid in uids:
    reconcile_admin_pending(uid)


def purge_expired_pending_silent() -> int:
  """Удаляет все просроченные ожидания без сообщений (старт / после рестарта бота)."""
  removed = 0
  for store in _pending_stores().values():
    normalize_pending_store(store)
  for _system, store in _pending_stores().items():
    for uid, data in list(pending_items(store)):
      if is_proof_expired(data.get("expires_at", 0)):
        pending_pop(store, uid)
        removed += 1
  reconcile_all_pending_admins()
  return removed


def is_proof_only_photo(message: Any) -> bool:
  """Сообщение только фото/документ без текста команды в подписи."""
  from bot.admins.mute import (
    _get_command_text,
    _has_command_text,
    _has_proof_media,
  )
  if not _has_proof_media(message):
    return False
  return not _has_command_text(_get_command_text(message))


async def safe_edit_message_text(
  bot: Any,
  *,
  chat_id: int,
  message_id: int,
  text: str,
  parse_mode: str = "HTML",
  reply_markup: Any = None,
) -> bool:
  """edit_message_text без ошибки «message is not modified»."""
  from bot.admins.mute import NO_PREVIEW

  link_preview = NO_PREVIEW
  try:
    await bot.edit_message_text(
      text,
      chat_id=chat_id,
      message_id=message_id,
      parse_mode=parse_mode,
      link_preview_options=link_preview,
      reply_markup=reply_markup,
    )
    return True
  except Exception as exc:
    msg = str(exc).lower()
    if "message is not modified" in msg:
      if reply_markup is None:
        try:
          await bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=None,
          )
        except Exception:
          pass
      return True
    raise


async def clear_pending_prompt_keyboard(pending: Dict[str, Any]) -> None:
  """Убирает inline-клавиатуру у сообщения «ждём фото»."""
  from bot.admins.mute import _bot

  prompt_chat = pending.get("prompt_chat_id")
  prompt_msg_id = pending.get("prompt_message_id")
  if not prompt_chat or not prompt_msg_id:
    return
  try:
    await _bot().edit_message_reply_markup(
      chat_id=prompt_chat, message_id=prompt_msg_id, reply_markup=None,
    )
  except Exception:
    pass


async def run_finalize_with_pending_fallback(
  message: Any,
  admin_id: int,
  store: Any,
  pending: Dict[str, Any],
  finalize_fn,
  *,
  on_db_unavailable,
) -> None:
  """
  План Б: pending снимается перед finalize; при ошибке БД ожидание восстанавливается,
  чтобы админ мог повторить отправку фото без новой команды.
  """
  from bot.admins.mute import DbUnavailableError

  backup = dict(pending)
  pending_pop(store, admin_id)
  await clear_pending_prompt_keyboard(pending)
  try:
    await finalize_fn()
  except DbUnavailableError:
    pending_set(store, admin_id, backup)
    await on_db_unavailable()


# ---------------------------------------------------------------------------
# Фоновый воркер: истечение ожидания фото во всех системах
# ---------------------------------------------------------------------------

_proof_pending_worker_started = False


async def _run_all_pending_proof_cleanups() -> None:
  """Снимает просроченные ожидания фото (мут / кик / бан / варн)."""
  reconcile_all_pending_admins()
  for store in _pending_stores().values():
    normalize_pending_store(store)

  from bot.admins.mute import _cleanup_expired_pending_async
  from bot.admins.ban import _cleanup_expired_pending_bans_async
  from bot.admins.kick import _cleanup_expired_pending_kicks_async
  from bot.admins.warn import _cleanup_expired_pending_warns_async

  await _cleanup_expired_pending_async()
  await _cleanup_expired_pending_bans_async()
  await _cleanup_expired_pending_kicks_async()
  await _cleanup_expired_pending_warns_async()


async def _proof_pending_worker_loop() -> None:
  while True:
    try:
      await asyncio.sleep(PROOF_PENDING_WORKER_INTERVAL_SEC)
      await _run_all_pending_proof_cleanups()
    except asyncio.CancelledError:
      break
    except Exception as exc:
      print(f"[PROOF][WORKER] tick error: {exc!r}")


def ensure_proof_pending_worker() -> None:
  """Запускает фоновую проверку истечения ожидания фото (один раз на процесс)."""
  global _proof_pending_worker_started
  if _proof_pending_worker_started:
    return
  try:
    loop = asyncio.get_running_loop()
  except RuntimeError:
    return
  _proof_pending_worker_started = True
  removed = purge_expired_pending_silent()
  if removed:
    print(f"[PROOF] 🧹 Снято просроченных ожиданий фото: {removed}")
  loop.create_task(_proof_pending_worker_loop())
  print(
    f"[PROOF] ✅ Ожидание фото: {proof_timeout_minutes()} мин "
    f"({proof_timeout_seconds()} сек), проверка каждые "
    f"{int(PROOF_PENDING_WORKER_INTERVAL_SEC)} сек"
  )
