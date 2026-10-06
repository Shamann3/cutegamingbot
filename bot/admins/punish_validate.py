# -*- coding: utf-8 -*-
"""
Проверка существования цели наказания в Telegram.

Отсекает фейковые/устаревшие user_id из локальной БД (например «10»), из‑за
которых Telegram API отвечает PARTICIPANT_ID_INVALID / USER_ID_INVALID.
"""
from __future__ import annotations

from html import escape
from typing import Any, Iterable, Optional, Tuple

_INVALID_TG_USER_MARKERS = frozenset({
  "PARTICIPANT_ID_INVALID",
  "USER_ID_INVALID",
  "PEER_ID_INVALID",
})

_USER_NOT_PARTICIPANT_MARKERS = frozenset({
  "USER_NOT_PARTICIPANT",
})


def _telegram_error_text(exc: BaseException) -> str:
  """Собирает текст ошибки Telegram API из aiogram-исключения."""
  parts: list[str] = []
  for val in (
    getattr(exc, "message", None),
    getattr(exc, "description", None),
    getattr(exc, "method", None),
    str(exc),
  ):
    text = str(val or "").strip()
    if text and text not in parts:
      parts.append(text)
  return " ".join(parts).upper()


def is_invalid_telegram_user_error(exc: BaseException) -> bool:
  """True, если Telegram однозначно сообщает, что user_id не существует."""
  msg = _telegram_error_text(exc)
  return any(marker in msg for marker in _INVALID_TG_USER_MARKERS)


def is_user_not_participant_error(exc: BaseException) -> bool:
  """True, если user_id валиден, но пользователь не состоит в группе."""
  msg = _telegram_error_text(exc)
  return any(marker in msg for marker in _USER_NOT_PARTICIPANT_MARKERS)


def _bot():
  from main import bot1
  return bot1


def _staff_chat_ids() -> Iterable[int]:
  from bot.admins.mute import live_staff_chat_ids
  return live_staff_chat_ids()


def probe_chat_ids(source_chat_id: Optional[int] = None) -> Tuple[int, ...]:
  """Чаты для проверки: сначала текущий, затем все официальные группы."""
  seen: set[int] = set()
  ordered: list[int] = []
  if source_chat_id and source_chat_id < 0:
    seen.add(source_chat_id)
    ordered.append(source_chat_id)
  for cid in _staff_chat_ids():
    if cid not in seen and cid < 0:
      seen.add(cid)
      ordered.append(cid)
  return tuple(ordered)


# Совместимость с существующим именем внутри модуля.
_probe_chat_ids = probe_chat_ids


async def inspect_chat_member(
  chat_id: int,
  user_id: int,
) -> Tuple[Optional[Any], Optional[str]]:
  """
  Запрашивает участника в группе.

  Возвращает (member, error_kind):
    • (member, None) успех (любой status, в т.ч. left/kicked);
    • (None, 'invalid_user') user_id не существует в Telegram;
    • (None, 'not_participant') аккаунт есть, но не в этой группе;
    • (None, 'check_failed') сетевая/прочая ошибка.
  """
  if chat_id > 0:
    return None, "check_failed"
  try:
    member = await _bot().get_chat_member(chat_id, user_id)
    return member, None
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return None, "invalid_user"
    if is_user_not_participant_error(e):
      return None, "not_participant"
    return None, "check_failed"


async def verify_telegram_user_exists(
  user_id: int,
  *,
  probe_chat_ids: Optional[Iterable[int]] = None,
) -> bool:
  """
  Проверяет, что user_id реальный аккаунт Telegram.

  Стратегия:
    1. getChat(user_id) если бот уже «знаком» с пользователем;
    2. getChatMember в официальных группах успешный ответ подтверждает ID;
    3. USER_NOT_PARTICIPANT в хотя бы одной группе ID валиден;
    4. PARTICIPANT_ID_INVALID / USER_ID_INVALID ID недействителен.
  """
  if user_id <= 0:
    return False

  bot = _bot()
  try:
    chat = await bot.get_chat(user_id)
    chat_id = getattr(chat, "id", None)
    chat_type = getattr(chat, "type", None)
    type_key = chat_type.value if hasattr(chat_type, "value") else str(chat_type or "")
    if chat_id == user_id and type_key == "private":
      return True
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return False

  chats = tuple(probe_chat_ids) if probe_chat_ids is not None else _probe_chat_ids()
  if not chats:
    return False

  invalid_user = False
  not_participant_seen = False
  member_confirmed = False
  for cid in chats:
    member, err = await inspect_chat_member(cid, user_id)
    if member is not None:
      member_confirmed = True
      break
    if err == "invalid_user":
      invalid_user = True
      break
    if err == "not_participant":
      not_participant_seen = True

  if invalid_user:
    return False
  if member_confirmed:
    return True
  if not_participant_seen:
    return True

  return False


async def validate_punishment_target_user(
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
) -> Optional[str]:
  """
  Возвращает текст ошибки для администратора или None, если цель валидна.
  """
  if not await verify_telegram_user_exists(
    user_id,
    probe_chat_ids=probe_chat_ids(source_chat_id),
  ):
    return "пользователь не найден в Telegram"
  return None


def punishment_invalid_user_html(user_id: int) -> str:
  """Единое HTML-сообщение для всех систем наказаний."""
  return (
    "<b><tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> "
    f"Пользователь <code>{escape(str(user_id))}</code> не найден в Telegram</b>\n"
    "<i>Проверьте ID, @username или укажите нарушителя ответом на сообщение.</i>"
  )


def invalid_numeric_target_token(body: list[str]) -> Optional[str]:
  """
  «бан 10 10», «кик 99 99» только цифры без единиц срока.
  Возвращает первый токен для сообщения об ошибке или None.
  """
  if not body:
    return None
  from bot.admins.mute import _body_starts_with_duration

  tokens = [p.strip() for p in body if p.strip()]
  if not tokens:
    return None
  if _body_starts_with_duration(tokens):
    return None
  if all(t.isdigit() for t in tokens):
    return tokens[0]
  return None


def _identity_rules():
  import sys
  from pathlib import Path
  server = Path(__file__).resolve().parents[2] / "server"
  folder = str(server)
  if folder not in sys.path:
    sys.path.insert(0, folder)
  import cute_identity
  return cute_identity


def _database():
  from bot.admins.mute import _db
  return _db()


def _person_from_telegram_object(obj: Any, *, private_only: bool) -> Optional[dict]:
  """Имя и username с объекта aiogram. Чужой чат человеком не считается."""
  if obj is None:
    return None
  if private_only:
    chat_type = getattr(obj, "type", None)
    type_key = chat_type.value if hasattr(chat_type, "value") else str(chat_type or "")
    if type_key != "private":
      return None
  rules = _identity_rules()
  return rules.person_from_user_fields(
    getattr(obj, "id", None),
    getattr(obj, "first_name", None),
    getattr(obj, "last_name", None),
    getattr(obj, "username", None),
    is_bot=bool(getattr(obj, "is_bot", False)),
  )


async def _stored_user(user_id: int) -> Tuple[bool, str, Optional[str]]:
  if user_id <= 0:
    return False, "", None
  db = _database()
  pool = getattr(db, "pool", None)
  if pool is None and hasattr(db, "ensure_pool"):
    try:
      await db.ensure_pool()
    except Exception:
      return False, "", None
    pool = getattr(db, "pool", None)
  if pool is None:
    return False, "", None
  try:
    row = await pool.fetchrow(
      "SELECT first_name, username FROM users WHERE user_id = $1",
      int(user_id),
    )
  except Exception:
    return False, "", None
  if not row:
    return False, "", None
  return True, (row["first_name"] or ""), (row["username"] or None)


async def _adopt_person(person: dict) -> None:
  rules = _identity_rules()
  db = _database()
  pool = getattr(db, "pool", None)
  if pool is None and hasattr(db, "ensure_pool"):
    await db.ensure_pool()
    pool = getattr(db, "pool", None)
  if pool is None:
    return
  await pool.execute(
    rules.ADOPT_USER_SQL,
    int(person["user_id"]),
    person["first_name"],
    person.get("username"),
  )


async def describe_telegram_user(
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
) -> Optional[dict]:
  """Имя из Telegram: личный getChat, затем участник текущего и официальных чатов."""
  if user_id <= 0:
    return None
  bot = _bot()
  chat = None
  try:
    chat = await bot.get_chat(user_id)
  except Exception as e:
    if is_invalid_telegram_user_error(e):
      return None
  if chat is not None:
    person = _person_from_telegram_object(chat, private_only=True)
    if person and not _identity_rules().name_is_placeholder(person["first_name"], user_id):
      return person
  not_participant = False
  for cid in probe_chat_ids(source_chat_id):
    member, err = await inspect_chat_member(cid, user_id)
    if err == "invalid_user":
      return None
    if err == "not_participant":
      not_participant = True
      continue
    if member is None:
      continue
    person = _person_from_telegram_object(getattr(member, "user", None), private_only=False)
    if person:
      return person
  if chat is not None:
    named = _person_from_telegram_object(chat, private_only=True)
    if named:
      return named
  if not_participant:
    return _identity_rules().person_from_user_fields(user_id, None, None, None)
  return None


async def describe_telegram_username(username: str) -> Optional[dict]:
  rules = _identity_rules()
  clean = rules.normalize_username(username)
  if not clean:
    return None
  try:
    chat = await _bot().get_chat(f"@{clean}")
  except Exception:
    return None
  return _person_from_telegram_object(chat, private_only=True)


async def ensure_punishment_profile(
  user_id: int,
  *,
  first_name: Optional[str] = None,
  last_name: Optional[str] = None,
  username: Optional[str] = None,
  source_chat_id: Optional[int] = None,
  from_telegram: bool = False,
) -> Optional[Tuple[int, str, Optional[str]]]:
  """Строка users перед наказанием.

  Если человека нет в Куте, имя берётся из Telegram и записывается.
  Уже известное имя не перезаписывается и Telegram повторно не спрашивается.
  None — Telegram такого пользователя не знает, писать в базу некого.
  """
  rules = _identity_rules()
  uid = int(user_id or 0)
  in_db, stored_name, stored_username = await _stored_user(uid)
  passed_username = rules.normalize_username(username) or stored_username
  if in_db and not rules.needs_telegram_profile(True, stored_name, uid):
    return uid, stored_name, passed_username or None

  handed = None
  if from_telegram and uid > 0:
    handed = rules.person_from_user_fields(
      uid, first_name, last_name, username, is_bot=False,
    )
  person = None
  if handed and not rules.name_is_placeholder(handed["first_name"], uid):
    person = handed
  elif uid > 0:
    person = await describe_telegram_user(uid, source_chat_id=source_chat_id)
  elif username:
    person = await describe_telegram_username(username)

  if person is None and handed is not None:
    person = handed
  if person is None:
    if in_db:
      label = " ".join(str(stored_name or "").split()) or str(uid)
      return uid, label, passed_username or None
    return None
  try:
    await _adopt_person(person)
  except Exception:
    pass
  return int(person["user_id"]), person["first_name"], person.get("username") or passed_username


async def reject_invalid_target_reply(
  message: Any,
  user_id: int,
  *,
  source_chat_id: Optional[int] = None,
  debug_tag: str = "invalid_user",
) -> bool:
  """
  План Б на шаге пруфа/финализации: если цель недействительна ответ админу.

  Returns True, если цель отклонена (вызывающий код должен прервать обработку).
  """
  if user_id <= 0:
    err = "пользователь не найден в Telegram"
  else:
    err = await validate_punishment_target_user(
      user_id, source_chat_id=source_chat_id,
    )
  if not err:
    return False
  from bot.admins.mute import NO_PREVIEW, _debug_hint

  try:
    await message.reply(
      punishment_invalid_user_html(user_id) + _debug_hint(debug_tag),
      parse_mode="HTML",
      link_preview_options=NO_PREVIEW,
    )
  except Exception:
    pass
  return True
